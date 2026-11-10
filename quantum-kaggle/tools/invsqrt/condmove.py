"""Mean-cost scan: unconditioned Toffoli-like gates whose product is only consumed inside classically
conditioned code (Agent A).

For each depth-0 unconditioned CCX writing target t, follow t forward until t is next written by a non-XOR
op (HMR, R, SWAP/CSWAP, or overwritten), collecting every read of t (as control, CX source, Z/CZ/CCZ operand).
If every read happens under a classical condition (depth > 0 or an `if b` gate), the CCX (and its partner
uncompute, if it is a CCX/del pattern) could move under that condition.  Reported with the reads' condition
bits; the saving is the probability that the condition is false (computed separately).
usage: python condmove.py circuit.kmx"""
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load


def main(path):
    ops = load(path)
    depth = 0; D = []; stack_bits = []; condsets = []
    for op, args, cond in ops:
        if op == 'PUSH_CONDITION':
            D.append(depth); condsets.append(tuple(stack_bits)); stack_bits.append(cond); depth += 1; continue
        if op == 'POP_CONDITION':
            D.append(depth); condsets.append(tuple(stack_bits))
            if stack_bits: stack_bits.pop()
            depth = max(0, depth - 1); continue
        D.append(depth); condsets.append(tuple(stack_bits) + ((cond,) if cond else ()))
    cands = []
    for k, (op, args, cond) in enumerate(ops):
        if op != 'CCX' or D[k] != 0 or cond is not None: continue
        t = args[2]
        reads = []
        j = k + 1; ended = None
        while j < len(ops):
            o2, a2, c2 = ops[j]
            qs = [a for a in a2 if a.startswith('q')]
            if t in qs:
                if o2 in ('HMR', 'R', 'SWAP', 'CSWAP'):
                    if not condsets[j]:
                        ended = (j, o2); break
                    reads.append((j, o2, condsets[j])); j += 1; continue
                if o2 == 'CX' and a2[1] == t:
                    reads.append((j, 'xor-in', condsets[j]))
                elif o2 == 'X' and a2[0] == t:
                    pass
                elif o2 == 'CCX' and a2[2] == t:
                    reads.append((j, 'xor-in', condsets[j]))
                else:
                    reads.append((j, o2, condsets[j]))
            j += 1
        real_reads = [r for r in reads if r[1] != 'xor-in']
        common = set(real_reads[0][2]) if real_reads else set()
        for r in real_reads: common &= set(r[2])
        if real_reads and common and all(r[2] for r in reads):
            cands.append((k, op, args, ended, sorted(common), len(real_reads)))
    print('unconditioned CCX whose target is read only under classical conditions:', len(cands))
    for c in cands[:40]: print(c)


if __name__ == '__main__':
    main(sys.argv[1])
