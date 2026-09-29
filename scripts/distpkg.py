#!/usr/bin/env python3
"""The packages of the distributions, for amd64 and arm64.

From the release archives `make package` lays out in build/pkg (bin,
lib/paslang, share), this writes, into build/pkg/dist:

  paslang_<v>-1_amd64.deb, paslang_<v>-1_arm64.deb         Debian, Ubuntu
  paslang-<v>-1.x86_64.rpm, paslang-<v>-1.aarch64.rpm       Fedora, RHEL, openSUSE
  paslang-<v>-1-x86_64.pkg.tar.zst, ...-aarch64.pkg.tar.zst  Arch
  paslang-<v>-x86_64-1.tgz, paslang-<v>-aarch64-1.tgz        Slackware

Each installs the compiler and the debugger's terminal in /usr/bin, the
units in /usr/lib/paslang (the arm64 ones in /usr/lib/paslang/aarch64),
the documentation in /usr/share/doc/paslang and the examples in
/usr/share/paslang/examples; the compiler finds its units beside its
bin, so it compiles as soon as the package is in. The programs are
static and need no library; the compiler needs GNU as and ld.

It needs dpkg-deb, rpmbuild and makepkg (all three run on any of the
distributions that carry them) and runs as an ordinary user.

  scripts/distpkg.py
"""
import os
import shutil
import subprocess
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PKG = os.path.join(ROOT, "build", "pkg")
DIST = os.path.join(PKG, "dist")
WORK = os.path.join(PKG, "work")
URL = "https://github.com/garacil/paslang"
AUTHOR = "Germán Aracil <garacil@tucall.com>"
SUMMARY = "A new Pascal on a Go-shaped engine: compiler, runtime and library"
LONG = [
    "paslang is Pascal with Go's engine underneath: 64-bit integers, UTF-8",
    "strings, routines that park instead of blocking a thread, channels and",
    "select, maps, ordered trees, heaps and an on-disk store in the language,",
    "the sync types, the hash words on the processor's instructions, and the",
    "network on parked routines. paslangc compiles it to static executables",
    "for GNU/Linux on amd64 and arm64, with no libc; a program compiled with",
    "-debug carries its own debugger, and pasdbg is its terminal.",
]
MACHINES = [
    # (release archive name, deb, rpm, arch, slackware)
    ("amd64", "amd64", "x86_64", "x86_64", "x86_64"),
    ("arm64", "arm64", "aarch64", "aarch64", "aarch64"),
]


def version():
    out = subprocess.run([os.path.join(ROOT, "bin", "paslangc"), "-v"], capture_output=True, text=True).stdout
    for w in out.split():
        if w[:1].isdigit() and w.count(".") == 2:
            return w
    sys.exit("distpkg: no version from bin/paslangc -v")


def stage(v, machine):
    """The installation tree under /usr, from the release archive's tree."""
    src = os.path.join(PKG, "paslang-%s-linux-%s" % (v, machine))
    if not os.path.isdir(src):
        sys.exit("distpkg: %s is missing: run make package first" % src)
    root = os.path.join(WORK, machine, "root")
    shutil.rmtree(os.path.join(WORK, machine), ignore_errors=True)
    shutil.copytree(src, os.path.join(root, "usr"), symlinks=True)
    for dirpath, dirnames, filenames in os.walk(root):
        os.chmod(dirpath, 0o755)
        for f in filenames:
            p = os.path.join(dirpath, f)
            os.chmod(p, 0o755 if dirpath.endswith("/usr/bin") else 0o644)
    doc = os.path.join(root, "usr/share/doc/paslang")
    with open(os.path.join(doc, "copyright"), "w") as f:
        f.write("paslang\nCopyright 2026 Germán Aracil <garacil@tucall.com>\n"
                "Source: %s\n\n"
                "The SHA-1, SHA-256, SHA-512 and CRC kernels of src/lib/pashash.paslang\n"
                "follow the assembly of Go 1.23; Go's license, which covers those parts,\n"
                "is in LICENSE-GO beside this file.\n" % URL)
    return root


def size_kb(root):
    total = 0
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            total += os.path.getsize(os.path.join(dirpath, f))
    return (total + 1023) // 1024


def deb(v, root, arch, machine):
    d = os.path.join(root, "DEBIAN")
    os.makedirs(d, exist_ok=True)
    suggests = "binutils-aarch64-linux-gnu, gdb" if arch == "amd64" else "gdb"
    ctl = ["Package: paslang", "Version: %s-1" % v, "Architecture: %s" % arch,
           "Maintainer: %s" % AUTHOR, "Installed-Size: %d" % size_kb(root),
           "Depends: binutils", "Suggests: %s" % suggests, "Section: devel",
           "Priority: optional", "Homepage: %s" % URL, "Description: %s" % SUMMARY]
    ctl += [" " + l for l in LONG]
    with open(os.path.join(d, "control"), "w") as f:
        f.write("\n".join(ctl) + "\n")
    os.chmod(d, 0o755)
    out = os.path.join(DIST, "paslang_%s-1_%s.deb" % (v, arch))
    subprocess.run(["dpkg-deb", "--root-owner-group", "-Zxz", "--build", root, out],
                   check=True, stdout=subprocess.DEVNULL)
    shutil.rmtree(d)
    return out


