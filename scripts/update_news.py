import os
import re
import json
import datetime
import feedparser
import requests
from bs4 import BeautifulSoup
import anthropic

SOURCES = [
    {"name": "医药经济报", "url": "https://www.yyjjb.com.cn/rss.xml", "type": "rss"},
]

MAX_ITEMS = 10
MAX_CHARS = 300


def fetch_rss(url, source_name, limit=4):
    items = []
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:limit]:
            items.append({
                "source": source_name,
                "title": entry.get("title", "").strip(),
                "link": entry.get("link", ""),
                "summary": BeautifulSoup(
                    entry.get("summary", entry.get("description", "")), "html.parser"
                ).get_text()[:500],
                "date": entry.get("published", ""),
            })
    except Exception as e:
        print(f"[WARN] RSS fetch failed for {source_name}: {e}")
    return items


def fetch_baidu_news(keyword, source_name, limit=5):
    items = []
    try:
        url = f"https://www.baidu.com/s?tn=news&rtt=1&bsst=1&cl=2&wd={requests.utils.quote(keyword)}&ie=utf-8"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; research-bot/1.0)"}
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        for a in soup.select("h3 a")[:limit]:
            items.append({
                "source": source_name,
                "title": a.get_text().strip(),
                "link": a.get("href", ""),
                "summary": "",
                "date": "",
            })
    except Exception as e:
        print(f"[WARN] Baidu news fetch failed: {e}")
    return items


def fetch_nmpa(limit=3):
    items = []
    try:
        url = "https://www.nmpa.gov.cn/xxgk/ggtg/index.html"
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get(url, headers=headers, timeout=10)
        resp.encoding = "utf-8"
        soup = BeautifulSoup(resp.text, "html.parser")
        for li in soup.select("ul.list li")[:limit]:
            a = li.find("a")
            span = li.find("span")
            if a:
                items.append({
                    "source": "NMPA政策",
                    "title": a.get_text().strip(),
                    "link": "https://www.nmpa.gov.cn" + a.get("href", ""),
                    "summary": "",
                    "date": span.get_text().strip() if span else "",
                })
    except Exception as e:
        print(f"[WARN] NMPA fetch failed: {e}")
    return items


def collect_raw_items():
    all_items = []
    all_items += fetch_rss(SOURCES[0]["url"], SOURCES[0]["name"], limit=4)
    all_items += fetch_baidu_news("制药装备 国产替代", "制药装备动态", limit=5)
    all_items += fetch_baidu_news("东富龙 楚天科技 森松", "龙头动态", limit=4)
    all_items += fetch_nmpa(limit=3)
    seen = set()
    unique = []
    for item in all_items:
        key = item["title"][:20]
        if key and key not in seen:
            seen.add(key)
            unique.append(item)
    return unique[:20]


