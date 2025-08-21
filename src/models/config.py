import json

from pydantic import BaseModel

from models.groups_exporter_config import GroupsExporterConfig
from models.previews_exporter_config import PreviewsExporterConfig
from utils.enums import Style


class Config(BaseModel):
    version: str
    style: Style
    log_panel_sizes: list[int] = []
    groups_exporter: GroupsExporterConfig = GroupsExporterConfig()
    previews_exporter: PreviewsExporterConfig = PreviewsExporterConfig()
