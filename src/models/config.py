import json

from pydantic import BaseModel

from models.groups_exporter_config import GroupsExporterConfig
from models.previews_exporter_config import PreviewsExporterConfig
from utils.enums import Style
from utils.version import CONFIG_VERSION


class Config(BaseModel):
    version: str = CONFIG_VERSION
    style: Style = Style.AUTO
    max_log_lines: int = 200
    log_panel_sizes: list[int] = []
    groups_exporter: GroupsExporterConfig = GroupsExporterConfig()
    previews_exporter: PreviewsExporterConfig = PreviewsExporterConfig()
