import unittest
from unittest.mock import patch

from backend.cloudmusic import engine


class SearchSelectionTest(unittest.TestCase):
    def setUp(self):
        self.songs = [
            {
                "id": 1911300549,
                "name": "命に嫌われている",
                "ar": [{"name": "カンザキイオリ"}],
            },
            {
                "id": 2758994933,
                "name": "被生命所厌恶【星尘中文填词】",
                "ar": [{"name": "星尘"}],
            },
        ]
        self._original_candidates = engine.search_song_api_candidates

    def tearDown(self):
        engine.search_song_api_candidates = self._original_candidates

    def _patch_candidates(self, mapping):
        """把搜索接口替换成按查询词返回固定候选，并记录实际调用过的查询词。"""
        calls = []

        def fake(title, limit=20):
            calls.append(title)
            return [dict(song) for song in mapping.get(title, [])]

        engine.search_song_api_candidates = fake
        return calls

    def test_first_strategy_uses_api_ranking(self):
        selected = engine.select_search_result(
            self.songs, "被生命所厌恶", strategy="first"
        )
        self.assertEqual(selected["id"], 1911300549)

    def test_classic_strategy_prefers_literal_title(self):
        selected = engine.select_search_result(
            self.songs, "被生命所厌恶", strategy="classic"
        )
        self.assertEqual(selected["id"], 2758994933)

    # ---------------------------------------------------------------- "的" 拆分规则
    def test_split_artist_song_rules(self):
        self.assertEqual(engine._split_artist_song("歌手的歌曲"), ("歌手", "歌曲"))
        self.assertIsNone(engine._split_artist_song("普通歌名"))
        self.assertIsNone(engine._split_artist_song("的歌曲"))
        self.assertIsNone(engine._split_artist_song("歌手的"))
        self.assertIsNone(engine._split_artist_song(""))

    # ---------------------------------------------------------------- "XXX的YYY" 反转搜索
    def test_possessive_direct_title_match_does_not_reverse(self):
        """完整歌名直接命中时，不能把真实歌名误拆成『歌手的歌』。"""
        calls = self._patch_candidates({
            "我们的爱": [
                {"id": 372, "name": "我们的爱", "ar": [{"name": "飞儿乐团"}]},
                {"id": 373, "name": "其他歌曲"},
            ],
            "爱 我们": [{"id": 999, "name": "别的歌"}],
        })
        sel_id, info = engine.resolve_song_api("我们的爱", strategy="first")
        self.assertEqual(sel_id, "372")
        self.assertFalse(info["possessiveFallback"])
        self.assertEqual(calls, ["我们的爱"])  # 只搜了一遍，未触发反转

    def test_possessive_reverse_search_when_no_title_hit(self):
        """『25时的命嫌』没有同名歌曲 -> 判定『歌手的歌』，改查『命嫌 25时』取第一。"""
        calls = self._patch_candidates({
            "25时的命嫌": [
                {"id": 99, "name": "編年史", "ar": [{"name": "中島みゆき"}]},
            ],
            "命嫌 25时": [
                {"id": 2623481920, "name": "命に嫌われている", "ar": [{"name": "カンザキイオリ"}]},
                {"id": 111, "name": "别的歌"},
            ],
        })
        sel_id, info = engine.resolve_song_api("25时的命嫌", strategy="first")
        self.assertEqual(sel_id, "2623481920")
        self.assertTrue(info["possessiveFallback"])
        self.assertEqual(info["searchQuery"], "命嫌 25时")
        self.assertEqual(calls, ["25时的命嫌", "命嫌 25时"])

    def test_possessive_fallback_miss_keeps_first_result(self):
        """反转查『YYY XXX』也没结果时，回退到原查询的第一条。"""
        calls = self._patch_candidates({
            "25时的命嫌": [
                {"id": 99, "name": "編年史", "ar": [{"name": "某人"}]},
            ],
            "命嫌 25时": [],
        })
        sel_id, info = engine.resolve_song_api("25时的命嫌", strategy="first")
        self.assertEqual(sel_id, "99")
        self.assertFalse(info["possessiveFallback"])
        self.assertEqual(calls, ["25时的命嫌", "命嫌 25时"])

    def test_possessive_does_not_apply_to_classic(self):
        """经典搜索保持文字评分算法，不触发反转。"""
        calls = self._patch_candidates({
            "25时的命嫌": [
                {"id": 99, "name": "編年史", "ar": [{"name": "某人"}]},
            ],
            "命嫌 25时": [{"id": 2623481920, "name": "命に嫌われている"}],
        })
        sel_id, info = engine.resolve_song_api("25时的命嫌", strategy="classic")
        self.assertEqual(sel_id, "99")
        self.assertFalse(info["possessiveFallback"])
        self.assertEqual(calls, ["25时的命嫌"])  # classic 只搜一遍

    def test_possessive_no_particle_no_reverse(self):
        """不含『的』的查询直接走 first 取第一。"""
        calls = self._patch_candidates({
            "被生命所厌恶": [
                {"id": 1911300549, "name": "命に嫌われている", "ar": [{"name": "カンザキイオリ"}]},
            ],
        })
        sel_id, info = engine.resolve_song_api("被生命所厌恶", strategy="first")
        self.assertEqual(sel_id, "1911300549")
        self.assertFalse(info["possessiveFallback"])
        self.assertEqual(calls, ["被生命所厌恶"])


class PlayingModeTest(unittest.TestCase):
    class FakeCDP:
        def __init__(self, mode):
            self.mode = mode
            self.clicks = 0

        def evaluate(self, expression, await_promise=False):
            if "button.click()" in expression:
                self.clicks += 1
                self.mode = "playOrder"
                return True
            return self.mode

    def test_already_order_mode_does_not_click(self):
        c = self.FakeCDP("playOrder")
        result = engine.ensure_order_mode(c)
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"])
        self.assertEqual(c.clicks, 0)

    def test_list_cycle_also_keeps_queue_order(self):
        c = self.FakeCDP("playCycle")
        result = engine.ensure_order_mode(c)
        self.assertTrue(result["ok"])
        self.assertFalse(result["changed"])
        self.assertEqual(c.clicks, 0)

    @patch("backend.cloudmusic.engine.time.sleep", lambda _: None)
    def test_random_mode_switches_to_order(self):
        c = self.FakeCDP("playRandom")
        result = engine.ensure_order_mode(c)
        self.assertTrue(result["ok"])
        self.assertTrue(result["changed"])
        self.assertEqual(result["playingMode"], "playOrder")
        self.assertEqual(c.clicks, 1)


if __name__ == "__main__":
    unittest.main()
