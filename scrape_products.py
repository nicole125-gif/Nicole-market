"""
竞品产品页抓取
目标：Bürkert / Gemü（盖米）/ ESG（青岛精锐）
域名：
  - Bürkert: www.burkert.com.cn/cn
  - Gemü:    www.gemu-group.com/en/products/（sitemap兜底）
  - ESG:     www.esgvalve.cn
输出：data/products_raw.json
"""

import json
import time
import hashlib
import requests
from bs4 import BeautifulSoup
from datetime import datetime
from pathlib import Path

Path("data").mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/120.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def safe_get(url, timeout=20):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        r.encoding = r.apparent_encoding
        print(f"  GET {url[:70]} → {r.status_code}")
        return r if r.status_code == 200 else None
    except Exception as e:
        print(f"  FAIL {url[:65]} → {e}")
        return None

def make_id(text):
    return hashlib.md5(text.encode()).hexdigest()[:8]

today = datetime.now().strftime("%Y-%m-%d")


# ─────────────────────────────────────────────
# Bürkert 中国官网
# 入口：www.burkert.com.cn/cn
# ─────────────────────────────────────────────
def scrape_burkert():
    print("\n→ Bürkert 产品抓取（中国官网）...")
    products = []
    base = "https://www.burkert.com.cn"

    # 先探产品总览页
    for path in ["/cn/type/Products", "/cn/products", "/cn"]:
        r = safe_get(base + path)
        if r and len(r.text) > 1000:
            soup = BeautifulSoup(r.text, "lxml")

            # 找产品链接：Type编号 或 /product/ 路径
            prod_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if (("/type/Type" in href or "/product" in href.lower())
                        and text and 2 < len(text) < 80):
                    full = href if href.startswith("http") else base + href
                    if full not in [u for _, u in prod_links]:
                        prod_links.append((text, full))

            if prod_links:
                print(f"  找到 {len(prod_links)} 个产品链接")
                for name, url in prod_links[:30]:
                    r2 = safe_get(url)
                    if not r2:
                        continue
                    soup2 = BeautifulSoup(r2.text, "lxml")
                    desc_el = (
                        soup2.find("div", class_=lambda c: c and "description" in str(c).lower())
                        or soup2.find("div", class_=lambda c: c and "intro" in str(c).lower())
                        or soup2.find("p")
                    )
                    desc = desc_el.get_text(strip=True)[:300] if desc_el else ""

                    # 应用行业标签
                    tags = [t.get_text(strip=True) for t in
                            soup2.find_all(["span","li"],
                                           class_=lambda c: c and "tag" in str(c).lower())
                            if t.get_text(strip=True) and len(t.get_text(strip=True)) < 30]

                    products.append({
                        "id":      make_id(name + url),
                        "company": "Bürkert",
                        "name":    name,
                        "url":     url,
                        "desc":    desc,
                        "tags":    tags[:6],
                        "source":  "burkert.com.cn",
                        "scraped": today,
                    })
                    time.sleep(0.6)
                break

    # 兜底：已知核心型号
    if len(products) < 5:
        print("  页面解析不足，补充已知型号")
        known = [
            ("Type 6012 - 隔膜阀（卫生级）",     ["制药","食品饮料","生物制品"]),
            ("Type 6223 - 角座阀",               ["食品饮料","制药","化工"]),
            ("Type 2000 - 两通电磁阀",            ["通用工业","化工"]),
            ("Type 3280 - 气动调节阀",            ["制药","生物制品"]),
            ("Robolux - 多通隔膜阀",              ["制药","生物制品"]),
            ("Type 8681 - 质量流量控制器",         ["半导体","实验室"]),
            ("Type 8802 - 过程控制器",            ["制药","食品饮料"]),
            ("Type 2301 - 气动隔膜阀",            ["制药","食品饮料"]),
            ("Type 3260 - 球形调节阀",            ["化工","石化"]),
            ("Type 8630 - 电感式电导率传感器",     ["制药","水处理"]),
        ]
        for name, industries in known:
            products.append({
                "id":        make_id(name),
                "company":   "Bürkert",
                "name":      name,
                "url":       base + "/cn/type/Products",
                "desc":      "",
                "industries": industries,
                "source":    "builtin_cache",
                "scraped":   today,
            })

    print(f"  Bürkert: {len(products)} 个产品")
    return products


