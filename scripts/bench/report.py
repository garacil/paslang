#!/usr/bin/env python3
# This file is part of paslang.
# Copyright (C) 2026 Germán Luis Aracil Boned <garacilb@gmail.com>
# GPL version 3 or later; see COPYING. No warranty.
"""Render legacy Go and selected Go/Rust benchmark records as Markdown.

report.py [record.json] [--rounds file] [--build file] [--servers file]
Each selected reference retains its own paslang measurement. Complete round
and memory diagnostics are exported as escaped, lossless JSON in HTML pre
blocks; surrogateescape bytes stay representable even on strict UTF-8 output.
"""
import argparse
import html
import json
import math
import statistics
import sys


REF_FORMATS = {'p525-draft-v1', 'paslang-bench-refs-v1'}
BUILD_FORMAT = 'paslang-compiler-build-refs-v1'


def safe(value):
    """Text for Markdown tables/HTML, without raw controls or surrogates."""
    text = str(value).encode('utf-8', 'backslashreplace').decode('utf-8')
    text = ''.join(char if ord(char) >= 32 or char in '\n\t' else '\\x%02x' % ord(char) for char in text)
    return html.escape(text, quote=True).replace('|', '&#124;').replace('\n', '<br>').replace('\r', '\\r')


def table(w, headings, rows):
    w('| ' + ' | '.join(safe(item) for item in headings) + ' |')
    w('|' + '|'.join('---' for _ in headings) + '|')
    for row in rows:
        w('| ' + ' | '.join(safe(item) for item in row) + ' |')
    w('')



def json_value(value):
    # Legacy Go records used Infinity for timeouts. Keep the distinction as
    # an explicit tag while emitting strict JSON rather than a non-JSON token.
    if isinstance(value, float) and not math.isfinite(value):
        return {'legacy_nonfinite_float': repr(value)}
    if isinstance(value, dict):
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def detail(w, title, data):
    # ensure_ascii retains a literal invalid UTF-8 byte decoded as \udcXX;
    # JSON also distinguishes it from an actual backslash-u string. No data
    # can terminate the HTML element or create a Markdown table/code fence.
    value = json.dumps(json_value(data), ensure_ascii=True, indent=2, allow_nan=False)
    w('<details><summary>' + safe(title) + '</summary>')
    w('<pre>' + html.escape(value, quote=True) + '</pre>')
    w('</details>')
    w('')


def read(path):
    with open(path, encoding='utf-8', errors='surrogateescape') as source:
        return json.load(source)


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def middle(value):
    if isinstance(value, list):
        return statistics.median(value) if value and all(finite(item) for item in value) else None
    return value if finite(value) else None


def num(value, places=3):
    if value is None:
        return '-'
    if isinstance(value, (int, float)) and not math.isfinite(value):
        return 'did not end'
    return f'{value:.{places}f}' if finite(value) else str(value)


def ref_name(value):
    return {'go': 'Go', 'rust': 'Rust'}.get(value, str(value))


def reference_label(row, record):
    label = ref_name(row.get('reference', 'go'))
    if row.get('reference') == 'rust':
        configuration = record.get('rust_configuration', {})
        target = row.get('reference_target', configuration.get('target'))
        provider = row.get('reference_provider', configuration.get('provider'))
        if target or provider:
            label += ' (' + ' / '.join(str(value) for value in (target, provider) if value) + ')'
    return label


def refs_record(record):
    return record.get('format') in REF_FORMATS or any('reference' in row for row in record.get('pairs', []) if isinstance(row, dict))


def version(value):
    if isinstance(value, dict):
        return value.get('stdout') or value.get('stderr') or '?'
    if isinstance(value, list):
        return ' '.join(map(str, value))
    return value or '?'


