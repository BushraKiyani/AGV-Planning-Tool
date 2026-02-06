from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional, Tuple
from urllib.parse import urljoin, urlparse

import pandas as pd
import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger("agv_web_scraper")


# -----------------------------
# Config
# -----------------------------
@dataclass(frozen=True)
class ScrapeConfig:
    """
    Configuration for scraping a vendor site.

    You can tune CSS selectors per site without changing code.
    """
    # products page -> links to device pages
    product_link_selectors: Tuple[str, ...] = (
        "a[href*='produkt']",
        "a[href*='product']",
        "a[href*='device']",
        "a.card, a.teaser, a.product",
        "a",
    )

    # within a device page, try these selectors to find a "spec table"
    # we support both <table> and <dl> patterns
    spec_table_selectors: Tuple[str, ...] = (
        "table",
        "div table",
    )

    spec_dl_selectors: Tuple[str, ...] = (
        "dl",
        "div dl",
    )

    # If the product name isn't clear, we fallback to <title> or h1.
    name_selectors: Tuple[str, ...] = (
        "h1",
        "h2",
        "header h1",
        ".product-title",
        ".page-title",
    )

    # basic HTTP behavior
    timeout_s: int = 20
    sleep_s: float = 0.4
    max_pages: int = 50  # safety
    max_devices: int = 100  # safety


# -----------------------------
# HTTP helpers
# -----------------------------
def _default_headers() -> Dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }


def fetch_html(url: str, timeout_s: int = 20, session: Optional[requests.Session] = None) -> str:
    sess = session or requests.Session()
    resp = sess.get(url, headers=_default_headers(), timeout=timeout_s)
    resp.raise_for_status()
    return resp.text


# -----------------------------
# Parsing helpers
# -----------------------------
def _clean_text(s: str) -> str:
    s = re.sub(r"\s+", " ", s or "").strip()
    return s


def _get_first_text(soup: BeautifulSoup, selectors: Iterable[str]) -> Optional[str]:
    for sel in selectors:
        el = soup.select_one(sel)
        if el:
            t = _clean_text(el.get_text(" ", strip=True))
            if t:
                return t
    return None


def _same_domain(base_url: str, url: str) -> bool:
    return urlparse(base_url).netloc == urlparse(url).netloc


def _is_probable_device_url(href: str) -> bool:
    """
    Heuristic filter to avoid nav/footer/social links.
    Tune if needed.
    """
    href_l = href.lower()
    bad = ("#", "mailto:", "tel:", "javascript:")
    if any(href_l.startswith(b) for b in bad):
        return False
    # Avoid common non-product pages
    if any(x in href_l for x in ["impressum", "privacy", "kontakt", "about", "news", "blog", "jobs"]):
        return False
    # Prefer urls that look product-ish
    return any(x in href_l for x in ["produkt", "product", "device", "agv", "ft", "fahrzeug", "vehicle"])


def extract_device_links(products_page_url: str, cfg: ScrapeConfig, session: Optional[requests.Session] = None) -> List[str]:
    """
    Extract candidate device URLs from a vendor products listing page.
    Returns absolute URLs (deduplicated).
    """
    html = fetch_html(products_page_url, timeout_s=cfg.timeout_s, session=session)
    soup = BeautifulSoup(html, "html.parser")

    links: List[str] = []
    seen = set()

    # We scan all anchors and filter with heuristics, because vendor sites vary a lot.
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href:
            continue

        url = urljoin(products_page_url, href)
        if not _same_domain(products_page_url, url):
            continue
        if not _is_probable_device_url(href):
            continue

        if url not in seen:
            seen.add(url)
            links.append(url)

        if len(links) >= cfg.max_devices:
            break

    return links


def _parse_html_table_to_kv(table) -> Dict[str, str]:
    """
    Parse <table> into a {key: value} dict.
    Supports common patterns:
      - 2-column rows: <th><td> or <td><td>
    """
    kv: Dict[str, str] = {}
    rows = table.find_all("tr")
    for r in rows:
        cells = r.find_all(["th", "td"])
        if len(cells) < 2:
            continue
        k = _clean_text(cells[0].get_text(" ", strip=True))
        v = _clean_text(cells[1].get_text(" ", strip=True))
        if k and v and k not in kv:
            kv[k] = v
    return kv


def _parse_html_dl_to_kv(dl) -> Dict[str, str]:
    """
    Parse <dl><dt>Key</dt><dd>Value</dd></dl> into dict.
    """
    kv: Dict[str, str] = {}
    dts = dl.find_all("dt")
    for dt in dts:
        dd = dt.find_next_sibling("dd")
        if not dd:
            continue
        k = _clean_text(dt.get_text(" ", strip=True))
        v = _clean_text(dd.get_text(" ", strip=True))
        if k and v and k not in kv:
            kv[k] = v
    return kv


def extract_specs_from_device_page(device_url: str, cfg: ScrapeConfig, session: Optional[requests.Session] = None) -> Dict[str, str]:
    """
    Extract device name and specs from a single device page.
    Returns a dict with at least:
      - source_url
      - device_name
      - plus key/value specs
    """
    html = fetch_html(device_url, timeout_s=cfg.timeout_s, session=session)
    soup = BeautifulSoup(html, "html.parser")

    device_name = _get_first_text(soup, cfg.name_selectors) or _clean_text(soup.title.get_text(strip=True)) if soup.title else "Unknown"

    # Try tables first
    kv_all: Dict[str, str] = {}
    for sel in cfg.spec_table_selectors:
        for table in soup.select(sel):
            kv = _parse_html_table_to_kv(table)
            if len(kv) >= 3:  # heuristic: a spec table should have at least a few entries
                kv_all.update(kv)

    # Try dl blocks too (some sites use dl for specs)
    for sel in cfg.spec_dl_selectors:
        for dl in soup.select(sel):
            kv = _parse_html_dl_to_kv(dl)
            if len(kv) >= 3:
                kv_all.update(kv)

    out: Dict[str, str] = {
        "source_url": device_url,
        "device_name": device_name,
        "vendor": urlparse(device_url).netloc.replace("www.", ""),
    }
    out.update(kv_all)
    return out


def scrape_vendor_devices(products_page_url: str, cfg: Optional[ScrapeConfig] = None) -> pd.DataFrame:
    """
    High-level helper:
    - extract device URLs from products page
    - scrape each device page for name + spec key/values
    - return a DataFrame (one row per device)
    """
    cfg = cfg or ScrapeConfig()
    sess = requests.Session()

    device_urls = extract_device_links(products_page_url, cfg, session=sess)
    if not device_urls:
        LOGGER.warning("No device URLs found on: %s", products_page_url)
        return pd.DataFrame()

    LOGGER.info("Found %d candidate device URLs.", len(device_urls))

    rows: List[Dict[str, str]] = []
    for i, url in enumerate(device_urls[: cfg.max_devices], start=1):
        try:
            LOGGER.info("(%d/%d) Scraping: %s", i, min(len(device_urls), cfg.max_devices), url)
            row = extract_specs_from_device_page(url, cfg, session=sess)
            rows.append(row)
        except Exception as e:
            LOGGER.warning("Failed scraping %s: %s", url, e)
        time.sleep(cfg.sleep_s)

    if not rows:
        return pd.DataFrame()

    # DataFrame with union of all keys
    df = pd.DataFrame(rows)

    # Optional: move common columns to front
    front = ["vendor", "device_name", "source_url"]
    cols = front + [c for c in df.columns if c not in front]
    df = df.reindex(columns=cols)

    return df
