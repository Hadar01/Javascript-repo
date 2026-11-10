"""Find groups of depth-0, unconditioned CCX gates XOR-ing into the same target qubit, with the target not
read or overwritten in between (Agent A).  Linear CX into the target are allowed inside a group.
usage: python groups.py circuit.kmx"""
import sys
sys.path.insert(0, __file__.rsplit('/', 1)[0])
from kmx_analyze import load

def find_groups(ops):
    groups = []
    open_g = {}          # target -> list of op indices
    depth = 0
    def close(t):
        g = open_g.pop(t, None)
        if g and sum(1 for k in g if ops[k][0] == 'CCX') >= 2: groups.append((t, g))
    for k, (op, args, cond) in enumerate(ops):
        if op == 'PUSH_CONDITION':
            for t in list(open_g): close(t)
            depth += 1; continue
        if op == 'POP_CONDITION':
            depth -= 1; continue
        qs = [a for a in args if a.startswith('q')]
        if depth > 0 or cond is not None:
            for t in list(open_g):
                if t in qs: close(t)
            continue
        if op == 'CCX':
            a, b, t = qs
            for tt in list(open_g):
                if tt in (a, b): close(tt)
            open_g.setdefault(t, []).append(k)
            continue
        if op == 'CX':
            c, t = qs
            if c in open_g: close(c)
            if t in open_g: open_g[t].append(k)
            continue
        for tt in list(open_g):
            if tt in qs: close(tt)
    for t in list(open_g): close(t)
    return groups

if __name__ == '__main__':
    ops = load(sys.argv[1])
    G = find_groups(ops)
    from collections import Counter
    print('groups with >=2 CCX:', len(G), 'size histogram', sorted(Counter(sum(1 for k in g if ops[k][0]=='CCX') for _, g in G).items()))
    print('span (ops) histogram', sorted(Counter(min(9, (g[-1]-g[0])//50) for _, g in G).items()))