def machine(w, record, path):
    metadata = record.get('machine', {})
    cpu = metadata.get('cpu', {})
    tools = metadata.get('toolchain', {})
    refs = record.get('references', ['go'])
    date = str(metadata.get('date', record.get('date', 'date not recorded')))[:10]
    w('# Benchmark against ' + safe(' and '.join(ref_name(item) for item in refs)) + ', ' + safe(date))
    w('')
    w('Record: ' + safe(path) + '. Measurements and failures below come from that record.')
    w('Go and Rust comparisons are separate evidence; an unmeasured reference has no result.')
    w('')
    w('## The machine')
    w('')
    rows = [('Processor', cpu.get('model', '?')), ('Logical CPUs', cpu.get('logical_cpus', '?')),
            ('Caches', 'L1d %s, L2 %s, L3 %s' % (cpu.get('l1d', '?'), cpu.get('l2', '?'), cpu.get('l3', '?'))),
            ('Clock/governor/boost', '%s MHz / %s / %s' % (cpu.get('max_mhz', '?'), cpu.get('governor', '?'), cpu.get('boost', '?'))),
            ('Native extensions', ', '.join(cpu.get('features_used', []))),
            ('Memory', metadata.get('memory', {})), ('System', metadata.get('os', '?')),
            ('Kernel/host', '%s / %s' % (metadata.get('kernel', '?'), metadata.get('hostname', '?'))),
            ('Load before/after', '%s / %s' % (metadata.get('load_before', '?'), metadata.get('load_after', '?')))]
    table(w, ['', 'Recorded value'], rows)
    w('## The toolchain')
    w('')
    table(w, ['', 'Recorded version'], [
        ('paslangc', version(record.get('paslangc', tools.get('paslangc')))),
        ('Go', version(record.get('go_version', tools.get('go')))),
        ('Rust', version(record.get('rustc', tools.get('rustc')))),
        ('Assembler', version(tools.get('as'))), ('Linker', version(tools.get('ld')))])
    keys = ('paslangc', 'go_version', 'go_environment', 'go_levels', 'rustc', 'rust_sysroot',
            'rust_cfg', 'rust_configuration', 'rust_artifacts', 'rust_capability_proof',
            'go_policy', 'go_capabilities', 'go_artifacts', 'go_artifact_evidence', 'libc', 'source_sha256', 'build_observations', 'capability_review', 'contracts')
    evidence = {key: record[key] for key in keys if key in record}
    if evidence:
        detail(w, 'Complete tool, source, flags, linkage and contract evidence', evidence)


def method(w, record):
    w('## The method')
    w('')
    if refs_record(record):
        w(safe(record.get('method', record.get('draft_method', 'Separate alternating series for each selected reference.'))))
        w('Each row compares one reference with its own paslang series. Paslang measurements from different reference series are kept distinct; no cross-reference average is created.')
        w('Requested rounds: ' + safe(record.get('requested_rounds', '?')) + '; memory samples: ' + safe(record.get('memory_runs', '?')) + '.')
        w('Time ratios are paslang/reference. Peak memory is derived only from successful recorded VmHWM samples. Missing measurements are shown as “-”.')
    else:
        w('Legacy Go record: the paired programs perform the same requested workload, alternating which runs first. The recorded ratio is paslang/Go.')
        w('Requested rounds: ' + safe(record.get('runs_per_program', '?')) + '; processors: ' + safe(', '.join(record.get('cpus', []))) + '.')
        w('Legacy records used the same Go executable with runtime feature controls for base. This report does not reinterpret that policy as a matched Go compilation level or a Rust measurement.')
    w('Every recorded output/status failure remains a failure even if later rounds agree. Full diagnostic strings below are JSON escaped without truncation; embedded newlines and invalid UTF-8 bytes remain distinguishable.')
    w('')


def stderr_empty(sample):
    """Missing historical fields carry no diagnostic; present fields must be empty."""
    return sample.get('stderr', '') == ''


def timed_diagnostics_empty(pair):
    samples = pair.get('rounds')
    if not isinstance(samples, list):
        return True  # Completeness/schema checks decide whether rounds are required.
    return all(isinstance(row, dict) and all(
        not isinstance(row.get(side), dict) or stderr_empty(row[side])
        for side in ('a', 'b', 'go', 'paslang')) for row in samples)


def memory_mib(samples, requested=None):
    if requested is not None and (not isinstance(requested, int) or isinstance(requested, bool) or requested < 1 or not isinstance(samples, list) or len(samples) != requested):
        return None
    if not isinstance(samples, list) or not samples or not all(isinstance(row, dict) and row.get('ok') and row.get('status') == 0 and stderr_empty(row) and finite(row.get('peak_kib')) and row['peak_kib'] > 0 for row in samples):
        return None
    return statistics.median(row['peak_kib'] / 1024 for row in samples)


