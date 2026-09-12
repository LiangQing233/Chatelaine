"""Validate sources and build separate Chatelaine and Provider Beta pack ZIPs.

Copyright (c) 2026 LiangQing233. SPDX-License-Identifier: MIT
This does not publish, upload, or certify platform/visual acceptance.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
THIRD_PARTY = Path('THIRD_PARTY_LICENSES/curios-9.5.1')
PACKS = ('behavior_pack_chatelaine_aggregator', 'resource_pack_chatelaine')
BETA_PACKS = ('behavior_pack_chatelaine_provider_beta',
              'resource_pack_chatelaine_provider_beta')
ARCHIVES = (
    ('Chatelaine-1.0.0-dev.zip', 'addon', PACKS),
    ('Chatelaine-Provider-Beta-1.0.0-dev.zip', 'provider_beta', BETA_PACKS),
)
ENTITIES_DIRECTORIES = (
    'addon/behavior_pack_chatelaine_aggregator/entities',
    'provider_beta/behavior_pack_chatelaine_provider_beta/entities',
)
FORBIDDEN = {'__pycache__', '.pytest_cache', '.git', '.mcdev.json'}


def required(path):
    if not path.is_file():
        raise ValueError('Missing release input: ' + str(path))
    return path.read_bytes()


def digest(path):
    return hashlib.sha256(required(path)).hexdigest()


def pack_files(path):
    if not path.is_dir():
        raise ValueError('Missing pack: ' + str(path))
    for entry in sorted(path.rglob('*')):
        relative = entry.relative_to(path)
        if any(part in FORBIDDEN for part in relative.parts) or entry.suffix in ('.pyc', '.pyo'):
            raise ValueError('Development artifact in release pack: ' + str(entry))
        if entry.is_file() and entry.name != '.gitkeep':
            yield entry


def release_files(root=ROOT):
    """Each archive contains exactly its behavior pack and resource pack."""
    root = Path(root)
    result = {}
    for archive_name, directory, packs in ARCHIVES:
        pack_root = root / directory
        files = {}
        for name in packs:
            for path in pack_files(pack_root / name):
                relative = path.relative_to(pack_root).as_posix()
                if relative in files:
                    raise ValueError('Duplicate archive entry: ' + relative)
                files[relative] = path
        result[archive_name] = files
    return result


def validate_entities(root=ROOT):
    """Source checkouts track the SDK directories with empty .gitkeep files."""
    for relative in ENTITIES_DIRECTORIES:
        path = Path(root) / relative
        if (not path.is_dir()
                or {entry.name for entry in path.iterdir()} != {'.gitkeep'}
                or required(path / '.gitkeep') != b''):
            raise ValueError('Expected entities containing only an empty .gitkeep: ' + str(path))


def validate_inputs(root=ROOT):
    root = Path(root)
    validate_entities(root)
    files = release_files(root)
    for name in ('LICENSE', 'NOTICE.md', 'LICENSES.md'):
        required(root / name)
    manifest = json.loads(required(root / THIRD_PARTY / 'ASSETS.json'))
    if manifest['license'] != 'LGPL-3.0-or-later' or len(manifest['files']) != 14:
        raise ValueError('Invalid third-party asset coverage')
    for name, expected in manifest['license_sha256'].items():
        if digest(root / THIRD_PARTY / name) != expected:
            raise ValueError('Upstream license changed: ' + name)
    distributed = set()
    for entry in manifest['files']:
        for path_field, hash_field in (('source_path', 'upstream_sha256'),
                                      ('distributed_path', 'distributed_sha256')):
            path = (root / entry[path_field]).resolve()
            path.relative_to(root.resolve())
            if digest(path) != entry[hash_field]:
                raise ValueError('Asset/source mismatch: ' + str(path))
        distributed.add(entry['distributed_path'])
    actual = {path.relative_to(root).as_posix()
              for path in (root / 'addon/resource_pack_chatelaine').rglob('*.png')}
    if actual != distributed:
        raise ValueError('Resource PNGs are not completely covered by ASSETS.json')
    required(root / THIRD_PARTY / 'SOURCE.md')
    required(root / THIRD_PARTY / 'source/slot_masks.json')
    spec = importlib.util.spec_from_file_location(
        '_chatelaine_release_textures', root / 'tools/generate_standard_slot_textures.py')
    generator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(generator)
    for name, payload in generator.expected_files().items():
        target = root / 'addon/resource_pack_chatelaine/textures/ui/chatelaine' / name
        if required(target) != payload:
            raise ValueError('Editable source does not reproduce: ' + str(target))
    return files


def write_archive(output, files, entities_directory):
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        info = zipfile.ZipInfo(entities_directory, date_time=(2026, 9, 12, 0, 0, 0))
        info.create_system = 3
        info.external_attr = (0o40755 << 16) | 0x10
        archive.writestr(info, b'')
        for name, path in sorted(files.items()):
            payload = required(path)
            info = zipfile.ZipInfo(name, date_time=(2026, 9, 12, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, payload)
    return {'archive': str(output.resolve()), 'files': len(files),
            'empty_directories': 1,
            'sha256': digest(output)}


def build(output_dir, root=ROOT):
    archives = validate_inputs(root)
    return {'archives': [
        write_archive(Path(output_dir) / name, archives[name], packs[0] + '/entities/')
        for name, directory, packs in ARCHIVES
    ]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path, default=ROOT / 'build')
    args = parser.parse_args()
    try:
        if args.check:
            print(json.dumps({'valid': True, 'archives': {
                name: len(files) for name, files in validate_inputs().items()},
                'entities_placeholders': len(ENTITIES_DIRECTORIES)}))
        else:
            print(json.dumps(build(args.output_dir), ensure_ascii=False))
    except (ValueError, OSError) as error:
        print('Chatelaine release validation failed: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
