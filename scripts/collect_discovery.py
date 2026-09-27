#!/usr/bin/env python3
"""Collect structured opportunity-discovery evidence from configured source adapters."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


USER_AGENT = "overseas-opportunity-radar/1.0 (+opportunity discovery)"


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def request_json(url: str, *, timeout: int = 20) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def request_text(url: str, *, timeout: int = 20) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/plain, text/html"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str], *, timeout: int = 20) -> Any:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def truncate(value: str | None, length: int = 300) -> str:
    clean = re.sub(r"\s+", " ", value or "").strip()
    return clean if len(clean) <= length else f"{clean[:length - 1]}…"


def status(source: dict[str, Any], state: str, detail: str, records: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {
        "source_id": source["id"],
        "label": source["label"],
        "category": source["category"],
        "adapter": source["adapter"],
        "status": state,
        "detail": detail,
        "records": records or [],
    }


def parse_json_output(output: str) -> Any:
    """Decode CLI JSON while tolerating update notices emitted after the payload."""
    decoder = json.JSONDecoder()
    for marker in ("[", "{"):
        offset = output.find(marker)
        if offset < 0:
            continue
        try:
            value, _ = decoder.raw_decode(output[offset:])
            return value
        except json.JSONDecodeError:
            continue
    raise ValueError("No JSON payload found in command output")


def get_field(item: dict[str, Any], field: str | None) -> Any:
    if not field:
        return None
    current: Any = item
    for part in field.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def expand_arguments(parts: list[str], limit: int) -> list[str]:
    return [part.replace("{limit}", str(limit)) for part in parts]


def map_opencli_records(source: dict[str, Any], payload: Any, *, evidence_type: str) -> list[dict[str, Any]]:
    if not isinstance(payload, list):
        raise ValueError("OpenCLI returned a non-list payload")
    field_map = source.get("field_map", {})
    signal_map = field_map.get("signal", {})
    records: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        title = get_field(item, field_map.get("title"))
        url = get_field(item, field_map.get("url"))
        if not title or not url:
            continue
        records.append(
            {
                "title": str(title),
                "url": str(url),
                "published_at": get_field(item, field_map.get("published_at")),
                "signal": {key: value for key, source_field in signal_map.items() if (value := get_field(item, source_field)) is not None},
                "summary": truncate(str(get_field(item, field_map.get("summary")) or "")),
                "evidence_type": evidence_type,
            }
        )
    return records


def collect_opencli_json(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Run an OpenCLI adapter described entirely by the source registry.

    OpenCLI site adapters provide compact, structured outputs. A source can include
    a non-browser fallback for a disconnected Chrome Bridge without duplicating
    provider-specific logic in this collector.
    """
    if not shutil.which("opencli"):
        return status(source, "unavailable", "opencli is not installed; use the source's configured public fallback in the active agent.")

    attempts = [(source["command"], source.get("arguments", []), source.get("evidence_type", "OpenCLI source result"), "primary")]
    fallback = source.get("fallback")
    if fallback:
        attempts.append((fallback["command"], fallback.get("arguments", []), fallback.get("evidence_type", source.get("evidence_type", "OpenCLI fallback result")), "fallback"))

    errors: list[str] = []
    for command_parts, argument_parts, evidence_type, route in attempts:
        command = ["opencli", *command_parts, *expand_arguments(argument_parts, args.limit), "-f", "json"]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=True, timeout=15)
            records = map_opencli_records(source, parse_json_output(completed.stdout), evidence_type=evidence_type)
            detail = f"Collected {len(records)} structured records via OpenCLI {' '.join(command_parts)}."
            if route == "fallback":
                detail = f"Primary OpenCLI route failed; {detail}"
            return status(source, "collected", detail, records)
        except subprocess.TimeoutExpired:
            errors.append(f"{' '.join(command_parts)} timed out")
        except (subprocess.SubprocessError, ValueError) as error:
            stderr = getattr(error, "stderr", "") or ""
            errors.append(truncate(stderr or str(error), 240))
    return status(source, "failed", f"OpenCLI routes failed: {'; '.join(errors)}")


