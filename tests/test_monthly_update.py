import copy
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MonthlyUpdateTests(unittest.TestCase):
    def test_apply_overrides_updates_tracks_kpis_and_review_notes(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        payload = {
            "date": "2026-06-05",
            "tracks": {"e2": {"heat": 82.8, "D": 85, "C": 82, "P": 75, "Pol": 90}},
            "kpis": [],
        }
        overrides = {
            "period": "2026-06",
            "tracks": {
                "e2": {
                    "heat": 84.0,
                    "D": 86,
                    "C": 83,
                    "P": 76,
                    "Pol": 90,
                    "tw": "半导体设备国产替代仍是本月最高优先级之一。",
                    "act": "优先跟踪北方华创、中微及先进封装设备链。",
                }
            },
            "track_use": {"e2": ["国产替代机会", "用于判断半导体设备国产化客户优先级。"]},
            "kpis": [{"v": "84.0", "l": "最高 Heat", "d": "半导体设备国产化", "c": "exp"}],
            "review_notes": ["请重点核查 e2 的政策分。"],
        }

        result, applied = monthly.apply_overrides(copy.deepcopy(payload), overrides)

        self.assertEqual(result["tracks"]["e2"]["heat"], 84.0)
        self.assertEqual(result["tracks"]["e2"]["tw"], "半导体设备国产替代仍是本月最高优先级之一。")
        self.assertEqual(result["track_use"]["e2"], ["国产替代机会", "用于判断半导体设备国产化客户优先级。"])
        self.assertEqual(result["kpis"][0]["d"], "半导体设备国产化")
        self.assertEqual(applied, ["track:e2", "track_use:e2", "kpis", "review_notes"])

    def test_build_monthly_summary_contains_expected_sections(self):
        monthly = load_module("scripts/monthly_update.py", "monthly_update")
        with tempfile.TemporaryDirectory() as tmp:
            summary_path = Path(tmp) / "2026-06-summary.md"
            payload = {
                "tracks": {
                    "e2": {"heat": 84.0, "delta": 1.2, "tr": "up"},
                    "p4": {"heat": 52.2, "delta": -5.3, "tr": "dn"},
                }
            }
            source_report = {
                "downloaded": [{"path": "reports/2026-06/example.pdf"}],
                "failed": [{"query": "半导体设备 国产化 月度 2026", "reason": "no allowed result"}],
            }

            monthly.write_summary(
                path=summary_path,
                period="2026-06",
                payload=payload,
                source_report=source_report,
                applied_overrides=["track:e2"],
                review_notes=["请重点核查半导体设备。"],
            )

            text = summary_path.read_text(encoding="utf-8")
            self.assertIn("# Nicole Intelligence Monthly Update · 2026-06", text)
            self.assertIn("新增报告数量：1", text)
            self.assertIn("最高 Heat：e2 84.0", text)
            self.assertIn("最大下滑：p4 -5.3", text)
            self.assertIn("track:e2", text)
            self.assertIn("请重点核查半导体设备。", text)

    def test_inject_scores_can_patch_track_use(self):
        inject = load_module("scripts/inject_scores.py", "inject_scores_module")
        html = """
<script>
const TRACK_USE = {
  zh: {
    e2:['国产替代机会','旧说明'],
    p2:['中试放大','旧说明']
  },
  en: {}
};
</script>
"""
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "index.html"
            path.write_text(html, encoding="utf-8")

            inject.inject_scores(
                {"track_use": {"e2": ["客户优先级", "用于判断半导体客户优先级。"]}},
                index_path=path,
                backup=False,
            )

            patched = path.read_text(encoding="utf-8")
            self.assertIn("e2:['客户优先级','用于判断半导体客户优先级。']", patched)
            self.assertIn("p2:['中试放大','旧说明']", patched)


if __name__ == "__main__":
    unittest.main()
