#!/usr/bin/env python3
"""
宏观Dashboard自动更新脚本
用法: python scripts/update_macro.py
"""

import re
import json
import os
import subprocess
from datetime import datetime

# ── 配置区 ────────────────────────────────────────────────
MINIMAX_API_KEY = os.environ.get("MINIMAX_API_KEY", "")
HTML_FILE = "index.html"

# ── Prompt：让MiniMax返回5个指标的最新值 ──────────────────
PROMPT_METRICS = """
你是中国宏观经济分析师。今天是{date}。

请根据中国国家统计局最新公布的数据，填写以下5个宏观指标的当前值。
如果某项数据尚未公布2026年全年值，填写最新可得的月度或季度数据，并在trend字段注明。

严格按以下JSON格式返回，不要任何多余文字、不要markdown代码块：

{{
  "metrics": [
    {{
      "label": "GDP 增速",
      "value": 5.0,
      "unit": "%",
      "trend": "+0.2%",
      "insight": "结构性增长优于规模扩张",
      "sparkData": [4.6, 4.8, 5.0]
    }},
    {{
      "label": "工业增加值",
      "value": 6.2,
      "unit": "%",
      "trend": "↑ Upward",
      "insight": "新质生产力贡献率超35%",
      "sparkData": [5.1, 5.7, 6.2]
    }},
    {{
      "label": "制造业固投",
      "value": 11.4,
      "unit": "%",
      "trend": "Stable",
      "insight": "数字化转型进入产线深水区",
      "sparkData": [9.2, 10.8, 11.4]
    }},
    {{
      "label": "出口增速",
      "value": 4.8,
      "unit": "%",
      "trend": "Shift",
      "insight": "高附加值组件替代传统代工",
      "sparkData": [5.9, 4.2, 4.8]
    }},
    {{
      "label": "PPI 走势",
      "value": 1.2,
      "unit": "%",
      "trend": "Recovery",
      "insight": "中下游利润空间重构",
      "sparkData": [-2.7, -0.8, 1.2]
    }}
  ],
  "summaryStats": [
    {{ "label": "综合景气度", "value": "Expansionary" }},
    {{ "label": "政策向量",   "value": "Targeted Easing" }},
    {{ "label": "外部压力指数", "value": "Moderate" }},
    {{ "label": "数字经济比重", "value": "43.7%" }}
  ],
  "dataDate": "说明数据来源时间，如：统计局2026年2月公报"
}}

要求：
- sparkData始终保持3个数字：[2024年值, 2025年值, 最新值]
- value和sparkData最后一项保持一致
- insight不超过12个字
- trend用简短英文或中文符号表达方向
""".format(date=datetime.now().strftime("%Y年%m月%d日"))


# ── 核心函数 ──────────────────────────────────────────────

def call_minimax(prompt: str) -> dict:
    import urllib.request
    url = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {MINIMAX_API_KEY}"
    }
    payload = {
        "model": "abab6.5s-chat",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": 1000
    }
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers=headers, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        result = json.loads(resp.read())

    content = result["choices"][0]["message"]["content"]
    content = re.sub(r"```json\s*", "", content)
    content = re.sub(r"```\s*", "", content)
    return json.loads(content.strip())


def read_html(filepath: str) -> str:
    with open(filepath, "r", encoding="utf-8") as f:
        return f.read()


def write_html(filepath: str, content: str):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"✓ 已写入 {filepath}")


def update_summary_stats(html: str, new_stats: list) -> str:
    lines = ["    summaryStats: ["]
    for i, stat in enumerate(new_stats):
        comma = "," if i < len(new_stats) - 1 else ""
        lines.append(f'      {{ label: "{stat["label"]}",   value: "{stat["value"]}" }}{comma}')
    lines.append("    ],")
    new_block = "\n".join(lines)
    pattern = r'    summaryStats:\s*\[.*?\],'
    new_html = re.sub(pattern, new_block, html, flags=re.DOTALL)
    if new_html == html:
        print("⚠️  summaryStats 未找到匹配")
    else:
        print("✓ summaryStats 已更新")
    return new_html


