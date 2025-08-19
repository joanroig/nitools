import numpy as np
from pydub import AudioSegment, silence

def trim_and_normalize_wav(input_path, output_path, trim_silence_flag, normalize_flag, sample_rate=None, bit_depth=None):
    audio = AudioSegment.from_file(input_path)
    # Check if the audio is empty or silent, process only if not
    if not (audio.rms == 0 or audio.dBFS == float('-inf')):
        if trim_silence_flag:
            silence_thresh = audio.dBFS - 100
            start_trim = silence.detect_leading_silence(audio, silence_threshold=silence_thresh)
            end_trim = silence.detect_leading_silence(audio.reverse(), silence_threshold=silence_thresh)
            duration = len(audio)
            audio = audio[start_trim:duration - end_trim]
        if normalize_flag:
            audio = audio.normalize()
    # Convert sample rate and bit depth if specified
    params = {}
    if sample_rate:
        if audio.frame_rate != sample_rate:
            audio = audio.set_frame_rate(sample_rate)
        params['parameters'] = {'sample_rate': sample_rate}
    if bit_depth:
        # pydub only supports 16/24/32 via sample_width
        width_map = {8: 1, 16: 2, 24: 3, 32: 4}
        if bit_depth in width_map and audio.sample_width != width_map[bit_depth]:
            audio = audio.set_sample_width(width_map[bit_depth])
    audio.export(output_path, format="wav")
