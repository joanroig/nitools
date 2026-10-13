import importlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


class BuilderCancellationTests(unittest.TestCase):
    def test_cancel_during_last_file_keeps_previous_index(self):
        for kind, extension, function, builder_name in (
            ("kits", "nbkt", "process_nbkt_file", "KitsJsonBuilder"),
            ("groups", "mxgrp", "process_mxgrp_file", "GroupsJsonBuilder"),
        ):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "input"
                source.mkdir()
                (source / ("test." + extension)).write_bytes(b"fixture")
                index = root / ("all_" + kind + ".json")
                index.write_text("previous index", encoding="utf-8")
                module = importlib.import_module(f"processors.{kind}.build_{kind}_json")

                class Worker:
                    cancelled = False

                    def cancel_requested(self):
                        return self.cancelled

                worker = Worker()

                def finish_file(*args, **kwargs):
                    worker.cancelled = True
                    return {"samples": [{"paths": ["sample.wav"]}]}

                with patch.object(module, function, side_effect=finish_file):
                    builder = getattr(module, builder_name)(str(source), str(root), generate_txt=False)
                    self.assertEqual(builder.run(worker), 1)
                self.assertEqual(index.read_text(encoding="utf-8"), "previous index")
                self.assertFalse(index.with_suffix(".report.json").exists())
