#!/usr/bin/env python3
"""Validate agent-produced evidence JSON using only the Python standard library."""
from __future__ import annotations
import json, sys
from pathlib import Path
from urllib.parse import urlsplit


def fail(msg: str) -> None:
    raise ValueError(msg)


def main() -> int:
    if len(sys.argv) != 2:
        print("Usage: validate-evidence.py <evidence.json>", file=sys.stderr)
        return 2
    path = Path(sys.argv[1])
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict): fail("root must be an object")
        if not data.get("collected_at"): fail("collected_at is required")
        results = data.get("results")
        if not isinstance(results, list): fail("results must be an array")
        record_count = 0
        for ri, result in enumerate(results):
            if not isinstance(result, dict): fail(f"results[{ri}] must be an object")
            if not result.get("source_id"): fail(f"results[{ri}].source_id is required")
            records = result.get("records")
            if not isinstance(records, list): fail(f"results[{ri}].records must be an array")
            for i, record in enumerate(records):
                prefix = f"results[{ri}].records[{i}]"
                if not isinstance(record, dict): fail(f"{prefix} must be an object")
                for field in ("title", "url", "summary", "evidence_type"):
                    if field not in record or not isinstance(record[field], str):
                        fail(f"{prefix}.{field} must be a string")
                u = urlsplit(record["url"])
                if u.scheme not in {"http", "https"} or not u.netloc:
                    fail(f"{prefix}.url must be an absolute http(s) URL")
                record_count += 1
        print(f"Evidence OK: {len(results)} source groups, {record_count} records")
        return 0
    except (OSError, json.JSONDecodeError, ValueError) as e:
        print(f"Evidence invalid: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
