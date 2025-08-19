import json


class Config:
    def __init__(self, version: str, style: str):
        self.version = version
        self.style = style

class ConfigEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Config):
            data = {key: value for key, value in obj.__dict__.items() if not key.startswith('_')}
            return data
        return super().default(obj)
