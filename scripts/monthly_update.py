#!/usr/bin/env python3
"""
Monthly Nicole Intelligence update orchestrator.

The script keeps the existing scoring/injection code as the source of truth and
adds the monthly shell around it: public report collection, optional RAG rebuild,
manual overrides, and a PR-ready summary.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CONFIG_DIR = ROOT / "config"
DATA_MONTHLY = ROOT / "data" / "monthly"
REPORT_HASH_FILE = DATA_MONTHLY / "report_hashes.json"


def load_yaml(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        import yaml
    except ImportError as exc:
        raise RuntimeError("PyYAML is required for monthly YAML config files") from exc
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data or {}


def normalize_period(value: str | None) -> str:
    if value:
        try:
            parsed = dt.datetime.strptime(value, "%Y-%m")
        except ValueError as exc:
            raise SystemExit("--period must use YYYY-MM, for example 2026-06") from exc
        return parsed.strftime("%Y-%m")
    return dt.date.today().strftime("%Y-%m")


def _load_hashes() -> dict:
    if REPORT_HASH_FILE.exists():
        return json.loads(REPORT_HASH_FILE.read_text(encoding="utf-8"))
    return {}


def _save_hashes(hashes: dict) -> None:
    DATA_MONTHLY.mkdir(parents=True, exist_ok=True)
    REPORT_HASH_FILE.write_text(json.dumps(hashes, ensure_ascii=False, indent=2), encoding="utf-8")


def _allowed(url: str, domains: list[str]) -> bool:
    host = urlparse(url).netloc.lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in domains)


def _safe_name(text: str, suffix: str) -> str:
    keep = "".join(ch if ch.isalnum() or ch in "-_." else "_" for ch in text).strip("_")
    return (keep[:80] or "report") + suffix


def search_public_report(query: str, domains: list[str]) -> tuple[str | None, str | None]:
    api_key = os.environ.get("BRAVE_API_KEY", "")
    if not api_key:
        return None, "BRAVE_API_KEY is not configured"

    params = urllib.parse.urlencode({"q": query, "count": 8, "freshness": "pm"})
    req = urllib.request.Request(
        f"https://api.search.brave.com/res/v1/web/search?{params}",
        headers={"Accept": "application/json", "X-Subscription-Token": api_key},
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        data = json.loads(resp.read())
    for item in data.get("web", {}).get("results", []):
        url = item.get("url", "")
        if url and _allowed(url, domains):
            return url, None
    return None, "no allowed result"


def download_public_reports(period: str, config: dict, dry_run: bool = False) -> dict:
    report = {"downloaded": [], "skipped": [], "failed": []}
    sources = config.get("report_sources", {})
    target_dir = ROOT / "reports" / period
    hashes = _load_hashes()

    for vertical, spec in sources.items():
        domains = spec.get("domains", [])
        for query in spec.get("queries", []):
            try:
                url, reason = search_public_report(query, domains)
                if not url:
                    report["failed"].append({"vertical": vertical, "query": query, "reason": reason})
                    continue
                if dry_run:
                    report["skipped"].append({"vertical": vertical, "query": query, "url": url, "reason": "dry-run"})
                    continue

                with urllib.request.urlopen(url, timeout=30) as resp:
                    content = resp.read()
                    content_type = resp.headers.get("Content-Type", "")
                digest = hashlib.sha256(content).hexdigest()
                if digest in hashes:
                    report["skipped"].append({"vertical": vertical, "query": query, "url": url, "reason": "duplicate"})
                    continue

                suffix = ".pdf" if "pdf" in content_type.lower() or url.lower().endswith(".pdf") else ".html"
                target_dir.mkdir(parents=True, exist_ok=True)
                path = target_dir / _safe_name(f"{vertical}_{query}", suffix)
                path.write_bytes(content)
                hashes[digest] = {"url": url, "path": str(path.relative_to(ROOT)), "period": period}
                report["downloaded"].append({"vertical": vertical, "query": query, "url": url, "path": str(path.relative_to(ROOT))})
            except Exception as exc:
                report["failed"].append({"vertical": vertical, "query": query, "reason": str(exc)})

    if not dry_run:
        _save_hashes(hashes)
    return report


def run_command(cmd: list[str], dry_run: bool = False) -> None:
    print("$ " + " ".join(cmd))
    if dry_run:
        return
    subprocess.run(cmd, cwd=ROOT, check=True)


def rebuild_rag(dry_run: bool = False) -> None:
    code = r"""
