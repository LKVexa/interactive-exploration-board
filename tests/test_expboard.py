import unittest

from expboard.core import BoardError, ExplorationBoard


def make_board():
    b = ExplorationBoard(
        question="Which storage engine for the audit ledger?",
        constraints=["must run on-prem", "no GPL dependencies"],
        assumptions=["write-heavy workload"],
        criteria={"durability": 0.5, "ops_cost": 0.3, "latency": 0.2})
    b.add_option("sqlite", "Embedded SQLite file store",
                 "single-node, zero-ops", ["one writer at a time"],
                 {"durability": 7, "ops_cost": 9, "latency": 8})
    b.add_option("postgres", "Managed PostgreSQL cluster",
                 "networked relational store", ["ops team available"],
                 {"durability": 9, "ops_cost": 5, "latency": 7})
    return b


class Frame(unittest.TestCase):
    def test_capture_and_normalized_weights(self):
        b = make_board()
        self.assertAlmostEqual(sum(b.frame["criteria"].values()), 1.0, places=5)
        self.assertEqual(b.frame["constraints"][0], "must run on-prem")
        self.assertEqual(b.history[0]["event"], "frame_captured")

    def test_validation(self):
        with self.assertRaises(BoardError):
            ExplorationBoard("", [], [], {"x": 1})
        with self.assertRaises(BoardError):
            ExplorationBoard("q", [], [], {})
        with self.assertRaises(BoardError):
            ExplorationBoard("q", [], [], {"x": 2.0})


class Options(unittest.TestCase):
    def test_cards_carry_context_and_assumptions(self):
        b = make_board()
        card = b.options["sqlite"]
        self.assertEqual(card["context"], "single-node, zero-ops")
        self.assertTrue(card["card_digest"].startswith("sha256:"))

    def test_duplicate_and_bad_ratings_rejected(self):
        b = make_board()
        with self.assertRaises(BoardError):
            b.add_option("sqlite", "again", "", [], {})
        with self.assertRaises(BoardError):
            b.add_option("x", "s", "c", [], {"nonsense": 5})
        with self.assertRaises(BoardError):
            b.add_option("y", "s", "c", [], {"latency": 15})

    def test_diversity_flag_on_near_duplicates(self):
        b = make_board()
        b.add_option("sqlite2", "Embedded SQLite file store variant",
                     "still single-node zero-ops", ["one writer at a time"],
                     {"durability": 7, "ops_cost": 9, "latency": 8})
        flags = b.materially_different_check()
        self.assertTrue(any(set(f["pair"]) == {"sqlite", "sqlite2"}
                            for f in flags))


class Scoring(unittest.TestCase):
    def test_arithmetic_shown_and_recomputable(self):
        b = make_board()
        sb = b.score()
        top = sb["ranking"][0]
        recomputed = round(sum(p["weighted"] for p in top["arithmetic"]), 4)
        self.assertEqual(top["total"], recomputed)
        self.assertEqual(sb["decision_authority"], "human")

    def test_ranking_order(self):
        sb = make_board().score()
        # postgres: .5*9+.3*5+.2*7 = 7.4 ; sqlite: .5*7+.3*9+.2*8 = 7.8
        self.assertEqual([r["option_id"] for r in sb["ranking"]],
                         ["sqlite", "postgres"])

    def test_missing_rating_blocks_not_defaults(self):
        b = make_board()
        b.add_option("files", "flat files", "", [], {"durability": 4})
        sb = b.score()
        self.assertEqual(len(sb["ranking"]), 2)
        self.assertEqual(sb["gaps"][0]["option_id"], "files")
        self.assertIn("BLOCKED", sb["gaps"][0]["status"])

    def test_deterministic(self):
        a, b_ = make_board().score(), make_board().score()
        self.assertEqual(a["ranking"], b_["ranking"])


class Interaction(unittest.TestCase):
    def test_reweighting_changes_ranking(self):
        b = make_board()
        b.reweight({"durability": 0.8, "ops_cost": 0.1, "latency": 0.1})
        sb = b.score()
        self.assertEqual(sb["ranking"][0]["option_id"], "postgres")
        self.assertEqual(b.history[-1]["event"], "reweighted")
        self.assertIn("old", b.history[-1])          # history, not rewrite

    def test_reweight_validation(self):
        b = make_board()
        with self.assertRaises(BoardError):
            b.reweight({"nope": 0.5})
        with self.assertRaises(BoardError):
            b.reweight({"latency": 0})

    def test_candidate_addition_after_scoring(self):
        b = make_board()
        b.score()
        b.add_option("s3", "Object storage ledger", "cloud", [],
                     {"durability": 8, "ops_cost": 8, "latency": 4})
        self.assertEqual(len(b.score()["ranking"]), 3)

    def test_challenge_recorded_on_card_and_scoreboard(self):
        b = make_board()
        b.challenge("sqlite", "single-writer assumption fails our workload",
                    by="david")
        sb = b.score()
        sq = next(r for r in sb["ranking"] if r["option_id"] == "sqlite")
        self.assertEqual(sq["challenged"][0]["by"], "david")
        self.assertFalse(sq["challenged"][0]["resolved"])
        with self.assertRaises(BoardError):
            b.challenge("nope", "x", by="d")

    def test_no_decision_api(self):
        import expboard.core as m
        for name in dir(m) + dir(ExplorationBoard):
            for bad in ("decide", "choose_winner", "approve", "select_final"):
                self.assertNotIn(bad, name.lower())


if __name__ == "__main__":
    unittest.main()
