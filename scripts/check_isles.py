#!/usr/bin/env python3
"""check_isles.py ISLES0.s ISLES0-ARM.s: testdata/isles built at -inline 0,
where its calls stay calls, keeps a loop's variables in registers across
the calls it makes (P384).

everypass: a variable in a register every routine keeps (rbx, r12, r13,
r15; x19 to x26), which the region saved at its entry, is read after
the loop's call of Twice and not loaded again before the loop goes
round. catcher: its try stores those registers and its handler loads
them back (on arm64 two a stp and an ldp), so a raise from a callee's region leaves them as the caller's
loop had them. findtwice: an exit from an island in its loop gives each
kept register its caller's value back, as the region's end does: two
loads or more of each from the slot its region keeps it in. """
import re
import sys


def routine(lines, name):
    out, on = [], False
    for ln in lines:
        if ln.startswith(name + ':'):
            on = True
            continue
        if on:
            if '.cfi_endproc' in ln:
                break
            out.append(ln.strip())
    if not out:
        sys.exit(f'{name}: not found')
    return out


def check(path, arm):
    lines = open(path).read().split('\n')
    bad = []
    kept = [f'x{n}' for n in range(19, 27)] if arm else ['rbx', 'r12', 'r13', 'r15']
    call = 'bl p_twice' if arm else 'call p_twice'

    def frame_load(ins, r):
        if arm:
            return re.match(rf'ldr {r}, \[x29, #-?\d+\]', ins) is not None
        return re.match(rf'movq -?\d+\(%rbp\), %{r}$', ins) is not None

    def reads(ins, r):
        if arm:
            ops = [o.strip() for o in ins.partition(' ')[2].split(',')]
            return any(r == o or o.startswith('[' + r) for o in ops[1:]) or \
                (ins.startswith(('str', 'cmp', 'cbz', 'cbnz', 'tst')) and r in ops[:1])
        ops = ins.partition(' ')[2]
        src = ops.rsplit(',', 1)[0] if ',' in ops else ops
        return '%' + r in src or ('%' + r + ',' not in ops and '%' + r in ops and
                                    not ins.startswith('mov'))

    ev = routine(lines, 'p_everypass')
    saved = set()
    for ins in ev:
        m = re.match(r'\.cfi_offset %?(\w+)', ins)
        if m:
            reg = m.group(1) if not arm else 'x' + m.group(1)
            if reg in kept:
                saved.add(reg)
    at = next((i for i, ins in enumerate(ev) if ins == call), None)
    labels = {ins[:-1]: i for i, ins in enumerate(ev) if ins.endswith(':')}
    back = None
    if at is not None:
        for j in range(at + 1, len(ev)):
            m = re.match(r'(j[a-z]+|b\.[a-z]+|b) (\.L\w+)$', ev[j])
            if m and m.group(2) in labels and labels[m.group(2)] < at:
                back = j
                break
    if at is None or back is None:
        bad.append('everypass: no loop that calls Twice')
    else:
        span = ev[at + 1:back]
        kept_across = [r for r in sorted(saved)
                       if any(reads(ins, r) for ins in span) and
                       not any(frame_load(ins, r) for ins in span)]
        if not kept_across:
            bad.append(f'everypass: no variable stays in {"/".join(kept)} across the call of Twice')
    ca = routine(lines, 'p_catcher')
    for r in kept:
        if arm:
            # one register's str or ldr, or two's stp or ldp (P384's pairs)
            st = sum(1 for ins in ca if re.match(rf'str {r}, \[x29, #-?\d+\]', ins) or
                     re.match(rf'stp (x\d+), (x\d+), \[x29, #-?\d+\]$', ins) and
                     r in re.match(r'stp (x\d+), (x\d+)', ins).groups())
            ld = sum(1 for ins in ca if frame_load(ins, r) or
                     re.match(rf'ldp (x\d+), (x\d+), \[x29, #-?\d+\]$', ins) and
                     r in re.match(r'ldp (x\d+), (x\d+)', ins).groups())
        else:
            st = sum(1 for ins in ca if re.match(rf'movq %{r}, -?\d+\(%rbp\)$', ins))
            ld = sum(1 for ins in ca if frame_load(ins, r))
        if st < 1 or ld < 1:
            bad.append(f'catcher: its try does not keep {r} for its handler')
    ft = routine(lines, 'p_findtwice')
    slots = {}
    for i, ins in enumerate(ft):
        m = re.match(r'\.cfi_offset %?(\w+)', ins)
        if m and i > 0:
            reg = m.group(1) if not arm else 'x' + m.group(1)
            st = re.match(r'str (x\d+), \[x29, #(-?\d+)\]$' if arm else
                          r'movq %(\w+), (-?\d+)\(%rbp\)$', ft[i - 1])
            if reg in kept and st and st.group(1) == reg:
                slots[reg] = st.group(2)
    if not slots:
        bad.append('findtwice: its loop keeps no variable in a kept register')
    for r, off in sorted(slots.items()):
        pat = rf'ldr {r}, \[x29, #{off}\]$' if arm else rf'movq {off}\(%rbp\), %{r}$'
        if sum(1 for ins in ft if re.match(pat, ins)) < 2:
            bad.append(f'findtwice: an exit from the loop does not give {r} back')
    return bad


def main():
    bad = check(sys.argv[1], False) + check(sys.argv[2], True)
    for b in bad:
        print(b)
    if bad:
        sys.exit(1)
    print('ok isles-asm')


if __name__ == '__main__':
    main()
