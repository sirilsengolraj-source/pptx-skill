#!/usr/bin/env python3
"""Generate a deck asset with the OpenAI Images API.

This is an optional network/API path. It never runs during normal deck
generation unless explicitly invoked or enabled through asset staging.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


API_URL = "https://api.openai.com/v1/images/generations"
DEFAULT_MODEL = "gpt-image-2"
DEFAULT_SIZE = "1536x1024"
DEFAULT_QUALITY = "medium"
DEFAULT_FORMAT = "png"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _download_url(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=120) as response:  # noqa: S310 - user-triggered API response URL
        return response.read()


def _api_post(payload: dict[str, Any], api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:  # noqa: S310 - official OpenAI API
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI image API error {exc.code}: {detail}") from exc


def generate_image(
    *,
    prompt: str,
    output: Path,
    model: str = DEFAULT_MODEL,
    size: str = DEFAULT_SIZE,
    quality: str = DEFAULT_QUALITY,
    output_format: str = DEFAULT_FORMAT,
    background: str = "auto",
    purpose: str = "",
    edit_note: str = "",
    api_key: str | None = None,
    metadata_path: Path | None = None,
) -> dict[str, Any]:
    if not prompt.strip():
        raise ValueError("prompt is required")
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY is required for generated images")

    payload: dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "quality": quality,
        "n": 1,
    }
    if output_format:
        payload["output_format"] = output_format
    if background:
        payload["background"] = background

    response = _api_post(payload, key)
    items = response.get("data")
    if not isinstance(items, list) or not items:
        raise RuntimeError(f"OpenAI image API returned no image data: {response}")

    first = items[0]
    if not isinstance(first, dict):
        raise RuntimeError(f"OpenAI image API returned malformed image data: {response}")
    if first.get("b64_json"):
        image_bytes = base64.b64decode(str(first["b64_json"]))
    elif first.get("url"):
        image_bytes = _download_url(str(first["url"]))
    else:
        raise RuntimeError(f"OpenAI image API returned neither b64_json nor url: {response}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_bytes(image_bytes)

    metadata = {
        "provider": "openai",
        "generated": True,
        "model": model,
        "size": size,
        "quality": quality,
        "output_format": output_format,
        "background": background,
        "prompt": prompt,
        "revised_prompt": first.get("revised_prompt") or response.get("revised_prompt"),
        "purpose": purpose,
        "edit_note": edit_note,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_note": "Generated with the OpenAI Images API from a user/agent prompt.",
        "license": "Generated asset; review applicable OpenAI terms before redistribution.",
        "provenance": "generated_openai_image",
    }
    meta_out = metadata_path or Path(f"{output}.metadata.json")
    _write_json(meta_out, metadata)
    return {"image_path": str(output), "metadata_path": str(meta_out), "metadata": metadata}


def _args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a slide-ready image asset with OpenAI.")
    parser.add_argument("--prompt", required=True, help="Image prompt")
    parser.add_argument("--output", required=True, help="Output image path (.png/.webp/.jpg)")
    parser.add_argument("--metadata", help="Optional metadata JSON path")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--size", default=DEFAULT_SIZE)
    parser.add_argument("--quality", default=DEFAULT_QUALITY)
    parser.add_argument("--output-format", default=DEFAULT_FORMAT)
    parser.add_argument("--background", default="auto")
    parser.add_argument("--purpose", default="")
    parser.add_argument("--edit-note", default="")
    return parser.parse_args()


def main() -> int:
    args = _args()
    result = generate_image(
        prompt=args.prompt,
        output=Path(args.output).expanduser().resolve(),
        metadata_path=Path(args.metadata).expanduser().resolve() if args.metadata else None,
        model=args.model,
        size=args.size,
        quality=args.quality,
        output_format=args.output_format,
        background=args.background,
        purpose=args.purpose,
        edit_note=args.edit_note,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
