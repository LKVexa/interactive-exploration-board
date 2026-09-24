"""Deterministic option comparison with atomic updates and human decision authority."""
from __future__ import annotations

import copy
import hashlib
import json
import math
import re
import threading
import time
import unicodedata

VERSION = "0.1.2a1"
MAX_OPTIONS = 200
MAX_CRITERIA = 100
MAX_EVENTS = 10000
MAX_BYTES = 16 * 1024 * 1024


class BoardError(Exception):
    """Invalid input or an exceeded board resource limit."""


def _canonical(obj):
    try:
        payload = json.dumps(obj, sort_keys=True, separators=(",", ":"),
                             allow_nan=False, ensure_ascii=False)
        if len(payload.encode("utf-8")) > MAX_BYTES:
            raise BoardError("board model exceeds 16 MiB")
        return payload
    except (TypeError, ValueError, OverflowError, UnicodeError, RecursionError) as exc:
        raise BoardError("invalid board model") from exc


def _digest(obj):
    return "sha256:" + hashlib.sha256(_canonical(obj).encode("utf-8")).hexdigest()


def _require_str(value, what, limit=65536, empty=False):
    if type(value) is not str or len(value) > limit or (not empty and not value.strip()):
        raise BoardError(f"{what} must be a bounded nonempty string")
    if any(unicodedata.category(c).startswith("C") and c not in "\n\t" for c in value):
        raise BoardError(f"{what} contains unsupported control characters")
    return value


def _label(value, what):
    value = _require_str(value, what, 256)
    if value != value.strip() or "\n" in value or "\t" in value:
        raise BoardError(f"{what} must be a single-line label without surrounding whitespace")
    return value


def _require_str_list(value, what):
    if type(value) not in (list, tuple) or len(value) > 100:
        raise BoardError(f"{what} must contain at most 100 strings")
    return [_require_str(v, what, 4096) for v in value]


def _require_number(value, what):
    if type(value) not in (int, float):
        raise BoardError(f"{what} must be a finite real number")
    try:
        number = float(value)
    except (ValueError, OverflowError) as exc:
        raise BoardError(f"{what} must be a finite real number") from exc
    if not math.isfinite(number):
        raise BoardError(f"{what} must be finite")
    return number


def _validate_weights(weights):
    if type(weights) is not dict or not 1 <= len(weights) <= MAX_CRITERIA:
        raise BoardError("criteria must contain 1..100 named weights")
    checked = {}
    for name, value in weights.items():
        name = _label(name, "criterion name")
        weight = _require_number(value, "criterion weight")
        if not 0 < weight <= 1:
            raise BoardError("criterion weights must be in (0, 1]")
        checked[name] = weight
    return dict(sorted(checked.items()))


def _normalized(weights):
    total = math.fsum(weights.values())
    result = {k: v / total for k, v in weights.items()}
    if any(v == 0 for v in result.values()):
        raise BoardError("weight ratio underflows floating-point precision")
    return result


def _card_digest(card):
    return _digest({k: v for k, v in card.items() if k != "card_digest"})


