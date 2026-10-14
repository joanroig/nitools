"""Local real-engine check. Requires an installed/licensed Maschine and one kit.

Run with Python 3.13 on a Mac; writes only to the selected output directory.
Never attach the resulting cached states/audio/report to a public issue.
"""
import argparse
import hashlib
import json
import platform
from pathlib import Path
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('kit', type=Path)
    parser.add_argument('--plugin', default='')
    parser.add_argument('--cycles', type=int, default=2, help='Independent preparation/render host cycles (default: 2)')
    parser.add_argument('--output', type=Path, default=Path('tmp/macos-qualification'))
    args = parser.parse_args()
    if sys.platform != 'darwin':
        parser.error('Run this qualification on macOS with Maschine installed')
    if args.cycles < 1:
        parser.error('--cycles must be positive')
    from formats.maschine import parse_maschine

    original = args.kit.read_bytes()
    decoded = parse_maschine(original)
    pads = [s for s in decoded['samples'] if s.get('instrument')]
    if not pads:
        parser.error('Choose a kit containing internal or hosted instruments')
    args.output.mkdir(parents=True, exist_ok=True)
    for cycle in range(1, args.cycles + 1):
        qualify_cycle(args.kit, args.plugin, args.output / f'cycle-{cycle}', pads, original)
    print(f'Passed {args.cycles} host cycles. Listen to the WAVs next.')


def qualify_cycle(kit, plugin, output, pads, original):
    import numpy as np
    import soundfile as sf
    from models.render_options import RenderOptions
    from processors.maschine_prepare import PreparationSession
    from processors.maschine_render import NativeSession, plugin_path
    output.mkdir(parents=True, exist_ok=True)
    options = RenderOptions(native_enabled=True, maschine_plugin=plugin,
                            cache_folder=str(output.resolve() / 'cache'))
    session = PreparationSession(options)
    try:
        prepared = session.prepare(kit.resolve())
    finally:
        session.close()
    with patch('processors.maschine_prepare.multiprocessing.get_context', side_effect=AssertionError('Cache resume started a host')):
        session = PreparationSession(options)
        try:
            assert session.prepare(kit.resolve()) == 'cached'
        finally:
            session.close()
    native = NativeSession(kit.resolve(), options)
    report = {'plugin': str(plugin_path(options)), 'architecture': platform.machine(),
              'preparation': prepared, 'cache_resume': True, 'renders': []}
    try:
        for sample in pads:
            pad = sample['pad']
            target = output / f'{pad:02}.wav'
            native.render(pad, target, None)
            audio, rate = sf.read(target)
            assert rate == 48000 and np.isfinite(audio).all() and np.max(np.abs(audio)) > 1e-7
            report['renders'].append({'pad': pad, 'frames': len(audio), 'sample_rate': rate})
    finally:
        native.close()
    assert hashlib.sha256(kit.read_bytes()).digest() == hashlib.sha256(original).digest(), 'Source kit changed'
    (output / 'qualification.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(f'Passed: {len(pads)} instrument pads rendered; source preserved; cache resumed. Listen to the WAVs next.')


if __name__ == '__main__':
    main()