def complete(row, record, strict=False):
    if row.get('complete') is False or row.get('completed') is False:
        return False
    requested = row.get('requested_rounds', record.get('requested_rounds', record.get('runs_per_program', record.get('rounds'))))
    samples = row.get('rounds')
    completed = row.get('completed_rounds', len(samples) if isinstance(samples, list) else None)
    if requested is None:
        return not strict and 'requested_rounds' not in row and 'completed_rounds' not in row
    if not isinstance(requested, int) or isinstance(requested, bool) or requested < 1:
        return False
    if completed is None and 'completed_rounds' not in row:
        sizes = [len(row[side]['walls_s']) for side in ('go', 'paslang') if isinstance(row.get(side), dict) and isinstance(row[side].get('walls_s'), list)]
        if not sizes:
            sizes = [len(row[key]) for key in ('paslang_s', 'go_s', 'reference_s') if isinstance(row.get(key), list)]
        completed = requested if not strict and not sizes else min(sizes) if sizes and len(set(sizes)) == 1 else None
    if completed != requested or isinstance(completed, bool):
        return False
    if isinstance(samples, list) and (len(samples) != requested or any(not isinstance(sample, dict) or sample.get('complete') is False or sample.get('completed') is False for sample in samples)):
        return False
    return True


def limits(row, record, ratio, budget, memory=None, memory_budget=None, *, check_memory=True, q3=False):
    if row.get('over') or ('ok' in row and row['ok'] is not True):
        return False
    if not finite(ratio) or ratio < 0 or not finite(budget) or budget <= 0 or ratio > budget:
        return False
    if check_memory and (not finite(memory) or memory <= 0 or not finite(memory_budget) or memory_budget <= 0 or memory > memory_budget):
        return False
    if 'reference' in row and (budget >= 1 or check_memory and memory_budget >= 1):
        return False
    needs_q3 = row.get('requires_q3_below_one', record.get('requires_q3_below_one', q3))
    if needs_q3 and (not finite(row.get('q3')) or not 0 <= row['q3'] < 1):
        return False
    return True


def pair_values(pair, record=None):
    record = record or {}
    if 'reference' in pair:
        reference = pair['reference']
        requested = pair.get('requested_memory_runs', pair.get('memory_runs', record.get('memory_runs')))
        if requested is None:
            requested = 0  # A selected-reference record must state its requested sample count.
        return (reference, middle(pair.get('reference_s')), middle(pair.get('paslang_s')),
                memory_mib(pair.get('reference_memory'), requested), memory_mib(pair.get('paslang_memory'), requested),
                pair.get('ratio_time'), pair.get('ratio_memory'), pair.get('time_budget'), pair.get('memory_budget'))
    go = pair.get('go') if isinstance(pair.get('go'), dict) else {}
    pl = pair.get('paslang') if isinstance(pair.get('paslang'), dict) else {}
    return ('go', go.get('median_s'), pl.get('median_s'), go.get('peak_rss_mb'), pl.get('peak_rss_mb'),
            pair.get('ratio_time'), pair.get('ratio_mem'), pair.get('budget'), pair.get('memory_budget', record.get('memory_budget', record.get('mem_budget', 0.99))))



def same_output(pair):
    if not pair.get('same_output') or not timed_diagnostics_empty(pair):
        return False
    if 'reference' not in pair and any(not isinstance(pair.get(side), dict) or pair[side].get('status', 0) != 0 or not stderr_empty(pair[side]) for side in ('go', 'paslang')):
        return False
    rounds = pair.get('rounds')
    strict = 'reference' in pair
    if strict and (not isinstance(rounds, list) or not rounds):
        return False
    first = {}
    if isinstance(rounds, list):
        for row in rounds:
            if not isinstance(row, dict) or row.get('errors'):
                return False
            for side in ('a', 'b'):
                sample = row.get(side)
                if not isinstance(sample, dict):
                    if strict:
                        return False
                    continue
                if strict and 'stdout' not in sample:
                    return False
                if sample.get('status') != 0:
                    return False
                if 'stdout' in sample:
                    if side in first and sample['stdout'] != first[side]:
                        return False
                    first.setdefault(side, sample['stdout'])
            if isinstance(row.get('a'), dict) and isinstance(row.get('b'), dict) and row['a'].get('stdout') != row['b'].get('stdout'):
                return False
    memory_outputs = {}
    for field, side in (('reference_memory', 'a'), ('paslang_memory', 'b')):
        samples = pair.get(field, [])
        if not isinstance(samples, list):
            return False
        for sample in samples:
            if not isinstance(sample, dict) or not sample.get('ok') or sample.get('status') != 0 or not stderr_empty(sample):
                return False
            if side in first and sample.get('stdout') != first[side]:
                return False
            if 'stdout' in sample:
                if side in memory_outputs and sample['stdout'] != memory_outputs[side]:
                    return False
                memory_outputs.setdefault(side, sample['stdout'])
    if 'a' in memory_outputs and 'b' in memory_outputs and memory_outputs['a'] != memory_outputs['b']:
        return False
    return True


