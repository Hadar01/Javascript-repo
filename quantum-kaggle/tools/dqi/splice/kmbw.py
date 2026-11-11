"""Circuit-as-columns helpers: slice op ranges from a parsed kmb (kmb.read_kmb dict), build new op lists, write .kmb.
Format follows kickmix Circuit::write_kmb_to (little-endian fields)."""
import struct, numpy as np, hashlib
MAGIC = bytes([0xd7, 0x50, 0xc7, 0xd5, 0xc3, 0x29, 0xd3, 0x26, 0xe3, 0xcc, 0x9f, 0x68, 0x34, 0xf2, 0xb8, 0xbf])
class Cols:
    """Column store: op bytes + operand arrays + tags, appendable by chunks."""
    def __init__(self):
        self.op = []; self.qqq = [[], [], []]; self.qq = [[], []]; self.q = []; self.b = []; self.c = []; self.tags = []
    def append_slice(self, d, a, b, bitmap=None):
        """Append ops [a,b) of parsed circuit d; optional bitmap: np array old_bit -> new_bit for b0/bc."""
        op = d['op']
        def rng(f):   # operand-array offsets of ops [a,b) for category predicate f (memory-light: counts only)
            s = 0; CH = 1 << 24
            for i in range(0, a, CH): s += int(np.count_nonzero(f(op[i:min(a, i + CH)])))
            e = s
            for i in range(a, b, CH): e += int(np.count_nonzero(f(op[i:min(b, i + CH)])))
            return s, e
        s3, e3 = rng(lambda x: ((x >> 4) & 3) == 3); s2, e2 = rng(lambda x: ((x >> 4) & 3) == 2); s1, e1 = rng(lambda x: ((x >> 4) & 3) == 1)
        sb, eb = rng(lambda x: (x & 0x40) != 0); sc, ec = rng(lambda x: (x & 0x80) != 0); st, et = rng(lambda x: x == 6)
        self.op.append(op[a:b].copy())
        for k in range(3): self.qqq[k].append(d['qqq%d' % k][s3:e3].copy())
        for k in range(2): self.qq[k].append(d['qq%d' % k][s2:e2].copy())
        self.q.append(d['q0'][s1:e1].copy())
        bb = d['b0'][sb:eb].copy(); cc = d['bc'][sc:ec].copy()
        if bitmap is not None: bb = bitmap[bb]; cc = bitmap[cc]
        self.b.append(bb.astype(np.uint32)); self.c.append(cc.astype(np.uint32))
        self.tags += d['tags'][st:et]
    def append_gates(self, gates):
        """gates: list of ('CX',a,b) | ('SWAP',a,b) | ('X',a) | ('TAG',text)."""
        ops = []; q2a = []; q2b = []; q1 = []
        for g in gates:
            if g[0] == 'CX': ops.append(0x21); q2a.append(g[1]); q2b.append(g[2])
            elif g[0] == 'SWAP': ops.append(0x22); q2a.append(g[1]); q2b.append(g[2])
            elif g[0] == 'X': ops.append(0x11); q1.append(g[1])
            elif g[0] == 'TAG': ops.append(0x06); self.tags.append(g[1])
            else: raise ValueError(g)
        self.op.append(np.array(ops, np.uint8)); self.qq[0].append(np.array(q2a, np.uint32)); self.qq[1].append(np.array(q2b, np.uint32))
        self.q.append(np.array(q1, np.uint32))
        for k in range(3): self.qqq[k].append(np.zeros(0, np.uint32))
        self.b.append(np.zeros(0, np.uint32)); self.c.append(np.zeros(0, np.uint32))
    def write(self, path, regs, num_qubits):
        op = np.concatenate(self.op); qqq = [np.concatenate(x).astype(np.uint32) for x in self.qqq]
        qq = [np.concatenate(x).astype(np.uint32) for x in self.qq]; q = np.concatenate(self.q).astype(np.uint32)
        b = np.concatenate(self.b).astype(np.uint32); c = np.concatenate(self.c).astype(np.uint32)
        allbits = [b, c] + [np.array([int(x) & 0x7fffffff for r in regs.values() for x in r if not (int(x) >> 31)], np.uint32)]
        nb = int(max(int(x.max()) if x.size else -1 for x in allbits)) + 1
        chars = ''.join(self.tags).encode(); ends = np.cumsum([len(t.encode()) for t in self.tags]).astype(np.uint64)
        f = open(path, 'wb'); w32 = lambda x: f.write(struct.pack('<I', x)); w64 = lambda x: f.write(struct.pack('<Q', x))
        f.write(MAGIC); w32(2); w32(num_qubits); w32(nb); w32(len(regs))
        for x in (len(op), len(qqq[0]), len(qq[0]), len(q), len(b), len(c), 0, len(self.tags), len(chars)): w64(x)
        for name, ids in regs.items():
            nm = name.encode(); w64(0); w64(len(nm) + 4 * len(ids) + 8); w32(len(nm)); w32(len(ids)); f.write(nm); f.write(np.asarray(ids, '<u4').tobytes())
        w64(1); w64(len(op)); f.write(op.tobytes())
        for code, arr in zip(range(2, 10), [qqq[0], qqq[1], qqq[2], qq[0], qq[1], q, b, c]):
            w64(code); w64(arr.size * 4); f.write(arr.astype('<u4').tobytes())
        w64(10); w64(0)
        w64(11); w64((len(self.tags) + 1) * 8 + len(chars)); w64(len(self.tags)); f.write(ends.astype('<u8').tobytes()); f.write(chars)
        f.close()
        return nb
def sha(p):
    h = hashlib.sha256()
    with open(p, 'rb') as f:
        for ch in iter(lambda: f.read(1 << 22), b''): h.update(ch)
    return h.hexdigest()
