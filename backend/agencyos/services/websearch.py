"""Web search provider abstraction. Tavily is implemented; with no key, search is reported unavailable."""
from __future__ import annotations

import os
from datetime import date

import requests


class SearchUnavailable(Exception):
    pass


def configured() -> bool:
    return bool(os.getenv("TAVILY_API_KEY"))


def search(query: str, max_results: int = 5) -> list[dict]:
    key = os.getenv("TAVILY_API_KEY")
    if not key:
        raise SearchUnavailable("No web search provider configured (set TAVILY_API_KEY)")
    r = requests.post("https://api.tavily.com/search", json={"api_key": key, "query": query, "max_results": max_results},
                      timeout=30)
    if r.status_code != 200:
        raise SearchUnavailable(f"Tavily HTTP {r.status_code}")
    out = []
    for x in r.json().get("results", []):
        out.append({"source": x.get("url"), "title": x.get("title"), "evidence": (x.get("content") or "")[:500],
                    "date": date.today().isoformat()})
    return out
