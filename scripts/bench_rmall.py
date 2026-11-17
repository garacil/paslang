#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# paslang is free software under the GNU General Public License,
# version 3 or (at your option) any later version; see the file COPYING.
"""bench_rmall.py PASLANGC [ROUNDS] (P631): the same trees removed by
sysutils' RemoveAll, Go's os.RemoveAll and Rust's std::fs::remove_dir_all
(scripts/bench_rmall/rm.*), each a process given the tree's path. Three
trees: wide (100 directories of 1,000 files), mixed (a tree of 4,096
directories, three levels of 16, with 8 files each and a link in each)
and deep (a chain of 2,000 directories). Each tree is made again before
each removal; the removals of the three alternate, ROUNDS each (5 by
default), and the median time of each is printed with its ratio to
paslang's; then each remover runs once under strace -f -c and the number
of its calls on the file system (FSCALLS, without each runtime's start)
is printed. Run on a quiet machine, in a scratch
directory of /tmp."""
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
# the calls of a removal, without each runtime's start
FSCALLS = {'unlinkat', 'unlink', 'rmdir', 'openat', 'openat2', 'open', 'getdents64', 'close', 'newfstatat',
           'fstat', 'statx', 'lseek', 'fcntl', 'fstatfs'}
SRC = os.path.join(HERE, 'bench_rmall')


def build(paslangc, out):
    subprocess.run([paslangc, '-o', os.path.join(out, 'rm_pas'), os.path.join(SRC, 'rm.paslang')], check=True,
                   cwd=os.path.dirname(HERE))
    env = dict(os.environ, GOCACHE=os.path.join(out, 'gocache'), GOFLAGS='-mod=mod')
    subprocess.run(['go', 'build', '-o', os.path.join(out, 'rm_go'), '.'], check=True, cwd=SRC, env=env)
    subprocess.run(['rustc', '-O', '-o', os.path.join(out, 'rm_rs'), os.path.join(SRC, 'rm.rs')], check=True)


def make(kind, path):
    os.makedirs(path)
    if kind == 'wide':
        for d in range(100):
            sub = os.path.join(path, 'd%d' % d)
            os.mkdir(sub)
            for f in range(1000):
                open(os.path.join(sub, 'f%d' % f), 'w').close()
    elif kind == 'mixed':
        def level(p, depth):
            for i in range(8):
                open(os.path.join(p, 'f%d' % i), 'w').close()
            os.symlink('/etc', os.path.join(p, 'link'))
            if depth == 0:
                return
            for d in range(16):
                q = os.path.join(p, 'd%d' % d)
                os.mkdir(q)
                level(q, depth - 1)
        level(path, 3)
    else:
        fd = os.open(path, os.O_DIRECTORY)
        for i in range(2000):
            os.mkdir('d', dir_fd=fd)
            nfd = os.open('d', os.O_DIRECTORY, dir_fd=fd)
            os.close(fd)
            fd = nfd
        os.close(fd)


def main():
    paslangc = sys.argv[1]
    rounds = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    work = tempfile.mkdtemp(prefix='paslang-rmbench-', dir='/tmp')
    try:
        build(paslangc, work)
        names = ['paslang', 'go', 'rust']
        bins = [os.path.join(work, b) for b in ('rm_pas', 'rm_go', 'rm_rs')]
        for kind in ('wide', 'mixed', 'deep'):
            times = {n: [] for n in names}
            for r in range(rounds):
                for n, b in zip(names, bins):
                    tree = os.path.join(work, 'tree')
                    make(kind, tree)
                    t0 = time.perf_counter()
                    p = subprocess.run([b, tree], capture_output=True, text=True)
                    t = time.perf_counter() - t0
                    if p.returncode != 0 or os.path.exists(tree):
                        print('%s %s failed: %s' % (kind, n, p.stdout.strip()))
                        subprocess.run(['rm', '-rf', tree])
                        times[n].append(float('nan'))
                        continue
                    times[n].append(t)
            base = statistics.median(times['paslang'])
            print('%-6s ' % kind + '  '.join(('%s %.1f ms (%.3f)' % (n, statistics.median(times[n]) * 1000,
                                                                       statistics.median(times[n]) / base))
                                              if all(t == t for t in times[n]) else '%s failed' % n
                                              for n in names))
            calls = []
            for n, b in zip(names, bins):
                tree = os.path.join(work, 'tree')
                make(kind, tree)
                out = os.path.join(work, 'strace.txt')
                subprocess.run(['strace', '-f', '-c', '-o', out, b, tree], capture_output=True)
                fs = 0
                for l in open(out).read().splitlines():
                    f = l.split()
                    if f and f[-1] in FSCALLS:
                        fs += int(f[3])
                calls.append('%s %d' % (n, fs))
                subprocess.run(['rm', '-rf', tree])
            print('       calls on the file system: ' + '  '.join(calls))
    finally:
        subprocess.run(['rm', '-rf', work])


if __name__ == '__main__':
    main()
