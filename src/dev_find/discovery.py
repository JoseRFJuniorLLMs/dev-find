from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx
from ddgs import DDGS

from .config import Settings

BLOCKED = {
    "linkedin.com","glassdoor.com","glassdoor.com.br","indeed.com","indeed.com.br",
    "facebook.com","instagram.com","youtube.com","x.com","twitter.com","google.com",
    "reclameaqui.com.br","wikipedia.org"
}

QUERIES = [
    '"empresa de software" {city} {state}',
    '"desenvolvimento de software" {city} {state}',
    '"consultoria de TI" {city} {state}',
    '"software house" {city} {state}',
    '"inteligência artificial" empresa {city} {state}',
    '"engenharia de dados" empresa {city} {state}',
]


@dataclass(frozen=True)
class CompanyCandidate:
    name: str
    website: str
    domain: str
    source: str
    source_query: str


def normalize(url: str) -> tuple[str, str] | None:
    if not url:
        return None
    if not url.startswith(("http://","https://")):
        url = "https://" + url
    p = urlparse(url)
    host = (p.hostname or "").lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host or host in BLOCKED or any(host.endswith("." + x) for x in BLOCKED):
        return None
    return host, f"{p.scheme}://{p.netloc}/"


class SearchDiscovery:
    def __init__(self, settings: Settings):
        self.s = settings

    def _brave(self, query: str) -> list[dict]:
        if not self.s.brave_search_api_key:
            return []
        headers = {"Accept":"application/json","X-Subscription-Token":self.s.brave_search_api_key,"User-Agent":self.s.user_agent}
        with httpx.Client(timeout=self.s.http_timeout_seconds, headers=headers) as c:
            r = c.get("https://api.search.brave.com/res/v1/web/search",
                      params={"q":query,"count":self.s.max_results_per_query,"country":"BR"})
            r.raise_for_status()
            return [{"title":x.get("title",""),"href":x.get("url","")} for x in r.json().get("web",{}).get("results",[])]

    def _ddgs(self, query: str) -> list[dict]:
        rows = DDGS().text(query, region="br-pt", safesearch="moderate", max_results=self.s.max_results_per_query)
        return [{"title":x.get("title",""),"href":x.get("href","")} for x in (rows or [])]

    def discover(self, city: str, state: str) -> list[CompanyCandidate]:
        seen, out = set(), []
        for pattern in QUERIES:
            query = pattern.format(city=city,state=state)
            try:
                rows = self._brave(query) if self.s.brave_search_api_key else self._ddgs(query)
            except Exception:
                continue
            for row in rows:
                n = normalize(row.get("href",""))
                if not n:
                    continue
                domain, website = n
                if domain in seen:
                    continue
                seen.add(domain)
                title = (row.get("title") or domain).split(" | ")[0].split(" - ")[0].strip()[:160]
                out.append(CompanyCandidate(title or domain, website, domain,
                            "brave" if self.s.brave_search_api_key else "ddgs", query))
        return out
