#!/usr/bin/env python3
"""
宏观Dashboard更新脚本
数据来源：Trading Economics API（guest:guest免费key，境外可访问）
git操作由workflow负责
"""

import re
import json
import urllib.request
from datetime import datetime

HTML_FILE = "index.html"
TE_KEY = "guest:guest"

# ── Trading Economics 指标配置 ────────────────────────────
# 指标名称参考：https://tradingeconomics.com/china/indicators
TE_SOURCES = [
    {
        "label":        "工业增加值",
        "te_indicator": "industrial-production",
        "trend_tmpl":   "↑ {date}同比",
        "insight_tmpl": "工业生产同比{value}%",
        "sparkData_2024": 5.1,
        "sparkData_2025": 5.7,
    },
    {
        "label":        "PPI 走势",
        "te_indicator": "producer-prices-change",
        "trend_tmpl":   "{date}同比",
        "insight_tmpl": "PPI同比{value}%",
        "sparkData_2024": -2.7,
        "sparkData_2025": -0.8,
    },
    {
        "label":        "出口增速",
        "te_indicator": "exports-yoy",
        "trend_tmpl":   "{date}同比",
        "insight_tmpl": "出口同比{value}%",
        "sparkData_2024": 5.9,
        "sparkData_2025": 4.2,
    },
    {
        "label":        "GDP 增速",
        "te_indicator": "gdp-growth-annual",
        "trend_tmpl":   "{date}年增速",
        "insight_tmpl": "GDP同比{value}%",
        "sparkData_2024": 4.6,
        "sparkData_2025": 4.8,
    },
]

# 无对应TE指标的，保持固定值
STATIC_METRICS = [
    {"label": "制造业固投", "value": 3.1, "trend": "1-2月同比", "insight": "制造业投资稳步推进", "sparkData": [9.2, 10.8, 3.1]},
]

STATIC_SUMMARY = [
    {"label": "综合景气度",   "value": "Expansionary"},
    {"label": "政策向量",     "value": "Targeted Easing"},
    {"label": "外部压力指数", "value": "Moderate"},
    {"label": "数字经济比重", "value": "43.7%"},
]


def fetch_te(source: dict) -> dict | None:
    label = source["te_indicator"]
    name  = source["label"]
    url = f"https://api.tradingeconomics.com/country/china/indicator/{label}?c={TE_KEY}&f=json"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = json.loads(r.read())

        if not data:
            print(f"⚠️  {name}: 返回空数据")
            return None

        record = data[0]
        value  = round(float(record.get("LastValue") or record.get("Value") or 0), 1)
        date   = str(record.get("LastUpdate", ""))[:7]
        trend  = source["trend_tmpl"].format(date=date)
        insight= source["insight_tmpl"].format(value=value)
        spark  = [source["sparkData_2024"], source["sparkData_2025"], value]

        print(f"✅ {name}: {value}%（{date}，TradingEconomics）")
        return {"label": name, "value": value, "trend": trend, "insight": insight, "sparkData": spark}

    except Exception as e:
        print(f"⚠️  {name}: 获取失败（{e}）")
        return None


def update_metric(html: str, label: str, value, trend: str, insight: str, sparkData: list) -> str:
    spark_str = "[" + ",".join(str(v) for v in sparkData) + "]"
    positions = [m.start() for m in re.finditer(rf'"{re.escape(label)}"', html)]
    if not positions:
        print(f"⚠️  {label}: HTML中未找到")
        return html
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
    print(f"{'✅' if changed else '⚠️ '} {label}: {changed}处更新 → {value}%")
    return html


def update_summary(html: str, stats: list) -> str:
    lines = ["    summaryStats: ["]
    for i, s in enumerate(stats):
        comma = "," if i < len(stats)-1 else ""
        lines.append(f'      {{ label: "{s["label"]}",   value: "{s["value"]}" }}{comma}')
    lines.append("    ],")
    new_html = re.sub(r'    summaryStats:\s*\[.*?\],', "\n".join(lines), html, flags=re.DOTALL)
    if new_html != html:
        print("✅ summaryStats 已更新")
    return new_html


def main():
    print(f"\n{'='*52}")
    print(f"宏观Dashboard更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    with open(HTML_FILE, "r", encoding="utf-8") as f:
        html = f.read()
    print(f"✓ 读取 {HTML_FILE}（{len(html):,} 字符）\n")

    # 1. Trading Economics实时数据
    print("[ Trading Economics API... ]")
    for src in TE_SOURCES:
        result = fetch_te(src)
        if result:
            html = update_metric(html, result["label"], result["value"],
                                 result["trend"], result["insight"], result["sparkData"])

    # 2. 静态指标
    print("\n[ 静态指标... ]")
    for m in STATIC_METRICS:
        html = update_metric(html, m["label"], m["value"], m["trend"], m["insight"], m["sparkData"])

    # 3. summaryStats
    print("\n[ summaryStats... ]")
    html = update_summary(html, STATIC_SUMMARY)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ 写入完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
