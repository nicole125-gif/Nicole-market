#!/usr/bin/env python3
"""
宏观Dashboard自动更新脚本
数据来源：直接抓取国家统计局官网，无AI估算
用法: python scripts/update_macro.py
"""

import re
import os
import subprocess
import urllib.request
from datetime import datetime

HTML_FILE = "index.html"

# ── 统计局数据源配置 ──────────────────────────────────────
# 每月统计局发布新数据后，只需更新这里的URL即可
NBS_SOURCES = [
    {
        "label": "工业增加值",
        "url": "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962782.html",
        # 从页面正文提取数值的正则（匹配"同比实际增长X.X%"）
        "pattern": r"规模以上工业增加值同比实际增长([\d.]+)%",
        "unit": "%",
        "trend_template": "↑ {period}同比",
        "period": "1-2月",
        "sparkData_2024": 5.1,
        "sparkData_2025": 5.7,
        "insight_template": "工业生产{period}同比增{value}%",
    },
    {
        "label": "制造业固投",
        "url": "https://www.stats.gov.cn/sj/zxfb/202603/t20260316_1962784.html",
        # 从页面正文提取制造业投资数值
        "pattern": r"制造业投资增长([\d.]+)%",
        "unit": "%",
        "trend_template": "{period}同比",
        "period": "1-2月",
        "sparkData_2024": 9.2,
        "sparkData_2025": 10.8,
        "insight_template": "制造业投资{period}增{value}%",
    },
]

# 其余指标暂用上次确认值（后续可逐步加入抓取）
STATIC_METRICS = [
    {
        "label": "GDP 增速",
        "value": 5.0, "unit": "%", "trend": "目标值",
        "insight": "结构性增长优于规模扩张",
        "sparkData": [4.6, 4.8, 5.0],
    },
    {
        "label": "出口增速",
        "value": 4.8, "unit": "%", "trend": "Shift",
        "insight": "高附加值组件替代传统代工",
        "sparkData": [5.9, 4.2, 4.8],
    },
    {
        "label": "PPI 走势",
        "value": 1.2, "unit": "%", "trend": "Recovery",
        "insight": "中下游利润空间重构",
        "sparkData": [-2.7, -0.8, 1.2],
    },
]

STATIC_SUMMARY = [
    {"label": "综合景气度",   "value": "Expansionary"},
    {"label": "政策向量",     "value": "Targeted Easing"},
    {"label": "外部压力指数", "value": "Moderate"},
    {"label": "数字经济比重", "value": "43.7%"},
]


# ── 抓取统计局页面并解析数值 ──────────────────────────────

def fetch_nbs_value(source: dict) -> dict | None:
    """抓取统计局页面，用正则提取目标数值，返回指标更新dict"""
    label = source["label"]
    url = source["url"]
    pattern = source["pattern"]

    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; market-dashboard/1.0)"}
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="ignore")

        match = re.search(pattern, html)
        if not match:
            print(f"⚠️  {label}：页面已抓取但正则未匹配，检查pattern")
            return None

        value = float(match.group(1))
        period = source["period"]
        trend = source["trend_template"].format(period=period)
        insight = source["insight_template"].format(period=period, value=value)
        spark = [source["sparkData_2024"], source["sparkData_2025"], value]

        print(f"✅ {label}：{value}{source['unit']}（来源：stats.gov.cn）")
        return {
            "label": label,
            "value": value,
            "unit": source["unit"],
            "trend": trend,
            "insight": insight,
            "sparkData": spark,
        }

    except Exception as e:
        print(f"⚠️  {label}：抓取失败（{e}）")
        return None


# ── HTML更新函数 ──────────────────────────────────────────

