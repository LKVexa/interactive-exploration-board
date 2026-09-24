import concurrent.futures
import hashlib
import json
import math
import unittest
from unittest.mock import patch
from expboard.core import BoardError, ExplorationBoard


def board():
    b = ExplorationBoard("Compare designs", [], [], {"quality": .5, "cost": .5})
    b.add_option("a", "Alpha architecture", "", [], {"quality": 5, "cost": 7})
    return b


def digest(obj):
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


class Regression(unittest.TestCase):
    def test_public_frame_cannot_be_mutated(self):
        b = board()
        b.frame["criteria"]["quality"] = 0
        self.assertEqual(b.frame["criteria"]["quality"], .5)

    def test_public_history_cannot_be_erased(self):
        b = board()
        b.history.clear()
        self.assertEqual(len(b.history), 2)

    def test_public_options_cannot_be_erased(self):
        b = board()
        b.options.clear()
        self.assertEqual(len(b.options), 1)

    def test_properties_cannot_be_replaced(self):
        b = board()
        for key in ("frame", "options", "history"):
            with self.subTest(key=key), self.assertRaises(AttributeError):
                setattr(b, key, {})

    def test_nested_history_is_snapshot(self):
        b = board()
        b.history[0]["frame"]["criteria"]["quality"] = 1
        self.assertEqual(b.history[0]["frame"]["criteria"]["quality"], .5)

    def test_challenge_changes_card_digest(self):
        b = board()
        old = b.options["a"]["card_digest"]
        b.challenge("a", "Check the assumption", "reviewer")
        self.assertNotEqual(old, b.options["a"]["card_digest"])

    def test_card_digest_covers_challenge_content(self):
        b = board()
        b.challenge("a", "Check", "reviewer")
        card = b.options["a"]
        self.assertEqual(card["card_digest"], digest({k: v for k, v in card.items() if k != "card_digest"}))

    def test_history_chain_recomputable(self):
        b = board()
        b.reweight({"quality": .8})
        b.challenge("a", "Check", "reviewer")
        previous = None
        for i, event in enumerate(b.history, 1):
            self.assertEqual(event["seq"], i)
            self.assertEqual(event["previous_event_digest"], previous)
            self.assertEqual(event["event_digest"], digest({k: v for k, v in event.items() if k != "event_digest"}))
            previous = event["event_digest"]
        self.assertEqual(b.board_state()["history_head"], previous)

    def test_history_records_full_challenge(self):
        b = board()
        entry = b.challenge("a", "Check the workload", "reviewer")
        self.assertEqual(b.history[-1]["challenge"], entry)

    def test_history_records_added_card(self):
        b = board()
        self.assertEqual(b.history[-1]["card"], b.options["a"])

    def test_score_bound_to_current_state(self):
        b = board()
        score = b.score()
        self.assertEqual(score["state_digest"], b.board_state()["state_digest"])
        self.assertEqual(score["ranking"][0]["card_digest"], b.options["a"]["card_digest"])
        self.assertEqual(score["scoreboard_digest"], digest({k: v for k, v in score.items() if k != "scoreboard_digest"}))

    def test_partial_reweight_uses_original_scale(self):
        b = ExplorationBoard("q", [], [], {"a": .2, "b": .2})
        result = b.reweight({"a": .4})
        self.assertAlmostEqual(result["a"], 2 / 3)
        self.assertEqual(b.frame["raw_weights"], {"a": .4, "b": .2})

    def test_repeated_partial_reweight_is_numerically_stable(self):
        b = board()
        first = b.reweight({"quality": .8})
        second = b.reweight({"quality": .8})
        self.assertEqual(first, second)

    def test_small_positive_weight_not_rounded_to_zero(self):
        b = ExplorationBoard("q", [], [], {"a": 1e-8, "b": 1})
        self.assertGreater(b.frame["criteria"]["a"], 0)

    def test_unrepresentable_weight_ratio_rejected(self):
        with self.assertRaises(BoardError):
            ExplorationBoard("q", [], [], {"a": 5e-324, "b": 1, "c": 1, "d": 1})

    def test_close_scores_not_tied_by_display_rounding(self):
        b = ExplorationBoard("q", [], [], {"x": 1})
        b.add_option("a", "A", "", [], {"x": 5})
        b.add_option("z", "Z", "", [], {"x": 5.000001})
        rows = b.score()["ranking"]
        self.assertEqual(rows[0]["option_id"], "z")
        self.assertEqual(rows[0]["display_total"], rows[1]["display_total"])
        self.assertGreater(rows[0]["total"], rows[1]["total"])

    def test_full_precision_arithmetic_recomputable(self):
        b = ExplorationBoard("q", [], [], {"a": .3, "b": .2, "c": .4})
        b.add_option("x", "X", "", [], {"a": 7.321, "b": 9.24, "c": .002})
        row = b.score()["ranking"][0]
        self.assertEqual(row["total"], math.fsum(p["weight"] * p["rating"] for p in row["arithmetic"]))

    def test_invalid_challenge_identifier_contract(self):
        b = board()
        for value in ([], {}, None, "", " a"):
            with self.subTest(value=value), self.assertRaises(BoardError):
                b.challenge(value, "check", "reviewer")

    def test_large_integer_contract(self):
        with self.assertRaises(BoardError):
            ExplorationBoard("q", [], [], {"x": 10 ** 1000})
        with self.assertRaises(BoardError):
            board().add_option("z", "z", "", [], {"quality": 10 ** 1000})

    def test_invalid_mixed_weight_keys_contract(self):
        with self.assertRaises(BoardError):
            board().reweight({2: .5, "unknown": .2})

    def test_empty_reweight_rejected(self):
        with self.assertRaises(BoardError):
            board().reweight({})

    def test_invalid_labels_rejected(self):
        for label in ("", " ", "a\nb", "x" * 257, "x\u202ey"):
            with self.subTest(label=label), self.assertRaises(BoardError):
                ExplorationBoard("q", [], [], {label: 1})

    def test_empty_summary_rejected(self):
        with self.assertRaises(BoardError):
            board().add_option("b", " ", "", [], {})

    def test_empty_challenge_rejected(self):
        with self.assertRaises(BoardError):
            board().challenge("a", "", "reviewer")

    def test_criteria_count_limit(self):
        with self.assertRaises(BoardError):
            ExplorationBoard("q", [], [], {str(i): 1 for i in range(101)})

    def test_assumption_count_limit(self):
        with self.assertRaises(BoardError):
            ExplorationBoard("q", [], ["x"] * 101, {"x": 1})

    def test_text_size_limit(self):
        with self.assertRaises(BoardError):
            ExplorationBoard("x" * 65537, [], [], {"x": 1})

    def test_option_limit_atomic(self):
        b = board()
        before = b.board_state()
        with patch("expboard.core.MAX_OPTIONS", 1), self.assertRaises(BoardError):
            b.add_option("b", "B", "", [], {})
        self.assertEqual(before, b.board_state())

    def test_event_limit_atomic(self):
        b = board()
        before = b.board_state()
        with patch("expboard.core.MAX_EVENTS", 2), self.assertRaises(BoardError):
            b.reweight({"quality": .8})
        self.assertEqual(before, b.board_state())

    def test_model_size_failure_atomic(self):
        b = board()
        before = b.board_state()
        with patch("expboard.core.MAX_BYTES", 100), self.assertRaises(BoardError):
            b.challenge("a", "check", "reviewer")
        self.assertEqual(before, b.board_state())

    def test_nonfinite_clock_failure_atomic(self):
        b = board()
        before = b.board_state()
        with patch("expboard.core.time.time", return_value=float("nan")), self.assertRaises(BoardError):
            b.add_option("b", "B", "", [], {})
        self.assertEqual(before, b.board_state())

    def test_invalid_rating_failure_atomic(self):
        b = board()
        before = b.board_state()
        with self.assertRaises(BoardError):
            b.add_option("b", "B", "", [], {"quality": 11})
        self.assertEqual(before, b.board_state())

    def test_duplicate_addition_concurrent(self):
        b = board()
        def add(_):
            try:
                b.add_option("b", "B", "", [], {})
                return True
            except BoardError:
                return False
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(add, range(20))), 1)
        self.assertEqual(len(b.history), 3)

    def test_concurrent_unique_mutations_preserve_sequence(self):
        b = board()
        def add(i):
            return b.add_option(str(i), "Candidate", "", [], {})
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(len(list(pool.map(add, range(20)))), 20)
        self.assertEqual([e["seq"] for e in b.history], list(range(1, 23)))

    def test_empty_board_is_explicit(self):
        self.assertEqual(ExplorationBoard("q", [], [], {"x": 1}).score()["status"], "EMPTY")

    def test_missing_ratings_give_partial_status(self):
        b = board()
        b.add_option("b", "B", "", [], {})
        self.assertEqual(b.score()["status"], "PARTIAL")

    def test_equal_score_ties_stable(self):
        b = board()
        b.add_option("b", "B", "", [], {"quality": 5, "cost": 7})
        self.assertEqual([r["option_id"] for r in b.score()["ranking"]], ["a", "b"])

    def test_nonenglish_diversity_unknown(self):
        b = ExplorationBoard("q", [], [], {"x": 1})
        b.add_option("a", "方案一", "", [], {})
        b.add_option("b", "方案二", "", [], {})
        self.assertEqual(b.materially_different_check()[0]["status"], "UNKNOWN")

    def test_previous_history_not_rewritten(self):
        b = board()
        old = b.history
        b.reweight({"quality": .8})
        b.challenge("a", "check", "reviewer")
        self.assertEqual(b.history[:len(old)], old)

    def test_input_lists_are_detached(self):
        constraints, assumptions = ["c"], ["a"]
        b = ExplorationBoard("q", constraints, assumptions, {"x": 1})
        constraints.append("changed")
        assumptions.append("changed")
        self.assertEqual(b.frame["constraints"], ["c"])
        self.assertEqual(b.frame["assumptions"], ["a"])

    def test_missing_rating_can_be_completed(self):
        b = board()
        b.add_option("b", "B", "", [], {"quality": 8})
        self.assertEqual(b.score()["status"], "PARTIAL")
        b.rate_option("b", {"cost": 6})
        self.assertEqual(b.score()["status"], "SCORED")
        self.assertEqual(b.options["b"]["ratings"], {"quality": 8, "cost": 6})

    def test_rating_revision_recorded_with_digest(self):
        b = board()
        old = b.options["a"]["card_digest"]
        b.rate_option("a", {"quality": 9})
        event = b.history[-1]
        self.assertEqual(event["old"]["quality"], 5)
        self.assertEqual(event["new"]["quality"], 9)
        self.assertNotEqual(old, b.options["a"]["card_digest"])

    def test_rating_update_return_detached(self):
        b = board()
        card = b.rate_option("a", {"quality": 9})
        card["ratings"]["quality"] = 0
        self.assertEqual(b.options["a"]["ratings"]["quality"], 9)

    def test_invalid_rating_update_atomic(self):
        b = board()
        before = b.board_state()
        for ratings in ({}, {"unknown": 5}, {"quality": True}, {"quality": -1}, []):
            with self.subTest(ratings=ratings), self.assertRaises(BoardError):
                b.rate_option("a", ratings)
        self.assertEqual(before, b.board_state())

    def test_rating_update_unknown_option_rejected(self):
        with self.assertRaises(BoardError):
            board().rate_option("missing", {"quality": 9})

    def test_rating_update_preserves_challenges(self):
        b = board()
        b.challenge("a", "Review", "reviewer")
        old = b.options["a"]["challenged"]
        b.rate_option("a", {"quality": 9})
        self.assertEqual(b.options["a"]["challenged"], old)
