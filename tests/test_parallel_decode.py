import multiprocessing
from concurrent.futures.process import BrokenProcessPool
import os
import time
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from processors.parallel_decode import decoded_files, BATCH_SIZE
from formats.maschine import parse_maschine
from formats.battery import parse_battery
from test_battery_format import fixture as battery_fixture
from test_maschine_format import synthetic_archive


def crash_decode(data):
    os._exit(9)


def slow_decode(data):
    # Each child leaves evidence of files actually started, not submitted work.
    marker = Path(data.decode()) / f'{os.getpid()}.calls'
    with marker.open('a') as handle:
        handle.write('started\n')
    time.sleep(0.4)
    return {}


class ParallelDecodeTests(unittest.TestCase):
    def test_spawn_keeps_order_and_reports_bad_files_without_losing_later_groups(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = []
            for number in range(BATCH_SIZE * 4 + 1):
                path = root / f'{number:03d}.mxgrp'
                path.write_bytes(b'broken' if number == BATCH_SIZE else synthetic_archive(legacy=bool(number % 2)))
                paths.append(str(path))
            with decoded_files(paths, parse_maschine, max_workers=2) as results:
                rows = list(results)
            self.assertEqual([r[0] for r in rows], paths)
            self.assertEqual([i for i, r in enumerate(rows) if r[2]], [BATCH_SIZE])
            self.assertEqual(rows[-1][1]['group'], 'Fixture')

    def test_battery_spawn_matches_serial_and_keeps_errors_in_order(self):
        with tempfile.TemporaryDirectory() as directory:
            paths = []
            raw = battery_fixture()
            expected = parse_battery(raw)
            for number in range(BATCH_SIZE * 4 + 1):
                path = Path(directory) / f'{number:03d}.nbkt'
                path.write_bytes(b'broken' if number == BATCH_SIZE else raw)
                paths.append(str(path))
            with decoded_files(paths, parse_battery, max_workers=2) as results:
                rows = list(results)
            self.assertEqual([r[0] for r in rows], paths)
            self.assertEqual([i for i, r in enumerate(rows) if r[2]], [BATCH_SIZE])
            for _, decoded, error in rows:
                if error is None:
                    self.assertEqual(decoded, expected)

    def test_cancel_while_first_batch_runs_stops_between_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / 'source'
            path.write_bytes(directory.encode())
            class Worker:
                def cancel_requested(self):
                    return bool(list(root.glob('*.calls')))
            original = {p.pid for p in multiprocessing.active_children()}
            with decoded_files([str(path)] * 128, slow_decode, Worker(), max_workers=2) as results:
                self.assertEqual(list(results), [])
            markers = list(root.glob('*.calls'))
            self.assertTrue(markers)
            # A running decode can finish, but no entire 16-file batch drains.
            self.assertTrue(all(len(p.read_text().splitlines()) <= 2 for p in markers))
            self.assertEqual({p.pid for p in multiprocessing.active_children()}, original)

    def test_crashed_child_closes_pool_and_next_run_can_succeed(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source'
            path.write_bytes(battery_fixture())
            original = {p.pid for p in multiprocessing.active_children()}
            with self.assertRaises(BrokenProcessPool):
                with decoded_files([str(path)] * 64, crash_decode, max_workers=2) as results:
                    list(results)
            self.assertEqual({p.pid for p in multiprocessing.active_children()}, original)
            with decoded_files([str(path)] * 64, parse_battery, max_workers=2) as results:
                self.assertEqual(sum(error is None for _, _, error in results), 64)
            self.assertEqual({p.pid for p in multiprocessing.active_children()}, original)

    def test_cancel_bounds_submissions_and_joins_children_before_returning(self):
        class Worker:
            cancelled = False
            def cancel_requested(self):
                return self.cancelled
        worker = Worker()
        from processors import parallel_decode
        real_pool = parallel_decode.ProcessPoolExecutor
        submitted = []
        def pool_factory(**kwargs):
            pool = real_pool(**kwargs)
            submit = pool.submit
            def tracked(*args):
                submitted.append(args[1])
                return submit(*args)
            pool.submit = tracked
            return pool
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'Test.mxgrp'
            path.write_bytes(synthetic_archive())
            original_children = {child.pid for child in multiprocessing.active_children()}
            with patch.object(parallel_decode, 'ProcessPoolExecutor', side_effect=pool_factory):
                with decoded_files([str(path)] * 1000, parse_maschine, worker, max_workers=2) as results:
                    first = next(results)
                    self.assertEqual(first[1]['group'], 'Fixture')
                    worker.cancelled = True
                    self.assertEqual(list(results), [])
            self.assertEqual(len(submitted), 4)
            self.assertTrue(all(len(batch) <= BATCH_SIZE for batch in submitted))
            self.assertEqual({child.pid for child in multiprocessing.active_children()}, original_children)


if __name__ == '__main__':
    unittest.main()
