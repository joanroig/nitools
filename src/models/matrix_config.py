from pydantic import BaseModel

# Default matrix for 4x4 pads (1-16)
DEFAULT_MATRIX = {
    1: 13,
    2: 14,
    3: 15,
    4: 16,
    5: 9,
    6: 10,
    7: 11,
    8: 12,
    9: 5,
    10: 6,
    11: 7,
    12: 8,
    13: 1,
    14: 2,
    15: 3,
    16: 4
}

class MatrixConfig(BaseModel):
    pads: dict[int, int] = DEFAULT_MATRIX.copy()
