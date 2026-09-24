"""Hardening tests added in 0.1.1-partial (findings A014-F1..F4)."""
import unittest

from expboard.core import BoardError, ExplorationBoard, VERSION


def make_board():
    b = ExplorationBoard("q?", ["c"], ["a"], {"d": 0.5, "l": 0.5})
    b.add_option("o1", "sum1 alpha beta", "ctx", ["a1"], {"d": 5, "l": 5})
    b.add_option("o2", "sum2 gamma delta", "ctx", ["a2"], {"d": 9, "l": 1})
    return b


class AliasingIsolation(unittest.TestCase):
    # A014-F1: returned structures must be snapshots, not live internals.
    def test_scoreboard_frame_is_snapshot(self):
        b = make_board()
        sb = b.score()
        sb["frame"]["criteria"]["d"] = 99
        self.assertEqual(b.frame["criteria"]["d"], 0.5)

    def test_scoreboard_rows_are_snapshots(self):
        b = make_board()
        row = b.score()["ranking"][0]
        row["assumptions"].append("INJECTED")
        row["challenged"].append({"bogus": True})
        oid = row["option_id"]
        self.assertNotIn("INJECTED", b.options[oid]["assumptions"])
        self.assertEqual(b.options[oid]["challenged"], [])

    def test_add_option_return_is_snapshot(self):
        b = make_board()
        card = b.add_option("o3", "s", "c", [], {"d": 1, "l": 1})
        card["ratings"]["d"] = 1000
        card["assumptions"].append("x")
        self.assertEqual(b.options["o3"]["ratings"]["d"], 1.0)
        self.assertEqual(b.options["o3"]["assumptions"], [])

    def test_board_state_is_snapshot(self):
        b = make_board()
        st = b.board_state()
        st["options"]["o1"]["ratings"]["d"] = -5
        st["frame"]["question"] = "hijacked"
        self.assertEqual(b.options["o1"]["ratings"]["d"], 5.0)
        self.assertEqual(b.frame["question"], "q?")

    def test_challenge_return_is_snapshot(self):
        b = make_board()
        entry = b.challenge("o1", "t", by="x")
        entry["resolved"] = True
        self.assertFalse(b.options["o1"]["challenged"][0]["resolved"])

    def test_positive_returned_data_still_complete(self):
        b = make_board()
        sb = b.score()
        self.assertEqual(len(sb["ranking"]), 2)
        self.assertEqual(sb["frame"]["question"], "q?")


class ErrorContract(unittest.TestCase):
    # A014-F2: invalid input raises BoardError, never bare TypeError etc.
    def test_bad_constructor_inputs(self):
        cases = [
            lambda: ExplorationBoard(None, [], [], {"x": 1}),
            lambda: ExplorationBoard("q", "notalist", [], {"x": 1}),
            lambda: ExplorationBoard("q", [1], [], {"x": 1}),
            lambda: ExplorationBoard("q", [], [], ["x"]),
            lambda: ExplorationBoard("q", [], [], {"x": "hi"}),
            lambda: ExplorationBoard("q", [], [], {"x": float("nan")}),
            lambda: ExplorationBoard("q", [], [], {"x": True}),
        ]
        for fn in cases:
            with self.assertRaises(BoardError):
                fn()

    def test_bad_option_inputs(self):
        b = make_board()
        cases = [
            lambda: b.add_option(1, "s", "c", [], {}),
            lambda: b.add_option("z", "s", "c", [], "notadict"),
            lambda: b.add_option("z", "s", "c", [], {"d": "9"}),
            lambda: b.add_option("z", "s", "c", [], {"d": float("nan")}),
            lambda: b.add_option("z", "s", "c", None, {}),
        ]
        for fn in cases:
            with self.assertRaises(BoardError):
                fn()

    def test_bad_reweight_and_challenge_inputs(self):
        b = make_board()
        with self.assertRaises(BoardError):
            b.reweight("notadict")
        with self.assertRaises(BoardError):
            b.reweight({"d": "0.9"})
        with self.assertRaises(BoardError):
            b.reweight({"d": float("inf")})
        with self.assertRaises(BoardError):
            b.challenge("o1", None, by="x")

    def test_valid_inputs_still_accepted(self):
        b = ExplorationBoard("q", [], [], {"x": 0.25, "y": 1})
        self.assertAlmostEqual(sum(b.frame["criteria"].values()), 1.0, places=5)
        b.add_option("o", "s", "c", [], {"x": 0, "y": 10})
        self.assertEqual(b.score()["ranking"][0]["option_id"], "o")


class DigestIntegrity(unittest.TestCase):
    # A014-F3/F4: digests must cover ratings and full option content.
    def test_public_rating_snapshot_cannot_tamper_with_state(self):
        b = make_board()
        d1 = b.board_state()["state_digest"]
        b.options["o1"]["ratings"]["d"] = 0  # simulate tamper
        d2 = b.board_state()["state_digest"]
        self.assertEqual(d1, d2)

    def test_state_digest_stable_for_same_state(self):
        b = make_board()
        self.assertEqual(b.board_state()["state_digest"],
                         b.board_state()["state_digest"])

    def test_card_digest_covers_ratings(self):
        b1 = ExplorationBoard("q", [], [], {"d": 0.5, "l": 0.5})
        b2 = ExplorationBoard("q", [], [], {"d": 0.5, "l": 0.5})
        b1.add_option("o", "s", "c", [], {"d": 5, "l": 5})
        b2.add_option("o", "s", "c", [], {"d": 0, "l": 0})
        self.assertNotEqual(b1.options["o"]["card_digest"],
                            b2.options["o"]["card_digest"])

    def test_card_digest_stable_for_identical_cards(self):
        b1 = ExplorationBoard("q", [], [], {"d": 0.5, "l": 0.5})
        b2 = ExplorationBoard("q", [], [], {"d": 0.5, "l": 0.5})
        b1.add_option("o", "s", "c", ["a"], {"d": 5, "l": 5})
        b2.add_option("o", "s", "c", ["a"], {"d": 5, "l": 5})
        self.assertEqual(b1.options["o"]["card_digest"],
                         b2.options["o"]["card_digest"])


class VersionConstant(unittest.TestCase):
    def test_version(self):
        self.assertEqual(VERSION, "0.1.2a1")


if __name__ == "__main__":
    unittest.main()
