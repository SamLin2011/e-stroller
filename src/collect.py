from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class CollectedItem:
    title: str
    url: str
    source_name: str
    source_category: str
    snippet: str = ""
    published_at: str | None = None
    collected_at: str = ""
    product_name: str | None = None
    brand: str | None = None
    market_region: str | None = None
    price: str | None = None
    electric_assist: str | None = None
    downhill_brake: str | None = None
    auto_parking: str | None = None
    auto_rocking: str | None = None
    app_control: str | None = None
    battery_life: str | None = None
    sensors: str | None = None
    ai_robotics: str | None = None
    safety_features: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def load_yaml(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def collect_all(config_dir: Path = Path("config")) -> tuple[list[CollectedItem], list[str]]:
    keywords_config = load_yaml(config_dir / "keywords.yml")
    sources_config = load_yaml(config_dir / "sources.yml")
    request_config = sources_config.get("request", {})

    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": request_config.get(
                "user_agent",
                "Mozilla/5.0 (compatible; stroller-intelligence-bot/1.0)",
            )
        }
    )

    items: list[CollectedItem] = []
    errors: list[str] = []

    for source in sources_config.get("sources", []):
        try:
            source_type = source.get("type", "page")
            if source_type == "rss":
                source_items = _collect_rss(source, keywords_config)
            elif source_type == "page":
                source_items = _collect_page(source, keywords_config, request_config, session)
            else:
                raise ValueError(f"Unsupported source type: {source_type}")
            items.extend(source_items)
        except Exception as exc:  # noqa: BLE001 - collection must survive individual failures
            message = f"{source.get('name', source.get('url'))}: {exc}"
            LOGGER.warning("Source failed: %s", message)
            errors.append(message)

    return _dedupe_items(items), errors


def _collect_rss(source: dict[str, Any], keywords_config: dict[str, Any]) -> list[CollectedItem]:
    feed = feedparser.parse(source["url"])
    if getattr(feed, "bozo", False) and getattr(feed, "bozo_exception", None):
        LOGGER.info("RSS parser warning for %s: %s", source["name"], feed.bozo_exception)

    items: list[CollectedItem] = []
    for entry in feed.entries[:30]:
        title = _clean_text(entry.get("title", ""))
        snippet = _clean_text(entry.get("summary", "") or entry.get("description", ""))
        url = normalize_url(entry.get("link", ""))
        text = f"{title}\n{snippet}"
        if not url or not _matches_keywords(text, keywords_config):
            continue
        items.append(
            _enrich_item(
                CollectedItem(
                    title=title or url,
                    url=url,
                    source_name=source.get("name", ""),
                    source_category=source.get("category", ""),
                    snippet=snippet[:1200],
                    published_at=_entry_published_at(entry),
                    collected_at=_now_utc(),
                ),
                text,
                keywords_config,
            )
        )
    return items


def _collect_page(
    source: dict[str, Any],
    keywords_config: dict[str, Any],
    request_config: dict[str, Any],
    session: requests.Session,
) -> list[CollectedItem]:
    response = session.get(source["url"], timeout=request_config.get("timeout_seconds", 20))
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    page_text = _clean_text(soup.get_text(" ", strip=True))
    title = _page_title(soup) or source.get("name", source["url"])
    published_at = _page_date(soup)
    canonical_url = normalize_url(_canonical_url(soup, source["url"]))

    items: list[CollectedItem] = []
    if source.get("always_include") or _matches_keywords(f"{title}\n{page_text}", keywords_config):
        items.append(
            _enrich_item(
                CollectedItem(
                    title=title,
                    url=canonical_url,
                    source_name=source.get("name", ""),
                    source_category=source.get("category", ""),
                    snippet=page_text[:1200],
                    published_at=published_at,
                    collected_at=_now_utc(),
                ),
                f"{title}\n{page_text}",
                keywords_config,
            )
        )

    max_links = int(request_config.get("max_links_per_source", 8))
    for link in _interesting_links(soup, source["url"], keywords_config)[:max_links]:
        if link == canonical_url:
            continue
        link_title, link_text = _link_context(soup, link)
        items.append(
            _enrich_item(
                CollectedItem(
                    title=link_title or link,
                    url=link,
                    source_name=source.get("name", ""),
                    source_category=source.get("category", ""),
                    snippet=link_text[:1200],
                    collected_at=_now_utc(),
                ),
                f"{link_title}\n{link_text}",
                keywords_config,
            )
        )

    return items


def _enrich_item(
    item: CollectedItem,
    text: str,
    keywords_config: dict[str, Any],
) -> CollectedItem:
    item.product_name = _extract_product_name(text, keywords_config)
    item.brand = _extract_brand(text, keywords_config)
    item.market_region = _extract_region(text)
    item.price = _extract_price(text)

    features = keywords_config.get("feature_keywords", {})
    item.electric_assist = _feature_hit(text, features.get("electric_assist", []))
    item.downhill_brake = _feature_hit(text, features.get("downhill_brake", []))
    item.auto_parking = _feature_hit(text, features.get("auto_parking", []))
    item.auto_rocking = _feature_hit(text, features.get("auto_rocking", []))
    item.app_control = _feature_hit(text, features.get("app_control", []))
    item.battery_life = _extract_battery(text) or _feature_hit(text, features.get("battery", []))
    item.sensors = _feature_hit(text, features.get("sensors", []))
    item.ai_robotics = _feature_hit(text, features.get("ai_robotics", []))
    item.safety_features = _feature_hit(text, features.get("safety", []))
    return item


