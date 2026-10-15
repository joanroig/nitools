"""Check the finished local package, without executing it or approving release.

Windows verifies the embedded PyInstaller payload and its ZIP copy. macOS
verifies the app tree before signing/DMG creation; it does not mount the DMG.
"""
import argparse
import hashlib
import json
from pathlib import Path
import tomllib
import zipfile

from bundle_policy import RESOURCES, check_payload_name

WINDOWS_FILES = {'NITools.exe', 'NIToolsApp.exe', 'runtime-requirements.txt',
                 'DEPENDENCIES.json', 'LICENSE', 'THIRD_PARTY_NOTICES.md', 'nitools-guide.pdf'}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def validate_inventory(inventory, names, read):
    """Require each inventoried payload and notice in the actual package."""
    payload = inventory['payload']
    if not payload or not inventory['dependencies']:
        raise ValueError('Empty package inventory')
    for row in payload:
        check_payload_name(row['path'])
        if row['path'] not in names:
            raise ValueError(f"Inventoried file missing from package: {row['path']}")
    for dependency in inventory['dependencies']:
        if not dependency['notices']:
            raise ValueError(f"Missing notices for {dependency['name']}")
        for notice in dependency['notices']:
            check_payload_name(notice)
            if not notice.startswith('licenses/') or not read(notice):
                raise ValueError(f'Missing or empty dependency notice: {notice}')


def validate_resources(read):
    root = Path(__file__).resolve().parents[1]
    for name in RESOURCES:
        if read('resources/' + name) != (root / 'resources' / name).read_bytes():
            raise ValueError(f'Packaged resource differs from source: {name}')
    project = tomllib.loads(read('pyproject.toml').decode('utf-8'))
    expected = tomllib.loads((root / 'pyproject.toml').read_text(encoding='utf-8'))
    if project['project']['version'] != expected['project']['version']:
        raise ValueError('Packaged version differs from source')


def verify_windows(folder):
    from PyInstaller.archive.readers import CArchiveReader
    folder = Path(folder).resolve()
    if {p.name for p in folder.iterdir()} != WINDOWS_FILES | {'licenses'}:
        raise ValueError('Unexpected or missing Windows package files')
    for path in folder.rglob('*'):
        if path.is_symlink() or not path.resolve().is_relative_to(folder):
            raise ValueError(f'Redirected package path: {path}')
        check_payload_name(path.relative_to(folder).as_posix())
    for name in WINDOWS_FILES:
        if not (folder / name).is_file() or not (folder / name).stat().st_size:
            raise ValueError(f'Missing or empty package file: {name}')
    archive = CArchiveReader(str(folder / 'NIToolsApp.exe'))
    names = {name.replace('\\', '/'): name for name in archive.toc}
    for name in names:
        check_payload_name(name)
    read_payload = lambda name: archive.extract(names[name])
    validate_resources(read_payload)
    inventory = json.loads((folder / 'DEPENDENCIES.json').read_text(encoding='utf-8'))
    validate_inventory(inventory, names, lambda name: (folder / name).read_bytes())
    actual = {name for name, original in names.items() if archive.toc[original][-1] in ('b', 'x')}
    if actual != {row['path'] for row in inventory['payload']}:
        raise ValueError('Embedded payload and dependency inventory differ')
    return len(names)


def verify_zip(folder, archive):
    """Do not extract: reject extra/missing/duplicate names and compare bytes."""
    folder = Path(folder)
    expected = {folder.name + '/' + p.relative_to(folder).as_posix(): p
                for p in folder.rglob('*') if p.is_file()}
    with zipfile.ZipFile(archive) as packaged:
        entries = [entry for entry in packaged.infolist() if not entry.is_dir()]
        names = [entry.filename.replace('\\', '/') for entry in entries]
        if len(names) != len(set(names)) or set(names) != set(expected):
            raise ValueError('ZIP contains duplicate, extra or missing files')
        for entry, name in zip(entries, names):
            if digest(packaged.read(entry)) != digest(expected[name].read_bytes()):
                raise ValueError(f'ZIP content differs from verified package: {name}')
    return len(expected)


def verify_macos(app):
    app = Path(app).resolve()
    resources = app / 'Contents/Resources'
    for path in app.rglob('*'):
        if not path.resolve().is_relative_to(app):
            raise ValueError(f'External bundle link: {path}')
        if path.is_file():
            relative = path.relative_to(app).as_posix()
            # PyInstaller relocates files between Resources and Frameworks.
            logical = relative.split('/', 2)[-1]
            check_payload_name(logical)
    for name in ('LICENSE', 'THIRD_PARTY_NOTICES.md'):
        if not (resources / name).read_bytes():
            raise ValueError(f'Empty package notice: {name}')
    validate_resources(lambda name: (resources / name).read_bytes())
    inventory = json.loads((resources / 'DEPENDENCIES.json').read_text(encoding='utf-8'))
    names = {row['path'] for row in inventory['payload']
             if (resources / row['path']).is_file()
             or (app / 'Contents/Frameworks' / row['path']).is_file()
             or (app / 'Contents/MacOS' / row['path']).is_file()}
    validate_inventory(inventory, names, lambda name: (resources / name).read_bytes())
    return len(names)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    platform = parser.add_mutually_exclusive_group(required=True)
    platform.add_argument('--windows', type=Path)
    platform.add_argument('--macos', type=Path)
    parser.add_argument('--zip', type=Path)
    args = parser.parse_args()
    if args.zip and not args.windows:
        parser.error('--zip requires --windows')
    count = verify_windows(args.windows) if args.windows else verify_macos(args.macos)
    print(f'Package content checks passed: {count} payload entries')
    if args.zip:
        print(f'ZIP matches verified folder: {verify_zip(args.windows, args.zip)} files')
