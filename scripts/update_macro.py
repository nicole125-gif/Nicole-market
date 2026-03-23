#!/usr/bin/env python3
"""
宏观Dashboard更新脚本
数据来源：直接解析 tradingeconomics.com/china/indicators 页面表格
该页面数据在HTML里，无需JS渲染
git操作由workflow负责
"""

import re
import urllib.request
from datetime import datetime

HTML_FILE = "index.html"

# 指标名称对应TE页面表格中的链接文字
INDICATOR_MAP = {
    "工业增加值": {
        "te_name":       "Industrial Production",
        "trend_tmpl":    "↑ {date}同比",
        "insight_tmpl":  "工业生产同比{value}%",
        "sparkData_2024": 5.1,
        "sparkData_2025": 5.7,
    },
    "PPI 走势": {
        "te_name":       "Producer Prices Change",
        "trend_tmpl":    "{date}同比",
        "insight_tmpl":  "PPI同比{value}%",
        "sparkData_2024": -2.7,
        "sparkData_2025": -0.8,
    },
    "出口增速": {
        "te_name":       "Exports YoY",
        "trend_tmpl":    "{date}同比",
        "insight_tmpl":  "出口同比{value}%",
        "sparkData_2024": 5.9,
        "sparkData_2025": 4.2,
    },
    "GDP 增速": {
        "te_name":       "GDP Annual Growth Rate",
        "trend_tmpl":    "{date}季度同比",
        "insight_tmpl":  "GDP同比{value}%",
        "sparkData_2024": 4.6,
        "sparkData_2025": 4.8,
    },
}

STATIC_METRICS = [
    {"label": "制造业固投", "value": 3.1, "trend": "1-2月同比", "insight": "制造业投资稳步推进", "sparkData": [9.2, 10.8, 3.1]},
]

STATIC_SUMMARY = [
    {"label": "综合景气度",   "value": "Expansionary"},
    {"label": "政策向量",     "value": "Targeted Easing"},
    {"label": "外部压力指数", "value": "Moderate"},
    {"label": "数字经济比重", "value": "43.7%"},
]


def fetch_te_table() -> dict:
    """
    抓取 tradingeconomics.com/china/indicators 页面表格
    返回 {indicator_name: {"value": float, "date": str}} 字典
    """
    url = "https://tradingeconomics.com/china/indicators"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        }
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        page = r.read().decode("utf-8", errors="ignore")

    results = {}
    # 解析表格：指标名\n</a></td>\n<td>数值</td>
    rows = re.findall(
        r'([^\n<]+)\s*\n\s*</a></td>\s*\n\s*<td>([-\d.]+)</td>',
        page
    )
    for name, value in rows:
        name = name.strip()
        try:
            results[name] = float(value.strip())
        except ValueError:
            pass

    return results


def update_metric(html, label, value, trend, insight, sparkData):
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
    print(f"{'✅' if changed else '⚠️ '} {label}: {changed}处写入 → {value}%")
    return html


def update_summary(html, stats):
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

    # 抓取TE表格
    print("[ 抓取 tradingeconomics.com/china/indicators 表格... ]")
    try:
        te_data = fetch_te_table()
        print(f"✓ 获取到 {len(te_data)} 个指标\n")
    except Exception as e:
        print(f"❌ 抓取失败: {e}")
        te_data = {}

    # 更新指标
    today = datetime.now().strftime("%Y-%m")
    for label, cfg in INDICATOR_MAP.items():
        te_name = cfg["te_name"]
        if te_name in te_data:
            value   = te_data[te_name]
            trend   = cfg["trend_tmpl"].format(date=today)
            insight = cfg["insight_tmpl"].format(value=value)
            spark   = [cfg["sparkData_2024"], cfg["sparkData_2025"], value]
            print(f"✅ {label}: {value}% (来自TE表格)")
            html = update_metric(html, label, value, trend, insight, spark)
        else:
            print(f"⚠️  {label}: 表格中未找到 '{te_name}'")

    print("\n[ 静态指标... ]")
    for m in STATIC_METRICS:
        html = update_metric(html, m["label"], m["value"], m["trend"], m["insight"], m["sparkData"])

    print("\n[ summaryStats... ]")
    html = update_summary(html, STATIC_SUMMARY)

    with open(HTML_FILE, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ 写入完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