from pathlib import Path
import hashlib, json, os

REPORTS_DIR = Path("reports")
DB_DIR = "pulse_vectordb"
HASH_FILE = Path("data/reports_hash.json")

current_hash = {}
for pattern in ("*.pdf", "*.html"):
    for p in sorted(REPORTS_DIR.rglob(pattern)):
        current_hash[str(p)] = hashlib.md5(p.read_bytes()).hexdigest()

prev_hash = json.loads(HASH_FILE.read_text()) if HASH_FILE.exists() else {}
if current_hash == prev_hash:
    print("RAG inputs unchanged; skip rebuild")
    raise SystemExit(0)

from langchain_community.document_loaders import PyPDFLoader, UnstructuredHTMLLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
import chromadb

docs = []
for p in sorted(REPORTS_DIR.rglob("*.pdf")):
    try:
        loaded = PyPDFLoader(str(p)).load()
        for d in loaded: d.metadata["source_file"] = str(p)
        docs.extend(loaded)
    except Exception as exc:
        print(f"Skip PDF {p}: {exc}")
for p in sorted(REPORTS_DIR.rglob("*.html")):
    try:
        loaded = UnstructuredHTMLLoader(str(p)).load()
        for d in loaded: d.metadata["source_file"] = str(p)
        docs.extend(loaded)
    except Exception as exc:
        print(f"Skip HTML {p}: {exc}")

if not docs:
    print("No RAG docs loaded")
    raise SystemExit(0)

chunks = RecursiveCharacterTextSplitter(chunk_size=600, chunk_overlap=100).split_documents(docs)
embedder = SentenceTransformer("BAAI/bge-small-zh-v1.5")
client = chromadb.PersistentClient(path=DB_DIR)
if "reports" in [c.name for c in client.list_collections()]:
    client.delete_collection("reports")
collection = client.create_collection("reports")
for i in range(0, len(chunks), 50):
    batch = chunks[i:i+50]
    texts = [c.page_content for c in batch]
    collection.add(
        ids=[f"chunk_{i+j}" for j in range(len(batch))],
        embeddings=embedder.encode(texts, show_progress_bar=False).tolist(),
        documents=texts,
        metadatas=[c.metadata for c in batch],
    )