def results(w, record, title='Results'):
    w('## ' + title)
    w('')
    rows, verdicts = [], []
    pairs = record.get('pairs', [])
    for pair in pairs:
        reference, rt, pt, rm, pm, ratio, memory, budget, mbudget = pair_values(pair, record)
        same = same_output(pair)
        measured = all(finite(value) for value in (rt, pt, rm, pm, ratio, memory, budget))
        verdict = same and measured and complete(pair, record, strict='reference' in pair) and limits(pair, record, ratio, budget, memory, mbudget)
        verdicts.append(verdict)
        rows.append((pair.get('pair', '?'), pair.get('cpu', '?'), reference_label(pair, record),
                     num(rt) if reference == 'go' else '-', num(rt) if reference == 'rust' else '-', num(pt),
                     num(ratio), num(budget, 2), num(rm, 1) if reference == 'go' else '-',
                     num(rm, 1) if reference == 'rust' else '-', num(pm, 1), num(memory), num(mbudget, 2),
                     'yes' if same else 'NO', 'PASS' if verdict else 'FAIL'))
    table(w, ['Pair', 'cpu', 'Reference', 'Go s', 'Rust s', 'paslang s (this series)', 'Time ratio', 'Time budget',
              'Go MiB', 'Rust MiB', 'paslang MiB (this series)', 'Memory ratio', 'Memory budget', 'Same output', 'Verdict'], rows)
    for pair in pairs:
        label = '%s / %s / %s' % (pair.get('pair', '?'), pair.get('cpu', '?'), reference_label(pair, record))
        # All complete outputs are retained, including early/middle round failures,
        # memory exits and successful later rounds. Nothing is first-line-only.
        detail(w, label + ': every round, output, status and memory sample', pair)
    if record.get('checkptr'):
        detail(w, 'Separate checkptr overhead measurement', record['checkptr'])
    if 'error' in record:
        detail(w, 'Record-level error (possibly incomplete measurements)', record['error'])
    if 'ok' in record:
        counts = record.get('requested_comparisons', len(pairs)) == record.get('completed_comparisons', len(pairs)) == len(pairs)
        w('Aggregate verdict: ' + ('PASS' if record['ok'] and verdicts and all(verdicts) and counts else 'FAIL') + '.')
        w('')


def rounds(w, path):
    record = read(path)
    if refs_record(record):
        results(w, record, 'Alternating rounds by reference')
        return
    w('## Alternating rounds')
    w('')
    w('Record: ' + safe(path) + '. ' + safe(record.get('method', '')))
    rows = []
    for name, row in record.get('pairs', {}).items():
        pair, _, cpu = name.partition('.')
        rows.append((pair, cpu or 'native', num(row.get('ratio_median')), num(row.get('q1')) + ' to ' + num(row.get('q3')),
                     num(row.get('paslang_s'), 4), num(row.get('go_s'), 4), num(row.get('budget'), 2),
                     'yes' if row.get('same_output') and timed_diagnostics_empty(row) else 'NO', row.get('over') or ('FAIL' if not (all(finite(row.get(key)) for key in ('ratio_median', 'q1', 'q3', 'paslang_s', 'go_s')) and row.get('same_output') and timed_diagnostics_empty(row) and complete(row, record) and limits(row, record, row.get('ratio_median'), row.get('budget'), check_memory=False, q3=True)) else '-')))
    table(w, ['Pair', 'cpu', 'Median ratio', 'Middle half', 'paslang s', 'Go s', 'Budget', 'Same output', 'Failure'], rows)
    detail(w, 'Complete alternating-round evidence', record)



