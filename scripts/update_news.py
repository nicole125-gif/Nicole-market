"""
update_news.py  —  PULSE 2026 每月自动更新脚本 (Claude API + web_search 版)
功能：
  1. 调用 Claude API (with web_search) 搜索 20 个子赛道最新动态并打分
  2. 计算 6 个板块综合分
  3. 保存历史到 data/history.json
  4. 注入 index.html（调用 inject_scores.py）
  5. 抓取制药装备行业动态 → 注入 pharma.html

依赖：anthropic>=0.40.0
GitHub Secret：ANTHROPIC_API_KEY
"""

import os
import re
import json
import time
import datetime
import anthropic

# ══════════════════════════════════════════════════════════════
# 1. 子赛道配置（id 必须和 index.html 里的 T 对象 key 对应）
# ══════════════════════════════════════════════════════════════
TRACKS = [
    {"id": "e1", "name": "液冷数据中心", "board": "EI",
     "search_query": "AI液冷数据中心 CDU冷板 液冷渗透率 2026",
     "strategy": "聚焦AI液冷（CDU/冷板/浸没式），关注算力基础设施液冷渗透率提升。"},
    {"id": "e2", "name": "半导体设备国产化", "board": "EI",
     "search_query": "半导体设备国产化 北方华创 中微公司 DRAM涨价 晶圆厂扩产 2026",
     "strategy": "聚焦半导体设备国产化，关注晶圆厂扩产和出口管制带来的国产替代机会。"},
    {"id": "e3", "name": "绿氢电解槽", "board": "EI",
     "search_query": "PEM电解槽 绿氢 AEM电解槽招标 质子交换膜制氢 2026",
     "strategy": "只关注PEM/AEM/SOEC技术路线。ALK/碱性电解槽不计入打分（价格战内卷）。如果新闻全是ALK，D/C均给40分以下。"},
    {"id": "e4", "name": "燃料电池", "board": "EI",
     "search_query": "燃料电池重卡 FCEV销量 氢燃料电池补贴政策 2026",
     "strategy": "关注燃料电池重卡/港口/钢厂场景，以及燃料电池测试台设备需求。"},
    {"id": "g1", "name": "锂电设备", "board": "GI",
     "search_query": "宁德时代扩产 先导智能订单 赢合科技 固态电池产线 锂电设备 2026",
     "strategy": "关注宁德时代/先导智能/赢合科技锂电设备链，聚焦固态电池和海外产能扩张设备需求。"},
    {"id": "p1", "name": "生物药国内产线", "board": "P&B",
     "search_query": "司美格鲁肽仿制药 GLP-1国内产能 ADC国内生产 多肽CDMO国内 2026",
     "strategy": "关注国内生物药产业链在建项目和本土需求。国内临床/NMPA获批/本土扩产→D分高；License-out出海→D分低（产能外流）。"},
    {"id": "p2", "name": "合成生物学", "board": "P&B",
     "search_query": "合成生物学中试 华恒生物 凯赛生物扩产 生物制造发酵罐 2026",
     "strategy": "关注合成生物学中试和量产设备（发酵罐/分离纯化），华恒/凯赛等扩产信号优先。"},
    {"id": "p3", "name": "生物药融资", "board": "P&B",
     "search_query": "生物医药投融资 创新药融资 生物科技一级市场 2026",
     "strategy": "关注生物医药一级市场融资，作为3-5年后设备需求的领先指标。"},
    {"id": "p4", "name": "制药装备Capex", "board": "P&B",
     "search_query": "制药装备招标 楚天科技订单 东富龙业绩 医药固定资产投资 FAI 2026",
     "strategy": "关注制药装备资本支出（楚天科技/东富龙），医药FAI是最直接的设备需求信号。"},
    {"id": "p5", "name": "CDMO订单景气", "board": "P&B",
     "search_query": "CDMO订单 凯莱英GLP-1 药明康德业绩 TIDES多肽 ADC CDMO询单 2026",
     "strategy": "关注CDMO订单景气（药明康德/凯莱英），聚焦TIDES多肽/ADC/GLP-1产线询单。"},
    {"id": "l1", "name": "质谱色谱仪器", "board": "L&M",
     "search_query": "质谱仪国产替代 禾信仪器 谱育科技 色谱仪进口替代 分析仪器 2026",
     "strategy": "关注质谱/色谱仪器国产替代（禾信/谱育），聚焦进口替代率和政府采购国产化政策。"},
    {"id": "l2", "name": "基因测序", "board": "L&M",
     "search_query": "华大智造测序仪 因美纳禁令 测序仪国产替代 基因测序市场 2026",
     "strategy": "关注基因测序国产替代（华大智造/真迈），因美纳禁令是最强催化信号。"},
    {"id": "l3", "name": "医疗IVD", "board": "L&M",
     "search_query": "IVD体外诊断集采 化学发光国产化 迈瑞医疗 POCT市场 2026",
     "strategy": "关注IVD仪器（化学发光/POCT/分子诊断）销量信号，包括采购扩张、国产替代。"},
    {"id": "f1", "name": "食品制造FAI", "board": "F&B",
     "search_query": "食品制造固定资产投资 预制菜产线 食品装备招标 烘焙食品机械 2026",
     "strategy": "关注食品制造装备（预制菜/烘焙产线），FAI是核心信号。"},
    {"id": "f2", "name": "酒饮料制造FAI", "board": "F&B",
     "search_query": "白酒产能投资 酒饮料固定资产投资 碳酸饮料扩产 啤酒产线 2026",
     "strategy": "关注白酒/饮料制造设备，白酒新建产能和存量替换，碳酸饮料产线同样跟踪。"},
    {"id": "f3", "name": "食品饮料消费端", "board": "F&B",
     "search_query": "食品饮料消费 功能饮品无糖茶 餐饮消费 预制菜消费增长 社零数据 2026",
     "strategy": "关注食品饮料消费端，功能饮品/预制菜消费增长优先，作为设备投资滞后指标。"},
    {"id": "f4", "name": "食品添加剂合成生物", "board": "F&B",
     "search_query": "赤藓糖醇代糖扩产 益生菌产能 天然甜味剂市场 合成生物发酵 2026",
     "strategy": "关注食品添加剂合成生物发酵设备（赤藓糖醇/益生菌/天然甜味剂产能扩张）。"},
    {"id": "m1", "name": "制造业PMI", "board": "Macro",
     "search_query": "中国制造业PMI 财新PMI 官方PMI 制造业景气指数 2026",
     "strategy": "关注制造业PMI作为宏观景气核心信号，聚焦生产/新订单/中小企业分项。"},
    {"id": "m2", "name": "M2社融CPI", "board": "Macro",
     "search_query": "中国M2 社会融资规模 央行货币政策 降准降息 CPI PPI 2026",
     "strategy": "关注M2/社融/降准降息货币政策信号，对制造业投资的流动性支撑。"},
    {"id": "m3", "name": "固定资产投资工业增加值", "board": "Macro",
     "search_query": "中国固定资产投资 制造业FAI 规上工业增加值 高技术制造业 2026",
     "strategy": "关注固定资产投资（尤其制造业FAI）和规上工业增加值，高技术制造业优先。"},
]

