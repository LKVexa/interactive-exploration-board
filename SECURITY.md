# Security and decision boundaries

This in-memory library ranks caller-supplied options. It does not choose, approve
or execute a decision. Ratings, criteria direction, constraints, claims and
challenger identities are not independently verified. Never treat rankings as
proof of suitability or as authorization.

Snapshots, locks and pre-commit validation protect ordinary API operations from
aliasing, races and partial updates. Python private fields are not access control.
Digest chains expose accidental changes when compared with trusted snapshots;
they do not prevent a caller from rewriting data and recomputing hashes.
History is not durable, authenticated or externally anchored.

The caller must authorize access, minimize sensitive input and review exports.
No redaction exists. Display source strings as untrusted text, with appropriate
escaping. Timestamps use the local wall clock and identities are caller supplied.

Limits bound routine model sizes and the quadratic lexical diversity comparison;
they do not isolate hostile code or every resource-exhaustion scenario. A deployed
service needs request limits, independent authorization and durable audit storage.
No third-party runtime dependencies exist; no build-tool vulnerability scan is
claimed. Report defects privately using synthetic examples.
