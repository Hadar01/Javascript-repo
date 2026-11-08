"""invsqrt v6 = Kirill Tymchishin's integration (QROM + Tower42): Rudra Bhaskar v7's derivative split on Sumit Chongder's
generator, plus our shared-prefix flags and empty-target moves (exact_functions.py), plus two more changes:
  - our F2 10 -> 9 (the coefficient register, live at the peak, is one qubit shorter);
  - anazemcev's borrowed x[21] (always 1 after normalisation) as a clean carry in Rudra's adders.
The modules next to this file are Kirill's published sources (Apache-2.0); stage_r5_w / private_arithmetic_r4_w take the
coefficient width from cfg.w2, handle the one R row whose shift turns negative at F2 9, and pass x[21] to every adder.
Measured 2026-10-23: 93 qubits, 1470 Toffolis, 44 rotations, metric path PASS 165,025.99 (Kirill's 168,521.13).
F2 9 alone (94 qubits) was 166,800.42.
    python build_invsqrt_v5.py OUT.kmb
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import stage_ref as ref, stage_r5_w as r5, private_arithmetic_r4_w as r4
exec(open(os.path.join(HERE, 'exact_functions.py')).read(), ref.__dict__)
cfg = ref.Cfg(9, ref.F1, ref.FYR, ref.GY, ref.DROP2)
tabs, worst = ref.build_tables(cfg)
lay = ref.layout(cfg, tabs)
split, _ = r4.prepare_split(ref, cfg, tabs)
cert = r4.integer_certificate(ref, cfg, tabs)
assert cert['pass'], cert
c = r5.build_candidate(ref, cfg, tabs, lay, split)
s = c.operation_statistics()
print(f'model worst {worst * 2**24:.3f} of tol; qubits {c.num_qubits} toffoli(static) {s.num_toffoli_like} rotations {s.num_z_pow(min_clifford_hierarchy_level=4)}')
c.to_file(sys.argv[1], format='kmb')
print('wrote', sys.argv[1])
