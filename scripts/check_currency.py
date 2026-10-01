#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Independent rational oracle for scaled-decimal Currency kernels."""
from fractions import Fraction
import random
import struct
import subprocess
import sys


LOW, HIGH, SCALE = -(1 << 63), (1 << 63) - 1, 10000
frontend = '--frontend' in sys.argv
if frontend:
    sys.argv.remove('--frontend')
generator = random.Random(152)
cases = []


def nearest(value):
    negative = value < 0
    quotient, remainder = divmod(abs(value.numerator), value.denominator)
    if 2 * remainder > value.denominator or (2 * remainder == value.denominator and quotient & 1):
        quotient += 1
    return -quotient if negative else quotient


def signed(word):
    return word if word < 1 << 63 else word - (1 << 64)


def fixed(value, places):
    rounded = nearest(Fraction(value * 10**places, SCALE))
    digits = str(abs(rounded)).zfill(places + 1)
    answer = digits if not places else digits[:-places] + '.' + digits[-places:]
    return ('-' if rounded < 0 else '') + answer


def shortest(value):
    text = fixed(value, 4).rstrip('0').rstrip('.') if value % SCALE else str(value // SCALE)
    return text


def digits(value, significant=0):
    if not value:
        return '[] 0'
    text = str(abs(value))
    point = len(text) - 4
    if significant:
        shift = significant - point - 4
        rounded = nearest(Fraction(abs(value) * 10**max(shift, 0), 10**max(-shift, 0)))
        if not rounded:
            return '[] 0'
        text = str(rounded)
        point = len(text) - 4 - shift
    return f'[{text.rstrip("0")}] {point}'


def add(operation, a, b=0, places=4):
    cases.append((operation, str(a), b, places))


boundaries = [LOW, LOW + 1, HIGH, HIGH - 1, -10001, -10000, -9999, -5001,
              -5000, -4999, -2, -1, 0, 1, 2, 4999, 5000, 5001, 9999, 10000, 10001]
for a in boundaries:
    for places in (0, 1, 2, 3, 4, 7, 24):
        add('scaled', a, places=places)
    add('neg', a)
    add('abs', a)
    add('int', a)
    for b in boundaries:
        for operation in ('add', 'sub', 'mul', 'div'):
            add(operation, a, b, generator.randrange(9))
for _ in range(2000):
    a, b = generator.randrange(LOW, HIGH + 1), generator.randrange(LOW, HIGH + 1)
    add(generator.choice(('add', 'sub', 'mul', 'div')), a, b, generator.randrange(9))
    add('scaled', a, places=generator.randrange(12))
    add('real', signed(generator.getrandbits(64)), places=generator.randrange(9))
    add('quad', signed(generator.getrandbits(64)), signed(generator.getrandbits(64)))
for a in (-922337203685478, -922337203685477, 922337203685477, 922337203685478):
    add('int', a)
for text in ('', 'nan', 'inf', '.', '-', ' 1', '1 ', '1e', '1e+', '1.2.3', '1\0',
             '0', '-0', '0.00005', '0.00015', '-0.00025', '0.00005000000000000001',
             '0.00004999999999999999', '922337203685477.5807', '-922337203685477.5808',
             '922337203685477.58075', '-922337203685477.58085', '1e100000', '1e-100000',
             '0e100000', '2.675', '999999.99995'):
    add('parse', text)
for _ in range(1000):
    text = str(generator.randrange(LOW, HIGH + 1)) + 'e' + str(generator.randrange(-30, 5))
    add('parse', text, places=generator.randrange(9))


def expected(case):
    operation, text, b, places = case
    if operation == 'parse':
        if frontend:
            text = text.strip()  # SysUtils accepts surrounding ASCII whitespace.
        try:
            value = nearest(Fraction(text) * SCALE)
        except (ValueError, ZeroDivisionError):
            return 'parse error 0\n'
        # Fraction allows whitespace, which our explicit grammar rejects.
        if text != text.strip() or not LOW <= value <= HIGH:
            return 'parse error 0\n'
    else:
        a = int(text)
        if operation == 'scaled': value = a
        elif operation == 'add': value = a + b
        elif operation == 'sub': value = a - b
        elif operation == 'mul': value = nearest(Fraction(a * b, SCALE))
        elif operation == 'div':
            if not b: return 'fault 1\n'
            value = nearest(Fraction(a * SCALE, b))
        elif operation == 'neg': value = -a
        elif operation == 'abs': value = abs(a)
        elif operation == 'int': value = a * SCALE
        elif operation == 'real':
            floating = struct.unpack('<d', struct.pack('<q', a))[0]
            try: value = nearest(Fraction(floating) * SCALE)
            except (ValueError, OverflowError): return 'fault 2\n'
        elif operation == 'quad':
            bits = ((b & ((1 << 64) - 1)) << 64) | (a & ((1 << 64) - 1))
            exponent = (bits >> 112) & 32767
            if exponent == 32767: return 'fault 2\n'
            mantissa = bits & ((1 << 112) - 1)
            power = -16494 if exponent == 0 else exponent - 16495
            if exponent: mantissa |= 1 << 112
            if bits >> 127: mantissa = -mantissa
            value = nearest(Fraction(mantissa * SCALE * 2**max(power, 0), 2**max(-power, 0)))
        else: raise AssertionError(operation)
        if not LOW <= value <= HIGH: return 'fault 0\n'
    bits = struct.unpack('<q', struct.pack('<d', float(shortest(value))))[0]
    quotient = abs(value) // SCALE * (-1 if value < 0 else 1)
    floor = value // SCALE
    ceil = -((-value) // SCALE)
    return (f'{value} {shortest(value)} {fixed(value, places)} {bits} '
            f'{quotient} {nearest(Fraction(value, SCALE))} {floor} {ceil}\n'
            f'{digits(value)} {digits(value, 7)}\n')


protocol = str(len(cases)) + '\n' + ''.join(f'{op}\n{a}\n{b}\n{places}\n' for op, a, b, places in cases)
answers = [expected(case) for case in cases]
result = subprocess.run(sys.argv[1:], input=protocol.encode(), stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE, timeout=180)
reference = ''.join(answers).encode()
if result.returncode or result.stdout != reference:
    actual = result.stdout.decode(errors='replace').splitlines()
    expected_lines = reference.decode().splitlines()
    for index, (left, right) in enumerate(zip(actual, expected_lines)):
        if left != right:
            print(f'line {index}: actual {left!r}, exact {right!r}', file=sys.stderr)
            break
    raise SystemExit(f'Currency oracle failed (exit {result.returncode}, {len(actual)}/{len(expected_lines)} lines): '
                     + result.stderr.decode(errors='replace'))
print(f'ok exact Currency {"language/SysUtils" if frontend else "kernels"} '
      f'({len(cases)} decimal/rational/IEEE cases)')
