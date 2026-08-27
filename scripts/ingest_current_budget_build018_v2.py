#!/usr/bin/env python3
"""Build 018 source-layout specialization for the final 2026/27 budget package.

The Build 004 table buckets remain untouched. Live-source diagnostics established
three source-layout differences in the final package:

- page 85: the change amount is at x=478.7/480.9 and the percentage at x=520.6, so
  Build 004's legacy x<527 change bucket merges distinct source cells;
- page 125: the RCMP table's first currency marker begins at x=205.4/206.0, so the
  legacy x<215 label bucket turns the source label `Net Total` into `Net Total $`;
- page 125: the text-only heading `RCMP HRD – SUMMARY OF CHANGES` extends to x=219.4,
  crossing the legacy label boundary even though the row contains no numbers.

This wrapper therefore applies only source-observed 2026/27 rules: labels end before
x=200, source change values remain x<510, and rows containing no numeric token are
treated wholly as text. All other Build 018 collection, validation, provenance and
arithmetic logic remains in `ingest_current_budget_build018`.
"""
from __future__ import annotations

import re

import ingest_current_budget_build018 as current


def budget_buckets_2026_27(row: list[dict]) -> dict[str, list[dict]]:
    buckets = {
        key: []
        for key in (
            "label",
            "prior_actual",
            "prior_budget",
            "projection",
            "current_budget",
            "source_delta",
            "source_delta_pct",
        )
    }

    # Source-observed text headings can extend beyond the numeric table's label area.
    # If the visual row has no number anywhere, it cannot be a service-area amount row.
    if not any(re.search(r"\d", str(word.get("text") or "")) for word in row):
        buckets["label"].extend(row)
        return buckets

    for word in row:
        x = float(word["x0"])
        if x < 200:
            key = "label"
        elif x < 280:
            key = "prior_actual"
        elif x < 340:
            key = "prior_budget"
        elif x < 405:
            key = "projection"
        elif x < 466:
            key = "current_budget"
        elif x < 510:
            key = "source_delta"
        else:
            key = "source_delta_pct"
        buckets[key].append(word)
    return buckets


current.base.budget_buckets = budget_buckets_2026_27

if __name__ == "__main__":
    current.main()