def summarize_with_claude(raw_items):
    client = anthropic.Anthropic(
        api_key=os.environ["MINIMAX_API_KEY"],
        base_url="https://api.minimaxi.com/anthropic"
    )

    items_text = "\n\n".join([
        f"来源：{i['source']}\n标题：{i['title']}\n内容：{i['summary'][:300]}\n链接：{i['link']}"
        for i in raw_items
    ])

    today = datetime.date.today().strftime("%Y年%m月%d日")

    prompt = f"""你是一位专注中国制药装备行业的研究分析师。

以下是本周抓取的行业原始信息（共{len(raw_items)}条），请：
1. 筛选出与"制药装备、生物制药设备、国产替代、出海、政策监管、上市公司动态"最相关的8-10条
2. 对每条生成一句精炼的中文摘要（50-80字），说明核心事件和对行业的意义
3. 保留原始链接（若为空则留空字符串）
4. 去除重复、广告、无实质内容的条目

请严格按以下 JSON 格式返回，不要有任何其他文字：
{{
  "updated": "{today}",
  "items": [
    {{
      "source": "来源名称",
      "title": "原始标题",
      "summary": "你的分析摘要（50-80字）",
      "link": "原始链接或空字符串",
      "date": "日期或空字符串"
    }}
  ]
}}

原始信息：
{items_text}
"""

    message = client.messages.create(
        model="MiniMax-M2.5",
        max_tokens=2000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_json = message.content[0].text.strip()
    raw_json = re.sub(r"^```json\s*", "", raw_json)
    raw_json = re.sub(r"\s*```$", "", raw_json)
    return json.loads(raw_json)


def build_news_html(data):
    items_html = ""
    for item in data["items"]:
        link_open = f'<a href="{item["link"]}" target="_blank" rel="noopener">' if item["link"] else "<span>"
        link_close = "</a>" if item["link"] else "</span>"
        date_str = f'<span class="news-date">{item["date"]}</span>' if item.get("date") else ""
        items_html += f"""
        <div class="news-item">
          <div class="news-meta">
            <span class="news-source">{item["source"]}</span>
            {date_str}
          </div>
          <div class="news-title">{link_open}{item["title"]}{link_close}</div>
          <div class="news-summary">{item["summary"]}</div>
        </div>"""

    return f"""<!-- NEWS_BLOCK_START -->
<section class="news-section" id="latest-news">
  <div class="news-header">
    <span class="news-label">行业动态 LATEST NEWS</span>
    <span class="news-updated">数据更新：{data["updated"]}</span>
  </div>
  <div class="news-grid">
    {items_html}
  </div>
</section>

<style>
.news-section {{
  margin: 60px auto 40px;
  max-width: 1200px;
  padding: 0 24px;
  font-family: inherit;
}}
.news-header {{
  display: flex;
  justify-content: space-between;
  align-items: center;
  border-bottom: 1px solid #ff2d78;
  padding-bottom: 10px;
  margin-bottom: 24px;
}}
.news-label {{
  font-size: 13px;
  font-weight: 700;
  letter-spacing: .12em;
  color: #ff2d78;
  text-transform: uppercase;
}}
.news-updated {{
  font-size: 11px;
  color: #888;
  letter-spacing: .04em;
}}
.news-grid {{
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 16px;
}}
.news-item {{
  background: #111;
  border: 1px solid #222;
  border-radius: 8px;
  padding: 16px 18px;
  transition: border-color .2s;
}}
.news-item:hover {{
  border-color: #ff2d78;
}}
.news-meta {{
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 8px;
}}
.news-source {{
  font-size: 10px;
  font-weight: 700;
  letter-spacing: .08em;
  color: #ff2d78;
  background: rgba(255,45,120,.1);
  padding: 2px 8px;
  border-radius: 20px;
  text-transform: uppercase;
}}
.news-date {{
  font-size: 10px;
  color: #555;
}}
.news-title a,
.news-title span {{
  font-size: 13px;
  font-weight: 600;
  color: #eee;
  text-decoration: none;
  line-height: 1.5;
  display: block;
  margin-bottom: 6px;
}}
.news-title a:hover {{
  color: #ff2d78;
}}
.news-summary {{
  font-size: 12px;
  color: #888;
  line-height: 1.7;
}}
</style>
<!-- NEWS_BLOCK_END -->"""


def inject_into_html(news_html, html_path="pharma.html"):
    with open(html_path, "r", encoding="utf-8") as f:
        content = f.read()
    if "<!-- NEWS_BLOCK_START -->" in content:
        content = re.sub(
            r"<!-- NEWS_BLOCK_START -->.*?<!-- NEWS_BLOCK_END -->",
            news_html,
            content,
            flags=re.DOTALL,
        )
    else:
        content = content.replace("</body>", news_html + "\n</body>")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"[OK] Injected {len(news_html)} chars into {html_path}")


if __name__ == "__main__":
    print("=== 开始抓取行业动态 ===")
    raw = collect_raw_items()
    print(f"[INFO] 抓取原始条目 {len(raw)} 条")
    if not raw:
        print("[WARN] 无有效条目，跳过更新")
        exit(0)
    print("[INFO] 调用 MiniMax 生成摘要...")
    data = summarize_with_claude(raw)
    print(f"[OK] 返回 {len(data['items'])} 条摘要")
    inject_into_html(news_html=build_news_html(data), html_path="pharma.html")
    print("=== 完成 ===")
