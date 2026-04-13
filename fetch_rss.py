#!/usr/bin/env python3
"""
PULSE 2026 RSS Fetcher
每日定时抓取各行业垂直RSS源，输出为仪表盘可读的JSON文件
"""

import json
import os
import sys
import time
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

import feedparser
import requests
from dateutil import parser as dateutil_parser

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
log = logging.getLogger(__name__)

# ── 路径配置 ──────────────────────────────────────────────
ROOT_DIR = Path(__file__).parent
CONFIG_PATH = ROOT_DIR / "rss_sources.json"
OUTPUT_DIR = ROOT_DIR / "data" / "rss"          # 输出到 data/rss/
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def load_config() -> dict:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def parse_date(entry) -> datetime:
    """尽力解析 feedparser 条目的时间"""
    for attr in ("published_parsed", "updated_parsed", "created_parsed"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    for attr in ("published", "updated", "created"):
        val = getattr(entry, attr, None)
        if val:
            try:
                return dateutil_parser.parse(val).astimezone(timezone.utc)
            except Exception:
                pass
    return datetime.now(timezone.utc)


def entry_to_item(entry, source_name: str, lang: str) -> dict:
    """把 feedparser entry 转成统一格式"""
    title = getattr(entry, "title", "").strip()
    link  = getattr(entry, "link",  "").strip()
    
    # 摘要：优先 summary，其次 content[0]
    summary = ""
    if hasattr(entry, "summary"):
        summary = entry.summary
    elif hasattr(entry, "content") and entry.content:
        summary = entry.content[0].get("value", "")
    # 去除 HTML 标签（简单处理）
    import re
    summary = re.sub(r"<[^>]+>", "", summary).strip()
    summary = summary[:300] + "…" if len(summary) > 300 else summary

    pub_dt   = parse_date(entry)
    item_id  = hashlib.md5(link.encode()).hexdigest()[:10]

    return {
        "id":       item_id,
        "title":    title,
        "url":      link,
        "summary":  summary,
        "source":   source_name,
        "lang":     lang,
        "pub_date": pub_dt.isoformat(),
        "pub_ts":   int(pub_dt.timestamp()),
    }


def fetch_source(source: dict, max_age_days: int, max_items: int, timeout: int, retries: int) -> list:
    """抓取单个RSS源，返回条目列表"""
    url   = source["url"]
    name  = source["name"]
    lang  = source.get("lang", "zh")
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_age_days)

    for attempt in range(1, retries + 1):
        try:
            log.info(f"  Fetching [{name}] (attempt {attempt}): {url}")
            # feedparser 内置 HTTP，加 User-Agent 防屏蔽
            headers = {"User-Agent": "Mozilla/5.0 (PULSE-2026-RSS-Bot/1.0)"}
            resp = requests.get(url, headers=headers, timeout=timeout)
            resp.raise_for_status()
            feed = feedparser.parse(resp.content)

            items = []
            for entry in feed.entries[:max_items * 2]:   # 多取一些再过滤
                item = entry_to_item(entry, name, lang)
                pub  = datetime.fromisoformat(item["pub_date"])
                if pub >= cutoff:
                    items.append(item)
                if len(items) >= max_items:
                    break

            log.info(f"    → {len(items)} items")
            return items

        except Exception as e:
            log.warning(f"    ✗ {e}")
            if attempt < retries:
                time.sleep(3)

    return []


def fetch_vertical(vertical_id: str, vertical_cfg: dict, global_settings: dict) -> dict:
    """抓取一个行业垂直的所有RSS源"""
    cfg      = global_settings
    max_src  = cfg["max_items_per_source"]
    max_vert = cfg["max_items_per_vertical"]
    max_age  = cfg["max_age_days"]
    timeout  = cfg["fetch_timeout_seconds"]
    retries  = cfg["retry_attempts"]

    log.info(f"\n▶ Vertical: {vertical_cfg['name']} ({vertical_id})")

    all_items = []
    for source in sorted(vertical_cfg["sources"], key=lambda s: s.get("priority", 9)):
        items = fetch_source(source, max_age, max_src, timeout, retries)
        all_items.extend(items)

    # 去重（按URL）+ 时间排序
    seen = set()
    deduped = []
    for item in sorted(all_items, key=lambda x: x["pub_ts"], reverse=True):
        if item["url"] not in seen:
            seen.add(item["url"])
            deduped.append(item)
        if len(deduped) >= max_vert:
            break

    return {
        "vertical_id":   vertical_id,
        "vertical_name": vertical_cfg["name"],
        "vertical_en":   vertical_cfg.get("name_en", ""),
        "color":         vertical_cfg.get("color", "#ffffff"),
        "updated_at":    datetime.now(timezone.utc).isoformat(),
        "item_count":    len(deduped),
        "items":         deduped,
    }


def main():
    log.info("=" * 60)
    log.info("PULSE 2026 RSS Fetch — started")
    log.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    log.info("=" * 60)

    config   = load_config()
    settings = config["global_settings"]
    verticals = config["verticals"]

    # 可以通过环境变量只跑指定垂直（方便调试）
    target = os.environ.get("RSS_TARGET_VERTICAL", "").strip()
    if target:
        verticals = {k: v for k, v in verticals.items() if k == target}
        log.info(f"Targeting single vertical: {target}")

    summary = {}

    for vid, vcfg in verticals.items():
        result = fetch_vertical(vid, vcfg, settings)
        
        # 写单个垂直 JSON
        out_path = OUTPUT_DIR / f"{vid}.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        log.info(f"  ✓ Saved: {out_path} ({result['item_count']} items)")

        summary[vid] = {
            "name":       result["vertical_name"],
            "item_count": result["item_count"],
            "updated_at": result["updated_at"],
        }

    # 写汇总索引
    index = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "verticals":    summary,
    }
    index_path = OUTPUT_DIR / "index.json"
    with open(index_path, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    log.info("\n" + "=" * 60)
    log.info(f"✅ Done. {len(summary)} verticals processed.")
    log.info(f"   Output → {OUTPUT_DIR}")
    log.info("=" * 60)


if __name__ == "__main__":
    main()