def collect_hacker_news(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    try:
        if args.query.strip():
            since = int((dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).timestamp())
            parameters = urllib.parse.urlencode(
                {
                    "query": args.query.strip(),
                    "tags": "show_hn",
                    "numericFilters": f"created_at_i>={since}",
                    "hitsPerPage": args.limit,
                }
            )
            payload = request_json(f"https://hn.algolia.com/api/v1/search?{parameters}")
            records = [
                {
                    "title": item.get("title") or item.get("story_title") or "Untitled",
                    "url": item.get("url") or f"https://news.ycombinator.com/item?id={item['objectID']}",
                    "discussion_url": f"https://news.ycombinator.com/item?id={item['objectID']}",
                    "published_at": item.get("created_at"),
                    "signal": {"score": item.get("points", 0), "comments": item.get("num_comments", 0)},
                    "summary": truncate(item.get("story_text") or item.get("comment_text") or item.get("title")),
                    "evidence_type": "Show HN query result and discussion",
                }
                for item in payload.get("hits", [])
            ]
            return status(source, "collected", f"Collected {len(records)} query-matched Show HN stories via the HN search index; query: {args.query.strip()}", records)
        ids = request_json("https://hacker-news.firebaseio.com/v0/showstories.json")[:args.limit]
        records: list[dict[str, Any]] = []
        for item_id in ids:
            item = request_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
            if not item or item.get("type") != "story":
                continue
            records.append(
                {
                    "title": item.get("title", "Untitled"),
                    "url": item.get("url") or f"https://news.ycombinator.com/item?id={item_id}",
                    "discussion_url": f"https://news.ycombinator.com/item?id={item_id}",
                    "published_at": dt.datetime.fromtimestamp(item.get("time", 0), tz=dt.timezone.utc).isoformat(),
                    "signal": {"score": item.get("score", 0), "comments": item.get("descendants", 0)},
                    "summary": truncate(item.get("text") or item.get("title")),
                    "evidence_type": "Show HN launch and discussion",
                }
            )
            if len(records) >= args.limit:
                break
        return status(source, "collected", f"Collected {len(records)} current Show HN stories via the official Firebase API.", records)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return status(source, "failed", f"Official Hacker News API request failed: {error}")


def collect_github(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    since = (dt.date.today() - dt.timedelta(days=args.days)).isoformat()
    query = " ".join(part for part in [args.query.strip(), f"created:>={since}"] if part)
    command = ["gh", "api", "-X", "GET", "search/repositories", "-f", f"q={query}", "-f", "sort=stars", "-f", "order=desc", "-f", f"per_page={args.limit}"]
    cli_error = ""
    try:
        if shutil.which("gh"):
            try:
                completed = subprocess.run(command, capture_output=True, text=True, check=True, timeout=30)
                payload = json.loads(completed.stdout)
                route = "GitHub CLI / authenticated REST API"
            except (subprocess.SubprocessError, ValueError) as error:
                cli_error = truncate(getattr(error, "stderr", "") or str(error), 300)
                payload = None
        else:
            payload = None
        if payload is None:
            parameters = urllib.parse.urlencode({"q": query, "sort": "stars", "order": "desc", "per_page": args.limit})
            payload = request_json(f"https://api.github.com/search/repositories?{parameters}")
            route = "GitHub public REST API" if not cli_error else f"GitHub public REST API fallback after CLI error: {cli_error}"
        records = [
            {
                "title": item["full_name"],
                "url": item["html_url"],
                "published_at": item.get("created_at"),
                "signal": {"stars": item.get("stargazers_count", 0), "forks": item.get("forks_count", 0)},
                "summary": truncate(item.get("description")),
                "evidence_type": "recent repository with star signal",
            }
            for item in payload.get("items", [])
        ]
        return status(source, "collected", f"Collected {len(records)} repositories via {route}; query: {query}", records)
    except (subprocess.SubprocessError, urllib.error.URLError, TimeoutError, ValueError) as error:
        detail = truncate(str(error), 500)
        if cli_error:
            detail = f"CLI error: {cli_error}; public REST fallback error: {detail}"
        return status(source, "failed", f"GitHub search failed: {detail}")


def collect_github_trending(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    try:
        text = request_text("https://r.jina.ai/http://github.com/trending?since=weekly", timeout=30)
        blocks = re.split(r"\n## ", text)
        records: list[dict[str, Any]] = []
        for block in blocks[1:]:
            header, _, remainder = block.partition("\n")
            match = re.match(r"\[([^\]]+?) / ([^\]]+?)\]\((?:http|https)://github\.com/([^/()\s]+)/([^/)\s]+)\)", header)
            stars = re.search(r"([\d,]+) stars this week", remainder)
            if not match or not stars:
                continue
            lines = [line.strip() for line in remainder.splitlines()]
            description = next((line for line in lines if line and "stars this week" not in line and "Built by" not in line and not line.startswith("[")), "")
            owner, repo = match.group(3), match.group(4)
            records.append(
                {
                    "title": f"{owner}/{repo}",
                    "url": f"https://github.com/{owner}/{repo}",
                    "published_at": utc_now(),
                    "signal": {"stars_this_week": int(stars.group(1).replace(",", ""))},
                    "summary": truncate(description),
                    "evidence_type": "GitHub Trending weekly leaderboard entry",
                }
            )
            if len(records) >= args.limit:
                break
        return status(source, "collected", f"Collected {len(records)} GitHub Trending weekly leaderboard entries.", records)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return status(source, "failed", f"GitHub Trending request failed: {error}")


def collect_github_markdown_catalog(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Read date-grouped product entries from a maintained GitHub Markdown catalog."""
    repository = source["repository"]
    branch = source.get("branch", "main")
    path = source.get("path", "README.md")
    encoded_path = "/".join(urllib.parse.quote(part) for part in path.split("/"))
    raw_url = f"https://raw.githubusercontent.com/{repository}/{branch}/{encoded_path}"
    section_pattern = re.compile(r"^###\s*(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*号添加\s*$")
    product_pattern = re.compile(
        r"^\s*\*\s*:(?P<state>[^:]+):\s*\[(?P<title>[^]]+)\]\((?P<url>[^)\s]+)\)\s*[：:]?\s*(?P<summary>.*)$"
    )
    try:
        text = request_text(raw_url, timeout=30)
        cutoff = dt.date.today() - dt.timedelta(days=args.days)
        section_date: dt.date | None = None
        records: list[dict[str, Any]] = []
        skipped_old_sections = 0
        for line in text.splitlines():
            section_match = section_pattern.match(line)
            if section_match:
                section_date = dt.date(*(int(value) for value in section_match.groups()))
                continue
            if section_date is None:
                continue
            if section_date < cutoff:
                skipped_old_sections += 1
                continue
            product_match = product_pattern.match(line)
            if not product_match:
                continue
            product_url = product_match.group("url")
            if not product_url.startswith(("http://", "https://")):
                continue
            state = product_match.group("state").strip()
            records.append(
                {
                    "title": product_match.group("title").strip(),
                    "url": product_url,
                    "published_at": section_date.isoformat(),
                    "signal": {"catalog_status": state, "catalog_date": section_date.isoformat()},
                    "summary": truncate(product_match.group("summary")),
                    "evidence_type": f"Chinese Independent Developer catalog entry ({repository})",
                    "source_url": source.get("url", f"https://github.com/{repository}"),
                }
            )
            if len(records) >= args.limit:
                break
        detail = (
            f"Collected {len(records)} recent date-grouped catalog entries from {repository} "
            f"via its public README."
        )
        if skipped_old_sections:
            detail += f" Skipped {skipped_old_sections} section(s) older than {args.days} days."
        return status(source, "collected", detail, records)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return status(source, "failed", f"GitHub Markdown catalog request failed: {error}")


def collect_betalist_daily_list(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Collect every homepage entry explicitly grouped as Today or Yesterday."""
    try:
        html = request_text("https://betalist.com/", timeout=30)
        day_headers = list(re.finditer(r"<strong>\s*(Today|Yesterday)\s*</strong>\s*([^<]+)", html, re.IGNORECASE))
        # Match the outer card only. Nested card markup also mentions
        # `.startup-row` in Tailwind selector classes.
        rows = list(re.finditer(r'<div\s+class="[^"]*\bstartup-row">', html, re.IGNORECASE))
        records: list[dict[str, Any]] = []
        ranks = {"today": 0, "yesterday": 0}
        for index, row in enumerate(rows):
            block_end = rows[index + 1].start() if index + 1 < len(rows) else len(html)
            block = html[row.start():block_end]
            link = re.search(r'<a[^>]+href="/startups/([^"?#]+)"', block, re.IGNORECASE)
            text = re.search(
                r'font-medium\s+text-gray-900">\s*([^<]+?)\s*</span>\s*<span[^>]*text-gray-500[^>]*>\s*([^<]+?)\s*</span>',
                block,
                re.IGNORECASE | re.DOTALL,
            )
            preceding_headers = [header for header in day_headers if header.start() < row.start()]
            if not link or not text or not preceding_headers:
                continue
            day, displayed_date = preceding_headers[-1].group(1).lower(), truncate(preceding_headers[-1].group(2), 80)
            if day not in ranks:
                continue
            ranks[day] += 1
            records.append(
                {
                    "title": re.sub(r"\s+", " ", text.group(1)).strip(),
                    "url": f"https://betalist.com/startups/{link.group(1)}",
                    "published_at": None,
                    "signal": {"day": day, "rank_within_day": ranks[day], "displayed_date": displayed_date},
                    "summary": truncate(re.sub(r"\s+", " ", text.group(2)).strip()),
                    "evidence_type": f"BetaList homepage {day.title()} list entry",
                }
            )
        if not records or not ranks["today"] or not ranks["yesterday"]:
            return status(source, "failed", "BetaList homepage did not expose a complete Today and Yesterday startup list.")
        return status(
            source,
            "collected",
            f"Collected all currently rendered BetaList homepage entries: Today={ranks['today']}, Yesterday={ranks['yesterday']}.",
            records,
        )
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return status(source, "failed", f"BetaList homepage request failed: {error}")


def collect_apple_top_free(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    country = source.get("country", "us")
    try:
        payload = request_json(f"https://rss.marketingtools.apple.com/api/v2/{country}/apps/top-free/{args.limit}/apps.json")

        def genre_names(genres: Any) -> list[str]:
            if not isinstance(genres, list):
                return []
            return [
                str(genre.get("name") or genre.get("genreName") or genre.get("label"))
                if isinstance(genre, dict)
                else str(genre)
                for genre in genres
                if (isinstance(genre, dict) and (genre.get("name") or genre.get("genreName") or genre.get("label"))) or isinstance(genre, str)
            ]

        records = [
            {
                "title": item["name"],
                "url": item["url"],
                "published_at": item.get("releaseDate"),
                "signal": {"rank": index},
                "summary": truncate(f"{item.get('artistName', 'Unknown developer')} · {', '.join(genre_names(item.get('genres'))) or 'App Store'}"),
                "evidence_type": f"Apple App Store {country.upper()} Top Free leaderboard entry",
            }
            for index, item in enumerate(payload.get("feed", {}).get("results", []), start=1)
        ]
        return status(source, "collected", f"Collected {len(records)} Apple App Store {country.upper()} Top Free entries.", records)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return status(source, "failed", f"Apple App Store chart request failed: {error}")


def collect_exploding_topics_radar(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    api_key = os.environ.get("EXPLODING_TOPICS_API_KEY")
    if not api_key:
        return status(source, "unavailable", "EXPLODING_TOPICS_API_KEY is not configured; this optional official trend-radar source was not queried.")
    endpoint = source["endpoint"]
    parameters = urllib.parse.urlencode({"api_key": api_key, "type": "exploding", "sort": "growth", "order": "desc", "timeframe": 12, "limit": args.limit})
    try:
        payload = request_json(f"https://api.explodingtopics.com/api/v1/{endpoint}?{parameters}", timeout=30)
        records: list[dict[str, Any]] = []
        for item in payload.get("result", []):
            growth = item.get("growth", {})
            records.append(
                {
                    "title": item.get("name") or item.get("title") or item.get("keyword") or item.get("path", "Untitled"),
                    "url": item.get("url") or item.get("link") or f"https://explodingtopics.com/{item.get('path', '')}",
                    "published_at": item.get("date_added") or None,
                    "signal": {"growth_12_months_pct": growth.get("12") or growth.get(12), "search_volume": item.get("search_volume")},
                    "summary": truncate(item.get("description") or item.get("category") or source["purpose"]),
                    "evidence_type": f"Exploding Topics {endpoint} growth-radar entry",
                }
            )
        return status(source, "collected", f"Collected {len(records)} official Exploding Topics {endpoint} radar entries.", records)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return status(source, "failed", f"Exploding Topics API request failed: {error}")


def collect_product_hunt_candidates(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    token = os.environ.get("PRODUCT_HUNT_ACCESS_TOKEN")
    if not token:
        fallback = collect_exa_site_search({**source, "adapter": "exa-site-search"}, args)
        fallback["detail"] = "Product Hunt API token is not configured; " + fallback["detail"]
        return fallback
    cutoff = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=args.days)).replace(microsecond=0).isoformat()
    query = """query($first: Int!, $after: DateTime!) {
      posts(first: $first, order: RANKING, postedAfter: $after) {
        edges { node { name tagline url createdAt votesCount commentsCount } }
      }
    }"""
    try:
        payload = post_json(
            "https://api.producthunt.com/v2/api/graphql",
            {"query": query, "variables": {"first": args.limit, "after": cutoff}},
            {"Authorization": f"Bearer {token}", "Content-Type": "application/json", "User-Agent": USER_AGENT},
            timeout=30,
        )
        errors = payload.get("errors", [])
        if errors:
            return status(source, "failed", f"Product Hunt API returned: {truncate(str(errors), 500)}")
        nodes = payload.get("data", {}).get("posts", {}).get("edges", [])
        records = [
            {
                "title": edge["node"]["name"],
                "url": edge["node"]["url"],
                "published_at": edge["node"].get("createdAt"),
                "signal": {"votes": edge["node"].get("votesCount", 0), "comments": edge["node"].get("commentsCount", 0)},
                "summary": truncate(edge["node"].get("tagline")),
                "evidence_type": "Product Hunt recent ranking entry",
            }
            for edge in nodes
        ]
        return status(source, "collected", f"Collected {len(records)} Product Hunt ranked posts through the official GraphQL API.", records)
    except (urllib.error.URLError, TimeoutError, ValueError) as error:
        return status(source, "failed", f"Product Hunt API request failed: {error}")


def parse_exa_text(text: str) -> list[dict[str, Any]]:
    parts = re.split(r"\n\s*---\s*\n", text.strip())
    records: list[dict[str, Any]] = []
    for part in parts:
        title = re.search(r"^Title:\s*(.+)$", part, re.MULTILINE)
        url = re.search(r"^URL:\s*(.+)$", part, re.MULTILINE)
        published = re.search(r"^Published:\s*(.+)$", part, re.MULTILINE)
        highlights = re.search(r"^Highlights:\s*(.*)$", part, re.MULTILINE | re.DOTALL)
        if not title or not url:
            continue
        records.append(
            {
                "title": title.group(1).strip(),
                "url": url.group(1).strip(),
                "published_at": published.group(1).strip() if published else None,
                "signal": {},
                "summary": truncate(highlights.group(1) if highlights else ""),
                "evidence_type": "indexed public result",
            }
        )
    return records


def restrict_to_source_domains(records: list[dict[str, Any]], domains: list[str]) -> tuple[list[dict[str, Any]], int]:
    """Do not trust a search engine's site filter when attributing a result to a source."""
    if not domains:
        return records, 0
    accepted: list[dict[str, Any]] = []
    excluded = 0
    for record in records:
        hostname = urllib.parse.urlsplit(record["url"]).hostname or ""
        hostname = hostname.lower()
        if any(hostname == domain or hostname.endswith(f".{domain}") for domain in domains):
            accepted.append(record)
        else:
            excluded += 1
    return accepted, excluded


def parse_timestamp(value: str | None) -> dt.datetime | None:
    if not value or value == "N/A":
        return None
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=dt.timezone.utc)
    except ValueError:
        return None


def keep_indexed_records(records: list[dict[str, Any]], days: int, date_policy: str) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Preserve idea sources while tagging rather than hiding uncertain freshness."""
    now = dt.datetime.now(dt.timezone.utc)
    cutoff = now - dt.timedelta(days=days)
    kept: list[dict[str, Any]] = []
    excluded = {"missing_or_invalid_date": 0, "future_date": 0, "outside_window": 0}
    for record in records:
        published = parse_timestamp(record.get("published_at"))
        if not published and date_policy in {"allow-unknown", "keep-all"}:
            record["date_quality"] = "unknown"
            record["evidence_type"] = "indexed public result (date unavailable)"
            kept.append(record)
        elif not published:
            excluded["missing_or_invalid_date"] += 1
        elif published > now + dt.timedelta(days=1):
            excluded["future_date"] += 1
        elif published < cutoff and date_policy != "keep-all":
            excluded["outside_window"] += 1
        else:
            record["date_quality"] = "in_window" if published >= cutoff else "outside_window"
            record["evidence_type"] = "indexed public result (page date; not a verified product-launch date)"
            kept.append(record)
    return kept, excluded


def collect_exa_site_search(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    if not shutil.which("mcporter"):
        return status(source, "unavailable", "mcporter / configured Exa search is not installed; run an equivalent source search in the active agent.")
    domains = source.get("domains", [])
    query_terms = args.query.strip() or source["purpose"]
    site_filter = " OR ".join(f"site:{domain}" for domain in domains)
    query = f"({site_filter}) {query_terms}"
    command = ["mcporter", "call", "exa.web_search_exa", f"query={query}", f"numResults={args.limit}", "--output", "json"]
    try:
        completed = subprocess.run(command, capture_output=True, text=True, check=True, timeout=45)
        payload = json.loads(completed.stdout)
        content = payload.get("content", [])
        text = "\n".join(block.get("text", "") for block in content if block.get("type") == "text")
        parsed_records, wrong_domain_count = restrict_to_source_domains(parse_exa_text(text), domains)
        date_policy = source.get("date_policy", "strict")
        records, excluded = keep_indexed_records(parsed_records, args.days, date_policy)
        excluded_summary = ", ".join(f"{kind}={count}" for kind, count in excluded.items() if count)
        detail = f"Collected {len(records)} indexed public results through Exa (date policy: {date_policy}); query: {query}"
        if excluded_summary:
            detail += f". Excluded before reporting: {excluded_summary}."
        if wrong_domain_count:
            detail += f" Dropped {wrong_domain_count} result(s) outside the configured source domains."
        return status(source, "collected", detail, records)
    except subprocess.TimeoutExpired:
        return status(source, "failed", "Exa search timed out.")
    except (subprocess.SubprocessError, ValueError) as error:
        detail = getattr(error, "stderr", "") or str(error)
        return status(source, "failed", f"Exa search failed: {truncate(detail, 500)}")


def collect_source(source: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    adapter = source["adapter"]
    if adapter == "opencli-json":
        return collect_opencli_json(source, args)
    if adapter == "product-hunt-candidates":
        return collect_product_hunt_candidates(source, args)
    if adapter == "hacker-news-search":
        return collect_hacker_news(source, args)
    if adapter == "github-repositories":
        return collect_github(source, args)
    if adapter == "github-trending":
        return collect_github_trending(source, args)
    if adapter == "github-markdown-catalog":
        return collect_github_markdown_catalog(source, args)
    if adapter == "betalist-daily-list":
        return collect_betalist_daily_list(source, args)
    if adapter == "apple-top-free":
        return collect_apple_top_free(source, args)
    if adapter == "exploding-topics-radar":
        return collect_exploding_topics_radar(source, args)
    if adapter == "exa-site-search":
        return collect_exa_site_search(source, args)
    return status(source, "unavailable", f"No collector is implemented for adapter: {adapter}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect structured opportunity-discovery evidence.")
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--query", default="")
    parser.add_argument("--days", type=int, default=14)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--sources", default="balanced", help="A profile name or comma-separated source IDs.")
    args = parser.parse_args()
    if args.days < 1 or args.limit < 1:
        parser.error("--days and --limit must be positive integers")

    registry = json.loads(args.registry.read_text(encoding="utf-8"))
    sources_by_id = {source["id"]: source for source in registry["sources"]}
    selected_ids = registry["profiles"].get(args.sources, [item.strip() for item in args.sources.split(",") if item.strip()])
    unknown = [source_id for source_id in selected_ids if source_id not in sources_by_id]
    if unknown:
        parser.error(f"Unknown source IDs: {', '.join(unknown)}")
    selected = [sources_by_id[source_id] for source_id in selected_ids]

    def uses_exa(source: dict[str, Any]) -> bool:
        return source["adapter"] == "exa-site-search" or (
            source["adapter"] == "product-hunt-candidates" and not os.environ.get("PRODUCT_HUNT_ACCESS_TOKEN")
        )

    exa_sources = [source for source in selected if uses_exa(source)]
    native_sources = [source for source in selected if not uses_exa(source)]
    collected_by_id: dict[str, dict[str, Any]] = {}
    # Exa's shared endpoint is rate-limited. Keep it low-concurrency while native
    # APIs and public leaderboards run in parallel rather than holding each other up.
    with concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(2, len(exa_sources)))) as exa_executor, concurrent.futures.ThreadPoolExecutor(max_workers=max(1, min(5, len(native_sources)))) as native_executor:
        exa_futures = [exa_executor.submit(collect_source, source, args) for source in exa_sources]
        native_futures = [native_executor.submit(collect_source, source, args) for source in native_sources]
        exa_results = [future.result() for future in exa_futures]
        native_results = [future.result() for future in native_futures]
    for result in [*exa_results, *native_results]:
        collected_by_id[result["source_id"]] = result
    results = [collected_by_id[source["id"]] for source in selected]

    payload = {
        "collected_at": utc_now(),
        "query": args.query,
        "days": args.days,
        "limit": args.limit,
        "sources": selected_ids,
        "results": results,
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    collected_count = sum(len(result["records"]) for result in results)
    failed_count = sum(result["status"] != "collected" for result in results)
    print(f"Collected {collected_count} records from {len(results)} sources; {failed_count} source(s) need attention.")
    print(f"Raw JSON: {args.output_json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
