"""Python inference latency: the baseline for the C++ model (bench/model_bench.cpp).

    python python/bench_inference.py --model data/model.bin --sklearn data/mlp.pkl \
        --golden data/golden.bin --out data/python_latency.json

Measures one prediction at a time, the way a strategy reacting to each book
update would call it, three ways:
  scikit-learn  predict_proba on one row
  numpy         the same network written as four numpy operations
  pure Python   the same network as plain loops
and, for contrast, scikit-learn on a batch of 1,000 rows (cost per row).
Each single-row result is checked against the golden predictions first.
"""

import argparse
import json
import pickle
import struct
import time

import numpy as np


def load_model(path):
    with open(path, "rb") as f:
        assert f.read(8) == b"HFTMLP01"
        n_in, h1, h2 = struct.unpack("<3I", f.read(12))

        def arr(*shape):
            n = int(np.prod(shape))
            return np.frombuffer(f.read(4 * n), dtype="<f4").reshape(shape)

        return {"mean": arr(n_in), "inv_std": arr(n_in), "w1": arr(n_in, h1), "b1": arr(h1),
                "w2": arr(h1, h2), "b2": arr(h2), "w3": arr(h2), "b3": arr(1)}


def load_golden(path):
    with open(path, "rb") as f:
        assert f.read(8) == b"HFTGLD01"
        n_in, n = struct.unpack("<2I", f.read(8))
        x = np.frombuffer(f.read(4 * n * n_in), dtype="<f4").reshape(n, n_in)
        p = np.frombuffer(f.read(4 * n), dtype="<f4")
    return x, p


def numpy_proba(m, x):
    z = (x - m["mean"]) * m["inv_std"]
    h1 = np.maximum(z @ m["w1"] + m["b1"], 0.0)
    h2 = np.maximum(h1 @ m["w2"] + m["b2"], 0.0)
    logit = float(h2 @ m["w3"] + m["b3"][0])
    return 1.0 / (1.0 + np.exp(-logit))


def python_proba(m, x):
    z = [(x[i] - m["mean"][i]) * m["inv_std"][i] for i in range(len(x))]
    h1 = [max(0.0, m["b1"][j] + sum(m["w1"][i][j] * z[i] for i in range(len(z)))) for j in range(len(m["b1"]))]
    h2 = [max(0.0, m["b2"][j] + sum(m["w2"][i][j] * h1[i] for i in range(len(h1)))) for j in range(len(m["b2"]))]
    logit = m["b3"][0] + sum(m["w3"][j] * h2[j] for j in range(len(h2)))
    return 1.0 / (1.0 + np.exp(-logit))


def timed(fn, inputs, calls):
    """Per-call latency in ns: p50, p99, mean."""
    t = np.empty(calls, dtype=np.int64)
    n = len(inputs)
    for i in range(calls):
        x = inputs[i % n]
        t0 = time.perf_counter_ns()
        fn(x)
        t[i] = time.perf_counter_ns() - t0
    return {"p50_ns": float(np.percentile(t, 50)), "p99_ns": float(np.percentile(t, 99)), "mean_ns": float(t.mean())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--sklearn", required=True)
    ap.add_argument("--golden", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    m = load_model(args.model)
    m_lists = {k: v.tolist() for k, v in m.items()}
    with open(args.sklearn, "rb") as f:
        sk = pickle.load(f)
    x, p_golden = load_golden(args.golden)
    x_list = [row.tolist() for row in x]

    def sk_proba(row):
        return sk["model"].predict_proba(((row - sk["mean"]) / sk["std"]).reshape(1, -1))[0, 1]

    # Same answers first, then speed.
    for name, fn, data in [("sklearn", sk_proba, x), ("numpy", lambda r: numpy_proba(m, r), x),
                           ("pure_python", lambda r: python_proba(m_lists, r), x_list)]:
        diff = max(abs(fn(data[i]) - p_golden[i]) for i in range(100))
        assert diff < 1e-4, f"{name} disagrees with the golden predictions by {diff}"

    results = {
        "sklearn_single_row": timed(sk_proba, x, 5_000),
        "numpy_single_row": timed(lambda r: numpy_proba(m, r), x, 50_000),
        "pure_python_single_row": timed(lambda r: python_proba(m_lists, r), x_list, 5_000),
    }
    z_all = (x - sk["mean"]) / sk["std"]
    t0 = time.perf_counter_ns()
    for _ in range(50):
        sk["model"].predict_proba(z_all)
    results["sklearn_batch_1000_per_row"] = {"mean_ns": (time.perf_counter_ns() - t0) / (50 * len(x))}

    for name, r in results.items():
        cols = "   ".join(f"{k} {v / 1000:8.2f} us" for k, v in r.items())
        print(f"{name:28s} {cols}")
    with open(args.out, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