# ══════════════════════════════════════════════════════════════
# 2. 板块综合分权重
# ══════════════════════════════════════════════════════════════
BOARD_WEIGHTS = {
    "EI":    {"e1": 0.30, "e2": 0.30, "e3": 0.25, "e4": 0.15},
    "GI":    {"g1": 1.0},
    "P&B":   {"p1": 0.25, "p2": 0.15, "p3": 0.10, "p4": 0.25, "p5": 0.25},
    "L&M":   {"l1": 0.40, "l2": 0.35, "l3": 0.25},
    "F&B":   {"f1": 0.30, "f2": 0.25, "f3": 0.20, "f4": 0.25},
    "Macro": {"m1": 0.35, "m2": 0.35, "m3": 0.30},
}

# ══════════════════════════════════════════════════════════════
# 3. 历史数据 I/O
# ══════════════════════════════════════════════════════════════
HISTORY_PATH = "data/history.json"

def load_history():
    if os.path.exists(HISTORY_PATH):
        with open(HISTORY_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_history(history, period, results):
    os.makedirs("data", exist_ok=True)
    history[period] = {
        tid: {
            "heat": r["heat"],
            "trend": r["trend"],
            "D": r["scores"]["D"],
            "C": r["scores"]["C"],
            "P": r["scores"]["P"],
            "Pol": r["scores"]["Pol"],
        }
        for tid, r in results.items()
    }
    with open(HISTORY_PATH, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[OK] 历史已保存 → {HISTORY_PATH}")

def get_prev_heat(history, track_id):
    periods = sorted(history.keys(), reverse=True)
    for p in periods:
        if track_id in history[p]:
            return history[p][track_id]["heat"]
    return 50.0

# ══════════════════════════════════════════════════════════════
# 4. Claude API — 核心打分函数
# ══════════════════════════════════════════════════════════════
def score_track_with_claude(client: anthropic.Anthropic, track: dict) -> dict:
    """
    让 Claude 用 web_search 搜索赛道最新动态，然后打分并生成摘要。
    返回: {D, C, P, Pol, core_data, comment, act}
    """
    today = datetime.date.today().strftime("%Y年%m月")
    track_name = track["name"]
    tid = track["id"]
    strategy = track.get("strategy", "")
    query = track["search_query"]

    system_prompt = (
        "你是中国B2B工业设备行业景气度分析师，专注为精密流体控制阀门供应商服务。"
        "你会使用web_search工具搜索最新行业动态，然后基于搜索结果进行打分分析。"
        "打分严格按格式输出，不添加任何额外解释。"
    )

    user_prompt = f"""请搜索【{track_name}】赛道在{today}的最新动态，然后进行景气度打分。

搜索建议关键词：{query}

赛道分析策略：{strategy}

搜索完成后，按以下规则打分（0-100整数）：
D = 需求动能：强劲订单/扩产/渗透率提升→80+，需求疲软/去库存→40-
C = 投资强度：大额招标/融资/Capex扩张→80+，FAI收缩/暂缓→40-
P = 价格盈利：涨价/毛利改善→高分，集采降价50%→38分（反向指标）
Pol = 政策情绪：强补贴/产业催化/入法→85+，政策空窗/监管收紧→45-

严格按以下格式输出4行，不要其他内容：
D=数字 C=数字 P=数字 Pol=数字
核心数据：（30字以内，最重要的一个数据点，含具体数字）
结论：（40字以内，本期景气度判断）
行动：（30字以内，对流体控制阀门供应商的具体行动建议）"""

    try:
        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=400,
            system=system_prompt,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=[{"role": "user", "content": user_prompt}],
        )

        # 提取文本输出（忽略 tool_use / tool_result blocks）
        raw = ""
        for block in response.content:
            if block.type == "text":
                raw += block.text

        print(f"  [Claude] {tid}: {raw[:100]}")
        return _parse_score_output(raw, tid)

    except Exception as e:
        print(f"  [ERROR] Claude API 失败 {tid}: {e}")
        return _default_scores(tid)


def _parse_score_output(raw: str, tid: str) -> dict:
    """解析 Claude 返回的4行格式文本。"""
    lines = raw.strip().split("\n")
    score_line = ""
    for line in lines:
        if re.search(r"D=\d+", line):
            score_line = line
            break

    d   = re.search(r"D=(\d+)",   score_line)
    c   = re.search(r"C=(\d+)",   score_line)
    p   = re.search(r" P=(\d+)",  score_line)
    pol = re.search(r"Pol=(\d+)", score_line)

    core_data, comment, act = "", "", ""
    for line in lines:
        line = line.strip()
        if line.startswith("核心数据"):
            core_data = re.split(r"[：:]", line, 1)[-1].strip()
        elif line.startswith("结论"):
            comment = re.split(r"[：:]", line, 1)[-1].strip()
        elif line.startswith("行动"):
            act = re.split(r"[：:]", line, 1)[-1].strip()

    if d and c and p and pol:
        return {
            "D":         min(100, max(0, int(d.group(1)))),
            "C":         min(100, max(0, int(c.group(1)))),
            "P":         min(100, max(0, int(p.group(1)))),
            "Pol":       min(100, max(0, int(pol.group(1)))),
            "core_data": core_data,
            "comment":   comment,
            "act":       act,
        }

    print(f"  [WARN] 解析失败 {tid}: '{score_line}'")
    return _default_scores(tid)


def _default_scores(tid: str) -> dict:
    return {"D": 50, "C": 50, "P": 50, "Pol": 50,
            "core_data": "数据获取异常", "comment": "请人工核查", "act": "暂缓决策"}


# ══════════════════════════════════════════════════════════════
# 5. 计算工具
# ══════════════════════════════════════════════════════════════
def calc_heat(scores: dict) -> float:
    """加权公式：D×35% + C×30% + P×20% + Pol×15%"""
    h = (scores["D"] * 0.35 + scores["C"] * 0.30 +
         scores["P"] * 0.20 + scores["Pol"] * 0.15)
    return round(h, 1)

def calc_trend(heat: float, prev_heat: float) -> str:
    if heat - prev_heat >= 2:   return "up"
    if heat - prev_heat <= -2:  return "dn"
    return "fl"

# ══════════════════════════════════════════════════════════════
# 6. 制药装备行业动态（注入 pharma.html）
# ══════════════════════════════════════════════════════════════
def fetch_pharma_news_with_claude(client: anthropic.Anthropic) -> dict:
    """让 Claude 搜索制药装备行业最新动态，返回结构化新闻数据。"""
    today = datetime.date.today().strftime("%Y年%m月")

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        tools=[{"type": "web_search_20250305", "name": "web_search"}],
        messages=[{
            "role": "user",
            "content": f"""请搜索{today}制药装备行业最新动态，包括：
1. 楚天科技、东富龙、森松国际等龙头企业动态
2. 制药装备招标、新建产线投资
3. 国产替代进展（生物反应器、冻干机等）
4. NMPA监管政策、GMP相关政策

搜索完成后，筛选最有价值的5条新闻，严格按以下JSON格式输出（不要markdown代码块）：
[{{"title":"新闻标题","summary":"30字中文摘要","tag":"政策|企业|市场|技术之一","link":""}}]"""
        }],
    )

    raw = ""
    for block in response.content:
        if block.type == "text":
            raw += block.text

    try:
        raw = re.sub(r"^```[a-z]*\s*|```$", "", raw.strip(), flags=re.MULTILINE).strip()
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        if m:
            items = json.loads(m.group(0))
            return {"items": items[:5], "updated": datetime.date.today().strftime("%Y-%m-%d")}
    except Exception as e:
        print(f"  [WARN] 制药新闻解析失败: {e}")

    return {"items": [], "updated": datetime.date.today().strftime("%Y-%m-%d")}


