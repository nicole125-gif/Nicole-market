import os
import re
import json
import datetime
import feedparser
import anthropic

# ── 子赛道配置 ─────────────────────────────────────────────
TRACKS = [
    {
        "id": "EI·液冷数据中心",
        "board": "EI",
        "keywords": ["AI液冷数据中心 CDU冷板", "液冷渗透率 数据中心", "AI基础设施 液冷设备"],
    },
    {
        "id": "EI·半导体设备国产化",
        "board": "EI",
        "keywords": ["半导体设备国产化 北方华创", "晶圆厂扩产 设备投资", "DRAM 半导体涨价"],
    },
    {
        "id": "EI·绿氢电解槽",
        "board": "EI",
        "keywords": ["PEM电解槽 绿氢", "氢能 电解槽招标", "质子交换膜 氢能设备"],
    },
    {
        "id": "EI·燃料电池",
        "board": "EI",
        "keywords": ["燃料电池 FCEV重卡", "氢燃料电池 销量", "燃料电池补贴政策"],
    },
    {
        "id": "GI·锂电设备",
        "board": "GI",
        "keywords": ["锂电设备 宁德时代 CATL", "锂电池产能扩张 设备订单", "先导智能 赢合科技"],
    },
    {
        "id": "P&B·生物药出海",
        "board": "P&B",
        "keywords": ["创新药 License-out BD交易", "司美格鲁肽 GLP-1 CDMO", "生物药出海 ADC"],
    },
    {
        "id": "P&B·合成生物学",
        "board": "P&B",
        "keywords": ["合成生物学 中试车间", "华恒生物 凯赛生物 发酵罐", "合成生物学 十五五"],
    },
    {
        "id": "P&B·生物药融资",
        "board": "P&B",
        "keywords": ["生物医药投融资 一级市场", "创新药融资 生物科技"],
    },
    {
        "id": "P&B·制药装备Capex",
        "board": "P&B",
        "keywords": ["医药制造业固定资产投资 FAI", "制药装备 资本支出", "医药FAI 国家统计局"],
    },
    {
        "id": "P&B·CDMO",
        "board": "P&B",
        "keywords": ["CDMO 药明康德 凯莱英", "TIDES ADC CDMO订单", "CDMO询单 多肽原料药"],
    },
    {
        "id": "L&M·质谱色谱仪器",
        "board": "L&M",
        "keywords": ["质谱仪 国产替代 禾信谱育", "色谱仪器 进口替代", "分析仪器 国产化率"],
    },
    {
        "id": "L&M·基因测序",
        "board": "L&M",
        "keywords": ["基因测序 华大智造 因美纳", "测序仪 国产替代", "WGS 肿瘤早检 测序"],
    },
    {
        "id": "L&M·医疗IVD",
        "board": "L&M",
        "keywords": ["IVD体外诊断 集采降价", "化学发光 国产化率", "医疗IVD 市场规模"],
    },
    {
        "id": "F&B·食品制造FAI",
        "board": "F&B",
        "keywords": ["食品制造业 固定资产投资", "食品装备 预制菜 产线", "食品制造FAI 统计局"],
    },
    {
        "id": "F&B·酒饮料制造FAI",
        "board": "F&B",
        "keywords": ["酒饮料制造 固定资产投资", "白酒产能 碳酸饮料 投资", "饮料制造FAI"],
    },
    {
        "id": "F&B·食品饮料消费",
        "board": "F&B",
        "keywords": ["食品饮料 消费数据 零售", "春节消费 年货 餐饮", "功能饮品 无糖茶 消费"],
    },
    {
        "id": "F&B·食品添加剂",
        "board": "F&B",
        "keywords": ["食品添加剂 合成生物学 发酵", "天然甜味剂 益生菌 扩产", "功能性食品成分 市场"],
    },
    {
        "id": "Macro·制造业PMI",
        "board": "Macro",
        "keywords": ["中国制造业PMI 官方 财新", "PMI 制造业景气指数"],
    },
    {
        "id": "Macro·M2社融CPIPPI",
        "board": "Macro",
        "keywords": ["中国M2 社融 货币政策", "CPI PPI 通胀 价格指数"],
    },
    {
        "id": "Macro·投资工业增加值",
        "board": "Macro",
        "keywords": ["固定资产投资 工业增加值 统计局", "制造业FAI 规上工业增加值"],
    },
]

