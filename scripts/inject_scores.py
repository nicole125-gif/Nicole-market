"""
inject_scores.py  —  PULSE 2026 数据注入模块
用法：在 update_news.py 跑完打分后调用 inject_scores(scores, path_to_index)

scores 格式（由 update_news.py 生成）：
{
  "date": "2026-04-08",           # 更新日期，写入 footer

  # ── 板块级（BM 对象）──
  "sectors": {
    "EI":  {"heat": 72.5, "tr": "up", "D": 82, "C": 80, "P": 68, "Pol": 86,
             "sum": "两会AI基建落地...", "sumAlert": "🔥",
             "insight": "<strong>液冷</strong>..."},
    "GI":  {...},
    "P&B": {...},
    "L&M": {...},
    "F&B": {...},
    "Macro": {...},
  },

  # ── 子赛道级（T 对象）──
  "tracks": {
    "e1": {"heat": 86.1, "tr": "up", "delta": 4.2, "D": 90, "C": 92, "P": 72, "Pol": 84,
           "data": ["数据点1", "数据点2", "数据点3"],
           "tw": "关键结论文字...",
           "act": "行动建议..."},
    ...
  },

  # ── 头部 KPI 栏（4个固定槽）──
  "kpis": [
    {"v": "86.1", "l": "最高 Heat",    "d": "↑ 液冷+关税双催化",  "c": "exp"},
    {"v": "到期",  "l": "司美格鲁肽",  "d": "3/20 仿制战启动",    "c": "dn"},
    {"v": "10%",  "l": "美国新关税",   "d": "122条 4月听证",      "c": "dn"},
    {"v": "50.4%","l": "3月制造业PMI", "d": "↑ 重返扩张区间",     "c": "up"},
  ]
}

所有字段都是可选的——只传你本次更新的字段，其余保持不变。
"""

import re
import json
import shutil
from datetime import date
from pathlib import Path


# ──────────────────────────────────────────────────────────
# 内部工具函数
# ──────────────────────────────────────────────────────────

def _js_str(v) -> str:
    """把 Python 值序列化成 JS 字面量（字符串加引号，数字直接写，list/dict 用 json）。"""
    if isinstance(v, str):
        # 保留 HTML 标签，只转义单引号
        escaped = v.replace("'", "\\'")
        return f"'{escaped}'"
    if isinstance(v, list):
        items = ",".join(_js_str(i) for i in v)
        return f"[{items}]"
    if isinstance(v, dict):
        pairs = ",".join(f"{k}:{_js_str(val)}" for k, val in v.items())
        return f"{{{pairs}}}"
    # number / bool / None
    if isinstance(v, bool):
        return "true" if v else "false"
    if v is None:
        return "null"
    return str(v)


def _patch_js_object_field(html: str, obj_name: str, key: str, field: str, new_val) -> str:
    """
    在形如  key:{..., field:OLD, ...}  的 JS 对象字面量中替换单个字段值。
    obj_name: 'BM' 或 'T'
    key:      'EI' / 'e1' / "P&B" 等
    field:    'heat' / 'D' / 'sum' 等
    new_val:  Python 值
    """
    new_js = _js_str(new_val)
    key_pat = re.escape(key)

    # ── 步骤 0：先定位父对象 BM={ 或 T={，限制搜索范围 ──
    parent_m = re.search(rf"\bconst {re.escape(obj_name)}\s*=\s*\{{", html)
    if not parent_m:
        print(f"  [WARN] parent object '{obj_name}' not found")
        return html
    search_start = parent_m.end()

    # 找父对象结束位置（粗略：找下一个 "};\n" 或 "};\r\n"）
    end_m = re.search(r"\};\s*\n", html[search_start:])
    search_end = search_start + end_m.end() if end_m else len(html)

    scope = html[search_start:search_end]

    # 找 key 入口（两种写法：  key:{  或  'key':{  或  "P&B":{  ）
    key_variants = [
        rf"(?<!\w){key_pat}:",        # 无引号
        rf"'{key_pat}':",             # 单引号
        rf'"{key_pat}":',             # 双引号
    ]
    key_re = "(?:" + "|".join(key_variants) + ")"

    m = re.search(key_re, scope)
    if not m:
        print(f"  [WARN] key '{key}' not found in {obj_name}")
        return html

    # 转回原始 html 的绝对位置
    start = search_start + m.start()

    # 在 start 之后找 field:VALUE
    # VALUE 分三类：
    #   1. 纯数字（含小数/负号）：  \-?\d+(\.\d+)?
    #   2. 带引号字符串（单引号，可含转义）：'(?:[^'\\]|\\.)*'
    #   3. 复合（稀少，暂不处理）
    field_pat = (
        rf"(?<!['\"\w]){re.escape(field)}:"   # 字段名（非属性名中间）
        r"(\-?\d+(?:\.\d+)?|'(?:[^'\\]|\\.)*')"  # 数字或单引号字符串
    )
    sub_html = html[start:]
    fm = re.search(field_pat, sub_html)
    if not fm:
        print(f"  [WARN] field '{field}' not found after key '{key}'")
        return html

    abs_start = start + fm.start()
    abs_end   = start + fm.end()

    # 构造替换串（保留字段名，只换值）
    field_len = len(field) + 1  # "field:"
    replacement = field + ":" + new_js
    html = html[:abs_start] + replacement + html[abs_end:]
    return html


