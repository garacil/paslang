#!/usr/bin/env python3
"""Writes src/lib/pashash.paslang (P111): every hash in Pascal with its
rounds written out (a loop only over the blocks), a second body on the
processor's instructions for SHA-1, SHA-256, SHA-512 (arm64) and the
CRCs, and each word's entry point twice, XxxCpu and XxxBase, so the
compiler picks one by -cpu and the program tests nothing at run time. The arm64 kernels come from Go 1.23's assembly through
scripts/asm_from_go.py; the amd64 SHA-NI kernels are generated here
after Go's sha256block_amd64.s and Intel's SHA extensions structure,
read against the SDM. The unit's text is the source the compiler
reads; run this after changing a kernel or a body:

    python3 scripts/hashgen.py
"""
import os
import sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import asm_from_go

def sha256():
    L = []
    a = L.append
    a('movdqu (%rdi), %xmm1')
    a('movdqu 16(%rdi), %xmm2')
    a('pshufd $0xb1, %xmm1, %xmm1')
    a('pshufd $0x1b, %xmm2, %xmm2')
    a('movdqa %xmm1, %xmm7')
    a('palignr $8, %xmm2, %xmm1')
    a('pblendw $0xf0, %xmm7, %xmm2')
    a('movabsq $0x0405060700010203, %rcx')
    a('movq %rcx, %xmm8')
    a('movabsq $0x0c0d0e0f08090a0b, %rcx')
    a('pinsrq $1, %rcx, %xmm8')
    a('1:')
    a('movdqa %xmm1, %xmm9')
    a('movdqa %xmm2, %xmm10')
    m = {'m0': '%xmm3', 'm1': '%xmm4', 'm2': '%xmm5', 'm3': '%xmm6'}
    def r0to11(mm, aa, c, msg1):
        a('movdqu %d(%%rsi), %%xmm0' % (c * 16))
        a('pshufb %xmm8, %xmm0')
        a('movdqa %%xmm0, %s' % m[mm])
        a('paddd %d(%%rax), %%xmm0' % (c * 16))
        a('sha256rnds2 %xmm1, %xmm2')
        a('pshufd $0x0e, %xmm0, %xmm0')
        a('sha256rnds2 %xmm2, %xmm1')
        if msg1:
            a('sha256msg1 %s, %s' % (m[mm], m[aa]))
    def r12to59(mm, c, aa, t, msg1, rev):
        if rev:
            a('movdqa %%xmm0, %s' % m[mm])
        else:
            a('movdqa %s, %%xmm0' % m[mm])
        a('paddd %d(%%rax), %%xmm0' % (c * 16))
        a('sha256rnds2 %xmm1, %xmm2')
        a('movdqa %s, %%xmm7' % m[mm])
        a('palignr $4, %s, %%xmm7' % m[aa])
        a('paddd %%xmm7, %s' % m[t])
        a('sha256msg2 %s, %s' % (m[mm], m[t]))
        a('pshufd $0x0e, %xmm0, %xmm0')
        a('sha256rnds2 %xmm2, %xmm1')
        if msg1:
            a('sha256msg1 %s, %s' % (m[mm], m[aa]))
    r0to11('m0', None, 0, False)
    r0to11('m1', 'm0', 1, True)
    r0to11('m2', 'm1', 2, True)
    a('movdqu 48(%rsi), %xmm0')
    a('pshufb %xmm8, %xmm0')
    r12to59('m3', 3, 'm2', 'm0', True, True)
    r12to59('m0', 4, 'm3', 'm1', True, False)
    r12to59('m1', 5, 'm0', 'm2', True, False)
    r12to59('m2', 6, 'm1', 'm3', True, False)
    r12to59('m3', 7, 'm2', 'm0', True, False)
    r12to59('m0', 8, 'm3', 'm1', True, False)
    r12to59('m1', 9, 'm0', 'm2', True, False)
    r12to59('m2', 10, 'm1', 'm3', True, False)
    r12to59('m3', 11, 'm2', 'm0', True, False)
    r12to59('m0', 12, 'm3', 'm1', True, False)
    r12to59('m1', 13, 'm0', 'm2', False, False)
    r12to59('m2', 14, 'm1', 'm3', False, False)
    a('movdqa %xmm6, %xmm0')
    a('movdqu 240(%rax), %xmm11')
    a('paddd %xmm11, %xmm0')
    a('sha256rnds2 %xmm1, %xmm2')
    a('pshufd $0x0e, %xmm0, %xmm0')
    a('sha256rnds2 %xmm2, %xmm1')
    a('paddd %xmm9, %xmm1')
    a('paddd %xmm10, %xmm2')
    a('addq $64, %rsi')
    a('decq %rdx')
    a('jnz 1b')
    a('pshufd $0x1b, %xmm1, %xmm1')
    a('pshufd $0xb1, %xmm2, %xmm2')
    a('movdqa %xmm1, %xmm7')
    a('pblendw $0xf0, %xmm2, %xmm1')
    a('palignr $8, %xmm7, %xmm2')
    a('movdqu %xmm1, (%rdi)')
    a('movdqu %xmm2, 16(%rdi)')
    return L

