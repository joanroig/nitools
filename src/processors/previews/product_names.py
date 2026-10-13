"""Resolve preview product IDs from the user's own installed metadata."""

import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from utils.logger import Logger

logger = Logger.get_logger("PreviewProductNames")


def service_center_paths():
    if sys.platform == "win32":
        return [Path(os.environ.get("CommonProgramFiles", r"C:\Program Files\Common Files"))
                / "Native Instruments/Service Center"]
    if sys.platform == "darwin":
        return [Path("/Library/Application Support/Native Instruments/Service Center"),
                Path.home() / "Library/Application Support/Native Instruments/Service Center"]
    return []


def load_product_names(directories=None):
    """Read UPID/Name pairs without copying or shipping the vendor catalog.

    Missing metadata is normal: unknown IDs retain the preview library name.
    Only the two required fields enter memory; nothing is persisted.
    """
    result = {}
    for directory in service_center_paths() if directories is None else directories:
        for path in sorted(Path(directory).glob("*.xml")):
            try:
                with path.open("rb") as stream:
                    data = stream.read(32 * 1024 * 1024 + 1)
                if len(data) > 32 * 1024 * 1024 or b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
                    raise ValueError("Oversized XML or unsupported entity declarations")
                root = ET.fromstring(data)
                for product in root.iter("Product"):
                    product_id = (product.findtext("UPID") or "").strip().casefold()
                    name = (product.findtext("Name") or "").strip()
                    if product_id and name:
                        result[product_id] = name
            except (OSError, ET.ParseError, ValueError) as error:
                logger.warning("Could not read local product names from %s: %s", path, error)
    return result