def build_news_html(data: dict) -> str:
    items_html = ""
    for item in data["items"]:
        lo = f'<a href="{item["link"]}" target="_blank" rel="noopener">' if item.get("link") else "<span>"
        lc = "</a>" if item.get("link") else "</span>"
        items_html += f"""
        <div class="news-item">
          <div class="news-meta">
            <span class="news-source">{item.get("tag","行业")}</span>
          </div>
          <div class="news-title">{lo}{item["title"]}{lc}</div>
          <div class="news-summary">{item["summary"]}</div>
        </div>"""
    return f"""<!-- NEWS_BLOCK_START -->
<section class="news-section" id="latest-news">
  <div class="news-header">
    <span class="news-label">行业动态 LATEST NEWS</span>
    <span class="news-updated">数据更新：{data["updated"]}</span>
  </div>
  <div class="news-grid">{items_html}</div>
</section>
<style>
.news-section{{margin:60px auto 40px;max-width:1200px;padding:0 24px;font-family:inherit}}
.news-header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid rgba(61,148,255,.4);padding-bottom:10px;margin-bottom:24px}}
.news-label{{font-size:13px;font-weight:700;letter-spacing:.12em;color:#3d94ff;text-transform:uppercase}}
.news-updated{{font-size:11px;color:#888;letter-spacing:.04em}}
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
.news-item{{background:#0c1420;border:1px solid rgba(160,200,255,.11);border-radius:8px;padding:16px 18px;transition:border-color .2s}}
.news-item:hover{{border-color:#3d94ff}}
.news-meta{{display:flex;gap:10px;align-items:center;margin-bottom:8px}}
.news-source{{font-size:10px;font-weight:700;letter-spacing:.08em;color:#3d94ff;background:rgba(61,148,255,.12);padding:2px 8px;border-radius:20px;text-transform:uppercase}}
.news-title a,.news-title span{{font-size:13px;font-weight:600;color:#f2f5fb;text-decoration:none;line-height:1.5;display:block;margin-bottom:6px}}
.news-title a:hover{{color:#3d94ff}}
.news-summary{{font-size:12px;color:#586880;line-height:1.7}}
</style>
<!-- NEWS_BLOCK_END -->"""


