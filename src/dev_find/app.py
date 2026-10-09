from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from .config import Settings
from .crawler import WebsiteCrawler
from .db import Database, utcnow
from .discovery import SearchDiscovery
from .emailer import Mailer

log=logging.getLogger("dev_find")


class DevFind:
    def __init__(self, settings: Settings):
        self.s=settings
        self.s.ensure_runtime_dirs()
        self.db=Database(self.s.db_path)
        self.db.init()
        self.db.seed_cities(self.s.cities_file)
        self.discovery=SearchDiscovery(self.s)

    def scan_city(self,city: str,state: str) -> dict[str,int]:
        candidates=self.discovery.discover(city,state)
        crawler=WebsiteCrawler(self.s)
        companies=contacts=0
        try:
            for candidate in candidates:
                cid=self.db.upsert_company(candidate.name,candidate.domain,candidate.website,city,state,candidate.source,candidate.source_query)
                companies+=1
                try:
                    result=crawler.crawl(candidate.website,candidate.domain)
                except Exception as exc:
                    log.warning("crawl_failed domain=%s error=%s",candidate.domain,exc)
                    continue
                self.db.set_careers_signal(cid,result.careers_signal)
                for contact in result.contacts:
                    self.db.upsert_contact(cid,contact.email,contact.kind,contact.score,contact.source_url)
                    contacts+=1
        finally:
            crawler.close()
        return {"companies":companies,"contacts":contacts}

    def scan_next_due_city(self) -> bool:
        row=self.db.next_due_city()
        if not row:
            return False
        try:
            result=self.scan_city(row["city"],row["state"])
            self.db.mark_city_scanned(row["id"],self.s.city_rescan_days)
            log.info("scan_done city=%s companies=%s contacts=%s",row["city"],result["companies"],result["contacts"])
        except Exception:
            log.exception("scan_error city=%s",row["city"])
        return True

    def _inside_window(self) -> bool:
        now=datetime.now(ZoneInfo(self.s.timezone))
        if now.weekday() not in self.s.send_weekdays:
            return False
        sh,sm=map(int,self.s.send_window_start.split(":"))
        eh,em=map(int,self.s.send_window_end.split(":"))
        start=now.replace(hour=sh,minute=sm,second=0,microsecond=0)
        end=now.replace(hour=eh,minute=em,second=0,microsecond=0)
        return start <= now <= end

    def _interval_ok(self) -> bool:
        last=self.db.last_sent_at()
        return not last or (utcnow()-last).total_seconds() >= self.s.min_send_interval_seconds

    def send_once(self):
        if self.db.sent_today_count() >= self.s.max_emails_per_day:
            return {"skipped":"daily_limit"}
        if not self._inside_window():
            return {"skipped":"outside_window"}
        if not self._interval_ok():
            return {"skipped":"minimum_interval"}

        if self.s.dry_run:
            row=self.db.preview_next(self.s.max_send_attempts)
            return (dict(row) | {"dry_run":True}) if row else None

        row=self.db.claim_next(self.s.max_send_attempts)
        if not row:
            return None
        try:
            message_id,subject=Mailer(self.s).send(row["email"],row["company_name"])
            self.db.mark_sent(row["application_id"],subject,message_id)
            return dict(row) | {"sent":True,"message_id":message_id}
        except Exception as exc:
            self.db.mark_failed(row["application_id"],str(exc))
            return dict(row) | {"sent":False,"error":str(exc)}

    def daemon(self) -> None:
        log.info("daemon_start dry_run=%s db=%s",self.s.dry_run,self.s.db_path)
        while True:
            self.scan_next_due_city()
            result=self.send_once()
            sleep_for=self.s.loop_seconds
            if result and result.get("sent"):
                sleep_for=max(sleep_for,self.s.min_send_interval_seconds + random.randint(0,self.s.max_send_jitter_seconds))
            time.sleep(sleep_for)
