from pydantic import BaseModel, Field


class PreviewsExporterConfig(BaseModel):
    """Configuration model for the Previews Exporter GUI."""
    input_folder: str = Field(default="./in", description="Input folder for .nifiles")
    output_folder: str = Field(default="./out", description="Output folder for JSON and TXT files")
    json_path: str = Field(default="", description="Path to the generated JSON file")
    proc_output_folder: str = Field(default="./out/previews", description="Output folder for processed audio previews")
    trim_silence: bool = Field(default=True, description="Trim silence from samples")
    normalize: bool = Field(default=True, description="Normalize samples")
    sample_rate: str = Field(default="", description="Target sample rate (e.g., '48000')")
    bit_depth: str = Field(default="", description="Target bit depth (e.g., '16')")
    skip_existing: bool = Field(default=True, description="Skip processing if output file already exists")
    skip_maschine_folders: bool = Field(default=True, description="Skip folders containing .mxgrp files (Maschine groups)")
    skip_battery_kits: bool = Field(default=True, description="Skip files ending with .nbkt.ogg (Battery kits)")
    skip_native_browser_preview_library: bool = Field(default=True, description="Skip 'Native Browser Preview Library' folder")
    find_real_instrument_folder: bool = Field(default=True, description="Find real instrument folder for the Preview Library")
    show_terminal: bool = Field(default=True, description="Show terminal output at the bottom of the window")
    width: int = Field(default=0, description="Window width")
    height: int = Field(default=0, description="Window height")