def update_metrics(html: str, metrics: list) -> str:
    """
    更新METRICS数组中每个指标的 value / trend / insight / sparkData。
    策略：逐个指标按label定位，精确替换对应字段，不碰actions/dataSource等复杂嵌套。
    """
    updated = 0
    for m in metrics:
        label = m["label"]

        # 匹配该指标的 value 字段（label后面紧跟的value）
        # 模式：label:"GDP 增速",...,value:5.0
        # 用非贪婪匹配定位到这个指标块内的value/trend/insight/sparkData

        # 替换 value
        pattern_val = rf'(label:"{re.escape(label)}"[^}}]{{0,30}}value:)\s*[\d.\-]+'
        new_html = re.sub(pattern_val, rf'\g<1>{m["value"]}', html)

        # 替换 trend（带引号的字符串）
        pattern_trend = rf'(label:"{re.escape(label)}".*?trend:)"[^"]*"'
        new_html = re.sub(pattern_trend, rf'\1"{m["trend"]}"', new_html, flags=re.DOTALL)

        # 替换 insight
        pattern_insight = rf'(label:"{re.escape(label)}".*?insight:)"[^"]*"'
        new_html = re.sub(pattern_insight, rf'\1"{m["insight"]}"', new_html, flags=re.DOTALL)

        # 替换 sparkData（数组）
        spark_str = "[" + ",".join(str(v) for v in m["sparkData"]) + "]"
        pattern_spark = rf'(label:"{re.escape(label)}".*?sparkData:)\[[^\]]*\]'
        new_html = re.sub(pattern_spark, rf'\1{spark_str}', new_html, flags=re.DOTALL)

        if new_html != html:
            print(f"✓ {label}: value={m['value']}{m['unit']}  sparkData={m['sparkData']}")
            updated += 1
            html = new_html
        else:
            print(f"⚠️  {label}: 未找到匹配，跳过")

    print(f"\n共更新 {updated}/{len(metrics)} 个指标")
    return html


def update_meta_timestamp(html: str) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    pattern = r'"20\d{2}-\d{2}-\d{2}"'
    new_html = re.sub(pattern, f'"{today}"', html, count=1)
    print(f"✓ 时间戳已更新为 {today}")
    return new_html


def git_commit_push(filepath: str, message: str):
    cmds = [
        ["git", "config", "user.name", "github-actions[bot]"],
        ["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"],
        ["git", "add", filepath],
    ]
    for cmd in cmds:
        subprocess.run(cmd, capture_output=True)

    # 只有有变化才commit
    diff = subprocess.run(["git", "diff", "--staged", "--quiet"])
    if diff.returncode == 0:
        print("ℹ️  无内容变化，跳过commit")
        return

    for cmd in [["git", "commit", "-m", message], ["git", "push"]]:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"⚠️  {' '.join(cmd)} 失败:\n{result.stderr}")
        else:
            print(f"✓ {' '.join(cmd)}")


# ── 备用数据（API失败时使用）────────────────────────────────
FALLBACK = {
    "metrics": [
        {"label": "GDP 增速",   "value": 5.0,  "unit": "%", "trend": "+0.2%",     "insight": "结构性增长优于规模扩张",   "sparkData": [4.6, 4.8, 5.0]},
        {"label": "工业增加值", "value": 6.2,  "unit": "%", "trend": "↑ Upward",  "insight": "新质生产力贡献率超35%",   "sparkData": [5.1, 5.7, 6.2]},
        {"label": "制造业固投", "value": 11.4, "unit": "%", "trend": "Stable",    "insight": "数字化转型进入产线深水区", "sparkData": [9.2, 10.8, 11.4]},
        {"label": "出口增速",   "value": 4.8,  "unit": "%", "trend": "Shift",     "insight": "高附加值组件替代传统代工", "sparkData": [5.9, 4.2, 4.8]},
        {"label": "PPI 走势",   "value": 1.2,  "unit": "%", "trend": "Recovery",  "insight": "中下游利润空间重构",       "sparkData": [-2.7, -0.8, 1.2]},
    ],
    "summaryStats": [
        {"label": "综合景气度",   "value": "Expansionary"},
        {"label": "政策向量",     "value": "Targeted Easing"},
        {"label": "外部压力指数", "value": "Moderate"},
        {"label": "数字经济比重", "value": "43.7%"},
    ]
}


# ── 主流程 ────────────────────────────────────────────────

def main():
    print(f"\n{'='*52}")
    print(f"宏观Dashboard更新 · {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"{'='*52}\n")

    html = read_html(HTML_FILE)
    print(f"✓ 已读取 {HTML_FILE}（{len(html):,} 字符）\n")

    # 调用MiniMax
    data = FALLBACK
    if MINIMAX_API_KEY:
        print("[ 调用 MiniMax API... ]")
        try:
            data = call_minimax(PROMPT_METRICS)
            date_note = data.get("dataDate", "")
            print(f"✓ API返回成功  数据来源：{date_note}\n")
        except Exception as e:
            print(f"⚠️  API失败（{e}），使用备用数据\n")
            data = FALLBACK
    else:
        print("⚠️  未设置 MINIMAX_API_KEY，使用备用数据\n")

    # 更新HTML
    print("[ 更新 METRICS 数组... ]")
    html = update_metrics(html, data.get("metrics", FALLBACK["metrics"]))

    print("\n[ 更新 summaryStats... ]")
    html = update_summary_stats(html, data.get("summaryStats", FALLBACK["summaryStats"]))

    print("\n[ 更新时间戳... ]")
    html = update_meta_timestamp(html)

    write_html(HTML_FILE, html)

    print("\n[ Git 提交... ]")
    msg = f"auto: 宏观数据更新 {datetime.now().strftime('%Y-%m-%d')}"
    git_commit_push(HTML_FILE, msg)

    print(f"\n{'='*52}")
    print("✅ 全部完成")
    print(f"{'='*52}\n")


if __name__ == "__main__":
    main()
