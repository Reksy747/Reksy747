import copy
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import game  # noqa: E402

TODAY = date(2026, 11, 6)


def st(hp=100, max_hp=100, name=None, stack=0):
    s = game.initial_state(TODAY)
    s["incident"] = {"name": name or game.INCIDENTS[0][0], "hp": hp, "max_hp": max_hp}
    s["yaml_stack"] = stack
    return s


def play(state, move, user="u", seed=1):
    return game.apply_move(state, move, user, seed, TODAY)


class ParseTitle(unittest.TestCase):
    def test_parse_title_accepts_case_and_spaces(self):
        self.assertEqual(game.parse_title("  Play:   Rollback "), "rollback")

    def test_parse_title_rejects_junk(self):
        for bad in ["", "play: rollback; rm -rf /", "play: nope", "x" * 500]:
            self.assertIsNone(game.parse_title(bad), bad)

    def test_valid_user(self):
        for ok in ["Reksy747", "a-b", "a"]:
            self.assertTrue(game.valid_user(ok), ok)
        for bad in ["", "-a", "a_b", "a" * 40]:
            self.assertFalse(game.valid_user(bad), bad)


class Moves(unittest.TestCase):
    def test_rollback_damage_18(self):
        s, reply = play(st(100), "rollback")
        self.assertEqual(s["incident"]["hp"], 82)
        self.assertEqual(s["log"][0]["user"], "u")
        self.assertEqual(s["log"][0]["move"], "rollback")
        self.assertTrue(s["log"][0]["text"])
        self.assertTrue(reply)

    def test_add_yaml_scales_and_caps(self):
        s1, _ = play(st(100), "add-yaml", "a")
        self.assertEqual(s1["incident"]["hp"], 96)
        self.assertEqual(s1["yaml_stack"], 1)
        s2, _ = play(s1, "add-yaml", "b")
        self.assertEqual(s2["incident"]["hp"], 88)
        s3, _ = play(st(100, stack=7), "add-yaml")
        self.assertEqual(s3["incident"]["hp"], 70)

    def test_blame_dns_zero_damage(self):
        s, _ = play(st(100), "blame-dns")
        self.assertEqual(s["incident"]["hp"], 100)

    def test_restart_it_damage_range_and_fix(self):
        fixed = 0
        for seed in range(201):
            s, _ = play(st(100), "restart-it", seed=seed)
            if s["hall_of_fame"]:
                fixed += 1
            else:
                self.assertIn(100 - s["incident"]["hp"], range(5, 11), seed)
        self.assertGreater(fixed, 0)

    def test_deploy_friday_both_outcomes(self):
        hps = {play(st(50), "deploy-friday", seed=i)[0]["incident"]["hp"] for i in range(201)}
        self.assertEqual(hps, {15, 70})

    def test_deploy_friday_heal_capped_at_max_hp(self):
        hps = {play(st(95), "deploy-friday", seed=i)[0]["incident"]["hp"] for i in range(201)}
        self.assertEqual(hps, {60, 100})


class Win(unittest.TestCase):
    def test_win_resets_and_records(self):
        old = game.INCIDENTS[0][0]
        s, _ = play(st(10, name=old, stack=3), "rollback", "winner")
        self.assertEqual(s["hall_of_fame"][0], {"user": "winner", "incident": old, "date": TODAY.isoformat()})
        self.assertEqual(s["last_resolved"], TODAY.isoformat())
        self.assertEqual(s["yaml_stack"], 0)
        new = s["incident"]
        self.assertNotEqual(new["name"], old)
        self.assertEqual(new["hp"], dict(game.INCIDENTS)[new["name"]])
        self.assertEqual(new["hp"], new["max_hp"])

    def test_hp_never_negative(self):
        for seed in range(50):
            s, _ = play(st(3), "rollback", seed=seed)
            self.assertGreaterEqual(s["incident"]["hp"], 0)

    def test_log_keeps_newest_five_first(self):
        s = st(100)
        for i, user in enumerate(["a", "b", "a", "b", "a", "b"]):
            s, _ = play(s, "blame-dns", user, seed=i)
        self.assertEqual(len(s["log"]), 5)
        self.assertEqual(s["log"][0]["user"], "b")

    def test_hall_of_fame_trimmed_to_ten(self):
        s = st(10)
        s["hall_of_fame"] = [{"user": f"p{i}", "incident": "x", "date": "2026-01-01"} for i in range(10)]
        s, _ = play(s, "rollback", "new")
        self.assertEqual(len(s["hall_of_fame"]), 10)
        self.assertEqual(s["hall_of_fame"][0]["user"], "new")


class Purity(unittest.TestCase):
    def test_same_seed_same_result(self):
        self.assertEqual(play(st(100), "restart-it", seed=7), play(st(100), "restart-it", seed=7))

    def test_apply_move_does_not_mutate_input(self):
        s = st(100)
        before = copy.deepcopy(s)
        play(s, "rollback")
        self.assertEqual(s, before)


class Validate(unittest.TestCase):
    def test_validate_rejects_same_user_case_insensitive(self):
        s, _ = play(st(100), "blame-dns", "Reksy747")
        move, msg = game.validate(s, "play: rollback", "reksy747")
        self.assertIsNone(move)
        self.assertTrue(msg)

    def test_validate_accepts_other_user(self):
        s, _ = play(st(100), "blame-dns", "Reksy747")
        self.assertEqual(game.validate(s, "play: rollback", "other"), ("rollback", None))

    def test_validate_rejects_bad_title_and_login(self):
        s = st(100)
        for title, user in [("hello", "ok"), ("play: rollback", "bad_user")]:
            move, msg = game.validate(s, title, user)
            self.assertIsNone(move)
            self.assertTrue(msg)


if __name__ == "__main__":
    unittest.main()
