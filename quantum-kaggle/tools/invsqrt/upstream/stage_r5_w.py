"""One private static-high phase checkpoint over the attributed R4 compiler.

Sumit Chongder's generator supplies the normalized signed-digit polynomial and
fitting: https://www.kaggle.com/code/sumitchongder/notebook2f196e646b
scriptVersionId=361357149. R4 adds our derivative split and top-carry reuse.
This candidate phases the static high output first, erases that QROM output,
and phases the full residual later. R4 files and its arithmetic are unchanged.
"""
from fractions import Fraction
import json
import math
from pathlib import Path
import time

import numpy as np
import private_arithmetic_r4_w as r4

R4_SHA256 = '639d573bf5e2e1f501a959eee1acf477d4567b858dcc1696ed2b72b8c908bada'


def build_candidate(reference, cfg, tables, layout, split):
    import kickmix as km
    assert (cfg.gy, layout['w1'], layout['LB'], layout['S'], layout['whi']) == (2, 18, 21, 20, 8)
    b = km.CircuitBuilder()
    x = b.create_quantum_register(22, name='x')
    flags = b.alloc_qubits(5)
    # These coefficients are still zero during normalization; allocate afterward.
    reference.normalize(b, x, flags)
    b.x(x[21])                                    # always 1 after normalisation; borrowed as a clean carry (anazemcev)
    BOR = (x[21],)
    w2 = cfg.w2
    c2, residual, coarse, low, high = [b.alloc_qubits(n) for n in [w2, 12, 7, 21, 8]]
    full_target = km.array(list(low) + list(residual) + list(c2) + list(high) + list(coarse))
    rest_target = km.array(list(low) + list(residual) + list(c2) + list(coarse))
    full_table, rest_table, high_table = [0] * 256, [0] * 256, [0] * 256
    for (parity, address), (k2, _, _) in tables.items():
        key, index = (parity, address), address + 128 * parity
        common = layout['lo'][key] | (split['residual'][key] << 21) | (k2 << 33)
        full_table[index] = common | (layout['hi'][key] << (33 + w2)) | (split['coarse'][key] << (41 + w2))
        rest_table[index] = common | (split['coarse'][key] << (33 + w2))
        high_table[index] = layout['hi'][key]
    address = km.array(list(x[14:21]) + [flags[0]])
    delta = x[:14]

    def phase_register(register, low_bit):
        ext = b.alloc_qubits(10)
        word = km.array(list(register) + list(ext))
        reference.shift_stages(b, flags, word, len(register), False)
        for i, qubit in enumerate(word):
            exponent = low_bit + i - cfg.fy - 10
            if exponent < 0:
                b.z_pow(qubit, Fraction(2) ** (exponent + 1))
        reference.shift_stages(b, flags, word, len(register), True)
        b.free(ext)

    def inner(inverse):
        rows = cfg.rrow_list()
        for i in reversed(rows) if inverse else rows:
            shift = cfg.sh2[i]
            if shift >= 0: off, tgt, carry = c2[shift:], residual, (c2[shift - 1] if shift else None)
            else: off, tgt, carry = c2, residual[-shift:], None          # C2 << -shift is exact (rd), as in Sumit's rrows
            b.cx(delta[i], tgt)
            r4.gadd_top_reused(b, off, tgt, carry, sub=inverse, borrowed=BOR)
            b.cx(delta[i], tgt)

    def outer(derivative, inverse):
        for i in range(14) if inverse else reversed(range(14)):
            shift = cfg.sh1[i]
            carry = derivative[shift - 1] if shift else None
            b.cx(delta[i], low)
            r4.gadd_top_reused(b, derivative[shift:], low, carry, sub=inverse, borrowed=BOR)
            b.cx(delta[i], low)

    b.init_lookup(table=full_table, address=address, target=full_target)
    phase_register(high, 20)
    # High and the shift workspace have been restored. For every X-measurement
    # mask m, unlookup contributes (-1)^(m.high(address)); its phase correction
    # contributes the same sign. Their product is +1, preserving our phase.
    # Address and its parity flag stay live and unchanged until after erasure.
    b.del_lookup(table=high_table, address=address, target=high)
    b.free(high)
    inner(False)
    r4.gadd_top_reused(b, residual[11:], coarse, borrowed=BOR)
    derivative = residual[:11] + coarse
    outer(derivative, False)
    # Include bit20 here. There is no output join: floor((L+2^20H)/4)
    # equals floor(L/4)+2^18H, so the two diagonal phases add exactly.
    phase_register(low[cfg.gy:], cfg.gy)
    outer(derivative, True)
    r4.gadd_top_reused(b, residual[11:], coarse, sub=True, borrowed=BOR)
    inner(True)
    b.del_lookup(table=rest_table, address=address, target=rest_target)
    b.free(rest_target)
    b.x(x[21])
    reference.unnormalize(b, x, flags)
    b.free(flags)
    return b.finish_circuit()