def _patch_date(html: str, new_date: str) -> str:
    """替换 footer 里的更新日期，格式 YYYY-MM-DD。"""
    return re.sub(
        r"最近更新\s+\d{4}-\d{2}-\d{2}",
        f"最近更新 {new_date}",
        html,
    )


def _patch_kpis(html: str, kpis: list) -> str:
    """
    替换 KPI 数组字面量（在 <script> 里硬编码的那段 forEach）。
    只替换数组内容，保留 forEach 回调不动。
    """
    new_arr = json.dumps(kpis, ensure_ascii=False, indent=0)
    # 目标形态：[{v:'...',l:'...',d:'...',c:'...'},...]
    # 用 JS 单引号重写（保持原文件风格）
    def to_js_obj(k):
        return (
            "{" +
            f"v:'{k['v']}',l:'{k['l']}',d:'{k['d']}',c:'{k['c']}'" +
            "}"
        )
    js_arr = "[" + ",\n ".join(to_js_obj(k) for k in kpis) + "]"

    # 匹配现有数组：从 "[{v:" 到 ].forEach
    pat = r"\[(?:\{v:'[^']*'[^\]]*\},?\s*)+\](?=\.forEach)"
    m = re.search(pat, html, re.DOTALL)
    if not m:
        print("  [WARN] KPI array not found, skipping")
        return html
    return html[:m.start()] + js_arr + html[m.end():]


# ──────────────────────────────────────────────────────────
# 主入口
# ──────────────────────────────────────────────────────────

