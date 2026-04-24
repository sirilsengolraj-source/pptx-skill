#!/usr/bin/env python3
"""Fetch a Wikimedia Commons image plus attribution metadata."""

from __future__ import annotations

import argparse
import csv
import html
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "pptx-skill/1.0 (+local deck asset staging)"
STRIP_TAGS_RE = re.compile(r"<[^>]+>")
ALLOWED_MIME = {"image/jpeg": ".jpg", "image/png": ".png"}


def _clean_text(value: Any) -> str:
    text = str(value or "")
    text = html.unescape(text)
    text = STRIP_TAGS_RE.sub("", text)
    return " ".join(text.split()).strip()


def _request_json(params: dict[str, Any]) -> dict[str, Any]:
    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"{COMMONS_API}?{query}",
        headers={"User-Agent": USER_AGENT},
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)


def _iter_candidates(query: str, limit: int) -> list[dict[str, Any]]:
    data = _request_json(
        {
            "action": "query",
            "format": "json",
            "generator": "search",
            "gsrsearch": query,
            "gsrnamespace": 6,
            "gsrlimit": max(1, min(limit, 20)),
            "prop": "imageinfo|info",
            "iiprop": "url|mime|extmetadata",
            "inprop": "url",
        }
    )
    pages = list((data.get("query") or {}).get("pages", {}).values())
    return sorted(pages, key=lambda item: int(item.get("index", 10**9)))


def _license_allowed(license_name: str, *, allow_sharealike: bool) -> bool:
    upper = (license_name or "").upper().replace("_", "-")
    if not upper:
        return False
    if upper.startswith("PD") or upper.startswith("PUBLIC DOMAIN") or upper.startswith("CC0"):
        return True
    if upper.startswith("CC-BY-SA"):
        return allow_sharealike
    if upper.startswith("CC-BY"):
        return True
    return False


def _best_image_info(page: dict[str, Any], *, allow_sharealike: bool) -> dict[str, Any] | None:
    info = ((page.get("imageinfo") or [{}])[0]) if page.get("imageinfo") else {}
    mime = str(info.get("mime") or "").lower()
    if mime not in ALLOWED_MIME:
        return None
    ext = info.get("extmetadata") or {}
    license_name = _clean_text((ext.get("LicenseShortName") or {}).get("value"))
    if not _license_allowed(license_name, allow_sharealike=allow_sharealike):
        return None
    return {
        "title": _clean_text(page.get("title", "")).removeprefix("File:"),
        "image_url": str(info.get("url") or "").strip(),
        "description_url": str(info.get("descriptionurl") or "").strip(),
        "source_page": str(page.get("fullurl") or info.get("descriptionurl") or "").strip(),
        "mime": mime,
        "license": license_name,
        "license_url": _clean_text((ext.get("LicenseUrl") or {}).get("value")),
        "artist": _clean_text((ext.get("Artist") or {}).get("value")),
        "credit": _clean_text((ext.get("Credit") or {}).get("value")),
        "description": _clean_text((ext.get("ImageDescription") or {}).get("value")),
    }


def _download(url: str, target: Path) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        target.write_bytes(response.read())


def _append_attribution(csv_path: Path, row: dict[str, str]) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "file_name",
        "file_path",
        "title",
        "source_page",
        "image_url",
        "license",
        "license_url",
        "artist",
        "credit",
        "query",
    ]
    existing: list[dict[str, str]] = []
    if csv_path.exists():
        with csv_path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            for item in reader:
                existing.append({k: str(v or "") for k, v in item.items()})
    existing = [item for item in existing if item.get("file_path") != row["file_path"]]
    existing.append(row)
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(existing)


def search_and_download(
    query: str,
    output_dir: Path,
    *,
    limit: int = 12,
    allow_sharealike: bool = True,
    name: str | None = None,
    attribution_csv: Path | None = None,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    for page in _iter_candidates(query, limit):
        candidate = _best_image_info(page, allow_sharealike=allow_sharealike)
        if not candidate:
            continue
        suffix = ALLOWED_MIME[candidate["mime"]]
        stem = re.sub(r"[^A-Za-z0-9_-]+", "_", name or candidate["title"]).strip("_") or "wikimedia_asset"
        target = output_dir / f"{stem}{suffix}"
        _download(candidate["image_url"], target)
        metadata_path = Path(f"{target}.metadata.json")
        metadata = {
            "provider": "wikimedia_commons",
            "query": query,
            "title": candidate["title"],
            "source_page": candidate["source_page"],
            "image_url": candidate["image_url"],
            "description_url": candidate["description_url"],
            "license": candidate["license"],
            "license_url": candidate["license_url"],
            "artist": candidate["artist"],
            "credit": candidate["credit"],
            "description": candidate["description"],
        }
        metadata_path.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        if attribution_csv:
            _append_attribution(
                attribution_csv,
                {
                    "file_name": target.name,
                    "file_path": str(target),
                    "title": candidate["title"],
                    "source_page": candidate["source_page"],
                    "image_url": candidate["image_url"],
                    "license": candidate["license"],
                    "license_url": candidate["license_url"],
                    "artist": candidate["artist"],
                    "credit": candidate["credit"],
                    "query": query,
                },
            )
        return {
            "image_path": str(target),
            "metadata_path": str(metadata_path),
            "source_page": candidate["source_page"],
            "image_url": candidate["image_url"],
            "license": candidate["license"],
            "license_url": candidate["license_url"],
            "artist": candidate["artist"],
            "credit": candidate["credit"],
            "title": candidate["title"],
        }
    raise RuntimeError(f"No Wikimedia Commons image matched the query with an allowed license: {query}")


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch an allowed Wikimedia Commons image.")
    parser.add_argument("--query", required=True, help="Search query for Wikimedia Commons")
    parser.add_argument("--output-dir", required=True, help="Directory to store the downloaded image")
    parser.add_argument("--name", help="Optional target basename")
    parser.add_argument("--limit", type=int, default=12, help="Maximum search results to inspect")
    parser.add_argument(
        "--disallow-sharealike",
        action="store_true",
        help="Reject CC-BY-SA images and keep only PD/CC0/CC-BY results",
    )
    parser.add_argument("--attribution-csv", help="Optional CSV file to append/update attribution rows")
    return parser.parse_args()


def main() -> int:
    args = _args()
    result = search_and_download(
        args.query,
        Path(args.output_dir).expanduser().resolve(),
        limit=args.limit,
        allow_sharealike=not args.disallow_sharealike,
        name=args.name,
        attribution_csv=Path(args.attribution_csv).expanduser().resolve() if args.attribution_csv else None,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