# 板块综合分权重
BOARD_WEIGHTS = {
    "EI":    {"EI·液冷数据中心": 0.30, "EI·半导体设备国产化": 0.30,
               "EI·绿氢电解槽": 0.25, "EI·燃料电池": 0.15},
    "GI":    {"GI·锂电设备": 1.0},
    "P&B":   {"P&B·生物药出海": 0.25, "P&B·合成生物学": 0.15,
               "P&B·生物药融资": 0.10, "P&B·制药装备Capex": 0.25, "P&B·CDMO": 0.25},
    "L&M":   {"L&M·质谱色谱仪器": 0.40, "L&M·基因测序": 0.35, "L&M·医疗IVD": 0.25},
    "F&B":   {"F&B·食品制造FAI": 0.30, "F&B·酒饮料制造FAI": 0.25,
               "F&B·食品饮料消费": 0.20, "F&B·食品添加剂": 0.25},
    "Macro": {"Macro·制造业PMI": 0.35, "Macro·M2社融CPIPPI": 0.35,
               "Macro·投资工业增加值": 0.30},
}


def get_client():
    return anthropic.Anthropic(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic"
    )


# ── 抓取新闻 ───────────────────────────────────────────────

def fetch_news_for_track(track, days=35):
    items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=days)
    for kw in track["keywords"]:
        url = f"https://news.google.com/rss/search?q={kw}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:5]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime.datetime(*pub[:6], tzinfo=datetime.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                items.append({
                    "title": entry.get("title", "").strip(),
                    "summary": entry.get("summary", "")[:200],
                    "date": entry.get("published", ""),
                })
        except Exception as e:
            print(f"  [WARN] {kw}: {e}")
    # 去重
    seen, unique = set(), []
    for i in items:
        k = i["title"][:15]
        if k and k not in seen:
            seen.add(k)
            unique.append(i)
    return unique[:12]


# ── MiniMax 打分 ───────────────────────────────────────────

