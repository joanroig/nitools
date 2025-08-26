from pydantic import BaseModel

# Default pad filter keywords
DEFAULT_PAD_FILTER = {
    1: ["kick"],
    2: ["snare", "snap", "stick", "clap", "rim", "combo", "hh"],
    3: ["hh", "hihat", "hi hat", "shaker", "tick"]
}

class PadFilterConfig(BaseModel):
    pads: dict[int, list[str]] = DEFAULT_PAD_FILTER.copy()
