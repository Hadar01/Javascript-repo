import re, sys, base64, zlib, hashlib, numpy as np, pathlib, shutil
txt = open(sys.argv[1]).read(); out = pathlib.Path(sys.argv[2]); pub = pathlib.Path(sys.argv[3])
get = lambda name: re.search(r'^%s = "([A-Za-z0-9+/=]+)"' % name, txt, re.M).group(1)
inv = zlib.decompress(base64.b64decode(get('INV'))); assert hashlib.sha256(inv).hexdigest().startswith('c6519219f598')
k0 = zlib.decompress(base64.b64decode(get('K0'))); assert hashlib.sha256(k0).hexdigest().startswith('c7c5d6d09889')
raw = zlib.decompress(base64.b64decode(get('WEIGHTS')))
W = np.frombuffer(raw[:8*143*44*8], dtype='<f8').reshape(8,143,44).copy(); H2 = np.frombuffer(raw[8*143*44*8:], dtype='<f8').reshape(8,44).copy()
assert hashlib.sha256(W.tobytes()).hexdigest()[:16]=='e2ef7307d839edc8' and hashlib.sha256(H2.tobytes()).hexdigest()[:16]=='d2f5284ff2ebf330'
(out/'dfthcsos').mkdir(parents=True, exist_ok=True)
(out/'invsqrt.kmb').write_bytes(inv)
for f in (pub/'dfthcsos').glob('angle_k_*.kmb'): shutil.copy(f, out/'dfthcsos'/f.name)
print('pub angle_k_0 == K0:', (pub/'dfthcsos'/'angle_k_0.kmb').read_bytes()==k0)
(out/'dfthcsos'/'angle_k_0.kmb').write_bytes(k0)
base = dict(np.load(pub/'dfthcsos'/'submission.npz'))
print('pub W same as theirs:', np.array_equal(base['W'], W), 'H2_I same:', np.array_equal(base['H2_I'], H2), 'keys', sorted(base))
o = {k: base[k] for k in base if k not in ('W','H2_I')}; o['W'], o['H2_I'] = W, H2
np.savez(out/'dfthcsos'/'submission.npz', **o); print('written')
