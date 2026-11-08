# Architecture of the public 62-qubit invsqrt circuit (v95, sha 1c5b1ee2…), recovered by semantic lifting

Agent A, 2026-11-08.

## Method

Tools are in `quantum-kaggle/tools/invsqrt/`:
- `decode.py` runs a bit-packed simulation of qubit *values* on 32,768 random x, with random HMR coins, and checkpoints every 50 or 250 ops at condition depth 0.
- `classify.py` labels each qubit at each checkpoint as one of:
  - a bit of the original x or of normalised x_n;
  - a bit of the leading-zero count lz;
  - GF(2)-linear in (x_n, lz, 1);
  - a function of the 8-bit table address only ("T");
  - a function of the address plus the top k bits of δ ("k");
  - a function of (address, δ);
  - a function that also depends on the shift.

Op indices below are positions in the 53.8k-op kmx stream. The full per-checkpoint map is in `$S/work_A/cls.txt`.

Our conventions: lz is the leading zeros of the 22-bit x (0..21); x_n = x << lz; e = lz & 1; address = (e, x_n[20:14]); δ = x_n[13:0].

## Register timeline

| ops | stage | non-x qubits in use | what they hold |
|---|---|---|---|
| 0–2.5k | normalisation | grows to 40 | 20-AND thermometer chain on unshifted x, erased by HMR with free Z fix-ups; then 47 controlled swaps in groups of controlled interval reversals |
| 2.5k–15k | table decode (XAG) | 40 (peak 62) | 45–47 address-only functions at any time. The span of all address functions seen over the circuit reaches the full 256 dimensions. So the "lookup" is an XOR-AND network that builds the table progressively with about 3 ANDs per output bit, not unary iteration. The address wires q14..q20 are temporarily turned into linear forms ("T" in x positions). |
| 15.9k–16.3k | high phase pass | 40 | 16 rotations on q28; bits muxed by the shift flags via controlled swaps. These are the high bits of K0, phased straight from the table. |
| 17.5k–21k | address freeing | 36 | x_n[17..20] become **0** at 19.5k (4 qubits freed). The address is not GF(2)-linear in the remaining wires, so it is recovered non-linearly from table registers (about 19 Toffolis in 17.5k–20k). |
| 21k–24k | R rows (and the start of Y) | 34–37 | 12 qubits become functions of (address, top 8 δ bits): the 12-bit R residual (R rows use only the top 8 δ bits). The remaining T registers shrink from 35 to 22. |
| 24k–25.7k | Y rows | 37 (3 zero) | No register is a pure table value any more. Values depend on more and more top δ bits (codes 3..8, then d/e = 13/14 bits). |
| 25.75k–25.96k | low phase pass | 38 | Y_low = (y · 2^26) mod 2^19 exactly (median error 1 unit) in **19 qubits**: q14, q55, q52, q22, q29, q45, q46, q30, q31, q58, q47, q56, q48, **q16, q20**, q26, **q17, q19**, q25. These are low to high. Five of them are x positions (address bits reused as accumulator bits). A 4-stage streaming delay line feeds q28 (26 rotations), using vacated x_n low bits (q0, q2, q3, q6, q8..q11) and released registers as buffers. |
| 26k–31.5k | reverse Y rows | 32–36 | — |
| 32k–34.3k | coefficient re-materialisation | 40 (peak 62) | 24 T qubits plus 16 R-type ("8") qubits: the second coefficient (K2) is rebuilt for the reverse R rows. |
| 34.7k–50k | measurement-based unlookup | down to 24 | Long CZ-only phase repair, essentially 0 Toffolis. |
| 50k–53.8k | un-normalisation | — | 48 controlled swaps plus conditional fix-ups |

## The qubit tricks

1. **Shift flags stored inside x's own qubits** (0 extra qubits for 4 of the 5 flags):
   - q21 (x_n top bit, always 1) holds bit 0 of lz;
   - q0 = x_n[0] ⊕ bit2(lz);
   - q1 = x_n[1] ⊕ [lz ≥ 8];
   - q2 = x_n[2] ⊕ (bit1(lz) ∧ [lz ≥ 4]);
   - q3 = x_n[3] ⊕ bit4(lz).

   Each flag is XORed into a low mantissa bit that is guaranteed 0 whenever the flag is 1. One more flag lives in q23. During the reverse half the flags move to a permuted arrangement (q0 = [lz≥8], q1 = bit2, …), following the controlled-reversal shift network.

   Consequence: the rows for δ bits 0..3 see x_n ⊕ flag, and must tolerate it. **Open question:** how this is made exact is not yet decoded.
