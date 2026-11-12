#!/usr/bin/env python3
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Compiled-symbol selectors for assembly checks (PASLANGI35).

These are build tools. Programs do not carry a decoder or a name registry.
The compiler's constructors live in pasast; this reader checks the emitted
component boundaries rather than assuming that an underscore is a scope.
"""
import re


def component(value):
    value = value.encode('ascii').lower().decode('ascii')
    return str(len(value)) + '_' + value


def procedure_symbol(unit, name):
    return 'p_f.' + component(unit) + component(name)


def decode(symbol):
    """Return kind, complete framed components and the synthetic suffix."""
    match = re.match(r'([pt])_([fmnaou])\.', symbol)
    if not match:
        raise ValueError('unknown symbol namespace: ' + symbol)
    kind = match[0][:-1]
    if kind not in ('p_f', 'p_m', 'p_n', 'p_a', 'p_o', 't_u', 't_n'):
        raise ValueError('unknown symbol kind: ' + symbol)
    count = 5 if kind == 'p_o' else 2
    at = match.end()
    parts = []
    for _ in range(count):
        length = re.match(r'(0|[1-9][0-9]*)_', symbol[at:])
        if not length:
            raise ValueError('missing component length: ' + symbol)
        at += length.end()
        end = at + int(length[1])
        if end > len(symbol):
            raise ValueError('truncated component: ' + symbol)
        parts.append(symbol[at:end])
        at = end
    return kind, tuple(parts), symbol[at:]


def program_name(symbol):
    """A plain program routine's source name, or empty for other scopes."""
    if not symbol.startswith('p_f.'):
        return ''
    kind, parts, tail = decode(symbol)
    return parts[1] if kind == 'p_f' and parts[0] == '' and tail == '' else ''
