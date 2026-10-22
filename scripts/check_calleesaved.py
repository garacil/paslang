#!/usr/bin/env python3
"""check_calleesaved.py FILE.s ...: every routine of the runtime keeps the
registers a caller's region holds its variables in across a call (P384).

paslang's routines keep rbx, r12, r13 and r15 on amd64 and x19 to x26
on arm64, the registers a region (P93) lends to variables, as the System
V psABI (3.2.1, figure 3.4) and AAPCS64 (6.1.1) have a routine keep
them: a region stores what they held in its frame and gives it back at
its end, a try gives them back where a raise lands, a park keeps them
on the routine's stack (.pk_res), an asm block pushes the ones it names.
A loop whose body calls leaves its variables in them across the call.
This reads each routine of the runtime in a program's assembly, from its
label (rt_...) to the next, and fails on one that writes such a register
and keeps no copy of it: no push of it (amd64), no store of it to the
stack (arm64: str or stp with sp or x29 as the base), no frame slot of a
region (.cfi_offset). The routines that never come back to a routine's
code, or come back only through .pk_res, are named below with why. """
import re
import sys

KEPT64 = {}
for r in ('rbx', 'r12', 'r13', 'r15'):
    for v in ((r, 'ebx', 'bx', 'bl', 'bh') if r == 'rbx' else (r, r + 'd', r + 'w', r + 'b')):
        KEPT64[v] = r
KEPTA = {f'{p}{n}': f'x{n}' for n in range(19, 27) for p in ('x', 'w')}

AWAY = {
    # a fatal stop: the message, then the process ends
    'rt_boundsfail': 'stops the program', 'rt_funnelfail': 'stops the program',
    'rt_blockfail': 'stops the program', 'rt_diechancap': 'stops the program',
    'rt_diepipe': 'dies of SIGPIPE', 'rt_diemsg': 'stops the program',
    'rt_fatalint': 'stops the program',
    # the process's start, an M's own loop and the scheduler on the M's
    # stack, sysmon's thread, a routine's end
    'rt_boot': 'the start of the process', 'rt_mnopwait': "an M's own loop, on its stack",
    'rt_mloop': "an M's own loop, on its stack",
    'rt_findrunnable': "the scheduler, called by rt_mloop and rt_idlepoll on the M's stack",
    'rt_sysmon': "sysmon's own thread", 'rt_goexit': "a routine's end",
    # the kernel gives the interrupted registers back at its sigreturn
    'rt_sighandler': 'a signal handler: sigreturn gives the registers back',
    # the routine's registers go to .pk_res before the switch to the M's
    # stack, and come back from there when it runs again
    'rt_morestack': 'keeps them in .pk_res before it leaves the stack',
    'rt_waitall': "parks through the M's stack, back through .pk_res",
    'rt_execwu': "waits on the M's stack, back through .pk_res",
    # a helper whose callers keep them: rt_acpoke and rt_acwait push all four
    'rt_acslot': 'called by rt_acpoke and rt_acwait, which push them',
}


def routines(lines):
    cur, body = None, []
    for ln in lines:
        m = re.match(r'^(rt_[A-Za-z0-9_]+):', ln)
        if m:
            if cur:
                yield cur, body
            cur, body = m.group(1), []
            continue
        if cur and re.match(r'^(p_|vmt_|\.globl p_)[A-Za-z0-9_]*', ln) and ln.endswith(':'):
            yield cur, body
            cur, body = None, []
            continue
        if cur:
            body.append(ln.strip())
    if cur:
        yield cur, body


def amd64(body):
    wrote, saved = set(), set()
    for ins in body:
        if not ins or ins.startswith('.') or ins.endswith(':'):
            m = re.match(r'\.cfi_offset %(\w+)', ins)
            if m and m.group(1) in KEPT64:
                saved.add(KEPT64[m.group(1)])
            continue
        op, _, rest = ins.partition(' ')
        regs = re.findall(r'%(\w+)', rest)
        if op.startswith('push'):
            saved.update(KEPT64[r] for r in regs if r in KEPT64)
            continue
        if op.startswith(('pop', 'cmp', 'test', 'j', 'call', 'ret')) or \
                (op.startswith('bt') and not op.startswith(('bts', 'btr', 'btc'))):
            continue
        # AT&T: the destination is the last operand
        last = rest.split(',')[-1].strip()
        if last.startswith('%') and last[1:] in KEPT64:
            wrote.add(KEPT64[last[1:]])
        if op.startswith(('xchg', 'xadd', 'cmpxchg')):
            wrote.update(KEPT64[r] for r in regs if r in KEPT64)
    return sorted(wrote - saved)


def arm64(body):
    wrote, saved = set(), set()
    for ins in body:
        if not ins or ins.startswith('.') or ins.endswith(':'):
            m = re.match(r'\.cfi_offset (\d+)', ins)
            if m and 19 <= int(m.group(1)) <= 26:
                saved.add('x' + m.group(1))
            continue
        op, _, rest = ins.partition(' ')
        ops = [o.strip() for o in rest.split(',')]
        if op in ('stp', 'str', 'stur'):
            if re.search(r'\[(sp|x29)\b', rest):
                saved.update(KEPTA[o] for o in ops if o in KEPTA)
            continue
        if op.startswith(('st', 'b', 'cb', 'tb', 'prfm', 'dmb', 'dsb', 'isb')) or \
                op in ('cmp', 'cmn', 'tst', 'ret', 'nop', 'svc'):
            continue
        if op in ('ldp', 'ldxp', 'ldaxp'):
            dests = ops[:2]
        elif op.startswith(('swp', 'ldadd', 'ldclr', 'ldset', 'ldeor')):
            dests = ops[1:2]
        elif op.startswith('cas'):
            dests = ops[:1]
        else:
            dests = ops[:1]
        wrote.update(KEPTA[d] for d in dests if d in KEPTA)
    return sorted(wrote - saved)


def main():
    bad = 0
    for path in sys.argv[1:]:
        lines = open(path).read().split('\n')
        arm = any(re.search(r'\bx29\b', ln) for ln in lines)
        seen = away = 0
        for name, body in routines(lines):
            if name in AWAY:
                away += 1
                continue
            seen += 1
            left = arm64(body) if arm else amd64(body)
            if left:
                print(f'{path}: {name} writes {", ".join(left)} and keeps no copy of it')
                bad += 1
        print(f'{path}: {seen} routines of the runtime keep them, {away} never come back to a routine with them live')
    if bad:
        sys.exit(1)
    print('ok calleesaved')


if __name__ == '__main__':
    main()
