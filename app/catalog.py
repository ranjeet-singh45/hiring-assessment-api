"""
Loads the SHL product catalog and normalizes it into a flat list of
Individual Test Solutions (Pre-packaged Job Solutions are filtered out).
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import httpx

CATALOG_URL = "https://tcp-us-prod-rnd.shl.com/voiceRater/shl-ai-hiring/shl_product_catalog.json"
CACHE_PATH = os.path.join(os.path.dirname(__file__), "..", "catalog_cache.json")

NAME_KEYS = ["name", "title", "product_name", "assessment_name"]
URL_KEYS = ["url", "link", "product_url", "href"]
TYPE_KEYS = ["test_type", "type", "category", "test_types", "assessment_type"]
DESC_KEYS = ["description", "summary", "details", "overview"]
DURATION_KEYS = ["duration", "assessment_length", "length", "time"]
JOB_LEVEL_KEYS = ["job_level", "job_levels", "level"]
REMOTE_KEYS = ["remote_testing", "remote"]
ADAPTIVE_KEYS = ["adaptive_irt", "adaptive"]
SOLUTION_TYPE_KEYS = ["solution_type", "catalog_type", "category_type"]


def _first(d: dict, keys: list[str], default=None):
    for k in keys:
        if k in d and d[k] not in (None, ""):
            return d[k]
    return default


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    if isinstance(v, str):
        for sep in [",", "|", "/"]:
            if sep in v:
                return [s.strip() for s in v.split(sep) if s.strip()]
        return [v.strip()] if v.strip() else []
    return [str(v)]


def _looks_like_job_solution(item: dict) -> bool:
    hint = " ".join(
        str(_first(item, SOLUTION_TYPE_KEYS, "")) + " " + str(item.get("category", ""))
    ).lower()
    if "job solution" in hint or "job-solution" in hint or "jobsolution" in hint:
        return True
    name = str(_first(item, NAME_KEYS, "")).lower()
    if "job solution" in name:
        return True
    return False


def _flatten(raw: Any) -> list[dict]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, dict):
        for key in ["products", "data", "items", "catalog", "results", "assessments"]:
            if key in raw and isinstance(raw[key], list):
                return raw[key]
        if all(isinstance(v, dict) for v in raw.values()):
            return list(raw.values())
    raise ValueError("Unrecognized catalog JSON shape")


def _normalize(raw_items: list[dict]) -> list[dict]:
    out = []
    seen_urls = set()
    for item in raw_items:
        if not isinstance(item, dict):
            continue
        if _looks_like_job_solution(item):
            continue
        name = _first(item, NAME_KEYS)
        url = _first(item, URL_KEYS)
        if not name or not url:
            continue
        if url in seen_urls:
            continue
        seen_urls.add(url)
        test_type = _as_list(_first(item, TYPE_KEYS))
        out.append(
            {
                "name": str(name).strip(),
                "url": str(url).strip(),
                "test_type": test_type,
                "description": str(_first(item, DESC_KEYS, "")).strip(),
                "duration": _first(item, DURATION_KEYS, ""),
                "job_levels": _as_list(_first(item, JOB_LEVEL_KEYS)),
                "remote_testing": _first(item, REMOTE_KEYS, ""),
                "adaptive_irt": _first(item, ADAPTIVE_KEYS, ""),
            }
        )
    return out


def _clean_json_text(text: str) -> str:
    """Fix raw newlines/tabs inside JSON string values, which are invalid JSON.
    Replaces literal newlines and tabs found inside quoted strings with a space,
    then strips any remaining control characters outside strings."""

    def fix_string(m: re.Match) -> str:
        inner = m.group(1)
        # Replace literal newline/carriage-return/tab inside the string with a space
        inner = inner.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
        # Strip other control characters
        inner = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', inner)
        return '"' + inner + '"'

    # Match JSON strings (handles escaped quotes inside)
    text = re.sub(r'"((?:[^"\\]|\\.)*)"', fix_string, text, flags=re.DOTALL)
    return text


class Catalog:
    def __init__(self):
        self.items: list[dict] = []
        self.loaded_at: float | None = None

    def load(self, force_refresh: bool = False) -> None:
        if not force_refresh and os.path.exists(CACHE_PATH):
            try:
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                if cached.get("items"):
                    self.items = cached["items"]
                    self.loaded_at = cached.get("loaded_at")
                    return
            except Exception:
                pass

        raw = None
        last_err = None
        for attempt in range(3):
            try:
                resp = httpx.get(CATALOG_URL, timeout=20.0, follow_redirects=True)
                resp.raise_for_status()
                text = _clean_json_text(resp.text)
                raw = json.loads(text)
                break
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))

        if raw is None:
            if os.path.exists(CACHE_PATH):
                with open(CACHE_PATH, "r", encoding="utf-8") as f:
                    cached = json.load(f)
                self.items = cached.get("items", [])
                self.loaded_at = cached.get("loaded_at")
                return
            raise RuntimeError(f"Could not fetch SHL catalog: {last_err}")

        flat = _flatten(raw)
        self.items = _normalize(flat)
        self.loaded_at = time.time()
        print(f"Catalog loaded: {len(self.items)} individual test solutions")

        try:
            with open(CACHE_PATH, "w", encoding="utf-8") as f:
                json.dump({"items": self.items, "loaded_at": self.loaded_at}, f)
        except Exception:
            pass

    def by_name_fuzzy(self, query: str) -> dict | None:
        q = query.lower().strip()
        for item in self.items:
            if item["name"].lower() == q:
                return item
        for item in self.items:
            if q in item["name"].lower() or item["name"].lower() in q:
                return item
        return None


catalog = Catalog()