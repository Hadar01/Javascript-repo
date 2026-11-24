// Width-and-gate pricing of the folded-residual invsqrt design (branch codex/fusion-folded-residual-probe,
// tools/invsqrt/folded_residual.js) against a measured baseline circuit.
// Run with Node.js: node folded_pricing.js
//
// The probe gives table sizes and an AND count for computing the 1,024-row affine lookup "with unrestricted temporary
// storage". This script adds what the score charges for: cost = Q x (Toffolis + T/4), Q = peak qubits.
// Every number below is a LOWER bound for the folded design: it charges only the parts listed, and never more than one
// table at a time, so a real circuit can only cost more.
"use strict";

// --- measured baseline: bb676b95 (official verifier, salt nov24-a, 200,540,928 shots) ---
const base = {name: "bb676b95 (33.17 public invsqrt)", Q: 37, toffoli: 1406.312162652404, t: 5.500087737701104,
              rotations: 33, eps: 1.8880574198146154e-13};
const rotT = eps => 0.56 * Math.log2(1 / eps) + 5.3;
base.teq = base.toffoli + (base.t + base.rotations * rotT(base.eps)) / 4;
base.cost = base.Q * base.teq;

// --- the probe's lookup estimator, extended to report the monomial storage it assumes ---
function anf(words) {
  const c = words.slice();
  for (let stride = 1; stride < c.length; stride *= 2) for (let i = 0; i < c.length; i++) if (i & stride) c[i] ^= c[i - stride];
  return c;
}
function lookupWithStorage(words) {
  const bits = Math.log2(words.length), coefficients = anf(words); let best = null;
  for (let low = 1; low < bits; low++) {
    const rows = 2 ** low, blocks = 2 ** (bits - low);
    const monomials = (rows - 1 - low) + (blocks - 1 - (bits - low));     // stored products of address bits
    let gates = monomials;
    for (let h = 1; h < blocks; h++) {
      const pivots = new Map();
      for (let l = 1; l < rows; l++) {
        let col = coefficients[h * rows + l];
        while (col !== 0n) { const p = col & -col; if (!pivots.has(p)) { pivots.set(p, col); break; } col ^= pivots.get(p); }
      }
      gates += pivots.size;                                                // products of a high monomial with a low-side basis
    }
    if (!best || gates < best.gates) best = {low, gates, monomials};
  }
  return best;
}

// --- tables exactly as in the probe's passing configuration (512 segments, 8 groups, 16 buckets, compensated) ---
const quantize = (v, b) => Math.round(v * 2 ** b) / 2 ** b;
const segments = 512, groups = 8, buckets = 16;
const offsets = [], slopes = [], corrections = [];
for (let parity = 0; parity <= 1; parity++) {
  const scale = 2 ** (-parity / 2);
  for (let s = 0; s < segments; s++) {
    const c = 1 + (s + 0.5) / segments, gc = 1 + (Math.floor(s * groups / segments) + 0.5) / groups;
    offsets.push(quantize(scale / Math.sqrt(c) + 3 * scale * (c ** -2.5 - gc ** -2.5) / (64 * segments ** 2), 29));
    slopes.push(quantize(-scale / (2 * segments * c ** 1.5), 27));
  }
  for (let g = 0; g < groups; g++) { const c = 1 + (g + 0.5) / groups;
    for (let b = 0; b < buckets; b++) { const r = (b + 0.5) / (2 * buckets * segments); corrections.push(quantize(3 * scale * r * r / (8 * c ** 2.5), 29)); } }
}
const affineWords = offsets.map((v, i) => (BigInt(v * 2 ** 29) << 28n) | BigInt(-slopes[i] * 2 ** 27));
const affineRows = affineWords.length, wordBits = 57;                     // 29-bit offset + 28-bit slope
const syn = lookupWithStorage(affineWords);

// --- pricing ---
const xBits = 22, addrBits = Math.log2(affineRows), rotTeq = base.rotations * rotT(base.eps) / 4;   // rotations: same count and eps as the baseline (generous)
const rows = [];
const price = (label, Q, teq, note) => rows.push({label, Q, teq: +teq.toFixed(1), cost: Math.round(Q * teq), vsBase: ((Q * teq) / base.cost - 1) * 100, note});
price("baseline " + base.name, base.Q, base.teq, "measured");
// A: narrowest possible: only the offset word is ever materialised; the lookup is unary iteration (rows - 1 Toffolis);
//    nothing else (no slope multiply, correction, shifts, cleanup, iteration ancillas) is charged.
price("A  affine lookup only, unary iteration, offset word only", xBits + 29, (affineRows - 1) + rotTeq,
      "Q = x(22) + offset word(29); T = lookup (1,023) + baseline rotations");
// B: as A plus the unary-iteration ladder ancillas.
price("B  A + iteration ladder ancillas", xBits + 29 + (addrBits - 1), (affineRows - 1) + rotTeq, "+ log2(1,024) - 1 ladder qubits");
// C: the probe's own lookup estimate (unrestricted storage): the monomials and the full 57-bit word are held at once.
price(`C  probe's lookup (${syn.gates} ANDs, split low=${syn.low})`, xBits + syn.monomials + wordBits, syn.gates + rotTeq,
      `Q = x(22) + ${syn.monomials} stored monomials + 57-bit word; T = ${syn.gates} + rotations`);
// D: C plus the correction lookup (82 ANDs per the probe) and the slope x u product (28 x 12 partial products, >= 336).
price("D  C + correction lookup (82) + slope x u (>= 336)", xBits + syn.monomials + wordBits, syn.gates + 82 + 336 + rotTeq, "still no shifts/cleanup");

console.log(`baseline Toffoli-equivalents per input ${base.teq.toFixed(2)}  (Toffolis ${base.toffoli.toFixed(2)} + rotations/T ${(base.teq - base.toffoli).toFixed(2)}), cost ${base.cost.toFixed(1)}`);
console.log(`affine table: ${affineRows} rows x ${wordBits} bits; probe estimator: ${syn.gates} ANDs at split low=${syn.low}, which stores ${syn.monomials} monomials`);
for (const r of rows) console.log(`${r.label.padEnd(62)} Q ${String(r.Q).padStart(4)}  Teq ${String(r.teq).padStart(7)}  cost ${String(r.cost).padStart(7)}  ${(r.vsBase >= 0 ? "+" : "") + r.vsBase.toFixed(1)}%   ${r.note}`);
// break-even: the largest Toffoli-equivalent budget at each width that still beats the baseline
for (const Q of [37, 44, 51, 60, 70]) console.log(`break-even at Q=${Q}: Teq < ${(base.cost / Q).toFixed(1)} (rotations alone ${rotTeq.toFixed(1)}; leaves ${(base.cost / Q - rotTeq).toFixed(1)} for every Toffoli)`);
