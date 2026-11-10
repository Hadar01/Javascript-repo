"""Minimal numpy reader for kickmix .kmb (binary format v2), written from the format writer in kickmix source.
Returns dict with op_types (uint8), operand arrays, registers, info tags; plus per-op operand index helpers."""
import numpy as np, struct
MAGIC_LEN = 16
def read_kmb(path):
    f = open(path, 'rb'); f.read(MAGIC_LEN)
    be32 = lambda: struct.unpack('<I', f.read(4))[0]
    be64 = lambda: struct.unpack('<Q', f.read(8))[0]
    ver = be32(); assert ver == 2
    nq, nb, nreg = be32(), be32(), be32()
    n_ops, n_qqq, n_qq, n_q, n_b, n_c, n_ang, n_tags, n_tagch = [be64() for _ in range(9)]
    regs = {}
    for _ in range(nreg):
        assert be64() == 0; be64()
        nl, rl = be32(), be32(); name = f.read(nl).decode()
        ids = np.frombuffer(f.read(4 * rl), dtype='<u4').astype(np.uint32)
        regs[name] = ids  # high bit set => qubit (little-endian on disk despite "be" helper names)
    assert be64() == 1; assert be64() == n_ops
    out = dict(num_qubits=nq, num_bits=nb, regs=regs)
    out['op'] = np.frombuffer(f.read(n_ops), dtype=np.uint8)
    def blob(code, cnt, dt, size):
        assert be64() == code; assert be64() == cnt * size
        return np.frombuffer(f.read(cnt * size), dtype=dt)
    out['qqq0'] = blob(2, n_qqq, np.uint32, 4); out['qqq1'] = blob(3, n_qqq, np.uint32, 4); out['qqq2'] = blob(4, n_qqq, np.uint32, 4)
    out['qq0'] = blob(5, n_qq, np.uint32, 4); out['qq1'] = blob(6, n_qq, np.uint32, 4)
    out['q0'] = blob(7, n_q, np.uint32, 4); out['b0'] = blob(8, n_b, np.uint32, 4); out['bc'] = blob(9, n_c, np.uint32, 4)
    out['ang'] = blob(10, n_ang, np.uint8, 16)
    assert be64() == 11; be64(); assert be64() == n_tags
    ends = np.frombuffer(f.read(8 * n_tags), dtype=np.uint64); chars = f.read(n_tagch)
    tags = []; s = 0
    for e in ends: tags.append(chars[s:int(e)].decode(errors='replace')); s = int(e)
    out['tags'] = tags
    assert f.read(1) == b''
    return out

NAMES = {0x0:'NEG',0x1:'POP_CONDITION',0x6:'INFO_TAG',0x7:'DEBUG_PRINT_EMPTY',0x40:'BIT_STORE0',0x41:'BIT_STORE1',0x42:'BIT_INVERT',
 0x10:'Z',0x11:'X',0x12:'R',0x13:'Z_POW',0x50:'HMR',0x20:'CZ',0x21:'CX',0x22:'SWAP',0x30:'CCZ',0x31:'CCX',0x32:'CSWAP',
 0x80:'NEG_IF',0x81:'PUSH_CONDITION'}
def opname(t):
    t = int(t)
    if t in NAMES: return NAMES[t]
    if t & 0x80 and (t & 0x7f) in NAMES: return NAMES[t & 0x7f] + '_IF'
    return hex(t)
