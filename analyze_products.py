"""
产品数据分析 - 使用 Claude API（SimpleAI 中转）
输入：data/products_raw.json
输出：data/products_analysis.json
"""

import json
import os
import time
import requests
from pathlib import Path
from datetime import datetime

# ── API 配置 ──
API_KEY  = os.environ.get("CLAUDE_API_KEY", "")
BASE_URL = os.environ.get("CLAUDE_BASE_URL", "https://key.simpleai.com.cn")
MODEL    = "claude-sonnet-4-6"

INPUT  = Path("data/products_raw.json")
OUTPUT = Path("data/products_analysis.json")

SYSTEM = """你是一个工业阀门行业分析师，专注卫生级、流体控制领域。
分析竞品产品时重点关注：产品定位、目标行业、技术差异化。
只返回 JSON，不加任何解释文字。"""

PROMPT = """分析以下阀门竞品信息：

公司：{company}
产品名：{name}
描述：{desc}

返回 JSON：
{{
  "product_type": "产品类型（隔膜阀/球阀/蝶阀/调节阀/电磁阀等）",
  "target_industries": ["目标行业列表"],
  "key_features": ["2-3个核心技术特点"],
  "price_tier": "高端/中高端/中端",
  "threat_level": 1到5的整数,
  "threat_reason": "对客户威胁原因（一句话，20字内）",
  "opportunity": "客户可针对的差异化机会（一句话，20字内）"
}}"""


def call_claude(product):
    """调用 Claude API（SimpleAI 中转）"""
    if not API_KEY:
        return rule_based_analysis(product)

    try:
        r = requests.post(
            f"{BASE_URL}/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {API_KEY}",
                "Content-Type":  "application/json",
            },
            json={
                "model": MODEL,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user",   "content": PROMPT.format(
                        company=product["company"],
                        name=product["name"],
                        desc=product.get("desc", "")[:200]
                    )}
                ],
                "temperature": 0.1,
                "max_tokens":  400,
            },
            timeout=25
        )
        content = r.json()["choices"][0]["message"]["content"]
        content = content.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return json.loads(content)

    except Exception as e:
        print(f"    Claude API 失败: {e}")
        return rule_based_analysis(product)


def rule_based_analysis(product):
    """无 API Key 时的规则降级"""
    name    = product["name"].lower()
    desc    = product.get("desc", "").lower()
    company = product["company"]
    text    = name + " " + desc

    ptype = "通用阀门"
    for t, keys in [
        ("隔膜阀", ["diaphragm", "membrane"]),
        ("球阀",   ["ball valve", "ball"]),
        ("蝶阀",   ["butterfly"]),
        ("调节阀", ["control valve", "regul"]),
        ("电磁阀", ["solenoid"]),
    ]:
        if any(k in text for k in keys):
            ptype = t
            break

    industries = []
    for ind, keys in [
        ("制药/生物制品", ["pharma", "bio", "sterile", "gmp"]),
        ("食品饮料",     ["food", "beverage", "dairy"]),
        ("化工",        ["chemical", "chem"]),
        ("水处理",      ["water treatment"]),
        ("半导体",      ["semicon", "ultra pure"]),
    ]:
        if any(k in text for k in keys):
            industries.append(ind)

    threat = 5 if company == "Bürkert" else 4 if company == "Gemü" else 3

    return {
        "product_type":      ptype,
        "target_industries": industries or ["通用工业"],
        "key_features":      ["待补充"],
        "price_tier":        "高端" if company in ["Bürkert", "Gemü"] else "中高端",
        "threat_level":      threat,
        "threat_reason":     f"{company} 在 {ptype} 领域产品成熟",
        "opportunity":       "价格与交期优势"
    }


def generate_summary(analyzed):
    by_company = {}
    for p in analyzed:
        by_company.setdefault(p["company"], []).append(p)

    summary = {}
    for company, products in by_company.items():
        analyses = [p.get("analysis", {}) for p in products]
        threats  = [a.get("threat_level", 3) for a in analyses]

        all_ind = []
        for a in analyses:
            all_ind += a.get("target_industries", [])
        ind_count = {}
        for i in all_ind:
            ind_count[i] = ind_count.get(i, 0) + 1

        type_count = {}
        for a in analyses:
            t = a.get("product_type", "")
            if t:
                type_count[t] = type_count.get(t, 0) + 1

        summary[company] = {
            "product_count":       len(products),
            "avg_threat_level":    round(sum(threats)/len(threats), 1) if threats else 0,
            "top_industries":      sorted(ind_count, key=ind_count.get, reverse=True)[:3],
            "product_type_dist":   type_count,
            "high_threat_products": [
                p["name"] for p in products
                if p.get("analysis", {}).get("threat_level", 0) >= 4
            ][:5]
        }
    return summary


def main():
    if not INPUT.exists():
        print("未找到 products_raw.json，请先运行 scrape_products.py")
        return

    with open(INPUT, encoding="utf-8") as f:
        data = json.load(f)

    products = data.get("products", [])
    print(f"\n{'='*50}")
    print(f"竞品产品分析  {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"API: {'Claude (SimpleAI)' if API_KEY else '规则降级模式'}")
    print(f"共 {len(products)} 个产品")
    print(f"{'='*50}\n")

    analyzed = []
    for i, p in enumerate(products):
        print(f"  [{i+1}/{len(products)}] {p['company']} | {p['name'][:40]}")
        p["analysis"] = call_claude(p)
        analyzed.append(p)
        time.sleep(0.5)

    summary = generate_summary(analyzed)

    with open(OUTPUT, "w", encoding="utf-8") as f:
        json.dump({
            "analyzed_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "model":       MODEL,
            "total":       len(analyzed),
            "summary":     summary,
            "products":    analyzed
        }, f, ensure_ascii=False, indent=2)

    print(f"\n→ 写入: {OUTPUT}")
    print("\n── 竞品摘要 ──")
    for company, s in summary.items():
        print(f"\n{company}")
        print(f"  产品数:     {s['product_count']}")
        print(f"  平均威胁:   {s['avg_threat_level']}/5")
        print(f"  主要行业:   {', '.join(s['top_industries'])}")
        print(f"  高威胁产品: {', '.join(s['high_threat_products'][:3]) or '无'}")


if __name__ == "__main__":
    main()
