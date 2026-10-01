#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""SysUtils family gates: both targets, inlining, GC and CPU affinity.

The Linux error catalogue is independently checked against the host's
C-locale strerror, not an expected file copied from the implementation.
"""
import locale
import os
import random
import re
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import uuid


compiler = str(Path(sys.argv[1]).resolve())
build = Path(sys.argv[2]).resolve()
qemu = sys.argv[3:]
if not qemu:
    raise SystemExit("usage: check_sysutils.py compiler build qemu [options]")
work = Path(tempfile.mkdtemp(prefix="sysutils-", dir=build))
base_env = {key: value for key, value in os.environ.items() if not key.startswith("PASLANG_GC")}
base_env['PASLANG_PARENT_ONLY'] = 'parent-owned'
base_env['TZ'] = 'UTC'
stress = dict(base_env, PASLANG_GCVERIFY="1", PASLANG_GCSTRESS="1", PASLANG_GCPOISON="1")
off = dict(base_env, PASLANG_GC="off")
cpu = str(min(os.sched_getaffinity(0)))


def run(command, environment=base_env, timeout=120, input_data=None):
    process = subprocess.Popen(command, env=environment, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, stdin=subprocess.PIPE,
                               start_new_session=True)
    try:
        output, _ = process.communicate(input=input_data, timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(process.pid, signal.SIGKILL)
        output, _ = process.communicate()
        raise RuntimeError(f"timeout: {command}\n{output.decode(errors='replace')}")
    if process.returncode:
        raise RuntimeError(f"exit {process.returncode}: {command}\n{output.decode(errors='replace')}")
    return output


locale.setlocale(locale.LC_MESSAGES, "C")
catalogue = []
for code in range(135):
    if code in (41, 58):  # unassigned Linux codes, not hidden aliases
        description = f"unknown system error {code}"
    elif code == 134:
        # asm-generic/errno.h EFTYPE: use the kernel's intended-operation
        # description, not glibc's alternative "file type or format" text.
        description = "wrong file type for the intended operation"
    else:
        message = os.strerror(code)
        # Preserve an initial acronym (RFS), as current Go does.
        description = message if message[:2].isupper() else message[0].lower() + message[1:]
    catalogue.append(f"{code}: {description}\n")
expected_catalogue = "".join(catalogue).encode()

# Pascal's spelling helpers and Go's lexical cleaning are different
# contracts. Use the appropriate independent executable oracle for each.
generator = random.Random(130)
paths = ["", "/", "//", "/..", ".", "..", "../../a/../..", "a/../../b", ".gitignore",
         "a/.hidden", "a/..", "file.", " a / b ", "C:\\folder\\file.ext", "a:b", "niño/雪.txt"]
components = ["", ".", "..", "...", "name", ".hidden", "file.tar.gz", " space ", "back\\slash", "雪"]
for _ in range(2000):
    paths.append("/".join(generator.choice(components) for _ in range(generator.randrange(1, 18))))
paths.append("a/" * 5000 + "../b")
path_input = (str(len(paths)) + "\n" + "\n".join(paths) + "\n").encode()
pascal_oracle = work / "pathscompat-fpc"
run(["fpc", "-FE" + str(work), "-FU" + str(work), "-o" + str(pascal_oracle),
     "testdata/pathscompat.paslang"])
def pascal_path_model(path):
    end = path.rfind("/") + 1
    name = path[end:]
    directory_end = end - 1 if end > 1 and path[end - 2] != "/" else end
    dot = path.rfind(".")
    extension = path[dot:] if dot > end else ""
    trailing = path if path.endswith("/") else path + "/"
    fields = [name, path[:end], path[:directory_end], extension,
              path[:len(path) - len(extension)] + ".new", "base/" + name,
              trailing, path[:-1] if path.endswith("/") else path,
              path if path.startswith("/") else "/" + path,
              path[1:] if path.startswith("/") else path]
    delimiter = lambda index: int(0 < index <= len(path) and path[index - 1] == "/")
    # Tests use byte lengths; a UTF-8 continuation cannot be a slash.
    fields.append(f"{delimiter(0)} {delimiter(1)} {delimiter(len(path))} {delimiter(len(path) + 1)}")
    return "\n".join(fields) + "\n"

# FPC also treats backslash as a separator on Unix. paslang deliberately
# follows Linux (and Go): backslash is an ordinary filename byte. Validate
# that difference against the exact model, not against FPC's convention.
reference_paths = [path for path in paths if "\\" not in path]
reference_input = (str(len(reference_paths)) + "\n" + "\n".join(reference_paths) + "\n").encode()
reference_model = "".join(pascal_path_model(path) for path in reference_paths).encode()
if run([str(pascal_oracle)], input_data=reference_input) != reference_model:
    raise RuntimeError("Pascal path model differs from intended FPC semantics")
expected_pascal_paths = "".join(pascal_path_model(path) for path in paths).encode()
go_oracle = work / "pathsclean-go"
run(["go", "build", "-o", str(go_oracle), "testdata/pathsclean_oracle.go"])
expected_clean_paths = run([str(go_oracle)], input_data=path_input)

# RFC 9562 canonical text and network byte order: Python's independent
# UUID parser/serializer, with our deliberately stricter accepted grammar.
guid_cases = []
for _ in range(512):
    value = uuid.UUID(int=generator.getrandbits(128))
    for text in (str(value), str(value).upper(), '{' + str(value) + '}'):
        guid_cases.append((text, '{' + str(value).upper() + '} ' + value.bytes.hex().upper()))
canonical_guid = '017f22e2-79b0-7cc3-98c4-dc0c0c07398f'
for index in range(36):
    guid_cases.append((canonical_guid[:index] + '!' + canonical_guid[index + 1:], 'ERROR'))
for text in ('', canonical_guid + 'x', ' ' + canonical_guid, canonical_guid + ' ',
             '{{' + canonical_guid + '}}', canonical_guid.replace('-', ''),
             'urn:uuid:' + canonical_guid, '\0' + canonical_guid[1:]):
    guid_cases.append((text, 'ERROR'))
guid_input = (str(len(guid_cases)) + '\n' + '\n'.join(text for text, _ in guid_cases) + '\n').encode()
expected_guids = ''.join(answer + '\n' for _, answer in guid_cases).encode()

# Supply an actual execve vector, not a dictionary which cannot contain
# duplicates, nameless or malformed entries. QEMU normalizes this vector
# before guest startup (util/envlist.c and linux-user/main.c); the ARM
# assertion describes exactly that guest vector, not the host's one.
environment_launcher = work / 'environment-launcher'
run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
     '-o', str(environment_launcher), 'testdata/sysenvironment_launcher.c'])
process_probe = work / 'process-probe'
run(['cc', '-std=c11', '-O2', '-Wall', '-Wextra', '-Werror',
     '-o', str(process_probe), 'testdata/sysprocess_probe.c'])

# Independent host stat/lstat model, including sparse >4 GiB sizes,
# links, FIFO, negative epochs and nanoseconds. No expected values are
# copied from SysUtils or from the raw statx layout under test.
stat_root = work / 'stat-model'
stat_root.mkdir()
stat_file = stat_root / 'sparse-ñ'
with stat_file.open('wb') as file:
    file.truncate((1 << 32) + 17)
os.chmod(stat_file, 0o2640)
os.utime(stat_file, ns=(-876543211, 1700000000123456789))
os.link(stat_file, stat_root / 'hardlink')
os.symlink(stat_file.name, stat_root / 'symlink')
os.symlink('missing', stat_root / 'dangling')
os.mkfifo(stat_root / 'fifo', 0o600)
stat_cases = []
def stat_model(path, follow):
    try:
        value = path.stat(follow_symlinks=follow)
        expected = (f'{value.st_mode} {value.st_uid} {value.st_gid} {value.st_nlink} '
                    f'{value.st_size} {value.st_ino} {os.major(value.st_dev)} {os.minor(value.st_dev)}\n')
        times = [str(part) for timestamp in (value.st_atime_ns, value.st_mtime_ns, value.st_ctime_ns)
                 for part in divmod(timestamp, 1_000_000_000)]
        return (expected + ' '.join(times) + '\n').encode()
    except OSError as error:
        return f'error {error.errno}\n'.encode()

for path in (stat_root, stat_file, stat_root / 'hardlink', stat_root / 'symlink',
             stat_root / 'dangling', stat_root / 'fifo', stat_root / 'missing'):
    for follow in (False, True):
        stat_cases.append(([str(path), str(int(follow))], None))

# uname is independently obtained through the host Python/C ABI. QEMU's
# Linux-user target reports its guest machine name, not the host machine.
kernel = os.uname()
version_parts = []
tail = kernel.release
for _ in range(3):
    digits = re.match(r'[0-9]*', tail).group()
    version_parts.append(int(digits or '0'))
    tail = tail[len(digits):]
    if not tail.startswith('.'):
        break
    tail = tail[1:]
version_parts.extend([0] * (3 - len(version_parts)))

def kernel_model(target):
    machine = kernel.machine if target == 'amd64' else 'aarch64'
    return ('\n'.join([kernel.sysname, kernel.release, kernel.version, machine,
                      ' '.join(map(str, version_parts)),
                      f'{machine}-{kernel.sysname} {kernel.release}']) + '\n').encode()

# Independent Unicode oracle: strict Python codecs (Unicode scalars,
# endian-specific UTF-16 and ASCII), not reference implementation bytes.
encodings = ('utf-8', 'utf-16-le', 'utf-16-be', 'ascii')
encoding_cases = []
encoding_expected = []
def encoding_case(kind, operation, data):
    encoding_cases.append(f'{kind}\n{operation}\n{data.hex()}\n')
    try:
        if operation == 0:
            text = data.decode('utf-8', errors='strict')
            try:
                output = text.encode(encodings[kind], errors='strict')
            except UnicodeEncodeError as error:
                encoding_expected.append(f'ERROR 4 {len(text[:error.start].encode("utf-8"))}\n')
                return
        else:
            output = data.decode(encodings[kind], errors='strict').encode('utf-8')
        encoding_expected.append(f'OK {output.hex()}\n')
    except UnicodeDecodeError as error:
        error_kind = 2 if operation == 0 or kind == 0 else 4 if kind == 3 else 3
        encoding_expected.append(f'ERROR {error_kind} {error.start}\n')

scalars = [0, 1, 127, 128, 2047, 2048, 55295, 57344, 65534, 65535, 65536, 1114111]
encoding_generator = random.Random(133)
for _ in range(512):
    scalar = encoding_generator.randrange(1114112)
    if not 55296 <= scalar <= 57343:
        scalars.append(scalar)
for scalar in scalars:
    text = 'A\0' + chr(scalar) + '雪😀Z'
    for kind, codec in enumerate(encodings):
        encoding_case(kind, 0, text.encode('utf-8'))
        if kind != 3:
            encoding_case(kind, 1, text.encode(codec))
for kind in range(4):
    encoding_case(kind, 0, b'')
    encoding_case(kind, 1, b'')
    for byte in range(256):
        encoding_case(kind, 1, bytes([byte]))
    for _ in range(512):
        data = encoding_generator.randbytes(encoding_generator.randrange(16))
        encoding_case(kind, 1, data)
for data in (b'\xff', b'\x80', b'\xc0\xaf', b'\xe0\x80\xaf', b'\xed\xa0\x80',
             b'\xf4\x90\x80\x80', b'\xf5\x80\x80\x80', b'\xe2\x82'):
    for kind in range(4):
        encoding_case(kind, 0, b'ASCII' + data)
for scalar in range(55296, 57344):
    for kind, codec in ((1, 'utf-16-le'), (2, 'utf-16-be')):
        data = scalar.to_bytes(2, 'little' if kind == 1 else 'big')
        encoding_case(kind, 1, data)
        encoding_case(kind, 1, data + b'\0')
encoding_input = (str(len(encoding_cases)) + '\n' + ''.join(encoding_cases)).encode()
expected_encodings = ''.join(encoding_expected).encode()

for target in ("amd64", "arm64"):
    core = build if target == "amd64" else build / "a64"
    runner = [] if target == "amd64" else qemu
    for family, names, message in (
        ('textcastbad', ('stringpointer', 'aliaspointer', 'stringinteger', 'aliasinteger'),
         b'a string or a Char goes here, not '),
        ('readlnbad', ('integer', 'byte', 'boolean', 'record'),
         b'ReadLn takes a string variable, not '),
    ):
        for name in names:
            result = subprocess.run([compiler, '-target', target, '-Fu', str(core),
                                     '-o', str(work / f'{family}-{name}-{target}'),
                                     f'testdata/{family}/{name}.paslang'],
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                    env=base_env, timeout=120)
            if not result.returncode or message not in result.stdout:
                raise RuntimeError(f'missing rejection {family}/{name} {target}: {result.stdout!r}')
    for level in (0, 40):
        for name in ("syserrors", "syserrcatalog", "pollerrors", "sysfiles", "syspipes",
                     "sysmetadata", "sysdirectories", "syscontents", "syscwd", "sysstatmodel",
                     "sysenvironment", "sysprocesses", "sysprocessfds", "syswidth", "systemresources", "sysosmodel",
                     "sysbuilder", "textcasts", "sysencoding", "sysencodingmodel", "syscstring",
                     "syshelpers", "sysguid", "sysguidmodel", "sysfamilies",
                     "pathscompat", "pathsclean"):
            binary = work / f"{name}-{target}-{level}"
            run([compiler, "-target", target, "-inline", str(level), "-Fu", str(core),
                 "-o", str(binary), f"testdata/{name}.paslang"])
            if name == "sysstatmodel":
                expected = None
            elif name == "syserrcatalog":
                expected = expected_catalogue
            elif name == "pathscompat":
                expected = expected_pascal_paths
            elif name == "pathsclean":
                expected = expected_clean_paths
            elif name == 'sysosmodel':
                expected = kernel_model(target)
            elif name == 'sysencodingmodel':
                expected = expected_encodings
            elif name == 'sysguidmodel':
                expected = expected_guids
            else:
                expected = Path(f"testdata/{name}.out").read_bytes()
            for environment in (stress, off):
                for affinity in (["taskset", "-c", cpu], []):
                    arguments = ([str(work / "poll-file")] if name == "pollerrors" else
                                 [str(work), str(process_probe)] if name == 'sysprocessfds' else
                                 ['qemu-normalized'] if name == 'sysenvironment' and target == 'arm64' else
                                 [str(work)] if name in ("sysfiles", "sysmetadata", "sysdirectories",
                                                        "syscontents", "syscwd", "sysprocesses", "syswidth",
                                                        "systemresources") else [])
                    input_data = (path_input if name in ("pathscompat", "pathsclean") else
                                  encoding_input if name == 'sysencodingmodel' else
                                  guid_input if name == 'sysguidmodel' else None)
                    cases = stat_cases if name == 'sysstatmodel' else [(arguments, expected)]
                    for arguments, expected_output in cases:
                        if name == 'sysstatmodel':
                            # Directory enumeration and following a symlink
                            # can change atime. Take the independent snapshot
                            # at this query, not before the entire IO suite.
                            expected_output = stat_model(Path(arguments[0]), arguments[1] == '1')
                        launch = [str(environment_launcher)] if name == 'sysenvironment' else []
                        output = run([*affinity, *launch, *runner, str(binary), *arguments], environment,
                                     input_data=input_data)
                        if output != expected_output:
                            raise RuntimeError(f"unexpected {binary} {arguments}:\n{output[:4096].decode(errors='replace')}")
    print(f"ok SysUtils {target} (inline 0/40, single/all CPUs, GC stress/off, errors/files/metadata/cwd/{len(paths)} paths)", flush=True)
