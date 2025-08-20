from pydantic import BaseModel, Field

class GroupsExporterConfig(BaseModel):
    """Configuration model for the Groups Exporter GUI."""
    input_folder: str = Field(default="./in", description="Input folder for .mxgrp files")
    output_folder: str = Field(default="./out", description="Output folder for JSON and TXT files")
    generate_txt: bool = Field(default=False, description="Generate TXT files alongside JSON")
    json_path: str = Field(default="", description="Path to the generated JSON file")
    proc_output_folder: str = Field(default="./out/groups", description="Output folder for processed audio groups")
    trim_silence: bool = Field(default=True, description="Trim silence from samples")
    normalize: bool = Field(default=True, description="Normalize samples")
    sample_rate: str = Field(default="", description="Target sample rate (e.g., '48000')")
    bit_depth: str = Field(default="", description="Target bit depth (e.g., '16')")
    enable_matrix: bool = Field(default=True, description="Enable pad reorder matrix")
    filter_pads: bool = Field(default=True, description="Enable pad filtering by keywords")
    include_preview: bool = Field(default=True, description="Include preview samples in export")
    fill_blanks: bool = Field(default=True, description="Fill blank pads with a default sample")
    fill_blanks_path: str = Field(default="./assets/.wav", description="Path to the sample for filling blank pads")