def read_html(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write_html(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✓ 已写入 {path}")

def update_one_metric(html: str, m: dict) -> str:
    label = m["label"]
    original = html

    # value（label与value跨行，用DOTALL+count=1精确匹配第一个）
    html = re.sub(
        rf'(label:\s*"{re.escape(label)}".*?value:\s*)[\d.\-]+',
        lambda match: match.group(1) + str(m["value"]),
        html, count=1, flags=re.DOTALL
    )

    # trend
    html = re.sub(
        rf'(label:\s*"{re.escape(label)}".*?trend:\s*)"[^"]*"',
        rf'\g<1>"{m["trend"]}"',
        html, count=1, flags=re.DOTALL
    )

    # insight
    html = re.sub(
        rf'(label:\s*"{re.escape(label)}".*?insight:\s*)"[^"]*"',
        rf'\g<1>"{m["insight"]}"',
        html, count=1, flags=re.DOTALL
    )

    # sparkData
    spark_str = "[" + ",".join(str(v) for v in m["sparkData"]) + "]"
    html = re.sub(
        rf'(label:\s*"{re.escape(label)}".*?sparkData:\s*)\[[^\]]*\]',
        rf'\g<1>{spark_str}',
        html, count=1, flags=re.DOTALL
    )

    if html == original:
        print(f"⚠️  {label}：HTML中未找到匹配，跳过")
    return html

def update_summary_stats(html: str, stats: list) -> str:
    lines = ["    summaryStats: ["]
    for i, s in enumerate(stats):
        comma = "," if i < len(stats) - 1 else ""
        lines.append(f'      {{ label: "{s["label"]}",   value: "{s["value"]}" }}{comma}')
    lines.append("    ],")
    new_block = "\n".join(lines)
    pattern = r'    summaryStats:\s*\[.*?\],'
    new_html = re.sub(pattern, new_block, html, flags=re.DOTALL)
    if new_html != html:
        print("✓ summaryStats 已更新")
    return new_html

def update_timestamp(html: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    new_html = re.sub(r'"20\d{2}-\d{2}-\d{2}"', f'"{today}"', html, count=1)
    print(f"✓ 时间戳 → {today}")
    return new_html

def git_push(filepath, message):
    subprocess.run(["git", "config", "user.name", "github-actions[bot]"], capture_output=True)
    subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], capture_output=True)
    subprocess.run(["git", "add", filepath], capture_output=True)
    diff = subprocess.run(["git", "diff", "--staged", "--quiet"])
    if diff.returncode == 0:
        print("ℹ️  内容无变化，跳过commit")
        return
    r = subprocess.run(["git", "commit", "-m", message], capture_output=True, text=True)
    print("✓ commit" if r.returncode == 0 else f"⚠️  commit失败: {r.stderr}")
    r = subprocess.run(["git", "push"], capture_output=True, text=True)
    print("✓ push" if r.returncode == 0 else f"⚠️  push失败: {r.stderr}")


# ── 主流程 ────────────────────────────────────────────────

def main():
    print(f"\n{'='*52}")
    print(f"宏观Dashboard更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    html = read_html(HTML_FILE)
    print(f"✓ 已读取 {HTML_FILE}（{len(html):,} 字符）\n")

    # 1. 抓取统计局实时数据
    print("[ 抓取国家统计局数据... ]")
    live_metrics = []
    for source in NBS_SOURCES:
        result = fetch_nbs_value(source)
        if result:
            live_metrics.append(result)

    # 2. 更新实时指标
    print(f"\n[ 更新 {len(live_metrics)} 个实时指标... ]")
    for m in live_metrics:
        html = update_one_metric(html, m)

    # 3. 更新静态指标（GDP/出口/PPI暂用固定值）
    print(f"\n[ 更新 {len(STATIC_METRICS)} 个静态指标... ]")
    for m in STATIC_METRICS:
        html = update_one_metric(html, m)

    # 4. 更新景气度条
    print("\n[ 更新 summaryStats... ]")
    html = update_summary_stats(html, STATIC_SUMMARY)

    # 5. 时间戳
    html = update_timestamp(html)

    # 6. 写入并推送
    write_html(HTML_FILE, html)
    msg = f"auto: 宏观数据更新 {datetime.now().strftime('%Y-%m-%d')}（统计局实时）"
    print(f"\n[ Git提交... ]")
    git_push(HTML_FILE, msg)

    print(f"\n{'='*52}")
    print("✅ 完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