def inject_scores(
    scores: dict,
    index_path: str | Path = "index.html",
    backup: bool = True,
) -> None:
    """
    把 scores 字典里的新数据写回 index.html。

    参数
    ----
    scores     : 见模块顶部注释
    index_path : index.html 的路径（默认当前目录）
    backup     : True → 写入前先备份为 index.html.bak
    """
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(f"index.html not found: {path.resolve()}")

    html = path.read_text(encoding="utf-8")

    if backup:
        bak = path.with_suffix(".html.bak")
        shutil.copy2(path, bak)
        print(f"[inject] 备份已保存 → {bak}")

    changed = 0

    # ── 1. 板块级 (BM) ──
    SECTOR_FIELDS = ["heat", "tr", "D", "C", "P", "Pol", "sum", "sumAlert", "insight"]
    for key, vals in scores.get("sectors", {}).items():
        for field, new_val in vals.items():
            if field not in SECTOR_FIELDS:
                continue
            old_html = html
            html = _patch_js_object_field(html, "BM", key, field, new_val)
            # 也在 T 对象的板块子键里搜索（key 是板块代号，T 里没有，跳过）
            if html != old_html:
                print(f"  [BM] {key}.{field} → {new_val}")
                changed += 1

    # ── 2. 子赛道级 (T) ──
    TRACK_FIELDS = ["heat", "tr", "delta", "D", "C", "P", "Pol", "tw", "act"]
    for key, vals in scores.get("tracks", {}).items():
        for field, new_val in vals.items():
            if field == "data":
                # data 是数组，特殊处理
                new_js = _js_str(new_val)
                # 找 key:{...data:[...]...} 里的 data 数组
                key_variants = [rf"(?<!\w){re.escape(key)}:", rf"'{re.escape(key)}':", rf'"{re.escape(key)}":']
                key_re = "(?:" + "|".join(key_variants) + ")"
                m = re.search(key_re, html)
                if m:
                    sub = html[m.start():]
                    dm = re.search(r"data:\[.*?\]", sub, re.DOTALL)
                    if dm:
                        abs_s = m.start() + dm.start()
                        abs_e = m.start() + dm.end()
                        html = html[:abs_s] + f"data:{new_js}" + html[abs_e:]
                        print(f"  [T]  {key}.data → [{len(new_val)} items]")
                        changed += 1
                    else:
                        print(f"  [WARN] {key}.data array not found")
                continue

            if field not in TRACK_FIELDS:
                continue
            old_html = html
            html = _patch_js_object_field(html, "T", key, field, new_val)
            if html != old_html:
                print(f"  [T]  {key}.{field} → {new_val}")
                changed += 1

    # ── 3. 日期 ──
    if "date" in scores:
        html = _patch_date(html, scores["date"])
        print(f"  [date] → {scores['date']}")
        changed += 1

    # ── 4. KPI 栏 ──
    if "kpis" in scores:
        html = _patch_kpis(html, scores["kpis"])
        print(f"  [kpis] → {len(scores['kpis'])} slots updated")
        changed += 1

    path.write_text(html, encoding="utf-8")
    print(f"[inject] ✅ 完成，共更新 {changed} 个字段 → {path}")


# ──────────────────────────────────────────────────────────
# 快速自测（python inject_scores.py）
# ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys, os

    test_scores = {
        "date": str(date.today()),

        "sectors": {
            "EI":  {"heat": 73.0, "tr": "up", "D": 83, "C": 80, "P": 69, "Pol": 87},
            "GI":  {"heat": 76.2, "tr": "fl"},
            "P&B": {"heat": 64.0},
            "L&M": {"heat": 62.5},
            "F&B": {"heat": 54.0, "tr": "dn"},
            "Macro": {"heat": 51.0, "D": 51, "C": 45, "P": 57, "Pol": 63},
        },

        "tracks": {
            "e1": {"heat": 87.0, "delta": 4.5, "D": 91, "C": 93},
            "e2": {"heat": 80.5},
            "g1": {"heat": 76.0},
        },

        "kpis": [
            {"v": "87.0", "l": "最高 Heat",    "d": "↑ 液冷持续领跑",    "c": "exp"},
            {"v": "到期",  "l": "司美格鲁肽",  "d": "3/20 仿制战启动",   "c": "dn"},
            {"v": "10%",  "l": "美国新关税",   "d": "232条持续施压",     "c": "dn"},
            {"v": "50.4%","l": "3月制造业PMI", "d": "↑ 重返扩张区间",    "c": "up"},
        ],
    }

    # 用上传的文件做测试
    src = Path("/mnt/user-data/uploads/index.html")
    dst = Path("/home/claude/index_test.html")
    shutil.copy2(src, dst)

    print("=== PULSE inject_scores 自测 ===")
    inject_scores(test_scores, dst, backup=False)

    # 验证几个关键字段
    result = dst.read_text(encoding="utf-8")
    checks = [
        ("EI heat→73.0",   "heat:73.0"  in result),
        ("e1 heat→87.0",   "heat:87.0"  in result),
        ("date updated",   str(date.today()) in result),
        ("KPI slot 1",     "87.0"       in result),
    ]
    print("\n验证结果：")
    for label, ok in checks:
        print(f"  {'✅' if ok else '❌'} {label}")
