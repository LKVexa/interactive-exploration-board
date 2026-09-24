# Interactive Exploration Board

**0.1.2a1 — experimental partial candidate, JY-S013-P001**

A Python library for comparing options against human-selected criteria.
It captures a question, constraints and assumptions, computes transparent
weighted rankings, and records candidate additions, revised ratings, reweighting
and unresolved challenges. Decision authority remains human.

## Install and use

Python 3.10 or newer; no third-party runtime dependencies.

~~~sh
python -m pip install .
python -m unittest discover -s tests -t .
~~~

~~~python
from expboard.core import ExplorationBoard

board = ExplorationBoard("Which storage design?", ["runs on-prem"], [],
                         {"durability": .6, "operability": .4})
board.add_option("embedded", "Embedded store", "single node", [],
                 {"durability": 7})
assert board.score()["gaps"]
board.rate_option("embedded", {"operability": 9})
board.challenge("embedded", "Verify write concurrency", by="reviewer")
board.reweight({"durability": .8})
scoreboard = board.score()
assert scoreboard["decision_authority"] == "human"
~~~

## Scoring and revisions

Raw criterion weights must be finite numbers in (0, 1]; normalized weights sum
to approximately one. Partial reweighting updates the original raw weight scale,
then normalizes all weights together. Repeating the same update has stable
numerical results, and each call records an event.

Ratings are caller-supplied numbers from 0 through 10, with higher always better.
For cost or risk criteria, the caller must choose a rating scale where a higher
rating is preferable. The board does not infer direction or verify ratings.
Constraints and assumptions are recorded context, not automatically enforced.

Missing ratings exclude that option from ranking and appear as BLOCKED gaps.
rate_option adds or revises selected ratings, preserving old values in history.
Scoreboard status is EMPTY, PARTIAL (one or more gaps), or SCORED. Challenged
options retain their ratings and show unresolved challenge entries.

Arithmetic retains floating-point precision through ranking. total is the sum
of unrounded weighted components; display_total rounds only for presentation.
Exact ties sort by option ID. This is transparent binary floating-point arithmetic,
not arbitrary-precision accounting or statistical confidence.

The diversity check flags substantial English token overlap. Missing comparable
tokens produce UNKNOWN. Lack of a flag does not establish meaningful diversity.
Summaries and assumptions, rather than context or performance, drive this heuristic.

## State and history

frame, options, history, board_state and score return detached snapshots.
Use methods to change the board; mutating returned dictionaries has no effect.
Thread locks serialize operations on the same instance. Invalid or oversized
updates fail before changing its state or appending history.

Card digests cover all content, including ratings and challenges. History contains
full change data, a sequence, timestamp, prior event digest and resulting content
digest. State and scoreboard digests bind the current snapshot and history head.
History grows by append during API use. Wall-clock timestamps are informational;
the event sequence defines order if the system clock moves backward.

This is in-memory history. It is lost when the process ends. Hashes are not
authentication, signatures or tamper-proof storage, and Python private attributes
are not a security boundary against hostile code in the same process.

## Limits and compatibility

At most 200 options, 100 criteria, 100 challenges per option and 10,000 history
events. Strings are bounded to 65,536 characters; labels to 256; assumption and
constraint lists to 100 strings of 4,096 characters each. Combined state content
and serialized event payloads are limited to 16 MiB, as are exported JSON models.
Extremely small weight ratios that underflow are rejected. Invalid inputs raise
BoardError; assigning the read-only snapshot properties raises AttributeError.

Version 0.1.1-partial -> 0.1.2a1 makes public properties snapshots, changes
partial reweighting to raw-scale updates, removes early rounding and refreshes
card/state digests. Regenerate stored snapshots. Use rate_option for ratings.
Two inherited assertions were updated for snapshot isolation and the new version.

75 tests include 29 inherited checks and 46 regressions. Source and installed-wheel
results: [CHECK_RUNS](docs/CHECK_RUNS.json). See [AUDIT](docs/AUDIT.md) and
[SECURITY](SECURITY.md). CI tests Linux Python 3.10/3.12/3.14 and Windows Python 3.12.

No web UI, persistence, authentication, prototype execution sandbox, model option
generation or original stage-gate roadmap is supplied. No production readiness
or automated decision authority is claimed.

## License

Copyright 2026 **RUSSELL PHILIP SMITHSON**.
[Apache License 2.0](LICENSE), with [NOTICE](NOTICE).
No third-party code is vendored.
