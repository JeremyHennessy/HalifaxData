# Offline refresh comparison semantics

Candidate preparation validates each retained response against its body hash, endpoint, media type and timezone-aware chronology (at most 40 seconds). Explicit adverse optional transport evidence is rejected: a different response URL, explicitly incomplete headers, a non-null transport error, or a worker termination value other than `confirmed`. Missing optional fields remain unknown; acceptance does not establish transport success independently.

The metadata response must finish no later than the CSV request starts. The elapsed span from metadata request start to CSV completion must not exceed 150 seconds. Equivalent timezone offsets are compared as instants. This is only a paired-capture chronology check. It does not verify robots admission, the full collection-attempt budget, timestamp authenticity, or a transactionally atomic snapshot.

`coverageComparison.years` is sorted across the union of observed baseline and candidate reporting years, including entirely removed and newly observed years. Each entry reports baseline and candidate record counts plus sorted added, removed and amount-changed keys. These are observations relative to the accepted baseline, not assertions that any year or source is complete. No financial sum is computed. Candidate output remains unpublished and unreviewed (`publicationAllowed: false`).

Only synthetic payment receipt times were moved to follow synthetic metadata completion. Original accepted baseline records and publication-review bytes are unchanged.
