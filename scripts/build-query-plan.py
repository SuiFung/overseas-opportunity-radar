#!/usr/bin/env python3
"""Build a cloud-native web-search plan. No network calls are made here."""
from __future__ import annotations
import argparse, datetime as dt, json
from pathlib import Path


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--output-json", type=Path, required=True)
    p.add_argument("--query", default="")
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--limit", type=int, default=8)
    p.add_argument("--sources", default="balanced")
    a = p.parse_args()
    if a.days < 1 or a.limit < 1:
        p.error("--days and --limit must be positive integers")
    reg = json.loads(a.registry.read_text(encoding="utf-8"))
    by_id = {s["id"]: s for s in reg["sources"]}
    ids = reg.get("profiles", {}).get(a.sources)
    if ids is None:
        ids = [x.strip() for x in a.sources.split(",") if x.strip()]
    unknown = [x for x in ids if x not in by_id]
    if unknown:
        p.error("Unknown source IDs: " + ", ".join(unknown))
    tasks = []
    for sid in ids:
        s = by_id[sid]
        base_queries = list(s.get("queries", []))
        if a.query.strip():
            base_queries = [f"{q} {a.query.strip()}" for q in base_queries] or [a.query.strip()]
        tasks.append({
            "source_id": sid,
            "label": s["label"],
            "category": s["category"],
            "radar_layer": s.get("radar_layer", ""),
            "signal_role": s.get("signal_role", "supporting"),
            "domains": s.get("domains", []),
            "purpose": s.get("purpose", ""),
            "queries": base_queries,
            "recency_days": min(a.days, int(s.get("recency_days", a.days))),
            "result_limit": a.limit,
            "instructions": "Use built-in web search. Prefer original source pages; verify important candidates by opening source pages when possible. Treat core sources as discovery inputs and validation sources as corroboration rather than standalone proof of novelty."
        })
    payload = {
        "runtime": reg.get("runtime", "cloud-native-web-search"),
        "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "query": a.query,
        "days": a.days,
        "limit": a.limit,
        "sources": ids,
        "default_topics": reg.get("default_topics", []),
        "tasks": tasks,
    }
    a.output_json.parent.mkdir(parents=True, exist_ok=True)
    a.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(a.output_json)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