class ExplorationBoard:
    """One in-memory board; properties return detached snapshots."""
    def __init__(self, question, constraints, assumptions, criteria):
        question = _require_str(question, "research question")
        constraints = _require_str_list(constraints, "constraints")
        assumptions = _require_str_list(assumptions, "assumptions")
        weights = _validate_weights(criteria)
        frame = {"question": question, "constraints": constraints,
                 "assumptions": assumptions, "raw_weights": weights,
                 "criteria": _normalized(weights)}
        self._lock = threading.RLock()
        self._frame, self._options, self._history = {}, {}, []
        self._history_bytes = 0
        self._commit("frame_captured", frame, {}, frame=frame)

    @property
    def frame(self):
        with self._lock:
            return copy.deepcopy(self._frame)

    @property
    def options(self):
        with self._lock:
            return copy.deepcopy(self._options)

    @property
    def history(self):
        with self._lock:
            return copy.deepcopy(self._history)

    def _commit(self, event, new_frame, new_options, **data):
        # Validate the complete prospective mutation before changing any state.
        if len(self._history) >= MAX_EVENTS:
            raise BoardError("history event limit reached")
        timestamp = _require_number(time.time(), "event timestamp")
        content = {"frame": new_frame, "options": new_options}
        entry = {"seq": len(self._history) + 1, "event": event, "at": timestamp,
                 "previous_event_digest": self._history[-1]["event_digest"] if self._history else None,
                 "content_digest": _digest(content), **copy.deepcopy(data)}
        entry["event_digest"] = _digest(entry)
        history_bytes = self._history_bytes + len(_canonical(entry).encode("utf-8"))
        if history_bytes + len(_canonical(content).encode("utf-8")) > MAX_BYTES:
            raise BoardError("combined state and history exceed 16 MiB")
        self._frame, self._options = copy.deepcopy(new_frame), copy.deepcopy(new_options)
        self._history.append(entry)
        self._history_bytes = history_bytes

    def add_option(self, option_id, summary, context, assumptions, ratings):
        option_id = _label(option_id, "option_id")
        summary = _require_str(summary, "summary")
        context = _require_str(context, "context", empty=True)
        assumptions = _require_str_list(assumptions, "option assumptions")
        if type(ratings) is not dict or len(ratings) > MAX_CRITERIA:
            raise BoardError("ratings must be a bounded criterion dictionary")
        with self._lock:
            if option_id in self._options:
                raise BoardError("option_id already exists")
            if len(self._options) >= MAX_OPTIONS:
                raise BoardError("at most 200 options are supported")
            checked = {}
            for name, value in ratings.items():
                _label(name, "rating criterion")
                if name not in self._frame["criteria"]:
                    raise BoardError("rating uses an unknown criterion")
                value = _require_number(value, "rating")
                if not 0 <= value <= 10:
                    raise BoardError("ratings must be in 0..10")
                checked[name] = value
            card = {"option_id": option_id, "summary": summary, "context": context,
                    "assumptions": assumptions, "ratings": dict(sorted(checked.items())),
                    "challenged": []}
            card["card_digest"] = _card_digest(card)
            options = dict(self._options, **{option_id: card})
            self._commit("option_added", self._frame, options, option_id=option_id,
                         card=card, card_digest=card["card_digest"])
            return copy.deepcopy(card)

    def materially_different_check(self):
        """Lexical overlap flags are advisory, never evidence of diversity."""
        with self._lock:
            return self._diversity(self._options)

    def rate_option(self, option_id, ratings):
        """Set or revise supplied ratings without erasing their prior history."""
        option_id = _label(option_id, "option_id")
        if type(ratings) is not dict or not 1 <= len(ratings) <= MAX_CRITERIA:
            raise BoardError("ratings must be a nonempty bounded dictionary")
        with self._lock:
            if option_id not in self._options:
                raise BoardError("unknown option")
            checked = {}
            for name, value in ratings.items():
                _label(name, "rating criterion")
                if name not in self._frame["criteria"]:
                    raise BoardError("rating uses an unknown criterion")
                value = _require_number(value, "rating")
                if not 0 <= value <= 10:
                    raise BoardError("ratings must be in 0..10")
                checked[name] = value
            options = copy.deepcopy(self._options)
            card = options[option_id]
            old = dict(card["ratings"])
            card["ratings"] = dict(sorted({**old, **checked}.items()))
            card["card_digest"] = _card_digest(card)
            self._commit("ratings_updated", self._frame, options, option_id=option_id,
                         old=old, new=card["ratings"], card_digest=card["card_digest"])
            return copy.deepcopy(card)

    @staticmethod
    def _diversity(options):
        tokens = {oid: set(re.findall(r"[a-z]{3,}", (o["summary"] + " " +
                  " ".join(o["assumptions"])).lower())) for oid, o in options.items()}
        flags, ids = [], sorted(tokens)
        for i, first in enumerate(ids):
            for second in ids[i + 1:]:
                union = tokens[first] | tokens[second]
                if not tokens[first] or not tokens[second]:
                    flags.append({"pair": [first, second], "status": "UNKNOWN",
                                  "note": "no comparable English tokens; human review required"})
                elif len(tokens[first] & tokens[second]) / len(union) > 0.6:
                    flags.append({"pair": [first, second], "status": "CHALLENGE",
                                  "note": "options may not be materially different — challenge recommended"})
        return flags

    def _state(self):
        state = {"frame": copy.deepcopy(self._frame),
                 "options": copy.deepcopy(dict(sorted(self._options.items()))),
                 "history_length": len(self._history),
                 "history_head": self._history[-1]["event_digest"]}
        state["state_digest"] = _digest(state)
        return state

    def board_state(self):
        with self._lock:
            return self._state()

    def score(self):
        with self._lock:
            rows, gaps = [], []
            for oid, option in sorted(self._options.items()):
                missing = sorted(set(self._frame["criteria"]) - set(option["ratings"]))
                if missing:
                    gaps.append({"option_id": oid, "missing_criteria": missing,
                                 "status": "BLOCKED — rate before scoring",
                                 "card_digest": option["card_digest"]})
                    continue
                parts = [{"criterion": c, "weight": w, "rating": option["ratings"][c],
                          "weighted": w * option["ratings"][c]}
                         for c, w in self._frame["criteria"].items()]
                total = math.fsum(p["weighted"] for p in parts)
                rows.append({"option_id": oid, "total": total, "display_total": round(total, 4),
                             "arithmetic": parts, "assumptions": list(option["assumptions"]),
                             "challenged": copy.deepcopy(option["challenged"]),
                             "card_digest": option["card_digest"]})
            rows.sort(key=lambda row: (-row["total"], row["option_id"]))
            result = {"schema": "expboard/scoreboard/v1", "board_version": VERSION,
                      "frame": copy.deepcopy(self._frame), "ranking": rows, "gaps": gaps,
                      "status": "EMPTY" if not self._options else ("PARTIAL" if gaps else "SCORED"),
                      "state_digest": self._state()["state_digest"],
                      "diversity_flags": self._diversity(self._options),
                      "decision_authority": "human",
                      "note": "rankings are inputs to a human decision; the board does not choose"}
            result["scoreboard_digest"] = _digest(result)
            return result

    def reweight(self, new_weights):
        if type(new_weights) is not dict or not new_weights:
            raise BoardError("new_weights must be a nonempty criterion dictionary")
        checked = _validate_weights(new_weights)
        with self._lock:
            if set(checked) - set(self._frame["raw_weights"]):
                raise BoardError("unknown criteria")
            raw = {**self._frame["raw_weights"], **checked}
            weights = _normalized(raw)
            frame = dict(self._frame, raw_weights=raw, criteria=weights)
            self._commit("reweighted", frame, self._options,
                         old=self._frame["criteria"], new=weights,
                         old_raw=self._frame["raw_weights"], new_raw=raw)
            return copy.deepcopy(weights)

    def challenge(self, option_id, challenge_text, by):
        option_id = _label(option_id, "option_id")
        challenge_text = _require_str(challenge_text, "challenge text")
        by = _label(by, "challenger name")
        with self._lock:
            if option_id not in self._options:
                raise BoardError("unknown option")
            if len(self._options[option_id]["challenged"]) >= 100:
                raise BoardError("at most 100 challenges per option")
            entry = {"text": challenge_text, "by": by,
                     "at": _require_number(time.time(), "challenge timestamp"),
                     "resolved": False}
            options = copy.deepcopy(self._options)
            card = options[option_id]
            card["challenged"].append(entry)
            card["card_digest"] = _card_digest(card)
            self._commit("challenged", self._frame, options, option_id=option_id,
                         by=by, challenge=entry, card_digest=card["card_digest"])
            return copy.deepcopy(entry)
