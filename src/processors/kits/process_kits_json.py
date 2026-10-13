from processors.sample_export import SampleCollectionProcessor
from utils.logger import Logger

logger = Logger.get_logger("KitsProcessor")


class KitsProcessor(SampleCollectionProcessor):
    def __init__(
        self, json_path, output_folder, trim_silence=False, normalize=False,
        sample_rate=None, bit_depth=None, matrix=None, enable_matrix=True,
        filter_pads=False, pad_filter=None, include_preview=False,
        skip_existing=False,
    ):
        super().__init__(
            json_path, output_folder, kind="kit", logger=logger,
            trim_silence=trim_silence, normalize=normalize,
            sample_rate=sample_rate, bit_depth=bit_depth, matrix=matrix,
            enable_matrix=enable_matrix, filter_pads=filter_pads,
            pad_filter=pad_filter, include_preview=include_preview,
            skip_existing=skip_existing,
        )
