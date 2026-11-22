"""Range minima over per-op free-wire profiles (block decomposition)."""
import numpy as np
class RMin:
    def __init__(self, a, B=4096):
        self.a, self.B = a, B; nb = (len(a) + B - 1) // B
        pad = np.full(nb * B, np.iinfo(a.dtype).max, a.dtype); pad[:len(a)] = a; self.bm = pad.reshape(nb, B).min(1)
    def __call__(self, i, j):                      # inclusive [i, j]
        a, B, bm = self.a, self.B, self.bm; bi, bj = i // B, j // B
        if bi == bj: return int(a[i:j + 1].min())
        m = min(a[i:(bi + 1) * B].min(), a[bj * B:j + 1].min())
        if bj > bi + 1: m = min(m, bm[bi + 1:bj].min())
        return int(m)