def sha1():
    L = []
    a = L.append
    msg = ['%xmm3', '%xmm4', '%xmm5', '%xmm6']
    a('movdqu (%rdi), %xmm0')
    a('pshufd $0x1b, %xmm0, %xmm0')
    a('pxor %xmm1, %xmm1')
    a('pinsrd $3, 16(%rdi), %xmm1')
    a('movabsq $0x08090a0b0c0d0e0f, %rcx')
    a('movq %rcx, %xmm7')
    a('movabsq $0x0001020304050607, %rcx')
    a('pinsrq $1, %rcx, %xmm7')
    a('1:')
    a('movdqa %xmm0, %xmm8')
    a('movdqa %xmm1, %xmm9')
    for j in range(20):
        M = msg[j % 4]
        ein = '%xmm1' if j % 2 == 0 else '%xmm2'
        eout = '%xmm2' if j % 2 == 0 else '%xmm1'
        if j < 4:
            a('movdqu %d(%%rsi), %s' % (j * 16, M))
            a('pshufb %%xmm7, %s' % M)
        if j == 0:
            a('paddd %s, %%xmm1' % M)
        else:
            a('sha1nexte %s, %s' % (M, ein))
        a('movdqa %%xmm0, %s' % eout)
        if 3 <= j <= 18:
            a('sha1msg2 %s, %s' % (M, msg[(j + 1) % 4]))
        a('sha1rnds4 $%d, %s, %%xmm0' % (j // 5, ein))
        if 1 <= j <= 16:
            a('sha1msg1 %s, %s' % (M, msg[(j + 3) % 4]))
        if 2 <= j <= 17:
            a('pxor %s, %s' % (M, msg[(j + 2) % 4]))
    a('sha1nexte %xmm9, %xmm1')
    a('paddd %xmm8, %xmm0')
    a('addq $64, %rsi')
    a('decq %rdx')
    a('jnz 1b')
    a('pshufd $0x1b, %xmm0, %xmm0')
    a('movdqu %xmm0, (%rdi)')
    a('pextrd $3, %xmm1, 16(%rdi)')
    return L


K256 = [0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
        0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
        0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
        0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
        0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
        0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
        0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
        0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2]
K512 = [0x428a2f98d728ae22, 0x7137449123ef65cd, 0xb5c0fbcfec4d3b2f, 0xe9b5dba58189dbbc,
        0x3956c25bf348b538, 0x59f111f1b605d019, 0x923f82a4af194f9b, 0xab1c5ed5da6d8118,
        0xd807aa98a3030242, 0x12835b0145706fbe, 0x243185be4ee4b28c, 0x550c7dc3d5ffb4e2,
        0x72be5d74f27b896f, 0x80deb1fe3b1696b1, 0x9bdc06a725c71235, 0xc19bf174cf692694,
        0xe49b69c19ef14ad2, 0xefbe4786384f25e3, 0x0fc19dc68b8cd5b5, 0x240ca1cc77ac9c65,
        0x2de92c6f592b0275, 0x4a7484aa6ea6e483, 0x5cb0a9dcbd41fbd4, 0x76f988da831153b5,
        0x983e5152ee66dfab, 0xa831c66d2db43210, 0xb00327c898fb213f, 0xbf597fc7beef0ee4,
        0xc6e00bf33da88fc2, 0xd5a79147930aa725, 0x06ca6351e003826f, 0x142929670a0e6e70,
        0x27b70a8546d22ffc, 0x2e1b21385c26c926, 0x4d2c6dfc5ac42aed, 0x53380d139d95b3df,
        0x650a73548baf63de, 0x766a0abb3c77b2a8, 0x81c2c92e47edaee6, 0x92722c851482353b,
        0xa2bfe8a14cf10364, 0xa81a664bbc423001, 0xc24b8b70d0f89791, 0xc76c51a30654be30,
        0xd192e819d6ef5218, 0xd69906245565a910, 0xf40e35855771202a, 0x106aa07032bbd1b8,
        0x19a4c116b8d2d0c8, 0x1e376c085141ab53, 0x2748774cdf8eeb99, 0x34b0bcb5e19b48a8,
        0x391c0cb3c5c95a63, 0x4ed8aa4ae3418acb, 0x5b9cca4f7763e373, 0x682e6ff3d6b2b8a3,
        0x748f82ee5defb2fc, 0x78a5636f43172f60, 0x84c87814a1f0ab72, 0x8cc702081a6439ec,
        0x90befffa23631e28, 0xa4506cebde82bde9, 0xbef9a3f7b2c67915, 0xc67178f2e372532b,
        0xca273eceea26619c, 0xd186b8c721c0c207, 0xeada7dd6cde0eb1e, 0xf57d4f7fee6ed178,
        0x06f067aa72176fba, 0x0a637dc5a2c898a6, 0x113f9804bef90dae, 0x1b710b35131c471b,
        0x28db77f523047d84, 0x32caab7b40c72493, 0x3c9ebe0a15c9bebc, 0x431d67c49c100d4c,
        0x4cc5d4becb3e42b6, 0x597f299cfc657e2a, 0x5fcb6fab3ad6faec, 0x6c44198c4a475817]
MDK = [0xd76aa478, 0xe8c7b756, 0x242070db, 0xc1bdceee, 0xf57c0faf, 0x4787c62a, 0xa8304613, 0xfd469501,
       0x698098d8, 0x8b44f7af, 0xffff5bb1, 0x895cd7be, 0x6b901122, 0xfd987193, 0xa679438e, 0x49b40821,
       0xf61e2562, 0xc040b340, 0x265e5a51, 0xe9b6c7aa, 0xd62f105d, 0x02441453, 0xd8a1e681, 0xe7d3fbc8,
       0x21e1cde6, 0xc33707d6, 0xf4d50d87, 0x455a14ed, 0xa9e3e905, 0xfcefa3f8, 0x676f02d9, 0x8d2a4c8a,
       0xfffa3942, 0x8771f681, 0x6d9d6122, 0xfde5380c, 0xa4beea44, 0x4bdecfa9, 0xf6bb4b60, 0xbebfbc70,
       0x289b7ec6, 0xeaa127fa, 0xd4ef3085, 0x04881d05, 0xd9d4d039, 0xe6db99e5, 0x1fa27cf8, 0xc4ac5665,
       0xf4292244, 0x432aff97, 0xab9423a7, 0xfc93a039, 0x655b59c3, 0x8f0ccc92, 0xffeff47d, 0x85845dd1,
       0x6fa87e4f, 0xfe2ce6e0, 0xa3014314, 0x4e0811a1, 0xf7537e82, 0xbd3af235, 0x2ad7d2bb, 0xeb86d391]
MDS = [7, 12, 17, 22] * 4 + [5, 9, 14, 20] * 4 + [4, 11, 16, 23] * 4 + [6, 10, 15, 21] * 4
KRC = [0x0000000000000001, 0x0000000000008082, 0x800000000000808a, 0x8000000080008000,
       0x000000000000808b, 0x0000000080000001, 0x8000000080008081, 0x8000000000008009,
       0x000000000000008a, 0x0000000000000088, 0x0000000080008009, 0x000000008000000a,
       0x000000008000808b, 0x800000000000008b, 0x8000000000008089, 0x8000000000008003,
       0x8000000000008002, 0x8000000000000080, 0x000000000000800a, 0x800000008000000a,
       0x8000000080008081, 0x8000000000008080, 0x0000000080000001, 0x8000000080008008]
KROT = [0, 1, 62, 28, 27, 36, 44, 6, 55, 20, 3, 10, 43, 25, 39, 41, 45, 15, 21, 8, 18, 2, 61, 56, 14]


def hex32(v):
    return '$%08x' % v


def hex64(v):
    return '$%016x' % v


def asm_block(lines, arm=False):
    out = []
    for l in lines:
        l = l.strip()
        if not l or l in ('sha1ret:', 'sha256ret:'):
            continue
        if arm:
            if l in ('blockloop:', 'loop:'):
                l = '1:'
            l = l.replace(', blockloop', ', 1b').replace(', loop', ', 1b')
        out.append('    ' + l)
    return '\n'.join(out)


def addr(base, off):
    if off == 0:
        return base
    return 'Pointer(Integer(%s) + %d)' % (base, off)


def sha256_plain():
    L = []
    a = L.append
    a('procedure Sha256BlocksPlain(State, Data: Pointer; N: Integer);')
    a('var')
    a('  ' + ', '.join('w%d' % i for i in range(16)) + ': UInt32;')
    a('  a, b, c, d, e, f, g, h: UInt32;')
    a('  j: Integer;')
    a('  p: Pointer;')
    a('begin')
    a('  for j := 0 to N - 1 do')
    a('  begin')
    a('    p := Pointer(Integer(Data) + j * 64);')
    for i in range(16):
        a('    w%d := LoadBE32(%s);' % (i, addr('p', 4 * i)))
    for i, n in enumerate('abcdefgh'):
        a('    %s := LoadLE32(%s);' % (n, addr('State', 4 * i)))
    r = list('abcdefgh')
    for i in range(64):
        w = 'w%d' % (i % 16)
        if i >= 16:
            w15 = 'w%d' % ((i - 15) % 16)
            w2 = 'w%d' % ((i - 2) % 16)
            w7 = 'w%d' % ((i - 7) % 16)
            a('    %s := %s + (RotateRight(%s, 7) xor RotateRight(%s, 18) xor (%s shr 3)) + %s +' % (w, w, w15, w15, w15, w7))
            a('      (RotateRight(%s, 17) xor RotateRight(%s, 19) xor (%s shr 10));' % (w2, w2, w2))
        A, B, C, D, E, F, G, H = r
        a('    %s := %s + (RotateRight(%s, 6) xor RotateRight(%s, 11) xor RotateRight(%s, 25)) +' % (H, H, E, E, E))
        a('      ((%s and %s) xor ((not %s) and %s)) + %s + %s;' % (E, F, E, G, hex32(K256[i]), w))
        a('    %s := %s + %s;' % (D, D, H))
        a('    %s := %s + (RotateRight(%s, 2) xor RotateRight(%s, 13) xor RotateRight(%s, 22)) +' % (H, H, A, A, A))
        a('      ((%s and %s) xor (%s and %s) xor (%s and %s));' % (A, B, A, C, B, C))
        r = [r[7]] + r[:7]
    for i, n in enumerate('abcdefgh'):
        a('    StoreLE32(%s, LoadLE32(%s) + %s);' % (addr('State', 4 * i), addr('State', 4 * i), n))
    a('  end;')
    a('end;')
    return '\n'.join(L)


def sha1_plain():
    L = []
    a = L.append
    a('procedure Sha1BlocksPlain(State, Data: Pointer; N: Integer);')
    a('var')
    a('  ' + ', '.join('w%d' % i for i in range(16)) + ': UInt32;')
    a('  a, b, c, d, e: UInt32;')
    a('  j: Integer;')
    a('  p: Pointer;')
    a('begin')
    a('  for j := 0 to N - 1 do')
    a('  begin')
    a('    p := Pointer(Integer(Data) + j * 64);')
    for i in range(16):
        a('    w%d := LoadBE32(%s);' % (i, addr('p', 4 * i)))
    for i, n in enumerate('abcde'):
        a('    %s := LoadLE32(%s);' % (n, addr('State', 4 * i)))
    r = list('abcde')
    ks = ['$5a827999', '$6ed9eba1', '$8f1bbcdc', '$ca62c1d6']
    for i in range(80):
        w = 'w%d' % (i % 16)
        if i >= 16:
            a('    %s := RotateLeft(w%d xor w%d xor w%d xor %s, 1);' % (w, (i - 3) % 16, (i - 8) % 16, (i - 14) % 16, w))
        A, B, C, D, E = r
        if i < 20:
            f = '((%s and %s) xor ((not %s) and %s))' % (B, C, B, D)
        elif i < 40 or i >= 60:
            f = '(%s xor %s xor %s)' % (B, C, D)
        else:
            f = '((%s and %s) xor (%s and %s) xor (%s and %s))' % (B, C, B, D, C, D)
        a('    %s := %s + RotateLeft(%s, 5) + %s + %s + %s;' % (E, E, A, f, ks[i // 20], w))
        a('    %s := RotateLeft(%s, 30);' % (B, B))
        r = [r[4], r[0], r[1], r[2], r[3]]
    for i, n in enumerate('abcde'):
        a('    StoreLE32(%s, LoadLE32(%s) + %s);' % (addr('State', 4 * i), addr('State', 4 * i), n))
    a('  end;')
    a('end;')
    return '\n'.join(L)


def sha512_plain():
    L = []
    a = L.append
    a('procedure Sha512BlocksPlain(State, Data: Pointer; N: Integer);')
    a('var')
    a('  ' + ', '.join('w%d' % i for i in range(16)) + ': Integer;')
    a('  a, b, c, d, e, f, g, h: Integer;')
    a('  j: Integer;')
    a('  p: Pointer;')
    a('begin')
    a('  for j := 0 to N - 1 do')
    a('  begin')
    a('    p := Pointer(Integer(Data) + j * 128);')
    for i in range(16):
        a('    w%d := LoadBE64(%s);' % (i, addr('p', 8 * i)))
    for i, n in enumerate('abcdefgh'):
        a('    %s := LoadLE64(%s);' % (n, addr('State', 8 * i)))
    r = list('abcdefgh')
    for i in range(80):
        w = 'w%d' % (i % 16)
        if i >= 16:
            w15 = 'w%d' % ((i - 15) % 16)
            w2 = 'w%d' % ((i - 2) % 16)
            w7 = 'w%d' % ((i - 7) % 16)
            a('    %s := %s + (RotateRight(%s, 1) xor RotateRight(%s, 8) xor (%s shr 7)) + %s +' % (w, w, w15, w15, w15, w7))
            a('      (RotateRight(%s, 19) xor RotateRight(%s, 61) xor (%s shr 6));' % (w2, w2, w2))
        A, B, C, D, E, F, G, H = r
        a('    %s := %s + (RotateRight(%s, 14) xor RotateRight(%s, 18) xor RotateRight(%s, 41)) +' % (H, H, E, E, E))
        a('      ((%s and %s) xor ((not %s) and %s)) + %s + %s;' % (E, F, E, G, hex64(K512[i]), w))
        a('    %s := %s + %s;' % (D, D, H))
        a('    %s := %s + (RotateRight(%s, 28) xor RotateRight(%s, 34) xor RotateRight(%s, 39)) +' % (H, H, A, A, A))
        a('      ((%s and %s) xor (%s and %s) xor (%s and %s));' % (A, B, A, C, B, C))
        r = [r[7]] + r[:7]
    for i, n in enumerate('abcdefgh'):
        a('    StoreLE64(%s, LoadLE64(%s) + %s);' % (addr('State', 8 * i), addr('State', 8 * i), n))
    a('  end;')
    a('end;')
    return '\n'.join(L)


def md5_blocks():
    L = []
    a = L.append
    a('procedure Md5Blocks(State, Data: Pointer; N: Integer);')
    a('var')
    a('  ' + ', '.join('m%d' % i for i in range(16)) + ': UInt32;')
    a('  a, b, c, d: UInt32;')
    a('  j: Integer;')
    a('  p: Pointer;')
    a('begin')
    a('  for j := 0 to N - 1 do')
    a('  begin')
    a('    p := Pointer(Integer(Data) + j * 64);')
    for i in range(16):
        a('    m%d := LoadLE32(%s);' % (i, addr('p', 4 * i)))
    for i, n in enumerate('abcd'):
        a('    %s := LoadLE32(%s);' % (n, addr('State', 4 * i)))
    r = list('abcd')
    for i in range(64):
        A, B, C, D = r
        if i < 16:
            f = '((%s and %s) or ((not %s) and %s))' % (B, C, B, D)
            g = i
        elif i < 32:
            f = '((%s and %s) or ((not %s) and %s))' % (D, B, D, C)
            g = (5 * i + 1) % 16
        elif i < 48:
            f = '(%s xor %s xor %s)' % (B, C, D)
            g = (3 * i + 5) % 16
        else:
            f = '(%s xor (%s or (not %s)))' % (C, B, D)
            g = (7 * i) % 16
        a('    %s := %s + RotateLeft(%s + %s + %s + m%d, %d);' % (A, B, A, f, hex32(MDK[i]), g, MDS[i]))
        r = [r[3], r[0], r[1], r[2]]
    for i, n in enumerate('abcd'):
        a('    StoreLE32(%s, LoadLE32(%s) + %s);' % (addr('State', 4 * i), addr('State', 4 * i), n))
    a('  end;')
    a('end;')
    return '\n'.join(L)


def keccak():
    L = []
    a = L.append
    a('{ Keccak-f[1600] (FIPS 202, 3.2 and 3.3): the 25 lanes in variables, each')
    a('  step written out, the 24 rounds in a loop, the round constants and')
    a('  the rotations of Table 2 in place. }')
    a('procedure KeccakF(A: Pointer);')
    a('var')
    a('  ' + ', '.join('a%d' % i for i in range(25)) + ': Integer;')
    a('  ' + ', '.join('b%d' % i for i in range(25)) + ': Integer;')
    a('  c0, c1, c2, c3, c4, d0, d1, d2, d3, d4: Integer;')
    a('  r: Integer;')
    a('begin')
    for i in range(25):
        a('  a%d := LoadLE64(%s);' % (i, addr('A', 8 * i)))
    a('  for r := 0 to 23 do')
    a('  begin')
    for x in range(5):
        a('    c%d := a%d xor a%d xor a%d xor a%d xor a%d;' % (x, x, x + 5, x + 10, x + 15, x + 20))
    for x in range(5):
        a('    d%d := c%d xor RotateLeft(c%d, 1);' % (x, (x + 4) % 5, (x + 1) % 5))
    for y in range(5):
        for x in range(5):
            a('    a%d := a%d xor d%d;' % (x + 5 * y, x + 5 * y, x))
    for y in range(5):
        for x in range(5):
            src = x + 5 * y
            dst = y + 5 * ((2 * x + 3 * y) % 5)
            if KROT[src] == 0:
                a('    b%d := a%d;' % (dst, src))
            else:
                a('    b%d := RotateLeft(a%d, %d);' % (dst, src, KROT[src]))
    for y in range(5):
        for x in range(5):
            a('    a%d := b%d xor ((not b%d) and b%d);' % (x + 5 * y, x + 5 * y, (x + 1) % 5 + 5 * y, (x + 2) % 5 + 5 * y))
    a('    a0 := a0 xor KeccakRC[r];')
    a('  end;')
    for i in range(25):
        a('  StoreLE64(%s, a%d);' % (addr('A', 8 * i), i))
    a('end;')
    return '\n'.join(L)


SIP = '''    v0 := v0 + v1;
    v1 := RotateLeft(v1, 13);
    v1 := v1 xor v0;
    v0 := RotateLeft(v0, 32);
    v2 := v2 + v3;
    v3 := RotateLeft(v3, 16);
    v3 := v3 xor v2;
    v0 := v0 + v3;
    v3 := RotateLeft(v3, 21);
    v3 := v3 xor v0;
    v2 := v2 + v1;
    v1 := RotateLeft(v1, 17);
    v1 := v1 xor v2;
    v2 := RotateLeft(v2, 32);'''


def variant(v):
    """The entry points of the words that have a body on the processor:
    XxxCpu and XxxBase, each calling only its own block routine. The
    bytes of S are reached as Pointer(S), never @S[1]: the address of
    an element is a write, and a string that came in shared (every
    const parameter is) was copied whole on every call (1.1.1)."""
    blk256 = 'Sha256BlocksCpu' if v == 'Cpu' else 'Sha256BlocksPlain'
    blk1 = 'Sha1BlocksCpu' if v == 'Cpu' else 'Sha1BlocksPlain'
    blk512 = 'Sha512BlocksCpu' if v == 'Cpu' else 'Sha512BlocksPlain'
    t = r'''
function Sha256Of{V}(const S: string; Init: Pointer; OutWords: Integer): string;
var
  st: array[0..7] of UInt32;
  buf: array[0..127] of Byte;
  i, n, nb: Integer;
begin
  for i := 0 to 7 do
    st[i] := LoadLE32(Pointer(Integer(Init) + i * 4));
  n := Length(S) div 64;
  if n > 0 then
    {BLK256}(@st[0], Pointer(S), n);
  Tail64(S, @buf[0], nb, False);
  {BLK256}(@st[0], @buf[0], nb);
  SetLength(Result, OutWords * 4);
  for i := 0 to OutWords - 1 do
    StoreBE32(@Result[i * 4 + 1], st[i]);
end;

function PasSha256{V}(const S: string): string;
begin
  Result := Sha256Of{V}(S, @H256[0], 8);
end;

function PasSha224{V}(const S: string): string;
begin
  Result := Sha256Of{V}(S, @H224[0], 7);
end;

function PasSha1{V}(const S: string): string;
var
  st: array[0..4] of UInt32;
  buf: array[0..127] of Byte;
  i, n, nb: Integer;
begin
  st[0] := $67452301;
  st[1] := $efcdab89;
  st[2] := $98badcfe;
  st[3] := $10325476;
  st[4] := $c3d2e1f0;
  n := Length(S) div 64;
  if n > 0 then
    {BLK1}(@st[0], Pointer(S), n);
  Tail64(S, @buf[0], nb, False);
  {BLK1}(@st[0], @buf[0], nb);
  SetLength(Result, 20);
  for i := 0 to 4 do
    StoreBE32(@Result[i * 4 + 1], st[i]);
end;

function Sha512Of{V}(const S: string; Init: Pointer; OutWords: Integer): string;
var
  st: array[0..7] of Integer;
  buf: array[0..255] of Byte;
  i, n, off, rest, nb: Integer;
begin
  for i := 0 to 7 do
    st[i] := LoadLE64(Pointer(Integer(Init) + i * 8));
  n := Length(S) div 128;
  if n > 0 then
    {BLK512}(@st[0], Pointer(S), n);
  { FIPS 180-4, 5.1.2: a 1 bit, zeros, the length in 128 bits }
  off := n * 128;
  rest := Length(S) - off;
  for i := 0 to 255 do
    buf[i] := 0;
  for i := 0 to rest - 1 do
    buf[i] := Byte(S[off + 1 + i]);
  buf[rest] := 128;
  if rest < 112 then
    nb := 1
  else
    nb := 2;
  StoreBE64(@buf[nb * 128 - 8], Length(S) * 8);
  {BLK512}(@st[0], @buf[0], nb);
  SetLength(Result, OutWords * 8);
  for i := 0 to OutWords - 1 do
    StoreBE64(@Result[i * 8 + 1], st[i]);
end;

function PasSha512{V}(const S: string): string;
begin
  Result := Sha512Of{V}(S, @H512[0], 8);
end;

function PasSha384{V}(const S: string): string;
begin
  Result := Sha512Of{V}(S, @H384[0], 6);
end;

function HashBy{V}(Alg: Integer; const S: string): string;
begin
  case Alg of
    0: Result := PasMd5(S);
    1: Result := PasSha1{V}(S);
    2: Result := PasSha224{V}(S);
    3: Result := PasSha256{V}(S);
    4: Result := PasSha384{V}(S);
  else
    Result := PasSha512{V}(S);
  end;
end;

{ HMAC (RFC 2104): H((K xor opad) || H((K xor ipad) || M)), the key
  hashed first when longer than the block. }
function PasHmac{V}(Alg: Integer; const Key, Msg: string): string;
var
  blk, i: Integer;
  k, ipad, opad: string;
begin
  if Alg >= 4 then
    blk := 128
  else
    blk := 64;
  k := Key;
  if Length(k) > blk then
    k := HashBy{V}(Alg, k);
  SetLength(ipad, blk);
  SetLength(opad, blk);
  for i := 1 to blk do
  begin
    if i <= Length(k) then
    begin
      ipad[i] := Char(Ord(k[i]) xor $36);
      opad[i] := Char(Ord(k[i]) xor $5c);
    end
    else
    begin
      ipad[i] := Char($36);
      opad[i] := Char($5c);
    end;
  end;
  Result := HashBy{V}(Alg, opad + HashBy{V}(Alg, ipad + Msg));
end;

{ The Merkle tree of RFC 9162: a leaf is SHA-256 of 0x00 and the entry,
  a node SHA-256 of 0x01 and its two children, the split of n leaves at
  the greatest power of two below n. }
function MTH{V}(const Items: array of string; Lo, Hi: Integer): string;
var
  n, k: Integer;
begin
  n := Hi - Lo;
  if n = 0 then
  begin
    Result := PasSha256{V}('');
    Exit;
  end;
  if n = 1 then
  begin
    Result := PasSha256{V}(Char(0) + Items[Lo]);
    Exit;
  end;
  k := 1;
  while k * 2 < n do
    k := k * 2;
  Result := PasSha256{V}(Char(1) + MTH{V}(Items, Lo, Lo + k) + MTH{V}(Items, Lo + k, Hi));
end;

function PasMerkleRoot{V}(const Leaves: array of string): string;
begin
  Result := MTH{V}(Leaves, 0, Length(Leaves));
end;

function Path{V}(const Items: array of string; Index, Lo, Hi: Integer): string;
var
  n, k: Integer;
begin
  n := Hi - Lo;
  if n <= 1 then
  begin
    Result := '';
    Exit;
  end;
  k := 1;
  while k * 2 < n do
    k := k * 2;
  if Index < Lo + k then
    Result := Path{V}(Items, Index, Lo, Lo + k) + MTH{V}(Items, Lo + k, Hi)
  else
    Result := Path{V}(Items, Index, Lo + k, Hi) + MTH{V}(Items, Lo, Lo + k);
end;

function PasMerkleProof{V}(const Leaves: array of string; Index: Integer): string;
begin
  if (Index < 0) or (Index >= Length(Leaves)) then
  begin
    WriteLn(ErrOutput, 'paslang: merkle index');
    Halt(1);
  end;
  Result := Path{V}(Leaves, Index, 0, Length(Leaves));
end;

{ RFC 9162, 2.1.3.2: the proof walked from the leaf up. }
function PasMerkleCheck{V}(const Leaf: string; Index, Count: Integer;
  const Proof, Root: string): Boolean;
var
  r, p: string;
  fn, sn, i: Integer;
begin
  Result := False;
  if (Index < 0) or (Index >= Count) then
    Exit;
  if Length(Proof) mod 32 <> 0 then
    Exit;
  r := PasSha256{V}(Char(0) + Leaf);
  fn := Index;
  sn := Count - 1;
  i := 1;
  while i + 31 <= Length(Proof) do
  begin
    if sn = 0 then
      Exit;
    p := Copy(Proof, i, 32);
    if ((fn and 1) <> 0) or (fn = sn) then
    begin
      r := PasSha256{V}(Char(1) + p + r);
      while ((fn and 1) = 0) and (fn <> 0) do
      begin
        fn := fn shr 1;
        sn := sn shr 1;
      end;
    end
    else
      r := PasSha256{V}(Char(1) + r + p);
    fn := fn shr 1;
    sn := sn shr 1;
    i := i + 32;
  end;
  Result := (sn = 0) and (r = Root);
end;
'''
    return t.replace('{V}', v).replace('{BLK256}', blk256).replace('{BLK1}', blk1).replace('{BLK512}', blk512)


def consts(name, typ, vals, fmt, per):
    L = ['  %s: array[0..%d] of %s = (' % (name, len(vals) - 1, typ)]
    for i in range(0, len(vals), per):
        row = ', '.join(fmt(v) for v in vals[i:i + per])
        L.append('    ' + row + (',' if i + per < len(vals) else ');'))
    return '\n'.join(L)


HEAD = r'''{$mode objfpc}{$H+}

{ The hash words of the language (P111): Md5, Sha1, Sha224, Sha256,
  Sha384, Sha512, Sha3_224, Sha3_256, Sha3_384, Sha3_512, the HMAC of
  each of the first six, Crc32, Crc32c, Adler32, Fnv1a32, Fnv1a64,
  Murmur3, SipHash, Hex, and the Merkle words on Sha256. Each algorithm
  is written here as its standard writes it (RFC 1321, FIPS 180-4,
  FIPS 202, RFC 2104, RFC 1952, RFC 3720, RFC 1950, MurmurHash3 and
  SipHash-2-4 as their authors published them, RFC 9162), in Pascal
  with its rounds written out (a loop only over the blocks), and the
  block routines of SHA-1, SHA-256, SHA-512 and the CRCs have a second
  body on the processor's own instructions, in asm blocks written after
  Go 1.23's crypto/sha1, sha256, sha512 and hash/crc32 assembly for
  each machine (docs/ref/go1.23) and read against the Intel SDM and the
  Arm ARM (docs/ref/asm): SHA-1 and SHA-256 on SHA-NI (amd64) and on
  FEAT_SHA1 and FEAT_SHA256 (arm64), SHA-512 on FEAT_SHA512 (arm64;
  amd64's SHA512 extension has no processor here to answer for it, so
  the Pascal rounds serve there), CRC32C on SSE4.2's crc32 and on
  FEAT_CRC32, CRC32 on PCLMULQDQ folding and on FEAT_CRC32.

  Each word that has such a body is exported twice, XxxCpu on the
  processor's instructions and XxxBase in Pascal: the
  compiler calls one or the other by -cpu, and the program tests
  nothing at run time; PASLANG_CPU=base no longer reaches here. A
  digest is a string of its bytes; Hex writes one out. This unit is
  written by scripts/hashgen.py from its template (the rounds are
  written out by it, the arm64 kernels come through
  scripts/asm_from_go.py); the text here is the source the compiler
  reads, and the script is run again after a change. }
unit pashash;

interface

function PasHex(const S: string): string;
function PasMd5(const S: string): string;
function PasSha1Cpu(const S: string): string;
function PasSha1Base(const S: string): string;
function PasSha224Cpu(const S: string): string;
function PasSha224Base(const S: string): string;
function PasSha256Cpu(const S: string): string;
function PasSha256Base(const S: string): string;
function PasSha384Cpu(const S: string): string;
function PasSha384Base(const S: string): string;
function PasSha512Cpu(const S: string): string;
function PasSha512Base(const S: string): string;
function PasSha3(const S: string; Bits: Integer): string;
function PasHmacCpu(Alg: Integer; const Key, Msg: string): string;
function PasHmacBase(Alg: Integer; const Key, Msg: string): string;
function PasCrc32Cpu(const S: string; Crc: Integer): Integer;
function PasCrc32Base(const S: string; Crc: Integer): Integer;
function PasCrc32cCpu(const S: string; Crc: Integer): Integer;
function PasCrc32cBase(const S: string; Crc: Integer): Integer;
function PasAdler32(const S: string; Adler: Integer): Integer;
function PasFnv1a32(const S: string): Integer;
function PasFnv1a64(const S: string): Integer;
function PasMurmur3(const S: string; Seed: Integer): Integer;
function PasSipHash(const S: string; K0, K1: Integer): Integer;
function PasMerkleRootCpu(const Leaves: array of string): string;
function PasMerkleRootBase(const Leaves: array of string): string;
function PasMerkleProofCpu(const Leaves: array of string; Index: Integer): string;
function PasMerkleProofBase(const Leaves: array of string; Index: Integer): string;
function PasMerkleCheckCpu(const Leaf: string; Index, Count: Integer; const Proof, Root: string): Boolean;
function PasMerkleCheckBase(const Leaf: string; Index, Count: Integer; const Proof, Root: string): Boolean;

implementation

const
  { FIPS 180-4, 4.2.2: the first 32 bits of the fractional parts of
    the cube roots of the first 64 primes, for the SHA-256 kernels }
'''

MID1 = r'''
  { FIPS 180-4, 5.3: the initial hash values }
  H256: array[0..7] of UInt32 = ($6a09e667, $bb67ae85, $3c6ef372, $a54ff53a,
    $510e527f, $9b05688c, $1f83d9ab, $5be0cd19);
  H224: array[0..7] of UInt32 = ($c1059ed8, $367cd507, $3070dd17, $f70e5939,
    $ffc00b31, $68581511, $64f98fa7, $befa4fa4);
  H512: array[0..7] of Integer = ($6a09e667f3bcc908, $bb67ae8584caa73b,
    $3c6ef372fe94f82b, $a54ff53a5f1d36f1, $510e527fade682d1, $9b05688c2b3e6c1f,
    $1f83d9abfb41bd6b, $5be0cd19137e2179);
  H384: array[0..7] of Integer = ($cbbb9d5dc1059ed8, $629a292a367cd507,
    $9159015a3070dd17, $152fecd8f70e5939, $67332667ffc00b31, $8eb44a8768581511,
    $db0c2e0d64f98fa7, $47b5481dbefa4fa4);
  { FIPS 180-4, 4.2.1: the four SHA-1 constants, for the arm64 kernel }
  K1: array[0..3] of UInt32 = ($5a827999, $6ed9eba1, $8f1bbcdc, $ca62c1d6);
'''

TAIL_HELPERS = r'''
var
  Crc32Tab: array[0..255] of UInt32;
  Crc32cTab: array[0..255] of UInt32;
  TabsReady: Integer;   { 1 once the tables are built, released after them }

function PasHex(const S: string): string;
const
  Digs = '0123456789abcdef';
var
  i, b: Integer;
begin
  SetLength(Result, Length(S) * 2);
  for i := 1 to Length(S) do
  begin
    b := Ord(S[i]);
    Result[i * 2 - 1] := Digs[(b shr 4) + 1];
    Result[i * 2] := Digs[(b and 15) + 1];
  end;
end;

{ The tail of a message for a 64-byte block hash (FIPS 180-4, 5.1.1;
  RFC 1321, 3.1-3.2): a 1 bit, zeros, and the length in bits, big-endian
  for SHA and little-endian for MD5, in one block or two, at Buf. }
procedure Tail64(const S: string; Buf: Pointer; out NBlocks: Integer; LittleLen: Boolean);
var
  n, off, rest, i, bits: Integer;
begin
  n := Length(S);
  off := (n div 64) * 64;
  rest := n - off;
  for i := 0 to 127 do
    PByte(Buf)[i] := 0;
  for i := 0 to rest - 1 do
    PByte(Buf)[i] := Byte(S[off + 1 + i]);
  PByte(Buf)[rest] := 128;
  if rest < 56 then
    NBlocks := 1
  else
    NBlocks := 2;
  bits := n * 8;
  if LittleLen then
    StoreLE64(Pointer(Integer(Buf) + NBlocks * 64 - 8), bits)
  else
    StoreBE64(Pointer(Integer(Buf) + NBlocks * 64 - 8), bits);
end;
'''

X86_CRC32C = r'''    1:
    cmpq $8, %rcx
    jb 2f
    crc32q (%rsi), %rax
    addq $8, %rsi
    subq $8, %rcx
    jmp 1b
    2:
    testq %rcx, %rcx
    jz 3f
    crc32b (%rsi), %eax
    incq %rsi
    decq %rcx
    jmp 2b
    3:'''

ARM_CRC = r'''    1:
    cmp x2, #16
    b.lt 2f
    ldp x8, x10, [x1], #16
    crc32{C}x w0, w0, x8
    crc32{C}x w0, w0, x10
    sub x2, x2, #16
    b 1b
    2:
    tbz x2, #3, 3f
    ldr x10, [x1], #8
    crc32{C}x w0, w0, x10
    3:
    tbz x2, #2, 4f
    ldr w10, [x1], #4
    crc32{C}w w0, w0, w10
    4:
    tbz x2, #1, 5f
    ldrh w10, [x1], #2
    crc32{C}h w0, w0, w10
    5:
    tbz x2, #0, 6f
    ldrb w10, [x1]
    crc32{C}b w0, w0, w10
    6:'''

X86_CRC32_CLMUL = r'''    movd %eax, %xmm0
    movdqu (%rsi), %xmm1
    movdqu 16(%rsi), %xmm2
    movdqu 32(%rsi), %xmm3
    movdqu 48(%rsi), %xmm4
    pxor %xmm0, %xmm1
    addq $64, %rsi
    subq $64, %rcx
    cmpq $64, %rcx
    jb 2f
    movabsq $0x154442bd4, %rdx
    movq %rdx, %xmm0
    movabsq $0x1c6e41596, %rdx
    pinsrq $1, %rdx, %xmm0
    1:
    movdqa %xmm1, %xmm5
    movdqa %xmm2, %xmm6
    movdqa %xmm3, %xmm7
    movdqa %xmm4, %xmm8
    pclmulqdq $0, %xmm0, %xmm1
    pclmulqdq $0, %xmm0, %xmm2
    pclmulqdq $0, %xmm0, %xmm3
    pclmulqdq $0, %xmm0, %xmm4
    movdqu (%rsi), %xmm11
    movdqu 16(%rsi), %xmm12
    movdqu 32(%rsi), %xmm13
    movdqu 48(%rsi), %xmm14
    pclmulqdq $0x11, %xmm0, %xmm5
    pclmulqdq $0x11, %xmm0, %xmm6
    pclmulqdq $0x11, %xmm0, %xmm7
    pclmulqdq $0x11, %xmm0, %xmm8
    pxor %xmm5, %xmm1
    pxor %xmm6, %xmm2
    pxor %xmm7, %xmm3
    pxor %xmm8, %xmm4
    pxor %xmm11, %xmm1
    pxor %xmm12, %xmm2
    pxor %xmm13, %xmm3
    pxor %xmm14, %xmm4
    addq $64, %rsi
    subq $64, %rcx
    cmpq $64, %rcx
    jge 1b
    2:
    movabsq $0x1751997d0, %rdx
    movq %rdx, %xmm0
    movabsq $0x0ccaa009e, %rdx
    pinsrq $1, %rdx, %xmm0
    movdqa %xmm1, %xmm5
    pclmulqdq $0, %xmm0, %xmm1
    pclmulqdq $0x11, %xmm0, %xmm5
    pxor %xmm5, %xmm1
    pxor %xmm2, %xmm1
    movdqa %xmm1, %xmm5
    pclmulqdq $0, %xmm0, %xmm1
    pclmulqdq $0x11, %xmm0, %xmm5
    pxor %xmm5, %xmm1
    pxor %xmm3, %xmm1
    movdqa %xmm1, %xmm5
    pclmulqdq $0, %xmm0, %xmm1
    pclmulqdq $0x11, %xmm0, %xmm5
    pxor %xmm5, %xmm1
    pxor %xmm4, %xmm1
    cmpq $16, %rcx
    jb 4f
    3:
    movdqu (%rsi), %xmm10
    movdqa %xmm1, %xmm5
    pclmulqdq $0, %xmm0, %xmm1
    pclmulqdq $0x11, %xmm0, %xmm5
    pxor %xmm5, %xmm1
    pxor %xmm10, %xmm1
    subq $16, %rcx
    addq $16, %rsi
    cmpq $16, %rcx
    jge 3b
    4:
    pcmpeqb %xmm3, %xmm3
    pclmulqdq $1, %xmm1, %xmm0
    psrldq $8, %xmm1
    pxor %xmm0, %xmm1
    movdqa %xmm1, %xmm2
    movabsq $0x163cd6124, %rdx
    movq %rdx, %xmm0
    psrlq $32, %xmm3
    psrldq $4, %xmm2
    pand %xmm3, %xmm1
    pclmulqdq $0, %xmm0, %xmm1
    pxor %xmm2, %xmm1
    movabsq $0x1db710641, %rdx
    movq %rdx, %xmm0
    movabsq $0x1f7011641, %rdx
    pinsrq $1, %rdx, %xmm0
    movdqa %xmm1, %xmm2
    pand %xmm3, %xmm1
    pclmulqdq $0x10, %xmm0, %xmm1
    pand %xmm3, %xmm1
    pclmulqdq $0, %xmm0, %xmm1
    pxor %xmm2, %xmm1
    pextrd $1, %xmm1, %eax'''



REST = r'''
{ ---- MD5 (RFC 1321) ---- }

{MD5}

function PasMd5(const S: string): string;
var
  st: array[0..3] of UInt32;
  buf: array[0..127] of Byte;
  i, n, nb: Integer;
begin
  st[0] := $67452301;
  st[1] := $efcdab89;
  st[2] := $98badcfe;
  st[3] := $10325476;
  n := Length(S) div 64;
  if n > 0 then
    Md5Blocks(@st[0], Pointer(S), n);
  Tail64(S, @buf[0], nb, True);
  Md5Blocks(@st[0], @buf[0], nb);
  SetLength(Result, 16);
  for i := 0 to 3 do
    StoreLE32(@Result[i * 4 + 1], st[i]);
end;

{ ---- SHA-3 (FIPS 202): the sponge with rate 1600 - 2 d bits and the
  01 suffix ---- }

{KECCAK}

function PasSha3(const S: string; Bits: Integer): string;
var
  a: array[0..24] of Integer;
  blk: array[0..143] of Byte;
  rate, i, j, n, off, rest, lanes: Integer;
  t: Integer;
begin
  if not ((Bits = 224) or (Bits = 256) or (Bits = 384) or (Bits = 512)) then
  begin
    WriteLn(ErrOutput, 'paslang: Sha3 takes 224, 256, 384 or 512 bits');
    Halt(1);
  end;
  rate := 200 - 2 * (Bits div 8);
  lanes := rate div 8;
  for i := 0 to 24 do
    a[i] := 0;
  n := Length(S) div rate;
  for j := 0 to n - 1 do
  begin
    for i := 0 to lanes - 1 do
      a[i] := a[i] xor LoadLE64(Pointer(Integer(Pointer(S)) + j * rate + i * 8));
    KeccakF(@a[0]);
  end;
  off := n * rate;
  rest := Length(S) - off;
  for i := 0 to 143 do
    blk[i] := 0;
  for i := 0 to rest - 1 do
    blk[i] := Byte(S[off + 1 + i]);
  blk[rest] := blk[rest] xor $06;
  blk[rate - 1] := blk[rate - 1] xor $80;
  for i := 0 to lanes - 1 do
    a[i] := a[i] xor LoadLE64(@blk[i * 8]);
  KeccakF(@a[0]);
  SetLength(Result, Bits div 8);
  i := 0;
  while i < Bits div 8 do
  begin
    t := a[i div 8];
    for j := 0 to 7 do
      if i + j < Bits div 8 then
        Result[i + j + 1] := Char((t shr (8 * j)) and 255);
    i := i + 8;
  end;
end;

{ ---- CRC-32 (RFC 1952, the polynomial of Ethernet and zlib) and
  CRC-32C (RFC 3720, Castagnoli), reflected; the table of 256 entries
  built the first time a Pascal path needs it ---- }

{ Two routines building the tables at once write the same values; the
  flag is stored after them and read before them, so a routine that
  sees it sees the tables. }
procedure BuildTabs;
var
  i, j: Integer;
  c, cc: UInt32;
begin
  if AtomicLoad(TabsReady) <> 0 then
    Exit;
  for i := 0 to 255 do
  begin
    c := UInt32(i);
    cc := UInt32(i);
    for j := 0 to 7 do
    begin
      if (c and 1) <> 0 then
        c := (c shr 1) xor $edb88320
      else
        c := c shr 1;
      if (cc and 1) <> 0 then
        cc := (cc shr 1) xor $82f63b78
      else
        cc := cc shr 1;
    end;
    Crc32Tab[i] := c;
    Crc32cTab[i] := cc;
  end;
  AtomicStore(TabsReady, 1);
end;

function Crc32Plain(Crc: UInt32; P: Pointer; N: Integer; Castagnoli: Boolean): UInt32;
var
  i: Integer;
  b: Integer;
begin
  Result := Crc;
  if Castagnoli then
    for i := 0 to N - 1 do
    begin
      b := PByte(P)[i];
      Result := Crc32cTab[(Result xor b) and 255] xor (Result shr 8);
    end
  else
    for i := 0 to N - 1 do
    begin
      b := PByte(P)[i];
      Result := Crc32Tab[(Result xor b) and 255] xor (Result shr 8);
    end;
end;

{ CRC32C on the processor: SSE4.2's crc32 eight bytes a step (SDM vol.
  2A, CRC32), FEAT_CRC32's CRC32CX two words a step after Go's
  crc32_arm64.s (Arm ARM C6.2.136). }
function Crc32cCpu(Crc: UInt32; P: Pointer; N: Integer): UInt32;
var
  c: UInt32;
begin
  c := Crc;
  asm amd64 (P: in rsi; N: in rcx; c: inout rax)
{X86_CRC32C}
  end;
  asm arm64 (P: in x1; N: in x2; c: inout x0)
{ARM_CRC32C}
  end;
  Result := c;
end;

{$ifndef CPUAARCH64}
{ Three crc32q chains at once (1.1.1), after Go's castagnoliSSE42Triple:
  crc32q takes three cycles but three of them run together, so three
  pieces of a buffer are summed in the time of one; A, B and C are the
  three CRCs, PA, PB and PC the pieces, Rounds how many 24-byte steps.
  Folding by PCLMULQDQ with Castagnoli's constants gave 18 GB/s here,
  this 33, so the fold was dropped. }
procedure Crc32cTriple(var A, B, C: UInt32; PA, PB, PC: Pointer; Rounds: Integer);
var
  ca, cb, cc: UInt32;
begin
  ca := A;
  cb := B;
  cc := C;
  asm amd64 (ca: inout rax; cb: inout rcx; cc: inout rdx; PA: in rsi; PB: in rdi; PC: in r8; Rounds: in r9)
    1:
    crc32q (%rsi), %rax
    crc32q (%rdi), %rcx
    crc32q (%r8), %rdx
    crc32q 8(%rsi), %rax
    crc32q 8(%rdi), %rcx
    crc32q 8(%r8), %rdx
    crc32q 16(%rsi), %rax
    crc32q 16(%rdi), %rcx
    crc32q 16(%r8), %rdx
    addq $24, %rsi
    addq $24, %rdi
    addq $24, %r8
    decq %r9
    jnz 1b
  end;
  A := ca;
  B := cb;
  C := cc;
end;

const
  CrcK1 = 168;
  CrcK2 = 1344;

var
  { CRC(i000, O), CRC(0i00, O), CRC(00i0, O), CRC(000i, O) for O of K
    zero bytes, K1 and K2: the CRC of a piece carried over the pieces
    after it (Go's castagnoliShift). Built at first use. }
  CrcShiftK1: array[0..3] of array[0..255] of UInt32;
  CrcShiftK2: array[0..3] of array[0..255] of UInt32;
  CrcShiftReady: Integer;

procedure BuildCrcShift;
var
  zeros: array[0..1343] of Byte;
  b, i: Integer;
begin
  if AtomicLoad(CrcShiftReady) <> 0 then
    Exit;
  for i := 0 to High(zeros) do
    zeros[i] := 0;
  for b := 0 to 3 do
    for i := 0 to 255 do
    begin
      CrcShiftK1[b][i] := Crc32cCpu(UInt32(i) shl (b * 8), @zeros[0], CrcK1);
      CrcShiftK2[b][i] := Crc32cCpu(UInt32(i) shl (b * 8), @zeros[0], CrcK2);
    end;
  AtomicStore(CrcShiftReady, 1);
end;

function CrcShift1(Crc: UInt32): UInt32;
begin
  Result := CrcShiftK1[3][Crc shr 24] xor CrcShiftK1[2][(Crc shr 16) and 255] xor
    CrcShiftK1[1][(Crc shr 8) and 255] xor CrcShiftK1[0][Crc and 255];
end;

function CrcShift2(Crc: UInt32): UInt32;
begin
  Result := CrcShiftK2[3][Crc shr 24] xor CrcShiftK2[2][(Crc shr 16) and 255] xor
    CrcShiftK2[1][(Crc shr 8) and 255] xor CrcShiftK2[0][Crc and 255];
end;

{ Go's updateCastagnoli: the buffer in three pieces of K2 (then K1)
  bytes summed together, the CRC of the first two carried over the
  bytes after them by the tables, the rest by one chain. }
function Crc32cFast(Crc: UInt32; P: Pointer; N: Integer): UInt32;
var
  a, b, c: UInt32;
  q, delta: Integer;
begin
  Result := Crc;
  q := Integer(P);
  if N >= CrcK1 * 3 then
  begin
    delta := q and 7;
    if delta <> 0 then
    begin
      delta := 8 - delta;
      Result := Crc32cCpu(Result, Pointer(q), delta);
      q := q + delta;
      N := N - delta;
    end;
    BuildCrcShift;
  end;
  while N >= CrcK2 * 3 do
  begin
    a := Result;
    b := 0;
    c := 0;
    Crc32cTriple(a, b, c, Pointer(q), Pointer(q + CrcK2), Pointer(q + 2 * CrcK2), CrcK2 div 24);
    Result := CrcShift2(CrcShift2(a) xor b) xor c;
    q := q + 3 * CrcK2;
    N := N - 3 * CrcK2;
  end;
  while N >= CrcK1 * 3 do
  begin
    a := Result;
    b := 0;
    c := 0;
    Crc32cTriple(a, b, c, Pointer(q), Pointer(q + CrcK1), Pointer(q + 2 * CrcK1), CrcK1 div 24);
    Result := CrcShift1(CrcShift1(a) xor b) xor c;
    q := q + 3 * CrcK1;
    N := N - 3 * CrcK1;
  end;
  if N > 0 then
    Result := Crc32cCpu(Result, Pointer(q), N);
end;
{$endif}

{ CRC32 on the processor: on arm64 FEAT_CRC32's CRC32X as above (Arm
  ARM C6.2.135); on amd64 the folding by PCLMULQDQ after Go's
  crc32_amd64.s ieeeCLMUL (Intel, Fast CRC Computation for Generic
  Polynomials Using PCLMULQDQ Instruction), which takes at least 64
  bytes and a whole number of 16-byte pieces: N is that, the caller
  finishes the rest. }
function Crc32Cpu(Crc: UInt32; P: Pointer; N: Integer): UInt32;
var
  c: UInt32;
begin
  c := Crc;
  asm amd64 (P: in rsi; N: in rcx; c: inout rax)
{X86_CRC32_CLMUL}
  end;
  asm arm64 (P: in x1; N: in x2; c: inout x0)
{ARM_CRC32}
  end;
  Result := c;
end;

function PasCrc32Base(const S: string; Crc: Integer): Integer;
var
  c: UInt32;
begin
  BuildTabs;
  c := UInt32(Crc);
  c := not c;
  if Length(S) > 0 then
    c := Crc32Plain(c, Pointer(S), Length(S), False);
  c := not c;
  Result := c;
end;

function PasCrc32Cpu(const S: string; Crc: Integer): Integer;
var
  c: UInt32;
  n, done: Integer;
begin
  c := UInt32(Crc);
  c := not c;
  n := Length(S);
  done := 0;
  if n > 0 then
  begin
{$ifdef CPUAARCH64}
    c := Crc32Cpu(c, Pointer(S), n);
    done := n;
{$else}
    if n >= 64 then
    begin
      done := n - (n mod 16);
      c := Crc32Cpu(c, Pointer(S), done);
    end;
{$endif}
    if done < n then
    begin
      BuildTabs;
      c := Crc32Plain(c, Pointer(Integer(Pointer(S)) + done), n - done, False);
    end;
  end;
  c := not c;
  Result := c;
end;

function PasCrc32cBase(const S: string; Crc: Integer): Integer;
var
  c: UInt32;
begin
  BuildTabs;
  c := UInt32(Crc);
  c := not c;
  if Length(S) > 0 then
    c := Crc32Plain(c, Pointer(S), Length(S), True);
  c := not c;
  Result := c;
end;

function PasCrc32cCpu(const S: string; Crc: Integer): Integer;
var
  c: UInt32;
  n, done: Integer;
begin
  c := UInt32(Crc);
  c := not c;
  n := Length(S);
  done := 0;
{$ifndef CPUAARCH64}
  if n > 0 then
  begin
    c := Crc32cFast(c, Pointer(S), n);
    done := n;
  end;
{$endif}
  if done < n then
    c := Crc32cCpu(c, Pointer(Integer(Pointer(S)) + done), n - done);
  c := not c;
  Result := c;
end;

{ ---- Adler-32 (RFC 1950), in runs of 5552 bytes between reductions ---- }

function PasAdler32(const S: string; Adler: Integer): Integer;
var
  a, b: Integer;
  i, n, run: Integer;
begin
  a := Adler and $ffff;
  b := (Adler shr 16) and $ffff;
  i := 1;
  n := Length(S);
  while i <= n do
  begin
    run := n - i + 1;
    if run > 5552 then
      run := 5552;
    while run > 0 do
    begin
      a := a + Ord(S[i]);
      b := b + a;
      i := i + 1;
      run := run - 1;
    end;
    a := a mod 65521;
    b := b mod 65521;
  end;
  Result := (b shl 16) or a;
end;

{ ---- FNV-1a, 32 and 64 bits (Fowler, Noll, Vo) ---- }

function PasFnv1a32(const S: string): Integer;
var
  h: UInt32;
  i: Integer;
begin
  h := $811c9dc5;
  for i := 1 to Length(S) do
  begin
    h := h xor UInt32(Ord(S[i]));
    h := h * $01000193;
  end;
  Result := h;
end;

function PasFnv1a64(const S: string): Integer;
var
  h, i: Integer;
begin
  h := $cbf29ce484222325;
  for i := 1 to Length(S) do
  begin
    h := h xor Ord(S[i]);
    h := h * $100000001b3;
  end;
  Result := h;
end;

{ ---- MurmurHash3, the 32-bit x86 variant (Austin Appleby) ---- }

function PasMurmur3(const S: string; Seed: Integer): Integer;
var
  h, k: UInt32;
  i, n, blocks: Integer;
begin
  h := UInt32(Seed);
  n := Length(S);
  blocks := n div 4;
  for i := 0 to blocks - 1 do
  begin
    k := LoadLE32(Pointer(Integer(Pointer(S)) + i * 4));
    k := k * $cc9e2d51;
    k := RotateLeft(k, 15);
    k := k * $1b873593;
    h := h xor k;
    h := RotateLeft(h, 13);
    h := h * 5 + $e6546b64;
  end;
  k := 0;
  if (n and 3) >= 3 then
    k := k xor UInt32(Ord(S[blocks * 4 + 3]) shl 16);
  if (n and 3) >= 2 then
    k := k xor UInt32(Ord(S[blocks * 4 + 2]) shl 8);
  if (n and 3) >= 1 then
  begin
    k := k xor UInt32(Ord(S[blocks * 4 + 1]));
    k := k * $cc9e2d51;
    k := RotateLeft(k, 15);
    k := k * $1b873593;
    h := h xor k;
  end;
  h := h xor UInt32(n);
  h := h xor (h shr 16);
  h := h * $85ebca6b;
  h := h xor (h shr 13);
  h := h * $c2b2ae35;
  h := h xor (h shr 16);
  Result := h;
end;

{ ---- SipHash-2-4 (Aumasson and Bernstein), a 128-bit key in two
  words, 64 bits out, each round written out ---- }

function PasSipHash(const S: string; K0, K1: Integer): Integer;
var
  v0, v1, v2, v3, m, b: Integer;
  i, n, blocks, j: Integer;
begin
  v0 := K0 xor $736f6d6570736575;
  v1 := K1 xor $646f72616e646f6d;
  v2 := K0 xor $6c7967656e657261;
  v3 := K1 xor $7465646279746573;
  n := Length(S);
  blocks := n div 8;
  for i := 0 to blocks - 1 do
  begin
    m := LoadLE64(Pointer(Integer(Pointer(S)) + i * 8));
    v3 := v3 xor m;
{SIP}
{SIP}
    v0 := v0 xor m;
  end;
  b := n shl 56;
  for j := 0 to (n and 7) - 1 do
    b := b or (Ord(S[blocks * 8 + 1 + j]) shl (8 * j));
  v3 := v3 xor b;
{SIP}
{SIP}
  v0 := v0 xor b;
  v2 := v2 xor $ff;
{SIP}
{SIP}
{SIP}
{SIP}
  Result := v0 xor v1 xor v2 xor v3;
end;
'''


def main():
    sha256_x86 = asm_block(sha256())
    sha1_x86 = asm_block(sha1())
    sha1_arm = asm_block(asm_from_go.body(asm_from_go.GO / 'sha1' / 'sha1block_arm64.s'), True)
    sha256_arm = asm_block(asm_from_go.body(asm_from_go.GO / 'sha256' / 'sha256block_arm64.s'), True)
    sha512_arm = asm_block(asm_from_go.sha512(), True)
    out = [HEAD]
    out.append(consts('K256', 'UInt32', K256, hex32, 8))
    out.append('  { FIPS 180-4, 4.2.3: the same of the first 80 primes, 64 bits, for the\n    SHA-512 kernel }')
    out.append(consts('K512', 'Integer', K512, hex64, 4))
    out.append('  { FIPS 202, 3.2.5: the round constants of Keccak-f[1600] }')
    out.append(consts('KeccakRC', 'Integer', KRC, hex64, 4))
    out.append(MID1)
    out.append(TAIL_HELPERS)
    out.append('\n{ ---- SHA-256 and SHA-224 (FIPS 180-4, 6.2 and 6.3): the rounds written\n  out, the message schedule in a ring of sixteen words ---- }\n')
    out.append(sha256_plain())
    out.append('''
{ The SHA-NI rounds after Go's sha256block_amd64.s (Intel SHA
  extensions: SHA256RNDS2, SHA256MSG1, SHA256MSG2, SDM vol. 2B), on the
  state as (A B E F) and (C D G H); the arm64 rounds after Go's
  sha256block_arm64.s (SHA256H, SHA256H2, SHA256SU0, SHA256SU1, Arm ARM
  C7.2.289-292). }
procedure Sha256BlocksCpu(State, Data: Pointer; N: Integer);
var
  k: Pointer;
  bytes: Integer;
begin
  k := @K256[0];
  bytes := N * 64;
  asm amd64 (State: in rdi; Data: in rsi; N: in rdx; k: in rax)
''' + sha256_x86 + '''
  end;
  asm arm64 (State: in x0; Data: in x1; k: in x2; bytes: in x3)
''' + sha256_arm + '''
  end;
end;

{ ---- SHA-1 (FIPS 180-4, 6.1) ---- }
''')
    out.append(sha1_plain())
    out.append('''
{ SHA-NI: SHA1RNDS4, SHA1NEXTE, SHA1MSG1, SHA1MSG2 (SDM vol. 2B), four
  rounds a step with the state as (A B C D) high to low and E in the
  top dword, the message schedule a group of four words ahead; arm64
  after Go's sha1block_arm64.s (SHA1C, SHA1P, SHA1M, SHA1H, SHA1SU0,
  SHA1SU1, Arm ARM C7.2.283-288). }
procedure Sha1BlocksCpu(State, Data: Pointer; N: Integer);
var
  k: Pointer;
  bytes: Integer;
begin
  k := @K1[0];
  bytes := N * 64;
  asm amd64 (State: in rdi; Data: in rsi; N: in rdx)
''' + sha1_x86 + '''
  end;
  asm arm64 (State: in x0; Data: in x1; k: in x2; bytes: in x3)
''' + sha1_arm + '''
  end;
end;

{ ---- SHA-512 and SHA-384 (FIPS 180-4, 6.4 and 6.5) ---- }
''')
    out.append(sha512_plain())
    out.append('''
{ arm64 after Go's sha512block_arm64.s: SHA512H, SHA512H2, SHA512SU0,
  SHA512SU1 (Arm ARM C7.2.293-296), the state in v8-v11, the message
  in v12-v19, the constants streamed through v20-v31. On amd64 the
  SHA512 extension has no processor here to answer for it: the Pascal
  rounds serve both bodies. }
procedure Sha512BlocksCpu(State, Data: Pointer; N: Integer);
{$ifdef CPUAARCH64}
var
  k: Pointer;
  bytes: Integer;
begin
  k := @K512[0];
  bytes := N * 128;
  asm arm64 (State: in x0; Data: in x1; bytes: in x2; k: in x3)
''' + sha512_arm + '''
  end;
end;
{$else}
begin
  Sha512BlocksPlain(State, Data, N);
end;
{$endif}
''')
    rest = REST.replace('{MD5}', md5_blocks()).replace('{KECCAK}', keccak())
    rest = rest.replace('{X86_CRC32C}', X86_CRC32C).replace('{ARM_CRC32C}', ARM_CRC.replace('{C}', 'c'))
    rest = rest.replace('{X86_CRC32_CLMUL}', X86_CRC32_CLMUL).replace('{ARM_CRC32}', ARM_CRC.replace('{C}', ''))
    rest = rest.replace('{SIP}', SIP)
    out.append(rest)
    out.append(variant('Cpu'))
    out.append(variant('Base'))
    out.append('\nend.\n')
    text = '\n'.join(out)
    open(os.path.join(ROOT, 'src', 'lib', 'pashash.paslang'), 'w').write(text)
    print('written', text.count('\n'), 'lines')


if __name__ == '__main__':
    main()
