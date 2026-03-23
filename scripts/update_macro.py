#!/usr/bin/env python3
"""
宏观Dashboard自动更新脚本
只负责修改HTML文件，git操作由workflow负责
用法: python scripts/update_macro.py
"""

import re
import urllib.request
from datetime import datetime

HTML_FILE = "index.html"

NBS_SOURCES = [
    {
        "label": "工业增加值",
        "url": "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html",
        "pattern": r"规模以上工业增加值同比实际增长([\d.]+)%",
        "trend": "↑ 1-2月同比",
        "insight": "开年工业生产强劲",
        "sparkData": [5.1, 5.7, None],
    },
    {
        "label": "制造业固投",
        "url": "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962784.html",
        "pattern": r"制造业投资增长([\d.]+)%",
        "trend": "1-2月同比",
        "insight": "制造业投资稳步推进",
        "sparkData": [9.2, 10.8, None],
    },
]

STATIC_METRICS = [
    {"label": "GDP 增速",  "value": 5.0, "trend": "目标值",   "insight": "结构性增长优于规模扩张",   "sparkData": [4.6, 4.8, 5.0]},
    {"label": "出口增速",  "value": 4.8, "trend": "Shift",    "insight": "高附加值组件替代传统代工", "sparkData": [5.9, 4.2, 4.8]},
    {"label": "PPI 走势",  "value": 1.2, "trend": "Recovery", "insight": "中下游利润空间重构",       "sparkData": [-2.7, -0.8, 1.2]},
]

STATIC_SUMMARY = [
    {"label": "综合景气度",   "value": "Expansionary"},
    {"label": "政策向量",     "value": "Targeted Easing"},
    {"label": "外部压力指数", "value": "Moderate"},
    {"label": "数字经济比重", "value": "43.7%"},
]


def fetch_nbs(source):
    label = source["label"]
    try:
        req = urllib.request.Request(
            source["url"],
            headers={"User-Agent": "Mozilla/5.0 (compatible; market-dashboard/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            page = resp.read().decode("utf-8", errors="ignore")
        m = re.search(source["pattern"], page)
        if not m:
            print(f"⚠️  {label}：正则未匹配")
            return None
        value = float(m.group(1))
        spark = source["sparkData"][:]
        spark[2] = value
        print(f"✅ {label}：{value}%（stats.gov.cn）")
        return {"label": label, "value": value, "trend": source["trend"],
                "insight": source["insight"], "sparkData": spark}
    except Exception as e:
        print(f"⚠️  {label}：抓取失败（{e}）")
        return None


def update_metric(html, label, value, trend, insight, sparkData):
    spark_str = "[" + ",".join(str(v) for v in sparkData) + "]"
    positions = [m.start() for m in re.finditer(rf'"{re.escape(label)}"', html)]
    changed = 0
    for pos in reversed(positions):
        chunk = html[pos:pos+1500]
        new_chunk = chunk
        new_chunk = re.sub(r'(value:\s*)[\d.\-]+',      rf'\g<1>{value}',     new_chunk, count=1)
        new_chunk = re.sub(r'(trend:\s*)"[^"]*"',        rf'\g<1>"{trend}"',   new_chunk, count=1)
        new_chunk = re.sub(r'(insight:\s*)"[^"]*"',      rf'\g<1>"{insight}"', new_chunk, count=1)
        new_chunk = re.sub(r'(sparkData:\s*)\[[^\]]*\]', rf'\g<1>{spark_str}', new_chunk, count=1)
        if new_chunk != chunk:
            html = html[:pos] + new_chunk + html[pos+1500:]
            changed += 1
    print(f"✓ {label}：{changed}处更新 → value={value}%")
    return html


def update_summary(html, stats):
    lines = ["    summaryStats: ["]
    for i, s in enumerate(stats):
        comma = "," if i < len(stats)-1 else ""
        lines.append(f'      {{ label: "{s["label"]}",   value: "{s["value"]}" }}{comma}')
    lines.append("    ],")
    new_html = re.sub(r'    summaryStats:\s*\[.*?\],', "\n".join(lines), html, flags=re.DOTALL)
    if new_html != html:
        print("✓ summaryStats 已更新")
    return new_html


def main():
    print(f"\n{'='*52}")
    print(f"宏观Dashboard更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    print(f"✓ 读取 {HTML_FILE}（{len(html):,} 字符）\n")

    print("[ 抓取统计局数据... ]")
    for src in NBS_SOURCES:
        result = fetch_nbs(src)
        if result:
            html = update_metric(html, result["label"], result["value"],
                                 result["trend"], result["insight"], result["sparkData"])

    print("\n[ 更新静态指标... ]")
    for m in STATIC_METRICS:
        html = update_metric(html, m["label"], m["value"], m["trend"], m["insight"], m["sparkData"])

    print("\n[ 更新 summaryStats... ]")
    html = update_summary(html, STATIC_SUMMARY)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ 已写入 {HTML_FILE}")
    print(f"\n{'='*52}")
    print("✅ 脚本完成，等待workflow执行git push")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