2. **Address bits x_n[17..20] are freed during the arithmetic** and reused as 4 (with x_n[14], x_n[16]: 5–6) of the 19 Y_low accumulator bits. The address is recovered from table registers with about 19 Toffolis.
3. **y is kept to 26 fractional bits** in a **19-bit** low register. Ours keeps 28 bits in a 21-bit register (we drop 2 bits only at the phase). The high part is phased directly from the table (high pass, 16 rotations) and never joined to Y_low (the "overlap" rotations).
4. **K2 is not live during the Y rows.** It is erased after the R rows and rebuilt for the reverse R rows (32k–34k). This is cheap because the table is an XAG over the address: re-deriving a few fields costs a few ANDs per bit.
5. **Very few adder carries during the rows.** With 37 of 40 non-x qubits holding data at 24k–25k, Gidney-style full-width carry registers (19 in our design) cannot be present. The rows run with at most about 3 spare qubits plus whatever registers are momentarily free. How the row adders achieve this is **not yet decoded**: candidates are carry-save merges, narrow rows, and measured carry erasure.
6. **The phase delay line uses vacated x_n low bits** (zero exactly when the corresponding shift flag fires) as buffers, so the phase costs no extra workspace.

## Cost map (static Toffolis by region; mean is lower because fix-ups run on about half the shots)

| stage | Toffolis |
|---|---|
| normalise (chain + 47 CSWAPs + flags) | ≈104 |
| table XAG | ≈130–150 |
| high pass | ≈62 |
| address freeing | ≈19 |
| R + Y rows forward | ≈250 |
| low pass | ≈90 |
| reverse rows + K2 rebuild | ≈255 uncond + ≈130 cond (half) |
| unlookup | ≈0 |
| un-normalise | ≈57 + ≈50 cond |

Total: 1,243 mean Toffolis + 41 rotations (295 Toffoli-equivalents).

## Comparison with our generator v2 (94 qubits, rows peak)

| item | ours | public | saving |
|---|---|---|---|
| flags | 5 dedicated (+ borrow x21) | in x's own bits (+ q23) | ≈4 |
| L / Y_low | 21 bits | 19 bits | 2 |
| K2 during Y rows | 9 kept | erased, rebuilt | 9 |
| carries during Y rows | 19 | ≈0–3 | ≈16 |
| freed address bits as accumulator | 0 | 4–6 | ≈5 |
| **total** | | | **≈36 → about 58–62** |

## Next steps

Implement, in order of value and certainty:
1. Erase and rebuild K2 (needs a cheap K2-only lookup, see `xag.py`).
2. y at 26 fractional bits (needs a model re-fit with a finer R).
3. Flags in x.
4. The carry-light row adders, which still need decoding: classify the qubits inside one Y-row window at 50-op resolution.

## Addendum: the Y-row adder (decoded from ops 24000–24400)

### Forward rows
- **Sign trick.** Each row starts with the signed-digit complement trick on the whole 20-bit Y_low register: `CX q11 → q54, q14, q55, …, q25`, controlled by one δ bit.
- **Rolling carries.** It then runs a Gidney ripple whose carries rotate through only about 8 scratch wires: q21, q27, q28, q40, q41, q50, q51, q57, q61.
- **Block structure.**
  - Carries are computed for a block of about 4 bits.
  - The block is unwound top-down, with free CZ fix-ups and the sums written as it goes.
  - The block's top carry is kept as the carry-in of the next block.
- **Deferred boundary carries.**
  - After it is used, the boundary carry is X-measured into a **stored** bit (`HMR q40 b211`, `HMR q41 b281`, `HMR q57 b422`, `HMR q61 b423`).
  - Its fix-up is deferred to the reverse pass, where the same carry value reappears. The borrows of the complement-trick subtraction ~(~T+v) equal the forward carries bit for bit, so the deferred fix-up there is a free Z on the recomputed carry.
- **Result:** about 1 Toffoli per bit, with ~5–8 carry wires instead of n−1.

### Reverse rows (ops 26k–35k)
- They recompute the carries, repay the stored fix-ups (the many deeply nested conditional CCZ blocks keyed on the stored bits), and erase their own carries.
- Many measurements go into the scratch bit b0 with no fix-up. These are qubits provably |0⟩ on reachable states, or carries whose kick is cancelled within the same branch.
- Conditional duplicate blocks (`PUSH_CONDITION if b414 …`) appear throughout. They exploit mean-cost accounting: one of two equivalent branches runs per shot.
- This is why the reverse pass costs about 2× the forward pass.
