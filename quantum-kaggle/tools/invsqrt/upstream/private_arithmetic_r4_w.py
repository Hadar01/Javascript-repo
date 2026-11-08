"""Private derivative split and top-carry reuse over Sumit Chongder's compiler.

Reference generator credited to Sumit Chongder:
https://www.kaggle.com/code/sumitchongder/notebook2f196e646b
scriptVersionId=361357149. Original-source license metadata is not asserted here.
The normalization, signed-digit model, fitting, and phase schedule belong to
that source. Our changes split its derivative accumulator and reuse the top
adder carry. R3 and the reference source are left unchanged.
"""
from fractions import Fraction
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import time

import numpy as np

REFERENCE_SHA256 = 'c23855304f9871fed84f82b3d7a9db52022ba904855ac3173d1f1db93016d96c'


def sha256(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load_reference(path):
    assert sha256(path) == REFERENCE_SHA256
    spec = importlib.util.spec_from_file_location('_sumit_reference_r4', path)
    reference = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reference)
    return reference


def gadd_top_reused(b, source, target, cin=None, sub=False, borrowed=()):
    """Gidney addition with n-2 clean carries; the last carry targets the MSB."""
    import kickmix as km
    a, t = list(source), list(target)
    n, m = len(t), len(a)
    assert n >= 1 and m <= n
    if sub:
        b.x(km.array(t))
    need = max(0, n - 2); bor = list(borrowed)[:need]
    fresh = b.alloc_qubits(need - len(bor)) if need - len(bor) else []
    carries = bor + list(fresh)
    for i in range(n - 1):
        previous = cin if i == 0 else carries[i - 1]
        last = i == n - 2
        out = t[-1] if last else carries[i]
        if previous is None:
            if i < m:
                (b.ccx if last else b.init_and)(a[i], t[i], out)
        elif i < m:
            b.cx(previous, a[i]); b.cx(previous, t[i])
            (b.ccx if last else b.init_and)(a[i], t[i], out)
            b.cx(previous, out)
        else:
            (b.ccx if last else b.init_and)(previous, t[i], out)
    if n - 1 < m:
        b.cx(a[n - 1], t[n - 1])
    if n == 1 and cin is not None:
        b.cx(cin, t[0])
    for i in reversed(range(n - 1)):
        previous = cin if i == 0 else carries[i - 1]
        last = i == n - 2
        if previous is None:
            if i < m:
                if not last:
                    b.del_and(a[i], t[i], carries[i])
                b.cx(a[i], t[i])
        elif i < m:
            if not last:
                b.cx(previous, carries[i]); b.del_and(a[i], t[i], carries[i])
            b.cx(previous, a[i]); b.cx(a[i], t[i])
        else:
            if not last:
                b.del_and(previous, t[i], carries[i])
            b.cx(previous, t[i])
    if len(fresh):
        b.free(fresh)
    if sub:
        b.x(km.array(t))


def prepare_split(reference, cfg, tables):
    d = np.arange(1 << reference.DB, dtype=np.int64)
    coarse, residual = {}, {}
    bounds = {'normalized_addresses_checked': 0, 'min_residual': 1 << 30,
              'max_residual': 0, 'max_table_residual': 0, 'max_coarse': 0}
    for key, (k2, k1, _) in tables.items():
        derivative, _ = reference.pipeline(cfg, k2, k1, d)
        base = int(derivative.min()) >> 11
        low = derivative - (base << 11)
        coarse[key], residual[key] = base, k1 - (base << 11)
        assert 0 <= residual[key] < 1 << 12
        assert (low >= 0).all() and (low < 1 << 12).all()
        assert ((base + (low >> 11)) < 1 << 7).all()
        joined = (low & 2047) + ((base + (low >> 11)) << 11)
        assert np.array_equal(joined, derivative)
        bounds['normalized_addresses_checked'] += len(d)
        bounds['min_residual'] = min(bounds['min_residual'], int(low.min()))
        bounds['max_residual'] = max(bounds['max_residual'], int(low.max()))
        bounds['max_table_residual'] = max(bounds['max_table_residual'], residual[key])
        bounds['max_coarse'] = max(bounds['max_coarse'], base)
    print('split: w2', cfg.w2, 'rrows', len(cfg.rrow_list()))
    return {'coarse': coarse, 'residual': residual}, bounds


