# Build 008 — Investigation-first analytics

Baseline: Build 007 (`e19eacaff3b7f1b8c35319b5541894a80483d5ae`).

Scope is presentation/derived analysis only. No ingestion scripts, normalized source artifacts, source registry semantics, or Build 007 payment-source safeguards are modified.

Implemented analytical surfaces:

- Cross-domain Investigations queue with separate materiality, deviation, persistence, and evidence components.
- Data-quality alerts isolated from fiscal/spending review leads.
- Budget pressure ranking from source-backed service-area budget/projection endpoints.
- Procurement concentration, repeat-award screening, category concentration, and explicit candidate vendor-name review without automatic merging.
- Like-for-like quarterly spending-summary movement analysis that excludes ambiguous matches and preserves the non-transaction boundary.
- Command Center redesigned around “What deserves attention?” while keeping released-domain coverage visible.

The review score is an ordering aid only. It is not a fraud score, probability of misconduct, estimate of waste, legal conclusion, or confirmed finding.