def rpm(v, root, arch, machine):
    top = os.path.join(WORK, machine, "rpm")
    for sub in ("SPECS", "RPMS", "BUILD", "BUILDROOT", "SOURCES", "SRPMS"):
        os.makedirs(os.path.join(top, sub), exist_ok=True)
    suggests = "Suggests: binutils-aarch64-linux-gnu\n" if arch == "x86_64" else ""
    spec = """Name: paslang
Version: %(v)s
Release: 1
Summary: %(summary)s
License: LicenseRef-paslang AND BSD-3-Clause
URL: %(url)s
Packager: %(author)s
Requires: binutils
%(suggests)sAutoReqProv: no
%%global debug_package %%{nil}
%%global __os_install_post %%{nil}
%%global __strip /bin/true
%%global _build_id_links none

%%description
%(long)s

%%install
mkdir -p %%{buildroot}
cp -a %(root)s/usr %%{buildroot}/

%%files
/usr/bin/paslangc
/usr/bin/pasdbg
/usr/lib/paslang
/usr/share/doc/paslang
/usr/share/paslang
""" % {"v": v, "summary": SUMMARY, "url": URL, "author": AUTHOR, "suggests": suggests,
       "long": "\n".join(LONG), "root": root}
    sp = os.path.join(top, "SPECS", "paslang.spec")
    with open(sp, "w") as f:
        f.write(spec)
    subprocess.run(["rpmbuild", "-bb", "--target", arch, "--define", "_topdir " + top, sp],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    built = os.path.join(top, "RPMS", arch, "paslang-%s-1.%s.rpm" % (v, arch))
    out = os.path.join(DIST, os.path.basename(built))
    shutil.copy(built, out)
    return out


def arch_pkg(v, root, carch, machine):
    b = os.path.join(WORK, machine, "arch")
    os.makedirs(b, exist_ok=True)
    pkgbuild = """pkgname=paslang
pkgver=%(v)s
pkgrel=1
pkgdesc='%(summary)s'
arch=('x86_64' 'aarch64')
url='%(url)s'
license=('LicenseRef-paslang' 'BSD-3-Clause')
depends=('binutils')
optdepends=('aarch64-linux-gnu-binutils: compile for arm64 on an x86-64 machine'
            'gdb: read the DWARF of a compiled program')
options=('!strip' '!debug' '!emptydirs')

package() {
  cp -a '%(root)s/usr' "$pkgdir/"
}
""" % {"v": v, "summary": SUMMARY, "url": URL, "root": root}
    with open(os.path.join(b, "PKGBUILD"), "w") as f:
        f.write(pkgbuild)
    conf = open("/etc/makepkg.conf").read()
    conf += "\nCARCH='%s'\nCHOST='%s-pc-linux-gnu'\nPKGDEST='%s'\nPKGEXT='.pkg.tar.zst'\nPACKAGER='%s'\n" % (
        carch, carch, DIST, AUTHOR)
    cf = os.path.join(b, "makepkg.conf")
    with open(cf, "w") as f:
        f.write(conf)
    env = dict(os.environ)
    env.pop("MAKEFLAGS", None)
    subprocess.run(["makepkg", "--config", cf, "-f", "--nodeps", "--noconfirm"], cwd=b, env=env,
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return os.path.join(DIST, "paslang-%s-1-%s.pkg.tar.zst" % (v, carch))


def slackware(v, root, sarch, machine):
    inst = os.path.join(root, "install")
    os.makedirs(inst, exist_ok=True)
    desc = ["paslang: paslang (a new Pascal on a Go-shaped engine)", "paslang:"]
    desc += ["paslang: " + l for l in LONG]
    while len(desc) < 11:
        desc.append("paslang:")
    with open(os.path.join(inst, "slack-desc"), "w") as f:
        f.write("# HOW TO EDIT THIS FILE: the handy ruler shows where the text may go.\n"
                "       |-----handy-ruler------------------------------------------------------|\n")
        f.write("\n".join(d[:79] for d in desc[:11]) + "\n")
    out = os.path.join(DIST, "paslang-%s-%s-1.tgz" % (v, sarch))

    def owned(ti):
        ti.uid = ti.gid = 0
        ti.uname = ti.gname = "root"
        return ti
    with tarfile.open(out, "w:gz") as t:
        t.add(root, arcname=".", filter=owned)
    shutil.rmtree(inst)
    return out


def main():
    v = version()
    shutil.rmtree(DIST, ignore_errors=True)
    os.makedirs(DIST)
    made = []
    for machine, debarch, rpmarch, carch, sarch in MACHINES:
        root = stage(v, machine)
        made.append(deb(v, root, debarch, machine))
        made.append(rpm(v, root, rpmarch, machine))
        made.append(arch_pkg(v, root, carch, machine))
        made.append(slackware(v, root, sarch, machine))
    shutil.rmtree(WORK, ignore_errors=True)
    for m in made:
        print(os.path.relpath(m, ROOT))


if __name__ == "__main__":
    main()
