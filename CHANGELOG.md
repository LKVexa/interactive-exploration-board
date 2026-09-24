# 0.1.2a1 — 2026-09-23

- Make board properties detached snapshots and serialize atomic updates.
- Bind full card content, history events, state and scoreboards with digests.
- Preserve score precision and apply partial weights on a consistent raw scale.
- Add recorded rating revisions to resolve missing-rating gaps.
- Bound models and improve error contracts and diversity uncertainty.
- Add 46 regressions, packaging, CI, README and Apache 2.0 LICENSE/NOTICE.
- Compatibility: regenerate snapshots and use methods for all board mutations.

# Changelog — Interactive Exploration Board (JY-S013-P001)

## 0.1.1-partial — 2026-09-14 (maintenance run run-0001, audit A014)

Baseline fingerprint: build-0001 product.zip
sha256 c78f986ecef80ccd6d92c237e6c6b5b302f0d19b3b2a2760d8a344b466edcbb5 (6715 bytes),
baseline version 0.1.0-partial (expboard/core.py VERSION), baseline tests 14/14 PASS.
All findings below were reproduced on the exact baseline bytes before fixing
(probe output archived in audit records).

### Fixes (repairs only — patch bump)

- **A014-F1 (high) — aliasing/isolation.** `score()`, `add_option()`,
  `challenge()` and `board_state()` returned live internal objects; mutating a
  returned scoreboard frame, ranking row, card, challenge entry or board_state
  silently corrupted board state (observed: setting `sb["frame"]["criteria"]["d"]=99`
  changed the board's real weights; expected: returned structures are snapshots).
  Fixed by returning deep copies everywhere; history log also stores a frame copy.
- **A014-F2 (medium) — error-contract leaks.** Non-string question, non-list
  constraints/assumptions, non-dict criteria/ratings, and non-numeric or
  NaN/inf weights/ratings escaped as bare `AttributeError`/`TypeError` instead
  of the documented `BoardError`; bool `True` was silently accepted as weight
  1.0. Fixed with typed validation helpers (`_require_str`, `_require_str_list`,
  `_require_number`, `_validate_weights`) raising `BoardError`; bools and
  non-finite numbers rejected.
- **A014-F3 (medium) — state_digest tamper-insensitive.** `board_state()`'s
  `state_digest` hashed only the frame and option *ids*, so tampering with a
  stored rating (or any card content) left the digest unchanged (observed:
  identical digest before/after `ratings["d"]=0`; expected: digest changes).
  Fixed: digest now covers full sorted option contents.
- **A014-F4 (low) — card_digest ignored ratings.** Two cards identical except
  for ratings produced the same `card_digest`. Fixed: digest includes sorted
  ratings.

### Compatibility

- Public API unchanged (constructor, add_option, materially_different_check,
  score, reweight, challenge, board_state). Returned data shapes unchanged.
- Behavioral changes: returned structures are now snapshots (mutating them no
  longer mutates the board — previously a defect, not a feature); previously
  leaking bare exceptions are now `BoardError`; bool/NaN/inf inputs now
  rejected; `state_digest`/`card_digest` values differ from 0.1.0-partial
  because they now cover full content. No baseline test asserted the old
  weaker behavior; none were weakened. 15 hardening tests added
  (tests/test_hardening.py).

### Rollback

Restore build-0001 `product.zip`
(sha256 c78f986ecef80ccd6d92c237e6c6b5b302f0d19b3b2a2760d8a344b466edcbb5).
No data migration involved; the board is in-memory only.