def score_track(client, track, news_items):
    if not news_items:
        print(f"  [WARN] {track['id']} 无新闻，使用默认分50")
        return {"D": 50, "C": 50, "P": 50, "Pol": 50,
                "core_data": "本期无有效新闻数据", "comment": "数据不足，参考上期"}

    news_text = "\n".join([f"- {i['title']}" for i in news_items[:10]])

    prompt = f"""你是中国B2B设备行业景气度分析师，使用以下打分方法论对赛道进行评分。

打分方法论：
- Demand(需求动能,35%)：出货量YoY/新订单/渗透率变化，Min-Max归一化，领先指标为主
- Capex(投资强度,30%)：招标规模YoY/融资额/固定资产投资，设备链最直接领先指标
- Price(价格盈利,20%)：反向指标！价格下跌=低分。Score=100-正向标准化。集采降价50%→38分
- Policy(政策情绪,15%)：产业补贴/社融/监管，定性评分，政策强催化→80+分

当前赛道：{track['id']}

本期相关新闻：
{news_text}

请基于以上新闻，对该赛道打分。
只返回以下格式，不要其他文字：
D|C|P|Pol|核心数据摘要(30字)|一句话点评(40字)

示例：82|75|58|88|DRAM Q1合约价+90%，设备投资2622亿|全产业链涨价潮确认，国产替代升级为供应链必选项"""

    try:
        msg = client.messages.create(
            model="MiniMax-M2.5-highspeed",
            max_tokens=300,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = next(b.text for b in msg.content if b.type == "text").strip()
        parts = raw.split("|")
        if len(parts) >= 6:
            return {
                "D":   min(100, max(0, int(float(parts[0].strip())))),
                "C":   min(100, max(0, int(float(parts[1].strip())))),
                "P":   min(100, max(0, int(float(parts[2].strip())))),
                "Pol": min(100, max(0, int(float(parts[3].strip())))),
                "core_data": parts[4].strip(),
                "comment":   parts[5].strip(),
            }
    except Exception as e:
        print(f"  [WARN] 打分解析失败 {track['id']}: {e}, raw={raw if 'raw' in dir() else 'N/A'}")
    return {"D": 50, "C": 50, "P": 50, "Pol": 50,
            "core_data": "解析失败", "comment": ""}


def calc_heat(scores):
    return round(
        scores["D"] * 0.35 + scores["C"] * 0.30 +
        scores["P"] * 0.20 + scores["Pol"] * 0.15, 2
    )


def calc_trend(heat_now, heat_prev):
    if heat_prev is None:
        return "→"
    delta = heat_now - heat_prev
    if delta >= 2:
        return "↑"
    elif delta <= -2:
        return "↓"
    return "→"


# ── 读写 history.json ──────────────────────────────────────

def load_history():
    path = "data/history.json"
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_history(history, period, results):
    history[period] = {t["id"]: results[t["id"]]["heat"] for t in TRACKS}
    with open("data/history.json", "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)
    print(f"[OK] history.json 已更新，新增 {period}")


def get_prev_heat(history, track_id):
    if not history:
        return None
    last_period = sorted(history.keys())[-1]
    return history[last_period].get(track_id)


# ── 更新 data.js ───────────────────────────────────────────

def update_data_js(results, board_heats, today_str):
    with open("data.js", "r", encoding="utf-8") as f:
        content = f.read()

    content = re.sub(r'lastUpdated:\s*"[^"]*"', f'lastUpdated: "{today_str}"', content)

    # 更新宏观指标 value（从 Macro 子赛道结果提取）
    macro_map = {
        "GDP GROWTH":    ("Macro·制造业PMI",         "GDP 增速"),
        "IND. VALUE ADD":("Macro·投资工业增加值",    "工业增加值"),
        "MFG. CAPEX":    ("Macro·投资工业增加值",    "制造业固投"),
        "EXPORT GROWTH": ("Macro·M2社融CPIPPI",      "出口增速"),
        "PPI TREND":     ("Macro·M2社融CPIPPI",      "PPI 走势"),
    }
    for label_en, (track_id, label_zh) in macro_map.items():
        if track_id in results:
            heat = results[track_id]["heat"]
            trend = results[track_id]["trend"]
            content = re.sub(
                rf'(labelEn:\s*"{re.escape(label_en)}"[^}}]*?trend:\s*")[^"]*"',
                rf'\g<1>{trend}"',
                content, flags=re.DOTALL
            )

    with open("data.js", "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] data.js 已更新")


# ── 制药装备新闻模块（保留原有功能）─────────────────────────

PHARMA_FEEDS = [
    ("制药装备动态", "https://news.google.com/rss/search?q=制药装备&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("龙头企业", "https://news.google.com/rss/search?q=楚天科技+OR+东富龙+OR+森松国际&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("国产替代", "https://news.google.com/rss/search?q=生物制药设备+国产替代&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
    ("政策监管", "https://news.google.com/rss/search?q=制药装备+政策+NMPA&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"),
]


def fetch_pharma_news():
    all_items = []
    cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=30)
    for source_name, url in PHARMA_FEEDS:
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:10]:
                pub = entry.get("published_parsed")
                if pub:
                    pub_dt = datetime.datetime(*pub[:6], tzinfo=datetime.timezone.utc)
                    if pub_dt < cutoff:
                        continue
                all_items.append({
                    "source": source_name,
                    "title": entry.get("title", "").strip(),
                    "link": entry.get("link", ""),
                    "summary": entry.get("summary", "")[:300],
                })
            print(f"[OK] {source_name}: {len(feed.entries)} 条")
        except Exception as e:
            print(f"[WARN] {source_name}: {e}")
    seen, unique = set(), []
    for item in all_items:
        k = item["title"][:20]
        if k and k not in seen:
            seen.add(k)
            unique.append(item)
    return unique[:20]


def summarize_pharma(client, raw_items):
    items_text = "\n\n".join([
        f"[{i+1}] 来源：{x['source']}\n标题：{x['title']}\n链接：{x['link']}"
        for i, x in enumerate(raw_items[:12])
    ])
    today = datetime.date.today().strftime("%Y年%m月%d日")
    prompt = f"""你是制药装备行业分析师。从以下新闻中筛选8条最相关的，每条写一句50字摘要。
只返回如下格式，每条一行，不要其他文字：
序号|来源|标题|摘要|链接

新闻列表：
{items_text}"""
    msg = client.messages.create(
        model="MiniMax-M2.5-highspeed",
        max_tokens=3000,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = next(b.text for b in msg.content if b.type == "text").strip()
    items = []
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line or line.startswith("序号"):
            continue
        parts = line.split("|")
        if len(parts) >= 5:
            items.append({"source": parts[1].strip(), "title": parts[2].strip(),
                          "summary": parts[3].strip(), "link": parts[4].strip()})
    return {"updated": today, "items": items[:10]}


def build_news_html(data):
    items_html = ""
    for item in data["items"]:
        lo = f'<a href="{item["link"]}" target="_blank" rel="noopener">' if item["link"] else "<span>"
        lc = "</a>" if item["link"] else "</span>"
        items_html += f"""
        <div class="news-item">
          <div class="news-meta"><span class="news-source">{item["source"]}</span></div>
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
.news-header{{display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #ff2d78;padding-bottom:10px;margin-bottom:24px}}
.news-label{{font-size:13px;font-weight:700;letter-spacing:.12em;color:#ff2d78;text-transform:uppercase}}
.news-updated{{font-size:11px;color:#888;letter-spacing:.04em}}
.news-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
.news-item{{background:#111;border:1px solid #222;border-radius:8px;padding:16px 18px;transition:border-color .2s}}
.news-item:hover{{border-color:#ff2d78}}
.news-meta{{display:flex;gap:10px;align-items:center;margin-bottom:8px}}
.news-source{{font-size:10px;font-weight:700;letter-spacing:.08em;color:#ff2d78;background:rgba(255,45,120,.1);padding:2px 8px;border-radius:20px;text-transform:uppercase}}
.news-title a,.news-title span{{font-size:13px;font-weight:600;color:#eee;text-decoration:none;line-height:1.5;display:block;margin-bottom:6px}}
.news-title a:hover{{color:#ff2d78}}
.news-summary{{font-size:12px;color:#888;line-height:1.7}}
</style>
<!-- NEWS_BLOCK_END -->"""


def inject_html(news_html, path):
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    if "<!-- NEWS_BLOCK_START -->" in content:
        content = re.sub(r"<!-- NEWS_BLOCK_START -->.*?<!-- NEWS_BLOCK_END -->",
                         news_html, content, flags=re.DOTALL)
    else:
        content = content.replace("</body>", news_html + "\n</body>")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] 已更新 {path}")


# ── 主流程 ─────────────────────────────────────────────────

if __name__ == "__main__":
    today = datetime.date.today()
    period = today.strftime("%Y%m")
    today_str = today.strftime("%Y-%m-%d")
    print(f"=== 开始更新 {period} ===")

    client = get_client()
    history = load_history()
    results = {}

    # 1. 对每个子赛道打分
    print("\n--- Heat Score 打分 ---")
    for track in TRACKS:
        print(f"  处理: {track['id']}")
        news = fetch_news_for_track(track)
        scores = score_track(client, track, news)
        heat = calc_heat(scores)
        prev_heat = get_prev_heat(history, track["id"])
        trend = calc_trend(heat, prev_heat)
        results[track["id"]] = {
            "heat": heat, "trend": trend,
            "scores": scores, "prev_heat": prev_heat
        }
        print(f"    Heat={heat} Trend={trend} D={scores['D']} C={scores['C']} P={scores['P']} Pol={scores['Pol']}")

    # 2. 计算板块综合分
    board_heats = {}
    for board, weights in BOARD_WEIGHTS.items():
        total_w, total_score = 0, 0
        for track_id, w in weights.items():
            if track_id in results:
                total_score += results[track_id]["heat"] * w
                total_w += w
        board_heats[board] = round(total_score / total_w, 1) if total_w else 50
    print("\n板块综合分:")
    for b, h in board_heats.items():
        print(f"  {b}: {h}")

    # 3. 保存历史
    save_history(history, period, results)

    # 4. 更新 data.js
    update_data_js(results, board_heats, today_str)

    # 5. 制药装备新闻
    print("\n--- 制药装备行业动态 ---")
    pharma_raw = fetch_pharma_news()
    print(f"[INFO] 抓取 {len(pharma_raw)} 条")
    if pharma_raw:
        pharma_data = summarize_pharma(client, pharma_raw)
        if pharma_data["items"]:
            inject_html(build_news_html(pharma_data), "pharma.html")

    print(f"\n=== 全部完成 {today_str} ===")