def compiler_expected_total(functions):
    """Recompute the compiler probe's arithmetic independently of saved flags."""
    if not isinstance(functions, int) or isinstance(functions, bool) or functions < 1:
        return None
    total = 0
    for index in range(functions):
        value = index + 1
        for step in range(1, 11):
            value = ((value * 3 + step) ^ (value >> 2)) & 0xffffffff
        if value % 7 == 0:
            value += len(str(value))
        total += value + index
    return total


def close_number(actual, expected):
    return finite(actual) and finite(expected) and math.isclose(actual, expected, rel_tol=1e-12, abs_tol=1e-15)


def build_observation_valid(observation, expected):
    if not isinstance(observation, dict) or observation.get('ok') is not True or observation.get('phase') != 'complete':
        return False
    built, execution = observation.get('build'), observation.get('execution')
    size = observation.get('executable_bytes')
    return (isinstance(built, dict) and built.get('status') == 0 and stderr_empty(built)
            and finite(built.get('wall_s')) and built['wall_s'] > 0
            and isinstance(size, int) and not isinstance(size, bool) and size > 0
            and isinstance(execution, dict) and execution.get('status') == 0
            and execution.get('stdout') == expected and stderr_empty(execution))


def build_round_evidence(row, record):
    """An aggregate ok/same_output flag cannot conceal a failed nonce round."""
    total = compiler_expected_total(record.get('functions'))
    samples = row.get('rounds')
    if total is None or not isinstance(samples, list) or not samples:
        return False
    pl, ref, pl_bytes, ref_bytes = [], [], [], []
    for index, sample in enumerate(samples, 1):
        if not isinstance(sample, dict) or sample.get('complete') is not True or sample.get('round') != index:
            return False
        nonce = sample.get('nonce')
        if not isinstance(nonce, int) or isinstance(nonce, bool) or nonce < 0 or nonce + total >= (1 << 63):
            return False
        expected = str(nonce + total) + '\n'
        if sample.get('expected_stdout') != expected:
            return False
        if not all(build_observation_valid(sample.get(side), expected) for side in ('paslang', 'reference')):
            return False
        pl.append(sample['paslang']['build']['wall_s'])
        ref.append(sample['reference']['build']['wall_s'])
        pl_bytes.append(sample['paslang']['executable_bytes'])
        ref_bytes.append(sample['reference']['executable_bytes'])
    if row.get('paslang_s') != pl or row.get('reference_s') != ref:
        return False
    if row.get('paslang_bytes') != pl_bytes or row.get('reference_bytes') != ref_bytes:
        return False
    ratios = [left / right for left, right in zip(pl, ref)]
    saved = row.get('ratios')
    if not isinstance(saved, list) or len(saved) != len(ratios) or not all(close_number(a, b) for a, b in zip(saved, ratios)):
        return False
    quartiles = statistics.quantiles(ratios, n=4) if len(ratios) > 1 else [ratios[0]] * 3
    return (close_number(row.get('ratio_median'), statistics.median(ratios))
            and close_number(row.get('q1'), quartiles[0]) and close_number(row.get('q3'), quartiles[2]))


def build_warmup_evidence(record):
    total = compiler_expected_total(record.get('functions'))
    warmups = record.get('warmups')
    if total is None or not isinstance(warmups, list) or not warmups:
        return False
    expected = str(total) + '\n'
    for row in warmups:
        if not isinstance(row, dict) or row.get('nonce') != 0 or row.get('expected_stdout') != expected or not build_observation_valid(row, expected):
            return False
    return True


