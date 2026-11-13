#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Capture/verify production SDK bytes, ELF targets and usable level objects."""
import argparse
import hashlib
import json
from pathlib import Path


def require(condition, message):
    if not condition:
        raise SystemExit('check_sdk_state: ' + message)


def identity(path, target=None, executable=False):
    require(path.is_file(), 'missing SDK file: ' + str(path))
    with path.open('rb') as stream:
        header = stream.read(20)
        stream.seek(0)
        digest = hashlib.file_digest(stream, 'sha256').hexdigest()
    if target is not None:
        # ELF64_Ehdr: e_ident[16], e_type, e_machine (gABI / elf.h).
        require(len(header) == 20 and header[:6] == b'\x7fELF\x02\x01'
                and int.from_bytes(header[16:18], 'little') == (2 if executable else 1)
                and int.from_bytes(header[18:20], 'little') == {'amd64': 62, 'arm64': 183}[target],
                'wrong ELF type/target: ' + str(path))
    return {'bytes': path.stat().st_size, 'sha256': digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('capture', 'verify'))
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--profile', nargs=3, action='append', required=True,
                        metavar=('TARGET', 'BASE_DIRECTORY', 'LEVEL_DIRECTORY'))
    parser.add_argument('--debugger', nargs=2, metavar=('TARGET', 'EXECUTABLE'))
    parser.add_argument('units', nargs='+', help='actual CORE_UNITS and LIB_UNITS source paths')
    args = parser.parse_args()
    units = [Path(name).stem for name in args.units]
    require(all(Path(name).suffix == '.paslang' for name in args.units)
            and len(set(units)) == len(units), 'unit list is empty or contains duplicates/non-source paths')
    profiles, files = [], {}
    require(len({item[0] for item in args.profile}) == len(args.profile), 'duplicate target profile')
    for target, directory, level in args.profile:
        require(target in ('amd64', 'arm64') and Path(level).name == level and level not in ('', '.', '..'),
                'invalid target or level directory')
        base = Path(directory).resolve()
        profiles.append([target, str(base), level])
        for unit in units:
            interface, plain, optimized = base / (unit + '.pi'), base / (unit + '.o'), base / level / (unit + '.o')
            files[str(interface)] = identity(interface)
            files[str(plain)] = identity(plain, target)
            files[str(optimized)] = identity(optimized, target)
            require(optimized.stat().st_mtime_ns >= plain.stat().st_mtime_ns,
                    'level object is older than its base and would not be selected: ' + str(optimized))
    debugger = None
    if args.debugger:
        target, name = args.debugger
        require(target in ('amd64', 'arm64'), 'invalid debugger target')
        path = Path(name).resolve()
        files[str(path)] = identity(path, target, executable=True)
        debugger = [target, str(path)]
    state = {'format': 'paslang-sdk-state-v1', 'units': units, 'profiles': profiles,
             'debugger': debugger, 'files': files}
    if args.action == 'capture':
        args.manifest.write_text(json.dumps(state, indent=2) + '\n')
    else:
        saved = json.loads(args.manifest.read_text())
        require({k: v for k, v in saved.items() if k != 'files'}
                == {k: v for k, v in state.items() if k != 'files'}, 'SDK inventory changed')
        require(set(saved['files']) == set(files), 'SDK file inventory changed')
        for name, observed in files.items():
            require(saved['files'][name] == observed, 'SDK bytes changed: ' + name)
    print('check_sdk_state: ' + args.action + ' ' + str(len(files)) + ' SDK files, targets and level freshness')


if __name__ == '__main__':
    main()