def model_units(reference, cfg, tables, xs):
    xs = np.asarray(xs, dtype=np.int64)
    leading = 21 - np.floor(np.log2(xs)).astype(np.int64)
    normalized = xs << leading
    index = ((normalized >> 14) & 127) + ((leading & 1) << 7)
    packed = np.array([tables[e, a] for e in (0, 1) for a in range(128)], dtype=np.int64)
    k2, derivative, k0 = (packed[index, j].copy() for j in range(3))
    d = normalized & ((1 << 14) - 1)
    for i in cfg.rrow_list():
        derivative -= (2 * ((d >> i) & 1) - 1) * reference.rd(k2, cfg.sh2[i])
    value = k0.copy()
    for i in reversed(range(14)):
        value -= (2 * ((d >> i) & 1) - 1) * reference.rd(derivative, cfg.sh1[i])
    assert (value >= 0).all()
    rounded = (value >> cfg.gy) << (leading >> 1)
    return rounded.astype(np.uint64) << np.uint64(64 - (cfg.fyr + 10))


def integer_certificate(reference, cfg, tables, max_x=3133452):
    worst, margin = 0.0, 1 << 64
    for start in range(1, max_x + 1, 131072):
        xs = np.arange(start, min(start + 131072, max_x + 1), dtype=np.int64)
        actual = model_units(reference, cfg, tables, xs)
        roots = [math.isqrt((1 << 130) // int(x)) for x in xs]
        expected = np.array([((r + 1) >> 1) & ((1 << 64) - 1) for r in roots], dtype=np.uint64)
        tolerance = np.array([min(r >> 25, 1 << 63) for r in roots], dtype=np.uint64)
        error = np.abs((actual - expected).view(np.int64)).view(np.uint64)
        assert (error < tolerance).all(), 'Integer phase certificate failed.'
        worst = max(worst, float((error / tolerance).max()))
        margin = min(margin, int((tolerance - error).min()))
    return {'pass': True, 'checked_inputs': max_x, 'worst_ratio': worst,
            'min_margin_units': margin}


def build_candidate(reference, cfg, tables, layout, split):
    import kickmix as km
    assert (layout['w1'], layout['LB'], layout['S'], layout['whi']) == (18, 21, 20, 8)
    b = km.CircuitBuilder()
    x = b.create_quantum_register(22, name='x')
    flags = b.alloc_qubits(5)
    c2, residual, coarse, low, high = [b.alloc_qubits(n) for n in [9, 12, 7, 21, 8]]
    target = km.array(list(low) + list(residual) + list(c2) + list(high) + list(coarse))
    table = [0] * 256
    for (parity, address), (k2, _, _) in tables.items():
        key = parity, address
        table[address + 128 * parity] = (layout['lo'][key] | (split['residual'][key] << 21)
            | (k2 << 33) | (layout['hi'][key] << 42) | (split['coarse'][key] << 50))
    address = km.array(list(x[14:21]) + [flags[0]])
    delta = x[:14]

    def inner(inverse):
        rows = cfg.rrow_list()
        for i in reversed(rows) if inverse else rows:
            shift = cfg.sh2[i]
            assert shift >= 0
            addend = c2[shift:]
            carry = c2[shift - 1] if shift else None
            b.cx(delta[i], residual)
            gadd_top_reused(b, addend, residual, carry, sub=inverse)
            b.cx(delta[i], residual)

    def outer(derivative, inverse):
        rows = range(14) if inverse else reversed(range(14))
        for i in rows:
            shift = cfg.sh1[i]
            addend = derivative[shift:]
            carry = derivative[shift - 1] if shift else None
            b.cx(delta[i], low)
            gadd_top_reused(b, addend, low, carry, sub=inverse)
            b.cx(delta[i], low)

    reference.normalize(b, x, flags)
    b.init_lookup(table=table, address=address, target=target)
    inner(False)
    gadd_top_reused(b, residual[11:], coarse)
    derivative = residual[:11] + coarse
    outer(derivative, False)
    ext = b.alloc_qubits(10)
    gadd_top_reused(b, low[20:], high)
    phase = km.array(list(low[cfg.gy:20]) + list(high) + list(ext))
    reference.shift_stages(b, flags, phase, 20 - cfg.gy + 8, False)
    for i, qubit in enumerate(phase):
        exponent = cfg.gy + i - cfg.fy - 10
        if exponent < 0:
            b.z_pow(qubit, Fraction(2) ** (exponent + 1))
    reference.shift_stages(b, flags, phase, 20 - cfg.gy + 8, True)
    gadd_top_reused(b, low[20:], high, sub=True)
    b.free(ext)
    outer(derivative, True)
    gadd_top_reused(b, residual[11:], coarse, sub=True)
    inner(True)
    b.del_lookup(table=table, address=address, target=target)
    b.free(target)
    reference.unnormalize(b, x, flags)
    b.free(flags)
    return b.finish_circuit()


def spot_check(circuit, reference, cfg, tables, spec):
    import kickmix as km
    from invsqrt import verify_submission_invsqrt as iv
    inputs, scratch = iv.validate_registers(circuit, spec)
    rng = np.random.default_rng(20261026)
    simulator = km.Simulator(batch_size=256, seed=20261026, debug_print=False)
    for batch in range(32):
        xs = rng.integers(1, spec.max_x + 1, 256, dtype=np.uint64)
        if batch == 0:
            edges = [1, 2, 3, spec.max_x]
            edges += [x for p in range(1, 22) for x in [2**p - 1, 2**p, 2**p + 1] if x <= spec.max_x]
            xs[:len(edges)] = edges
        simulator.clear_for_shot()
        simulator.write_across_shots(inputs, iv.to_bits(xs, spec.width)); simulator.do(circuit)
        assert np.array_equal(iv.from_bits(simulator.read_across_shots(inputs)), xs)
        assert not simulator.read_across_shots(scratch).any()
        actual = np.array([iv.half_turns_to_units(simulator.read_shot_phase(i)) for i in range(256)], dtype=np.uint64)
        assert np.array_equal(actual, model_units(reference, cfg, tables, xs))


def run_arithmetic_r4(baseline_circuit, baseline_report, reference_file, *, output, max_workers=4):
    baseline, output = Path(baseline_circuit), Path(output)
    assert baseline.resolve() != (output / 'candidate.kmb').resolve(), 'Candidate must not overwrite the verified fallback.'
    import kickmix as km
    from invsqrt import verify_submission_invsqrt as iv
    output.mkdir(parents=True, exist_ok=True)
    baseline_sha = sha256(baseline)
    assert baseline_report['status'] == 'PASS' and baseline_report['verified_shots'] == 200540928
    assert baseline_report['circuit_sha256'] == baseline_sha
    assert math.isfinite(baseline_report['score']) and baseline_report['score'] > 0
    fallback = {'improved': False, 'selected_circuit': str(baseline), 'report': dict(baseline_report)}
    audit = {'private_only': True, 'candidate': 'sumit_signed_digit_derivative_L11_top_carry_reuse',
             'reference_sha256': REFERENCE_SHA256, 'baseline_sha256': baseline_sha}
    try:
        reference = load_reference(reference_file)
        cfg = reference.Cfg(reference.F2, reference.F1, reference.FYR, reference.GY, reference.DROP2)
        tables, model_worst = reference.build_tables(cfg)
        layout = reference.layout(cfg, tables)
        split, audit['bounds'] = prepare_split(reference, cfg, tables)
        certificate = integer_certificate(reference, cfg, tables)
        audit['integer_certificate'] = certificate
        audit['reference_model_worst_relative'] = model_worst
        circuit = build_candidate(reference, cfg, tables, layout, split)
        stats = circuit.operation_statistics()
        rotations = int(stats.num_z_pow(min_clifford_hierarchy_level=4))
        epsilon = math.pi * certificate['min_margin_units'] / 2**64 / rotations
        estimated = circuit.num_qubits * (stats.num_toffoli_like +
            (stats.num_t_like + rotations * iv.rotation_t_count(epsilon)) / 4)
        audit.update(num_qubits=circuit.num_qubits, max_toffoli_count=int(stats.num_toffoli_like),
                     rotations=rotations, estimated_cost=float(estimated))
        print('PRIVATE R4 ARITHMETIC STATS', json.dumps(audit), flush=True)
        if estimated >= baseline_report['score']:
            result = {**fallback, 'audit': audit, 'reason': 'No conservative compiled-cost improvement.'}
        else:
            spec = iv.ProblemSpecInvSqrt.for_n_p(10)
            spot_check(circuit, reference, cfg, tables, spec)
            audit['spot_check_shots'] = 8192
            candidate = output / 'candidate.kmb'; circuit.to_file(candidate, format='kmb')
            digest = sha256(candidate)
            reloaded = km.Circuit.from_file(candidate, format='kmb')
            started = time.monotonic()
            report = iv.verify(reloaded, spec, max_workers=max_workers)
            report['verification_seconds'] = time.monotonic() - started
            assert report['status'] == 'PASS' and report['verified_shots'] == 200540928
            assert report['circuit_sha256'] == digest == sha256(candidate)
            assert math.isfinite(report['score']) and 0 < report['score'] < baseline_report['score']
            assert report['num_qubits'] == circuit.num_qubits and report['score'] <= estimated + 1e-6
            report['artifact_sha256'] = digest
            result = {'improved': True, 'selected_circuit': str(candidate), 'report': report, 'audit': audit}
    except Exception as error:
        result = {**fallback, 'audit': audit, 'candidate_failure': type(error).__name__ + ': ' + str(error)}
    (output / 'selected.json').write_text(json.dumps(result, indent=2))
    print('PRIVATE R4 ARITHMETIC SELECTED', json.dumps(result), flush=True)
    return result