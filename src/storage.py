from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_STORAGE_PATH = Path("data/seen_urls.json")


def load_seen_urls(path: Path = DEFAULT_STORAGE_PATH) -> set[str]:
    if not path.exists():
        return set()

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set()

    urls = payload.get("seen_urls", [])
    if not isinstance(urls, list):
        return set()
    return {str(url) for url in urls if url}


def save_seen_urls(urls: Iterable[str], path: Path = DEFAULT_STORAGE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "seen_urls": sorted({str(url) for url in urls if url}),
    }
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def merge_seen_urls(new_urls: Iterable[str], path: Path = DEFAULT_STORAGE_PATH) -> set[str]:
    merged = load_seen_urls(path)
    merged.update(str(url) for url in new_urls if url)
    save_seen_urls(merged, path)
    return merged
