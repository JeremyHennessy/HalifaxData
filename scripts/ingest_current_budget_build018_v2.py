#!/usr/bin/env python3
"""Build 018 source-layout specialization for the final 2026/27 budget package.

The Build 004 table buckets remain untouched. Live-source diagnostics on final-package
page 85 showed the source's change amount at x=478.7/480.9 and the percentage at
x=520.6. Build 004's legacy x<527 change bucket therefore merged both cells.

This wrapper changes exactly one boundary for the 2026/27 source: source change values
remain x<510 and percentage values begin at x>=510. All other Build 018 collection,
validation, provenance and arithmetic logic remains in ingest_current_budget_build018.
"""
from __future__ import annotations

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
    for word in row:
        x = float(word["x0"])
        if x < 215:
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
