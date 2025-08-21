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
    show_terminal: bool = Field(default=True, description="Show terminal output at the bottom of the window")
