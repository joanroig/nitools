import json

from pydantic import BaseModel

from models.groups_exporter_config import GroupsExporterConfig
from utils.enums import Style


class Config(BaseModel):
    version: str
    style: Style
    groups_exporter: GroupsExporterConfig = GroupsExporterConfig()