def build(w, path):
    record = read(path)
    w('## Compiler build time and executable size')
    w('')
    w('Record: ' + safe(path) + '; generated functions: ' + safe(record.get('functions', '?')) + '.')
    verdicts = []
    if record.get('format') == BUILD_FORMAT:
        w('Each reference has a separate paslang build series. Times include compiler/linker work; each generated nonce is checked in that round. File sizes retain each toolchain’s default linkage and metadata; they are not stripped-code-size parity measurements.')
        w('')
        rows = []
        for row in record.get('pairs', []):
            reference = row.get('reference')
            rt, pt = middle(row.get('reference_s')), middle(row.get('paslang_s'))
            rb, pb = middle(row.get('reference_bytes')), middle(row.get('paslang_bytes'))
            measured = all(finite(value) for value in (rt, pt, rb, pb, row.get('ratio_median'), row.get('q1'), row.get('q3')))
            completed = complete(row, record, strict=True)
            valid = bool(row.get('same_output')) and measured and completed and limits(row, record, row.get('ratio_median'), row.get('budget'), check_memory=False, q3=True) and build_round_evidence(row, record)
            verdicts.append(valid)
            rows.append((row.get('cpu'), reference_label(row, record), row.get('completed_rounds', 0),
                         num(rt) if reference == 'go' else '-', num(rt) if reference == 'rust' else '-', num(pt),
                         num(row.get('ratio_median')), num(row.get('q1')) + ' to ' + num(row.get('q3')), num(row.get('budget'), 2),
                         num(rb, 0), num(pb, 0), 'yes' if row.get('same_output') else 'NO', 'PASS' if valid else 'FAIL'))
        table(w, ['cpu', 'Reference', 'Rounds', 'Go build s', 'rustc s', 'paslangc s (this series)',
                  'Median ratio', 'Middle half', 'Budget', 'Reference bytes', 'paslang bytes (this series)', 'Every output', 'Verdict'], rows)
    else:
        pt, gt = middle(record.get('paslang_s')), middle(record.get('go_s'))
        measured = all(finite(value) for value in (pt, gt, record.get('ratio_median'), record.get('q1'), record.get('q3')))
        valid = measured and bool(record.get('same_output')) and complete(record, record) and limits(record, record, record.get('ratio_median'), record.get('budget'), check_memory=False, q3=True)
        failure = record.get('over') or ('FAIL' if not valid else '-')
        verdicts.append(valid)
        table(w, ['Rounds', 'paslangc s', 'go build s', 'Median ratio', 'Middle half', 'Budget', 'Same output', 'Failure'], [
            (record.get('rounds'), num(pt), num(gt), num(record.get('ratio_median')),
             num(record.get('q1')) + ' to ' + num(record.get('q3')), num(record.get('budget'), 2),
             'yes' if record.get('same_output') else 'NO', failure)])
    valid = bool(record.get('ok', True)) and bool(verdicts) and all(verdicts) and not record.get('error')
    if record.get('format') == BUILD_FORMAT:
        valid = (valid and record.get('phase') == 'complete' and build_warmup_evidence(record)
                 and record.get('requested_comparisons') == record.get('completed_comparisons') == len(record.get('pairs', [])))
    w('Aggregate build-probe verdict: ' + ('PASS' if valid else 'FAIL') + '.')
    w('')
    detail(w, 'Complete build commands, flags, cache policy, sizes, linkage, nonces and execution evidence', record)


def servers(w, path):
    record = read(path)
    w('## The servers')
    w('')
    w('Record: ' + safe(path) + '; rounds: ' + safe(record.get('runs', '?')) + '.')
    rows = []
    for row in record.get('pairs', []):
        rows.append((row.get('pair'), row.get('cpu'), row.get('n'), num(middle(row.get('go_s'))), num(middle(row.get('paslang_s'))),
                     num(row.get('ratio')), num(row.get('budget'), 2), num(middle(row.get('go_mb')), 1),
                     num(middle(row.get('paslang_mb')), 1), num(row.get('ratio_mem')), 'yes' if row.get('same_output') else 'NO'))
    table(w, ['Pair', 'cpu', 'n', 'Go s', 'paslang s', 'Time ratio', 'Budget', 'Go MiB', 'paslang MiB', 'Memory ratio', 'Same output'], rows)
    detail(w, 'Complete server evidence', record)


def main(arguments):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('record', nargs='?', default='build/bench/last.json')
    for option in ('--rounds', '--build', '--servers'):
        parser.add_argument(option)
    options = parser.parse_args(arguments)
    record = read(options.record)
    output = []
    w = output.append
    if record.get('format') == BUILD_FORMAT:
        w('# Compiler build probe')
        w('')
        build(w, options.record)
    else:
        machine(w, record, options.record)
        method(w, record)
        results(w, record)
    for key, render in (('rounds', rounds), ('build', build), ('servers', servers)):
        if getattr(options, key):
            render(w, getattr(options, key))
    w('## What each pair does')
    w('')
    print('\n'.join(output))


if __name__ == '__main__':
    main(sys.argv[1:])