# ─────────────────────────────────────────────
# Gemü（盖米）
# sitemap → 产品页抓取，JS渲染兜底已知系列
# ─────────────────────────────────────────────
def scrape_gemu():
    print("\n→ Gemü（盖米）产品抓取...")
    products = []
    base = "https://www.gemu-group.com"

    # 通过 sitemap 找产品 URL
    prod_urls = []
    r = safe_get(base + "/sitemap.xml")
    if r:
        soup = BeautifulSoup(r.text, "lxml-xml")
        prod_urls = [
            loc.get_text(strip=True) for loc in soup.find_all("loc")
            if "/en/products/" in loc.get_text()
            and loc.get_text().count("/") > 5
        ]
        print(f"  Sitemap 找到 {len(prod_urls)} 个产品 URL")

    for url in prod_urls[:25]:
        r2 = safe_get(url)
        if not r2:
            continue
        soup2 = BeautifulSoup(r2.text, "lxml")
        h1 = soup2.find("h1")
        name = h1.get_text(strip=True) if h1 else url.rstrip("/").split("/")[-1]
        if not name or len(name) < 3:
            continue
        desc_el = soup2.find("p")
        desc = desc_el.get_text(strip=True)[:300] if desc_el else ""
        products.append({
            "id":      make_id(name + url),
            "company": "Gemü",
            "name":    name,
            "url":     url,
            "desc":    desc,
            "source":  "gemu-group.com",
            "scraped": today,
        })
        time.sleep(0.5)

    # 兜底已知系列
    if len(products) < 5:
        print("  Sitemap 抓取不足，补充已知系列")
        known = [
            ("Series 515 - 无菌隔膜阀",    ["制药","生物制品"]),
            ("Series 500 - 隔膜阀",        ["制药","食品饮料","生物制品"]),
            ("Series 600 - 隔膜阀",        ["制药","化工"]),
            ("Series 650 - 调节阀",        ["制药","化工"]),
            ("Series 700 - 蝶阀",          ["食品饮料","水处理"]),
            ("Series 612 - 球阀",          ["化工","石化"]),
            ("Series R686 - 隔膜调节阀",   ["制药","生物制品"]),
            ("Series 3/47 - 蝶阀",         ["食品饮料","化工"]),
            ("Type 1435 - 截止调节阀",     ["石化","化工"]),
        ]
        for name, industries in known:
            products.append({
                "id":        make_id(name),
                "company":   "Gemü",
                "name":      name,
                "url":       base + "/en/products/",
                "desc":      "",
                "industries": industries,
                "source":    "builtin_cache",
                "scraped":   today,
            })

    print(f"  Gemü: {len(products)} 个产品")
    return products


# ─────────────────────────────────────────────
# ESG 中国官网
# 入口：www.esgvalve.cn
# ─────────────────────────────────────────────
def scrape_esg():
    print("\n→ ESG（青岛精锐）产品抓取...")
    products = []
    base = "https://www.esgvalve.cn"

    for path in ["/product", "/products", "/product/", "/"]:
        r = safe_get(base + path)
        if r and len(r.text) > 500:
            soup = BeautifulSoup(r.text, "lxml")
            prod_links = []
            for a in soup.find_all("a", href=True):
                href = a["href"]
                text = a.get_text(strip=True)
                if (("product" in href.lower() or "valve" in href.lower()
                     or "阀" in text)
                        and text and 2 < len(text) < 60):
                    full = href if href.startswith("http") else base + href
                    if full not in [u for _, u in prod_links] and full != base + path:
                        prod_links.append((text, full))

            if prod_links:
                print(f"  找到 {len(prod_links)} 个产品链接")
                for name, url in prod_links[:25]:
                    r2 = safe_get(url)
                    if not r2:
                        continue
                    soup2 = BeautifulSoup(r2.text, "lxml")
                    desc_el = (
                        soup2.find("div", class_=lambda c: c and
                                   any(k in str(c).lower() for k in ["desc","content","detail","intro"]))
                        or soup2.find("p")
                    )
                    desc = desc_el.get_text(strip=True)[:300] if desc_el else ""
                    products.append({
                        "id":      make_id(name + url),
                        "company": "ESG",
                        "name":    name,
                        "url":     url,
                        "desc":    desc,
                        "source":  "esgvalve.cn",
                        "scraped": today,
                    })
                    time.sleep(0.6)
                break

    # 兜底
    if len(products) < 3:
        print("  补充 ESG 已知产品")
        known = [
            ("气动角座阀",        ["食品饮料","制药","化工"]),
            ("ASME-BPE 隔膜阀",  ["制药","生物制品"]),
            ("热动力疏水阀",      ["食品饮料","化工"]),
            ("对夹式止回阀",      ["食品饮料","水处理"]),
            ("不锈钢球阀",        ["通用工业","化工"]),
            ("气动蝶阀",          ["食品饮料","水处理"]),
        ]
        for name, industries in known:
            products.append({
                "id":        make_id(name),
                "company":   "ESG",
                "name":      name,
                "url":       base + "/product/",
                "industries": industries,
                "source":    "builtin_cache",
                "scraped":   today,
            })

    print(f"  ESG: {len(products)} 个产品")
    return products


# ─────────────────────────────────────────────
# 主函数
# ─────────────────────────────────────────────
def main():
    print(f"\n{'='*55}")
    print(f"竞品产品抓取  {today}")
    print(f"Bürkert → burkert.com.cn/cn")
    print(f"Gemü    → gemu-group.com（sitemap）")
    print(f"ESG     → esgvalve.cn")
    print(f"{'='*55}")

    all_products = []
    all_products += scrape_burkert()
    all_products += scrape_gemu()
    all_products += scrape_esg()

    out = {
        "scraped_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total":      len(all_products),
        "by_company": {
            c: len([p for p in all_products if p["company"] == c])
            for c in ["Bürkert", "Gemü", "ESG"]
        },
        "products": all_products,
    }

    out_file = Path("data/products_raw.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)

    print(f"\n→ 共 {len(all_products)} 个产品")
    for c, n in out["by_company"].items():
        print(f"   {c}: {n}")
    print(f"→ 写入: {out_file}")

if __name__ == "__main__":
    main()
