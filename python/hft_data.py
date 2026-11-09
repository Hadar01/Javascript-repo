"""Load the training data written by apps/feature_dump, and build labels.

The column names and row layout come from the .json file feature_dump
writes next to the data. They are deliberately not redefined here: the
features exist in exactly one place (include/hft/features/features.hpp).
"""

import json

import numpy as np


def load_rows(path):
    """Return (rows, feature_names). rows is a numpy structured array."""
    with open(path + ".json") as f:
        meta = json.load(f)
    n = meta["num_features"]
    dtype = np.dtype(
        [("exch_ts", "<u8"), ("mid2", "<i8"), ("locate", "<u2"), ("pad", "<u2"), ("f", "<f4", (n,)), ("pad2", "<u4")]
    )
    if dtype.itemsize != meta["row_bytes"]:
        raise ValueError(f"row layout mismatch: python {dtype.itemsize} bytes, file {meta['row_bytes']} bytes")
    rows = np.fromfile(path, dtype=dtype)
    if len(rows) != meta["rows"]:
        raise ValueError(f"expected {meta['rows']} rows, found {len(rows)}")
    return rows, meta["feature_names"]


def next_move_labels(mid2):
    """Direction of the next mid-price change, for one symbol's rows in time order.

    Returns int8 per row: 1 if the next change is up, 0 if down, -1 if the mid
    never changes again (no label). Row t only "sees" data up to t; the label
    looks strictly into the future, which is what we want to predict.
    """
    n = len(mid2)
    labels = np.full(n, -1, dtype=np.int8)
    # change[k] = c means the mid differs between rows c and c+1.
    change = np.flatnonzero(np.diff(mid2) != 0)
    if len(change) == 0:
        return labels
    k = np.searchsorted(change, np.arange(n))  # first change at or after row t
    has_next = k < len(change)
    c = change[k[has_next]]
    labels[has_next] = (mid2[c + 1] > mid2[c]).astype(np.int8)
    return labels


def labelled_dataset(rows):
    """Features X (float32), labels y (0/1), timestamps, in the original row
    order (time order), for the rows that have a label."""
    labels = np.full(len(rows), -1, dtype=np.int8)
    for loc in np.unique(rows["locate"]):
        idx = np.flatnonzero(rows["locate"] == loc)  # this symbol's rows, still in time order
        labels[idx] = next_move_labels(rows["mid2"][idx])
    keep = labels >= 0
    return rows["f"][keep], labels[keep].astype(np.int64), rows["exch_ts"][keep]
