# Audit and hardening — 0.1.2a1

Date: 2026-09-23. Source: JY-S013-P001 / 0.1.1-partial / run-0001 / product.
Reviewed all frame, option, scoring, reweighting, challenge and state code.
Original source remains separate from this release checkout.

## Repaired findings

- Public frame, options and history were mutable, allowing unlogged changes and
  history deletion. Read-only properties now return detached snapshots; supported
  mutations are serialized with a per-instance lock.
- Challenge changes left card digests stale, and history omitted challenge text.
  Full card digests, complete event payloads and linked event digests now bind
  current content and preserve prior events.
- State/scoreboards did not bind history or the compared card snapshots.
  State includes the history head and length; scoreboards include state/card
  digests and a digest of the complete result.
- Normalized weights and weighted components were rounded before sorting,
  eliminating tiny positive weights and conflating close scores. Normalization
  and scoring now retain float precision; only display_total is rounded.
- Partial reweighting mixed new raw inputs with previously normalized values.
  The board now preserves raw weights and updates them consistently.
- Missing ratings permanently blocked a card because no recorded update method
  existed. rate_option now merges validated ratings and records old/new values.
- Huge integers, malformed option IDs and mixed criterion keys could escape the
  BoardError contract. Explicit bounded validation handles these cases.
- Failed operations could mutate before recording history. Complete prospective
  state and event validation now precedes commit, with count and byte limits.
- Diversity results over non-English/empty token sets implied no warning.
  Missing comparable English tokens now produce UNKNOWN.

## Verification and release

29 inherited tests passed before changes. 75 source and installed-wheel tests
pass after changes, including 46 regressions covering concurrency, atomic failure,
snapshot isolation, full digest recomputation, reweighting and rating updates.
Two inherited assertions changed for the version and public snapshot contract.
Historical evidence is retained separately; CI covers Linux 3.10/3.12/3.14 and
Windows 3.12.

Version 0.1.1-partial -> 0.1.2a1. Regenerate snapshots; public property mutation
no longer changes the board. Partial weights use their raw scale and close
rankings may change after removal of premature rounding.

Added packaging, pinned-action CI, README, security documentation and Apache 2.0
LICENSE/NOTICE naming RUSSELL PHILIP SMITHSON. No third-party runtime dependencies
require upgrades, and no build-tool vulnerability scan is claimed.

This remains an advisory in-memory candidate. Hashes are not authentication,
history is not durable, and constraints, diversity and ratings need human review.
The prototype sandbox and original stage-gate roadmap remain unimplemented.