def run_arithmetic_r5(baseline_circuit, baseline_report, reference_file, *, output, max_workers=4):
    baseline, output = Path(baseline_circuit), Path(output)
    assert baseline.resolve() != (output / 'candidate.kmb').resolve(), 'Candidate must not overwrite the verified fallback.'
    assert r4.sha256(r4.__file__) == R4_SHA256
    import kickmix as km
    from invsqrt import verify_submission_invsqrt as iv
    output.mkdir(parents=True, exist_ok=True)
    baseline_sha = r4.sha256(baseline)
    assert baseline_report['status'] == 'PASS' and baseline_report['verified_shots'] == 200540928
    assert baseline_report['circuit_sha256'] == baseline_sha
    assert math.isfinite(baseline_report['score']) and baseline_report['score'] > 0
    fallback = {'improved': False, 'selected_circuit': str(baseline), 'report': dict(baseline_report)}
    audit = {'private_only': True, 'candidate': 'static_high_phase_checkpoint',
             'r4_module_sha256': R4_SHA256, 'reference_sha256': r4.REFERENCE_SHA256,
             'baseline_sha256': baseline_sha}
    try:
        reference = r4.load_reference(reference_file)
        cfg = reference.Cfg(reference.F2, reference.F1, reference.FYR, reference.GY, reference.DROP2)
        tables, model_worst = reference.build_tables(cfg)
        layout = reference.layout(cfg, tables)
        split, audit['bounds'] = r4.prepare_split(reference, cfg, tables)
        certificate = r4.integer_certificate(reference, cfg, tables)
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
        print('PRIVATE R5 ARITHMETIC STATS', json.dumps(audit), flush=True)
        if not math.isfinite(estimated) or estimated >= baseline_report['score']:
            result = {**fallback, 'audit': audit, 'reason': 'No conservative compiled-cost improvement.'}
        else:
            spec = iv.ProblemSpecInvSqrt.for_n_p(10)
            r4.spot_check(circuit, reference, cfg, tables, spec)
            audit['spot_check_shots'] = 8192
            candidate = output / 'candidate.kmb'; circuit.to_file(candidate, format='kmb')
            digest = r4.sha256(candidate)
            reloaded = km.Circuit.from_file(candidate, format='kmb')
            started = time.monotonic()
            report = iv.verify(reloaded, spec, max_workers=max_workers)
            report['verification_seconds'] = time.monotonic() - started
            assert report['status'] == 'PASS' and report['verified_shots'] == 200540928
            assert report['circuit_sha256'] == digest == r4.sha256(candidate)
            assert math.isfinite(report['score']) and 0 < report['score'] < baseline_report['score']
            assert report['num_qubits'] == circuit.num_qubits and report['score'] <= estimated + 1e-6
            report['artifact_sha256'] = digest
            result = {'improved': True, 'selected_circuit': str(candidate), 'report': report, 'audit': audit}
    except Exception as error:
        result = {**fallback, 'audit': audit, 'candidate_failure': type(error).__name__ + ': ' + str(error)}
    (output / 'selected.json').write_text(json.dumps(result, indent=2))
    print('PRIVATE R5 ARITHMETIC SELECTED', json.dumps(result), flush=True)
    return result