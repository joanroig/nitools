"""Inventory actual PyInstaller inputs and retain installed license notices.

This records evidence; it does not certify complete corresponding-source access.
The release review must also cover embedded native dependencies.
"""
import argparse
import ast
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform
import re
import shutil
import sys

from bundle_policy import check_payload_name


def collect(build, output):
    build, output = Path(build), Path(output).resolve()
    packages = list(metadata.distributions())
    owners = {}
    for distribution in packages:
        for file in distribution.files or []:
            owners[str(Path(distribution.locate_file(file)).resolve()).casefold()] = distribution
    rows = ast.literal_eval((build / 'PKG-00.toc').read_text(encoding='utf-8'))[2]
    rows += ast.literal_eval((build / 'PYZ-00.toc').read_text(encoding='utf-8'))[1]
    # Onedir macOS binaries/data are in COLLECT, not the executable's PKG.
    for toc in build.glob('COLLECT-*.toc'):
        rows += ast.literal_eval(toc.read_text(encoding='utf-8'))[-1]
    selected, files = {}, []
    for name, source, kind in rows:
        if kind in {'OPTION', 'DEPENDENCY', 'SYMLINK'}:
            continue
        check_payload_name(name)
        if not source or not Path(source).is_file():
            continue
        distribution = owners.get(str(Path(source).resolve()).casefold())
        if distribution:
            provider = distribution.metadata['Name']
            selected[provider] = distribution
        elif Path(source).resolve().is_relative_to(Path(sys.base_prefix).resolve()):
            provider = 'CPython'
        elif Path(source).resolve().is_relative_to(Path(__file__).resolve().parents[1]):
            provider = 'NITools/generated'
        else:
            raise ValueError(f'Unidentified build input: {name} ({source})')
        if kind in {'BINARY', 'EXTENSION', 'DATA', 'EXECUTABLE'}:
            files.append({'path': name.replace('\\', '/'), 'provider': provider,
                          'sha256': hashlib.sha256(Path(source).read_bytes()).hexdigest()})
    license_root = output / 'licenses'
    # This is generated build output. Never carry old binding notices into a
    # new package, and never follow a redirected directory outside the output.
    if license_root.exists():
        if license_root.is_symlink() or license_root.resolve() != license_root:
            raise ValueError(f'Refusing to replace redirected license output: {license_root}')
        shutil.rmtree(license_root)
    license_root.mkdir(parents=True, exist_ok=True)
    supplemental = Path(__file__).parent / 'notices'
    pyside = next((dist for name, dist in selected.items() if name.lower().replace('_', '-') == 'pyside6-essentials'), None)
    if pyside is not None and not (supplemental / f'PySide6-{pyside.version}').is_dir():
        raise ValueError(f'Refresh supplemental Qt notices for PySide6 {pyside.version}')
    shutil.copytree(supplemental, license_root / 'upstream')
    inventory = []
    for name, distribution in sorted(selected.items()):
        retained = []
        for file in distribution.files or []:
            # Include nested notices (e.g. setuptools' vendored components).
            if not re.search(r'license|licence|copying|copyright|notice|authors', Path(file).name, re.I):
                continue
            source = Path(distribution.locate_file(file))
            if not source.is_file() or source.suffix in {'.py', '.pyc'}:
                continue
            relative = Path(*[part for part in Path(file).parts if part not in {'.', '..'}])
            target = license_root / name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            retained.append(target.relative_to(output).as_posix())
        if not retained:
            raise ValueError(f'No installed license text found for {name}; resolve before distributing')
        inventory.append({'name': name, 'version': distribution.version, 'notices': retained,
                          'source_metadata': distribution.metadata.get_all('Project-URL', [])})
    python_license = Path(sys.base_prefix) / ('LICENSE.txt' if sys.platform == 'win32' else 'LICENSE')
    if not python_license.is_file():
        # setup-python macOS installations keep the license beside their prefix.
        candidates = list(Path(sys.base_prefix).glob('**/LICENSE.txt'))
        candidates = [p for p in candidates if 'site-packages' not in p.parts]
        if not candidates:
            raise ValueError('CPython license missing from interpreter distribution')
        python_license = candidates[0]
    shutil.copyfile(python_license, license_root / 'CPython.txt')
    inventory.append({'name': 'CPython', 'version': platform.python_version(), 'notices': ['licenses/CPython.txt']})
    # SoundFile's wheel places codec attribution outside its dist-info directory.
    try:
        soundfile = metadata.distribution('soundfile')
        extra = Path(soundfile.locate_file('licensing/license_notes.md'))
        if extra.is_file():
            shutil.copyfile(extra, license_root / 'SoundFile-codecs.md')
    except metadata.PackageNotFoundError:
        pass
    result = {'python': platform.python_version(), 'platform': sys.platform, 'machine': platform.machine(),
              'dependencies': inventory, 'payload': sorted(files, key=lambda row: row['path'])}
    (output / 'DEPENDENCIES.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    print(f'Inventoried {len(files)} payload files and preserved notices for {len(inventory)} dependencies')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('build')
    parser.add_argument('output')
    args = parser.parse_args()
    collect(args.build, args.output)
