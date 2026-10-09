from __future__ import annotations

import re
import time
import urllib.robotparser
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from .config import Settings

EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
CAREER_TERMS = (
    "carreira","carreiras","trabalhe conosco","trabalhe-conosco","vaga","vagas",
    "jobs","careers","recrutamento","talentos","talent"
)
LINK_TERMS = CAREER_TERMS + ("contato","contact","fale conosco","fale-conosco")
REJECT = {"noreply","no-reply","abuse","privacy","privacidade","dpo","security","postmaster","webmaster","suporte"}
ROLE_SCORES = {
    "rh":("rh",100),"hr":("rh",100),"recrutamento":("recrutamento",100),
    "recruiting":("recrutamento",100),"vagas":("vagas",98),"jobs":("jobs",98),
    "careers":("careers",98),"carreiras":("careers",98),"talentos":("talentos",96),
    "talent":("talentos",96),"people":("people",90),"peopleops":("people",90),
    "contato":("contato",55),"contact":("contato",55),"faleconosco":("contato",52),
    "info":("contato",45)
}


@dataclass(frozen=True)
class Contact:
    email: str
    kind: str
    score: int
    source_url: str


@dataclass(frozen=True)
class CrawlResult:
    contacts: list[Contact]
    careers_signal: bool


def score_email(email: str, careers_signal: bool) -> tuple[str,int]:
    local = email.split("@",1)[0].lower()
    if local in REJECT or "noreply" in local or "no-reply" in local:
        return "reject",0
    normalized = re.sub(r"[^a-z0-9]","",local)
    for key,(kind,score) in ROLE_SCORES.items():
        if normalized == re.sub(r"[^a-z0-9]","",key):
            if kind == "contato" and not careers_signal:
                return "reject",0
            return kind,score
    return "reject",0


def same_domain(email_domain: str, company_domain: str) -> bool:
    return email_domain == company_domain or email_domain.endswith("." + company_domain)


class WebsiteCrawler:
    def __init__(self, settings: Settings):
        self.s = settings
        self.client = httpx.Client(
            timeout=settings.http_timeout_seconds,
            follow_redirects=True,
            headers={"User-Agent":settings.user_agent,"Accept-Language":"pt-BR,pt;q=0.9,en;q=0.6"}
        )

    def close(self) -> None:
        self.client.close()

    def _allowed(self, website: str, url: str) -> bool:
        try:
            r = self.client.get(urljoin(website,"/robots.txt"))
            if r.status_code >= 400:
                return True
            rp = urllib.robotparser.RobotFileParser()
            rp.parse(r.text.splitlines())
            return rp.can_fetch(self.s.user_agent,url)
        except Exception:
            return True

    def _fetch(self,url: str) -> str | None:
        try:
            r = self.client.get(url)
            if r.status_code >= 400:
                return None
            if "html" not in r.headers.get("content-type","").lower():
                return None
            return r.text
        except Exception:
            return None

    def crawl(self, website: str, domain: str) -> CrawlResult:
        queue=[website]
        visited=set()
        pages=[]
        careers=False

        while queue and len(visited) < self.s.max_pages_per_site:
            url=queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            if not self._allowed(website,url):
                continue
            html=self._fetch(url)
            if not html:
                continue
            pages.append((url,html))
            soup=BeautifulSoup(html,"html.parser")
            text=soup.get_text(" ",strip=True).lower()
            if any(term in text or term in url.lower() for term in CAREER_TERMS):
                careers=True
            for a in soup.find_all("a",href=True):
                href=a.get("href","").strip()
                joined=urljoin(url,href)
                p=urlparse(joined)
                host=(p.hostname or "").lower()
                if host.startswith("www."):
                    host=host[4:]
                if host != domain and not host.endswith("." + domain):
                    continue
                hay=f"{a.get_text(' ',strip=True)} {joined}".lower()
                if any(term in hay for term in LINK_TERMS):
                    clean=joined.split("#",1)[0]
                    if clean not in visited and clean not in queue:
                        queue.append(clean)
            time.sleep(self.s.crawl_delay_seconds)

        found={}
        for url,html in pages:
            soup=BeautifulSoup(html,"html.parser")
            for a in soup.select('a[href^="mailto:"]'):
                e=a.get("href","")[7:].split("?",1)[0].strip().lower()
                if e:
                    found[e]=url
            for e in EMAIL_RE.findall(html):
                found[e.lower()]=url

        contacts=[]
        for email,source_url in found.items():
            if "@" not in email:
                continue
            email_domain=email.rsplit("@",1)[1].lower()
            if not same_domain(email_domain,domain):
                continue
            kind,score=score_email(email,careers)
            if score:
                contacts.append(Contact(email,kind,score,source_url))
        contacts.sort(key=lambda x:(-x.score,x.email))
        return CrawlResult(contacts,careers)
