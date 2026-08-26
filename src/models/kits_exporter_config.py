from pydantic import BaseModel, Field

from models.matrix_config import MatrixConfig
from models.pad_filter_config import PadFilterConfig


class KitsExporterConfig(BaseModel):
    """Configuration model for the Kits Exporter GUI."""
    input_folder: str = Field(default="./in/battery", description="Input folder for .nbkt files")
    output_folder: str = Field(default="./out/kits", description="Output folder for JSON and TXT files")
    generate_txt: bool = Field(default=False, description="Generate TXT files alongside JSON")
    json_path: str = Field(default="", description="Path to the generated JSON file")
    proc_output_folder: str = Field(default="./out/kits_export", description="Output folder for exported kit samples")
    trim_silence: bool = Field(default=True, description="Trim silence from samples")
    normalize: bool = Field(default=True, description="Normalize samples")
    sample_rate: str = Field(default="48000", description="Target sample rate (e.g., '48000')")
    bit_depth: str = Field(default="24", description="Target bit depth (e.g., '24')")
    enable_matrix: bool = Field(default=True, description="Enable pad reorder matrix")
    skip_existing: bool = Field(default=True, description="Skip processing if output file already exists")
    matrix_config: MatrixConfig = Field(default_factory=MatrixConfig, description="Configuration for pad reordering matrix")
    filter_pads: bool = Field(default=False, description="Enable pad filtering by keywords")
    pad_filter_config: PadFilterConfig = Field(default_factory=PadFilterConfig, description="Configuration for pad filtering keywords")
    include_preview: bool = Field(default=True, description="Include preview samples in export")
    replace_missing: bool = Field(default=True, description="Replace missing samples with best candidate from the same kit")
    show_terminal: bool = Field(default=True, description="Show terminal output at the bottom of the window")
    width: int = Field(default=0, description="Window width")
    height: int = Field(default=0, description="Window height")
