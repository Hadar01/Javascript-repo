import sys, numpy as np
sys.path[:0]=[sys.argv[1]]
from dfthcsos import verify as v
npz=sys.argv[2]; d=np.load(npz); inp=v.load_inputs(npz)
m=v.evaluate_words(inp,d['angle_words'],d['tree_edges'],8)
print(repr(m['error_1']), repr(m['error_2']), repr(m['E_gap']), repr(m['Lambda']), repr(m['lambda_eff']), v.passes_accuracy(m))
