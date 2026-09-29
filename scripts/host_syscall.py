#!/usr/bin/env python3
"""FPC bootstrap only: adapt the host copies in build/host so FPC takes them.

paslangc compiles Syscall and Amd64 itself; FPC needs help:
  - Syscall gets an assembler body in paslinux;
  - Amd64 (1 on an amd64 compile, 0 on arm64) is a word of the language,
    usable in any unit without a uses clause, so every host copy gets it
    as an FPC macro. The FPC host is amd64. Macros do not reach string
    literals or comments, so 'Amd64' in the parser's tables is untouched.
  - LongInt and Integer are 64 bits in paslang and 32 in FPC; the host
    copies say Int64 for both, so var parameters match and the host
    compiler computes as paslang does.
  - WaitFd(fd), a word of the language (it parks the routine until fd
    is readable), gets a blocking poll at the end of paslinux's
    interface: paslib and pasx11 name it in statements. Until 1.0.138
    paslib declared a WaitFd of its own, which FPC used and paslangc
    ignored for the builtin; every predefined name is reserved now.
The host build passes -vm6018 (unreachable code), which a constant
Amd64 makes of every 'if Amd64 = 0'.
Before 2026-09-26 only paslinux was adapted and Amd64 was a function in
its implementation, so paslib, pashelp and the driver, which use Amd64,
no longer built under FPC and nobody noticed (P94).
"""
import sys
from pathlib import Path

GLUE = """{$WARN 4055 OFF}
function Syscall(Nr: Int64; A: Int64 = 0; B: Int64 = 0; C: Int64 = 0;
  D: Int64 = 0; E: Int64 = 0): Int64; assembler; nostackframe;
asm
  movq %rdi, %rax
  movq %rsi, %rdi
  movq %rdx, %rsi
  movq %rcx, %rdx
  movq %r8, %r10
  movq %r9, %r9
  syscall
end;

procedure WaitFd(Fd: Int64);
var
  pfd: Int64;
begin
  pfd := (Fd and $FFFFFFFF) or (Int64(1) shl 32);
  OsPoll(PtrInt(@pfd), 1, -1);
end;

"""
IFACE = """procedure WaitFd(Fd: Int64);

"""

HEAD = "{$mode objfpc}{$H+}"
MACRO = "{$MACRO ON}{$DEFINE Amd64:=1}{$DEFINE LongInt:=Int64}{$DEFINE Integer:=Int64}"


def adapt(path: Path) -> None:
    text = path.read_text()
    if MACRO not in text:
        if not text.startswith(HEAD):
            sys.exit("%s: does not start with %s" % (path, HEAD))
        text = HEAD + MACRO + text[len(HEAD):]
    if path.name == "paslinux.pas" and "function Syscall(" not in text:
        needle = "implementation\n"
        if needle not in text:
            sys.exit("paslinux: no implementation")
        text = text.replace(needle, IFACE + "implementation\n" + GLUE, 1)
    path.write_text(text)


def main() -> None:
    target = Path(sys.argv[1])
    files = sorted(target.glob("*.pas")) if target.is_dir() else [target]
    for f in files:
        adapt(f)


if __name__ == "__main__":
    main()