def _matches_keywords(text: str, keywords_config: dict[str, Any]) -> bool:
    haystack = text.casefold()
    keywords = (
        keywords_config.get("core_keywords", [])
        + keywords_config.get("priority_products", [])
        + keywords_config.get("brands", [])
    )
    return any(str(keyword).casefold() in haystack for keyword in keywords)


def _extract_product_name(text: str, keywords_config: dict[str, Any]) -> str | None:
    lowered = text.casefold()
    for product in keywords_config.get("priority_products", []):
        if str(product).casefold() in lowered:
            return str(product)

    patterns = [
        r"\b[A-Z][A-Za-z0-9-]+\s+(?:e-?stroller|stroller|pram)\b",
        r"\b(?:AI|Smart|Electric|Robotic)\s+[A-Za-z0-9-]+\s+stroller\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


def _extract_brand(text: str, keywords_config: dict[str, Any]) -> str | None:
    lowered = text.casefold()
    for brand in keywords_config.get("brands", []):
        if str(brand).casefold() in lowered:
            return str(brand)
    return None


def _extract_region(text: str) -> str | None:
    regions = {
        "United States": ["United States", "U.S.", "USA", "$"],
        "Canada": ["Canada", "CAD"],
        "Europe": ["Europe", "EU", "€"],
        "United Kingdom": ["United Kingdom", "UK", "£"],
        "China": ["China", "中国", "RMB", "¥"],
        "Japan": ["Japan", "日本", "JPY"],
    }
    for region, tokens in regions.items():
        if any(token in text for token in tokens):
            return region
    return None


def _extract_price(text: str) -> str | None:
    match = re.search(r"(?:(?:US|CA)?\$|€|£|¥)\s?\d[\d,]*(?:\.\d{2})?", text)
    return match.group(0) if match else None


def _extract_battery(text: str) -> str | None:
    match = re.search(
        r"(?i)(?:battery|range|runtime|续航)[^.。;；]{0,80}(?:\d+\s?(?:h|hours|hrs|km|miles|mah|wh))",
        text,
    )
    return _clean_text(match.group(0)) if match else None


def _feature_hit(text: str, keywords: list[str]) -> str | None:
    lowered = text.casefold()
    for keyword in keywords:
        if str(keyword).casefold() in lowered:
            return "mentioned"
    return None


def _interesting_links(
    soup: BeautifulSoup,
    base_url: str,
    keywords_config: dict[str, Any],
) -> list[str]:
    links: list[str] = []
    for anchor in soup.find_all("a", href=True):
        text = _clean_text(anchor.get_text(" ", strip=True))
        href = urljoin(base_url, anchor["href"])
        candidate = f"{text} {href}"
        if _matches_keywords(candidate, keywords_config):
            links.append(normalize_url(href))
    return list(dict.fromkeys(url for url in links if url.startswith(("http://", "https://"))))


def _link_context(soup: BeautifulSoup, url: str) -> tuple[str, str]:
    for anchor in soup.find_all("a", href=True):
        href = normalize_url(urljoin(url, anchor["href"]))
        if href == url:
            title = _clean_text(anchor.get_text(" ", strip=True))
            parent_text = _clean_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else title
            return title, parent_text
    return "", ""


def _page_title(soup: BeautifulSoup) -> str:
    selectors = [
        ("meta", {"property": "og:title"}),
        ("meta", {"name": "twitter:title"}),
        ("title", {}),
        ("h1", {}),
    ]
    for name, attrs in selectors:
        tag = soup.find(name, attrs=attrs)
        if not tag:
            continue
        value = tag.get("content") if tag.name == "meta" else tag.get_text(" ", strip=True)
        if value:
            return _clean_text(value)
    return ""


def _page_date(soup: BeautifulSoup) -> str | None:
    date_names = [
        ("meta", {"property": "article:published_time"}),
        ("meta", {"property": "article:modified_time"}),
        ("meta", {"name": "date"}),
        ("meta", {"name": "pubdate"}),
        ("time", {}),
    ]
    for name, attrs in date_names:
        tag = soup.find(name, attrs=attrs)
        if not tag:
            continue
        value = tag.get("content") or tag.get("datetime") or tag.get_text(" ", strip=True)
        if value:
            return _clean_text(value)
    return None


def _canonical_url(soup: BeautifulSoup, fallback_url: str) -> str:
    tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    if tag and tag.get("href"):
        return urljoin(fallback_url, tag["href"])
    return fallback_url


def _entry_published_at(entry: Any) -> str | None:
    for field in ("published", "updated", "created"):
        value = entry.get(field)
        if value:
            return str(value)
    return None


def _dedupe_items(items: list[CollectedItem]) -> list[CollectedItem]:
    deduped: dict[str, CollectedItem] = {}
    for item in items:
        if not item.url:
            continue
        deduped.setdefault(item.url, item)
    return list(deduped.values())


def normalize_url(url: str) -> str:
    if not url:
        return ""
    parsed = urlparse(url.strip())
    query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in {"fbclid", "gclid"}
    ]
    normalized = parsed._replace(query=urlencode(query, doseq=True), fragment="")
    return urlunparse(normalized)


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", BeautifulSoup(value or "", "html.parser").get_text(" ", strip=True)).strip()


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()
