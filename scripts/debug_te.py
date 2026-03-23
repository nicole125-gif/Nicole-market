#!/usr/bin/env python3
"""
调试脚本：打印TE页面原始HTML结构，帮助确认正则
"""
import urllib.request, re

url = "https://tradingeconomics.com/china/indicators"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
})
with urllib.request.urlopen(req, timeout=20) as r:
    page = r.read().decode("utf-8", errors="ignore")

print(f"页面总长度: {len(page)}")

# 找Industrial Production附近原始HTML
for keyword in ["Industrial Production", "Producer Prices", "Exports YoY", "GDP Annual"]:
    idx = page.find(keyword)
    if idx >= 0:
        print(f"\n=== {keyword} @{idx} ===")
        print(page[idx-50:idx+200])
    else:
        print(f"\n=== {keyword}: 未找到 ===")