def inject_html(news_html: str, path: str):
    if not os.path.exists(path):
        print(f"  [SKIP] {path} 不存在，跳过")
        return
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "<!-- NEWS_BLOCK_START -->" in content:
        content = re.sub(r"<!-- NEWS_BLOCK_START -->.*?<!-- NEWS_BLOCK_END -->",
                         news_html, content, flags=re.DOTALL)
    else:
        content = content.replace("</body>", news_html + "\n</body>")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] 行业动态已注入 → {path}")


# ══════════════════════════════════════════════════════════════
# 7. 主流程
# ══════════════════════════════════════════════════════════════
if __name__ == "__main__":
    today     = datetime.date.today()
    period    = today.strftime("%Y%m")
    today_str = today.strftime("%Y-%m-%d")
    print(f"=== PULSE 2026 开始更新 {today_str} ===")

    client  = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    history = load_history()
    results = {}

    # ── Step 1：子赛道打分（Claude + web_search）──────────────
    print("\n--- Heat Score 打分 (Claude web_search) ---")
    for track in TRACKS:
        tid = track["id"]
        print(f"  处理: {tid} [{track['name']}]")
        scores = score_track_with_claude(client, track)
        heat   = calc_heat(scores)
        prev   = get_prev_heat(history, tid)
        trend  = calc_trend(heat, prev)
        results[tid] = {
            "heat": heat, "trend": trend,
            "scores": scores, "prev_heat": prev,
        }
        print(f"    Heat={heat} ({trend})  D={scores['D']} C={scores['C']} "
              f"P={scores['P']} Pol={scores['Pol']}")
        # 礼貌性等待，避免触发速率限制
        time.sleep(3)

    # ── Step 2：板块综合分 ─────────────────────────────────────
    board_heats = {}
    for board, weights in BOARD_WEIGHTS.items():
        total_w, total_score = 0, 0
        for tid, w in weights.items():
            if tid in results:
                total_score += results[tid]["heat"] * w
                total_w     += w
        board_heats[board] = round(total_score / total_w, 1) if total_w else 50.0

    print("\n板块综合分：")
    for b, h in board_heats.items():
        print(f"  {b}: {h}")

    # ── Step 3：保存历史 ───────────────────────────────────────
    save_history(history, period, results)

    # ── Step 4：注入 index.html ────────────────────────────────
    print("\n--- 注入 index.html ---")
    try:
        import sys
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from inject_scores import inject_scores

        scores_payload = {
            "date":    today_str,
            "sectors": {},
            "tracks":  {},
        }

        # 板块级
        for b, heat in board_heats.items():
            tids = list(BOARD_WEIGHTS[b].keys())
            prev_heats = [results[t]["prev_heat"] for t in tids if t in results]
            prev_board = round(sum(prev_heats) / len(prev_heats), 1) if prev_heats else 50
            scores_payload["sectors"][b] = {
                "heat": heat,
                "tr":   calc_trend(heat, prev_board),
            }

        # 子赛道级
        for tid, r in results.items():
            delta = round(r["heat"] - r["prev_heat"], 1)
            entry = {
                "heat":  r["heat"],
                "tr":    r["trend"],
                "delta": delta,
                "D":     r["scores"]["D"],
                "C":     r["scores"]["C"],
                "P":     r["scores"]["P"],
                "Pol":   r["scores"]["Pol"],
            }
            if r["scores"].get("core_data"):
                entry["data"] = [r["scores"]["core_data"]]
            if r["scores"].get("comment"):
                entry["tw"] = r["scores"]["comment"]
            if r["scores"].get("act"):
                entry["act"] = r["scores"]["act"]
            scores_payload["tracks"][tid] = entry

        index_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "..", "index.html"
        )
        inject_scores(scores_payload, index_path=index_path)

    except Exception as e:
        print(f"  [ERROR] inject_scores 失败: {e}")
        import traceback; traceback.print_exc()

    # ── Step 5：制药装备行业动态 → pharma.html ─────────────────
    print("\n--- 制药装备行业动态 (Claude web_search) ---")
    try:
        pharma_data = fetch_pharma_news_with_claude(client)
        print(f"  获取 {len(pharma_data['items'])} 条新闻")
        if pharma_data["items"]:
            pharma_path = os.path.join(
                os.path.dirname(os.path.abspath(__file__)), "..", "pharma.html"
            )
            inject_html(build_news_html(pharma_data), pharma_path)
        else:
            print("  [SKIP] 无有效新闻条目")
    except Exception as e:
        print(f"  [ERROR] 制药新闻失败: {e}")

    print(f"\n=== 全部完成 {today_str} ===")
