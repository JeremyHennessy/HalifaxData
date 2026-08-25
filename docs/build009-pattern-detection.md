# Build 009 — Automated Pattern & Cross-Domain Detection

Baseline: Build 008 (`c47281b7b4418075855cc43fc703091df68c2f7a`).

Build 009 is a derived analytical/UI layer only. It does not modify ingestion scripts, normalized source artifacts, source registry semantics, Build 007 payment-source safeguards, or Build 008 evidence boundaries.

## Automated pattern surfaces

- Multi-year budget pressure using exact normalized business-unit + service-area continuity.
- Only final historical budget source states plus the current released budget row contribute to persistence scoring. Draft, proposed and pre-COVID rows remain context only.
- Procurement persistence and acceleration using exact published vendor identities, annual award histories, reporting-body concentration and repeat-award frequency.
- Candidate vendor aliases remain a separate review process and are never silently merged into pattern calculations.
- Full quarterly spending-summary trajectories use exact normalized record type + row label + amount semantics. PDF page/table context and monetary-token count are treated as layout metadata rather than longitudinal identity; any date that becomes non-unique after ignoring those layout attributes is excluded rather than guessed.
- Build 008's stricter pairwise quarterly matcher remains unchanged as supporting evidence.
- Cross-domain corroboration uses an exact normalized published business-unit label between an operating-expense-summary trajectory and either a multi-year budget pattern or the released current Budget Pressure layer. Historical organization labels are not force-crosswalked to create a match.

## Interpretation boundaries

Cross-domain corroboration does not force different accounting views into one measure. Dollar values are never summed across budget and quarterly-spending views, and an exact shared business-unit label does not prove identical accounting scope or causality.

Pattern scores remain review-ordering aids. Persistence, acceleration, concentration or corroboration do not establish waste, fraud, illegality, lack of competition or policy breach.
