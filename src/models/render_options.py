from pydantic import BaseModel, Field


class RenderOptions(BaseModel):
    enabled: bool = False
    native_enabled: bool = False
    auto_prepare: bool = True
    prepare_timeout: float = Field(default=120.0, ge=5, le=900, allow_inf_nan=False)
    maschine_plugin: str = ''
    cache_folder: str = ''
    plugin_folder: str = ''
    note: int = Field(default=60, ge=0, le=127)
    velocity: int = Field(default=100, ge=1, le=127)
    hold: float = Field(default=1.0, ge=0.05, le=30, allow_inf_nan=False)
    tail: float = Field(default=2.0, ge=0.05, le=30, allow_inf_nan=False)
    timeout: float = Field(default=90.0, ge=1, le=600, allow_inf_nan=False)