os.makedirs("data", exist_ok=True)
HASH_FILE.write_text(json.dumps(current_hash, ensure_ascii=False, indent=2))
print(f"RAG DB ready: {collection.count()} chunks")
"""
    run_command([sys.executable, "-c", code], dry_run=dry_run)


def apply_overrides(payload: dict, overrides: dict) -> tuple[dict, list[str]]:
    applied: list[str] = []
    for tid, fields in (overrides.get("tracks") or {}).items():
        payload.setdefault("tracks", {}).setdefault(tid, {}).update(fields)
        applied.append(f"track:{tid}")
    for tid, fields in (overrides.get("track_use") or {}).items():
        payload.setdefault("track_use", {})[tid] = fields
        applied.append(f"track_use:{tid}")
    if overrides.get("kpis"):
        payload["kpis"] = overrides["kpis"]
        applied.append("kpis")
    if overrides.get("review_notes"):
        payload["review_notes"] = overrides["review_notes"]
        applied.append("review_notes")
    return payload, applied


def payload_from_history(period: str) -> dict:
    hist_path = ROOT / "data" / "history.json"
    if not hist_path.exists():
        return {"tracks": {}}
    history = json.loads(hist_path.read_text(encoding="utf-8"))
    key = period.replace("-", "")
    current = history.get(key, {})
    previous_periods = sorted([p for p in history if p < key], reverse=True)
    previous = history.get(previous_periods[0], {}) if previous_periods else {}
    tracks = {}
    for tid, values in current.items():
        prev_heat = previous.get(tid, {}).get("heat", values.get("heat", 50))
        tracks[tid] = {
            "heat": values.get("heat", 50),
            "delta": round(values.get("heat", 50) - prev_heat, 1),
            "tr": values.get("trend", "fl"),
        }
    return {"tracks": tracks}


def write_summary(
    path: Path,
    period: str,
    payload: dict,
    source_report: dict,
    applied_overrides: list[str],
    review_notes: list[str],
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tracks = payload.get("tracks", {})
    ranked = sorted(tracks.items(), key=lambda item: item[1].get("heat", 0), reverse=True)
    falling = sorted(tracks.items(), key=lambda item: item[1].get("delta", 0))
    top_line = f"{ranked[0][0]} {ranked[0][1].get('heat')}" if ranked else "N/A"
    drop_line = f"{falling[0][0]} {falling[0][1].get('delta'):+.1f}" if falling else "N/A"

    lines = [
        f"# Nicole Intelligence Monthly Update · {period}",
        "",
        f"- 更新批次：{period}",
        f"- 新增报告数量：{len(source_report.get('downloaded', []))}",
        f"- 数据源失败数量：{len(source_report.get('failed', []))}",
        f"- 最高 Heat：{top_line}",
        f"- 最大下滑：{drop_line}",
        "",
        "## 赛道分数变化",
    ]
    for tid, values in ranked:
        lines.append(f"- {tid}: Heat {values.get('heat')} / Delta {values.get('delta', 0):+}")

    lines.extend(["", "## 数据源失败"])
    if source_report.get("failed"):
        for item in source_report["failed"]:
            lines.append(f"- {item.get('vertical', '-')}: {item.get('query', '-')} · {item.get('reason', '-')}")
    else:
        lines.append("- 无")

    lines.extend(["", "## 人工覆盖项"])
    lines.extend([f"- {item}" for item in applied_overrides] or ["- 无"])

    lines.extend(["", "## 需要重点审核"])
    lines.extend([f"- {item}" for item in review_notes] or ["- 自动生成内容与新增报告来源"])

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_monthly_update(args: argparse.Namespace) -> None:
    period = normalize_period(args.period)
    sources = load_yaml(CONFIG_DIR / "monthly_sources.yml")
    overrides = load_yaml(CONFIG_DIR / "monthly_overrides.yml")
    print(f"=== Nicole Intelligence monthly update · {period} ===")

    source_report = download_public_reports(period, sources, dry_run=args.dry_run)
    run_command([sys.executable, "fetch_rss.py"], dry_run=args.dry_run)
    rebuild_rag(dry_run=args.dry_run)
    run_command([sys.executable, "scripts/update_news.py"], dry_run=args.dry_run)

    payload = payload_from_history(period)
    payload, applied = apply_overrides(payload, overrides if overrides.get("period") in (None, period) else {})
    if applied and not args.dry_run:
        sys.path.insert(0, str(ROOT / "scripts"))
        from inject_scores import inject_scores

        inject_scores(payload, index_path=ROOT / "index.html", backup=False)

    summary_path = DATA_MONTHLY / f"{period}-summary.md"
    if args.dry_run:
        print(f"[dry-run] Would write {summary_path.relative_to(ROOT)}")
        print(json.dumps({"source_report": source_report, "applied_overrides": applied}, ensure_ascii=False, indent=2))
    else:
        write_summary(
            path=summary_path,
            period=period,
            payload=payload,
            source_report=source_report,
            applied_overrides=applied,
            review_notes=payload.get("review_notes", []),
        )
        print(f"[OK] Summary written → {summary_path.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--period", help="Monthly period in YYYY-MM format")
    parser.add_argument("--dry-run", action="store_true", help="Plan the update without writing site files")
    args = parser.parse_args()
    run_monthly_update(args)


if __name__ == "__main__":
    main()
