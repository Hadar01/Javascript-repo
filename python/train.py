"""Train the next-mid-move model and export it for C++.

    python python/train.py --features data/features.bin --model data/model.bin \
        --golden data/golden.bin --sklearn data/mlp.pkl --report data/train_report.json

Steps:
  1. Load the features feature_dump wrote; label each row with the direction
     of the symbol's next mid change.
  2. Split CHRONOLOGICALLY: the first 70% of the time range trains, the last
     30% tests. A random split would let the model train on rows from the
     future of the rows it is tested on (look-ahead leakage), which inflates
     the test scores of anything with time structure.
  3. Standardise with statistics from the training part only, for the same
     reason.
  4. Compare two one-line rules, logistic regression, and an MLP (32, 16).
  5. Export the MLP in the HFTMLP01 format include/hft/model/mlp.hpp reads,
     and a "golden" file: 1,000 test inputs with Python's predictions, which
     C++ must reproduce (tests/mlp_test.cpp).
"""

import argparse
import json
import pickle
import struct
import time

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, roc_auc_score
from sklearn.neural_network import MLPClassifier

from hft_data import labelled_dataset, load_rows

H1, H2 = 32, 16  # must match strategy::DefaultModel in model_strategy.hpp


def write_model(path, mean, std, mlp):
    w1, w2, w3 = mlp.coefs_  # sklearn stores weights input-major: (in, out). C++ wants exactly that.
    b1, b2, b3 = mlp.intercepts_
    n_in = w1.shape[0]
    assert w1.shape == (n_in, H1) and w2.shape == (H1, H2) and w3.shape == (H2, 1)
    with open(path, "wb") as f:
        f.write(b"HFTMLP01")
        f.write(struct.pack("<3I", n_in, H1, H2))
        for arr in (mean, 1.0 / std, w1, b1, w2, b2, w3[:, 0], b3):
            f.write(np.ascontiguousarray(arr, dtype="<f4").tobytes())


def write_golden(path, x_raw, proba):
    with open(path, "wb") as f:
        f.write(b"HFTGLD01")
        f.write(struct.pack("<2I", x_raw.shape[1], x_raw.shape[0]))
        f.write(np.ascontiguousarray(x_raw, dtype="<f4").tobytes())
        f.write(np.ascontiguousarray(proba, dtype="<f4").tobytes())


def scores(y, p_up):
    return {"accuracy": float(accuracy_score(y, p_up > 0.5)), "auc": float(roc_auc_score(y, p_up))}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--features", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--golden", required=True)
    ap.add_argument("--sklearn", required=True, help="pickled sklearn MLP, for the Python latency baseline")
    ap.add_argument("--report", required=True)
    ap.add_argument("--train-fraction", type=float, default=0.7)
    args = ap.parse_args()

    rows, names = load_rows(args.features)
    x, y, ts = labelled_dataset(rows)
    split = int(len(x) * args.train_fraction)  # rows are in time order: this is a chronological split
    x_tr, y_tr, x_te, y_te = x[:split], y[:split], x[split:], y[split:]
    print(f"{len(rows)} rows, {len(x)} labelled; train {len(x_tr)}, test {len(x_te)}; "
          f"share of 'up' labels: train {y_tr.mean():.3f}, test {y_te.mean():.3f}")

    mean = x_tr.astype(np.float64).mean(axis=0)
    std = x_tr.astype(np.float64).std(axis=0)
    std[std < 1e-6] = 1.0  # a constant column: leave it unscaled rather than divide by ~0
    z_tr, z_te = (x_tr - mean) / std, (x_te - mean) / std

    i_imb, i_sign = names.index("imbalance_1"), names.index("last_move_sign")
    results = {
        # Rule 1: more size on the bid than the ask -> the mid ticks up next.
        "rule_imbalance": scores(y_te, 0.5 + 0.5 * x_te[:, i_imb]),
        # Rule 2: the mid reverses its last move.
        "rule_reversal": scores(y_te, 0.5 - 0.5 * x_te[:, i_sign]),
    }

    t = time.perf_counter()
    logreg = LogisticRegression(max_iter=1000).fit(z_tr, y_tr)
    results["logistic_regression"] = scores(y_te, logreg.predict_proba(z_te)[:, 1])
    results["logistic_regression"]["train_seconds"] = time.perf_counter() - t

    t = time.perf_counter()
    mlp = MLPClassifier(hidden_layer_sizes=(H1, H2), activation="relu", alpha=1e-4, batch_size=512,
                        learning_rate_init=1e-3, max_iter=40, early_stopping=True, n_iter_no_change=5,
                        random_state=0)
    mlp.fit(z_tr, y_tr)
    p_te = mlp.predict_proba(z_te)[:, 1]
    results["mlp_32_16"] = scores(y_te, p_te)
    results["mlp_32_16"]["train_seconds"] = time.perf_counter() - t
    results["mlp_32_16"]["epochs"] = mlp.n_iter_

    for name, r in results.items():
        print(f"  {name:22s} accuracy {r['accuracy']:.4f}   AUC {r['auc']:.4f}")
    coefs = dict(zip(names, logreg.coef_[0].round(3).tolist()))
    print("  logistic coefficients (standardised):", coefs)

    write_model(args.model, mean, std, mlp)
    write_golden(args.golden, x_te[:1000], p_te[:1000])
    with open(args.sklearn, "wb") as f:
        pickle.dump({"model": mlp, "mean": mean, "std": std}, f)
    report = {
        "source": json.load(open(args.features + ".json"))["source"],
        "rows": int(len(rows)), "labelled": int(len(x)), "train": int(len(x_tr)), "test": int(len(x_te)),
        "up_share_test": float(y_te.mean()), "feature_names": names, "results": results,
        "logistic_coefficients": coefs,
    }
    with open(args.report, "w") as f:
        json.dump(report, f, indent=2)
    print(f"wrote {args.model}, {args.golden}, {args.sklearn}, {args.report}")


if __name__ == "__main__":
    main()
