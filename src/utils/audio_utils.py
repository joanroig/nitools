import os

import numpy as np
import resampy
import soundfile as sf


def trim_and_normalize_wav(
    input_path: str,
    output_path: str,
    trim_silence: bool = True,
    normalize: bool = True,
    sample_rate: int | None = None,
    bit_depth: int | None = None,
):
    # Load audio
    data, sr = sf.read(input_path, always_2d=True)
    info = sf.info(input_path)
    data = data.T  # shape: (channels, samples)

    # Only process if audio is not completely silent
    if np.any(np.abs(data) > 0):
        if trim_silence:
            # Compute RMS per frame across channels
            rms = np.sqrt(np.mean(data**2, axis=0))
            rms_db = 20 * np.log10(np.maximum(rms, 1e-12))
            threshold_db = rms_db.max() - 100  # relative threshold
            non_silent_idx = np.where(rms_db > threshold_db)[0]
            if non_silent_idx.size > 0:
                start, end = non_silent_idx[0], non_silent_idx[-1] + 1
                data = data[:, start:end]

        if normalize:
            peak = np.max(np.abs(data))
            if peak > 0:
                data = data / peak * 0.999  # avoid clipping

    # Resample if needed
    if sample_rate and sr != sample_rate:
        data = np.array([resampy.resample(ch, sr, sample_rate) for ch in data])
        sr = sample_rate

    # Determine subtype
    subtype_map = {8: 'PCM_U8', 16: 'PCM_16', 24: 'PCM_24', 32: 'PCM_32'}
    if bit_depth:
        subtype = subtype_map.get(bit_depth)
        if subtype is None:
            raise ValueError(f"Unsupported bit depth: {bit_depth}")
    else:
        subtype = info.subtype if info.format == "WAV" else "PCM_24"

    # Write audio
    if data.size == 0:
        raise RuntimeError(f"No audio data to write for '{output_path}'")
    try:
        sf.write(output_path, data.T, sr, subtype=subtype, format="WAV")
    except Exception as e:
        # Safety check: remove empty WAV files
        if os.path.exists(output_path) and os.path.getsize(output_path) <= 44:
            os.remove(output_path)
            raise RuntimeError(f"WAV file '{output_path}' is empty or invalid (44 bytes) and was deleted")
        raise RuntimeError(f"Failed to write '{output_path}': {e}") from e
