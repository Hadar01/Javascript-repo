"""Shared loader for retain_scan hash records."""
import numpy as np
DT = np.dtype([('k', '<u8'), ('type', 'u1'), ('sub', 'u1'), ('depth', 'u1'), ('opc', 'u1'), ('a', '<u4'), ('b', '<u4'),
               ('c', '<u4'), ('hp1', '<u8'), ('hp2', '<u8'), ('hf1', '<u8'), ('hf2', '<u8'), ('popP', '<u4'), ('popC', '<u4'), ('ht', '<u8'), ('popT', '<u4'), ('pad', '<u4')])
assert DT.itemsize == 80
def load(path): return np.fromfile(path, dtype=DT)
