"""Bounded, ordered decoding; only the coordinator writes index/diagnostic files."""

from collections import deque
from concurrent.futures import ProcessPoolExecutor
from contextlib import contextmanager
import multiprocessing
import os
from pathlib import Path



BATCH_SIZE = 16
MIN_PARALLEL_FILES = 64


def _decode_batch(paths, decoder):
    results = []
    for path in paths:
        try:
            results.append((path, decoder(Path(path).read_bytes()), None))
        except Exception as error:
            results.append((path, None, str(error)))
    return results


@contextmanager
def decoded_files(paths, decoder, worker=None, max_workers=None):
    workers = max_workers if max_workers is not None else min(8, os.cpu_count() or 1)
    if len(paths) < MIN_PARALLEL_FILES or workers <= 1:
        # Small selections avoid process startup. None requests normal decoding
        # in the builder, keeping the single-file APIs unchanged.
        yield ((path, None, None) for path in paths)
        return
    pool = ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context('spawn'))
    pending = deque()
    batches = iter(paths[i:i + BATCH_SIZE] for i in range(0, len(paths), BATCH_SIZE))

    def cancelled():
        return worker is not None and worker.cancel_requested()

    def submit():
        batch = next(batches, None)
        if batch is not None and not cancelled():
            pending.append(pool.submit(_decode_batch, batch, decoder))

    def results():
        while pending and not cancelled():
            # Consume in source order for deterministic indexes and unique TXT
            # filenames, while other batches continue on independent cores.
            batch = pending.popleft().result()
            for result in batch:
                if cancelled():
                    return
                yield result
            submit()

    try:
        for _ in range(workers * 2):
            submit()
        yield results()
    finally:
        for future in pending:
            future.cancel()
        pool.shutdown(wait=True, cancel_futures=True)
