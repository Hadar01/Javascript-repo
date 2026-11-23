// Run with Node.js: node folded_residual.js
// Arithmetic feasibility screen of the fusion phase target. All angles are turns.
// This does not compile a reversible circuit or call the Kaggle verifier.
// Products of the dyadic slope and local coordinate fit in binary64 exactly here.
// Table synthesis and the comparison oracle use ordinary floating-point math.
"use strict";
const maxX = 3133452;
const quantize = (v, bits) => Math.round(v * 2 ** bits) / 2 ** bits;

// Gate estimate for computing a lookup once, with unrestricted temporary storage.
// Split the address bits. Precompute monomials on each half. For each nonconstant
// high monomial, multiply it by a basis for the low-side output polynomials.
// XORs, including subtraction of a constant Boolean term, are free in this count.
function lookupAndEstimate(words) {
  const bits = Math.log2(words.length);
  const coefficients = words.slice();
  for (let stride = 1; stride < words.length; stride *= 2) {
    for (let i = 0; i < words.length; i++) {
      if (i & stride) coefficients[i] ^= coefficients[i - stride];
    }
  }
  let best = Infinity;
  for (let low = 1; low < bits; low++) {
    const rows = 2 ** low, blocks = 2 ** (bits - low);
    let gates = (rows - 1 - low) + (blocks - 1 - (bits - low));
    for (let h = 1; h < blocks; h++) {
      // Column rank equals row rank. Omit the constant low monomial (index 0).
      const pivots = new Map();
      for (let l = 1; l < rows; l++) {
        let col = coefficients[h * rows + l];
        while (col !== 0n) {
          const pivot = col & -col;
          if (!pivots.has(pivot)) { pivots.set(pivot, col); break; }
          col ^= pivots.get(pivot);
        }
      }
      gates += pivots.size;
    }
    best = Math.min(best, gates);
  }
  return best;
}

function evaluate(segments, groups, buckets, compensate) {
  if (segments % groups !== 0) throw new Error("groups must divide segments");
  const offsets = [], slopes = [], corrections = [];
  for (let parity = 0; parity <= 1; parity++) {
    const scale = 2 ** (-parity / 2);
    for (let s = 0; s < segments; s++) {
      const c = 1 + (s + 0.5) / segments;
      // Offset half the worst quadratic mismatch caused by sharing a curvature across a group.
      const gc = 1 + (Math.floor(s * groups / segments) + 0.5) / groups;
      const offset = 3 * scale * (c ** -2.5 - gc ** -2.5) / (64 * segments ** 2);
      offsets.push(quantize(scale / Math.sqrt(c) + (compensate ? offset : 0), 29));
      slopes.push(quantize(-scale / (2 * segments * c ** 1.5), 27));
    }
    for (let g = 0; g < groups; g++) {
      const c = 1 + (g + 0.5) / groups;
      for (let b = 0; b < buckets; b++) {
        const radius = (b + 0.5) / (2 * buckets * segments);
        corrections.push(quantize(3 * scale * radius ** 2 / (8 * c ** 2.5), 29));
      }
    }
  }
  let worst = 0, worstX = 0, outside = 0;
  for (let e = 0; 2 ** e <= maxX; e++) {
    const start = 2 ** e, end = Math.min(2 * start - 1, maxX);
    const parity = e % 2, exponentScale = 2 ** -Math.floor(e / 2);
    for (let x = start; x <= end; x++) {
      const position = (x - start) * segments / start;
      const s = Math.floor(position), u = position - s - 0.5;
      const g = Math.floor(s * groups / segments);
      const b = Math.min(buckets - 1, Math.floor(2 * buckets * Math.abs(u)));
      const row = parity * segments + s;
      const correction = corrections[(parity * groups + g) * buckets + b];
      const linear = quantize(slopes[row] * u, 29);
      const phase = quantize((offsets[row] + linear + correction) * exponentScale, 37);
      const ref = 1 / Math.sqrt(x);
      const fraction = Math.abs(phase - ref) / (ref * 2 ** -24);
      if (fraction > 1) outside++;
      if (fraction > worst) { worst = fraction; worstX = x; }
    }
  }
  const maxWord = Math.max(...corrections) * 2 ** 29;
  const affineWords = offsets.map((v, i) =>
    (BigInt(v * 2 ** 29) << 28n) | BigInt(-slopes[i] * 2 ** 27));
  const correctionWords = corrections.map(v => BigInt(v * 2 ** 29));
  return {segments, groups, buckets, compensate,
    affineLookupForwardAnds: lookupAndEstimate(affineWords),
    correctionLookupForwardAnds: lookupAndEstimate(correctionWords), affineRows: 2 * segments, correctionRows: 2 * groups * buckets,
    correctionBits: Math.ceil(Math.log2(1 + maxWord)), worstFraction: +worst.toFixed(6), worstX, outside};
}
for (const config of [[512, 8, 16, false], [512, 8, 16, true], [512, 16, 16, true],
                      [256, 32, 64, true], [1024, 2, 8, true]]) {
  console.log(JSON.stringify(evaluate(...config)));
}
