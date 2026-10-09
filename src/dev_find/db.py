from __future__ import annotations

import csv
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator


SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS cities (
    id INTEGER PRIMARY KEY,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    priority INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    scan_count INTEGER NOT NULL DEFAULT 0,
    last_scanned_at TEXT,
    next_scan_at TEXT,
    UNIQUE(city, state)
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    domain TEXT NOT NULL UNIQUE,
    website TEXT NOT NULL,
    city TEXT NOT NULL,
    state TEXT NOT NULL,
    source TEXT NOT NULL,
    source_query TEXT,
    first_seen_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    careers_signal INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    kind TEXT NOT NULL,
    score INTEGER NOT NULL,
    source_url TEXT NOT NULL,
    discovered_at TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(company_id, email)
);

CREATE TABLE IF NOT EXISTS applications (
    id INTEGER PRIMARY KEY,
    company_id INTEGER NOT NULL UNIQUE REFERENCES companies(id) ON DELETE CASCADE,
    contact_id INTEGER NOT NULL REFERENCES contacts(id),
    email TEXT NOT NULL,
    subject TEXT,
    status TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0,
    attempted_at TEXT,
    sent_at TEXT,
    next_attempt_at TEXT,
    message_id TEXT,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_city_due ON cities(active, next_scan_at, priority);
CREATE INDEX IF NOT EXISTS idx_contacts_company_score ON contacts(company_id, active, score);
CREATE INDEX IF NOT EXISTS idx_app_status ON applications(status, next_attempt_at);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime | None = None) -> str:
    return (dt or utcnow()).isoformat()


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def connect(self) -> sqlite3.Connection:
        con = sqlite3.connect(self.path, timeout=30)
        con.row_factory = sqlite3.Row
        con.execute("PRAGMA foreign_keys=ON")
        return con

    @contextmanager
    def tx(self) -> Iterator[sqlite3.Connection]:
        con = self.connect()
        try:
            con.execute("BEGIN IMMEDIATE")
            yield con
            con.commit()
        except Exception:
            con.rollback()
            raise
        finally:
            con.close()

    def init(self) -> None:
        with self.connect() as con:
            con.executescript(SCHEMA)

    def seed_cities(self, csv_path: Path) -> None:
        if not csv_path.exists():
            return
        with csv_path.open(encoding="utf-8", newline="") as fh, self.connect() as con:
            for row in csv.DictReader(fh):
                con.execute(
                    """
                    INSERT INTO cities(city,state,priority,next_scan_at)
                    VALUES(?,?,?,?)
                    ON CONFLICT(city,state) DO UPDATE SET priority=excluded.priority,active=1
                    """,
                    (row["city"].strip(), row["state"].strip(), int(row["priority"]), iso()),
                )

    def add_city(self, city: str, state: str, priority: int = 50) -> None:
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO cities(city,state,priority,next_scan_at)
                VALUES(?,?,?,?)
                ON CONFLICT(city,state) DO UPDATE SET active=1,priority=excluded.priority
                """,
                (city.strip(), state.strip().upper(), priority, iso()),
            )

    def next_due_city(self):
        with self.connect() as con:
            return con.execute(
                """
                SELECT * FROM cities
                WHERE active=1 AND (next_scan_at IS NULL OR next_scan_at<=?)
                ORDER BY priority DESC,COALESCE(last_scanned_at,'') ASC,id ASC LIMIT 1
                """,
                (iso(),),
            ).fetchone()

    def mark_city_scanned(self, city_id: int, days: int) -> None:
        now = utcnow()
        with self.connect() as con:
            con.execute(
                "UPDATE cities SET scan_count=scan_count+1,last_scanned_at=?,next_scan_at=? WHERE id=?",
                (iso(now), iso(now + timedelta(days=days)), city_id),
            )

    def mark_city_retry(self, city_id: int, hours: int = 6) -> None:
        retry = utcnow() + timedelta(hours=hours)
        with self.connect() as con:
            con.execute(
                "UPDATE cities SET next_scan_at=? WHERE id=?",
                (iso(retry), city_id),
            )

    def upsert_company(self, name: str, domain: str, website: str, city: str, state: str, source: str, source_query: str) -> int:
        now = iso()
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO companies(name,domain,website,city,state,source,source_query,first_seen_at,last_seen_at)
                VALUES(?,?,?,?,?,?,?,?,?)
                ON CONFLICT(domain) DO UPDATE SET website=excluded.website,last_seen_at=excluded.last_seen_at,active=1
                """,
                (name, domain, website, city, state, source, source_query, now, now),
            )
            return int(con.execute("SELECT id FROM companies WHERE domain=?", (domain,)).fetchone()["id"])

    def set_careers_signal(self, company_id: int, value: bool) -> None:
        with self.connect() as con:
            con.execute("UPDATE companies SET careers_signal=? WHERE id=?", (1 if value else 0, company_id))

    def upsert_contact(self, company_id: int, email: str, kind: str, score: int, source_url: str) -> None:
        with self.connect() as con:
            con.execute(
                """
                INSERT INTO contacts(company_id,email,kind,score,source_url,discovered_at)
                VALUES(?,?,?,?,?,?)
                ON CONFLICT(company_id,email) DO UPDATE SET
                  score=MAX(contacts.score,excluded.score),
                  kind=CASE WHEN excluded.score>=contacts.score THEN excluded.kind ELSE contacts.kind END,
                  source_url=CASE WHEN excluded.score>=contacts.score THEN excluded.source_url ELSE contacts.source_url END,
                  active=1
                """,
                (company_id, email.lower(), kind, score, source_url, iso()),
            )

    def sent_today_count(self) -> int:
        day = utcnow().date().isoformat()
        with self.connect() as con:
            return int(con.execute(
                "SELECT COUNT(*) n FROM applications WHERE status='sent' AND substr(sent_at,1,10)=?",
                (day,)
            ).fetchone()["n"])

    def last_sent_at(self) -> datetime | None:
        with self.connect() as con:
            row = con.execute("SELECT sent_at FROM applications WHERE status='sent' ORDER BY sent_at DESC LIMIT 1").fetchone()
        return datetime.fromisoformat(row["sent_at"]) if row and row["sent_at"] else None

    def _next_sql(self) -> str:
        return """
        SELECT c.id company_id,c.name company_name,c.domain,c.website,c.city,c.state,
               ct.id contact_id,ct.email,ct.kind,ct.score,
               a.id application_id,a.status application_status,a.attempts
        FROM companies c
        JOIN contacts ct ON ct.company_id=c.id AND ct.active=1
        LEFT JOIN applications a ON a.company_id=c.id
        WHERE c.active=1
          AND ct.id=(SELECT id FROM contacts x WHERE x.company_id=c.id AND x.active=1
                     ORDER BY x.score DESC,x.id ASC LIMIT 1)
          AND (a.id IS NULL OR (a.status='failed' AND a.attempts<? AND
               (a.next_attempt_at IS NULL OR a.next_attempt_at<=?)))
        ORDER BY CASE c.city WHEN 'Campinas' THEN 0 ELSE 1 END,ct.score DESC,c.first_seen_at ASC
        LIMIT 1
        """

    def preview_next(self, max_attempts: int):
        with self.connect() as con:
            return con.execute(self._next_sql(), (max_attempts, iso())).fetchone()

    def claim_next(self, max_attempts: int):
        with self.tx() as con:
            row = con.execute(self._next_sql(), (max_attempts, iso())).fetchone()
            if not row:
                return None
            if row["application_id"] is None:
                app_id = con.execute(
                    "INSERT INTO applications(company_id,contact_id,email,status,attempts,attempted_at) VALUES(?,?,?,'sending',1,?)",
                    (row["company_id"], row["contact_id"], row["email"], iso()),
                ).lastrowid
            else:
                app_id = row["application_id"]
                con.execute(
                    "UPDATE applications SET status='sending',attempts=attempts+1,attempted_at=?,contact_id=?,email=?,last_error=NULL WHERE id=?",
                    (iso(), row["contact_id"], row["email"], app_id),
                )
            return dict(row) | {"application_id": app_id}

    def mark_sent(self, application_id: int, subject: str, message_id: str) -> None:
        with self.connect() as con:
            con.execute(
                "UPDATE applications SET status='sent',subject=?,sent_at=?,message_id=?,next_attempt_at=NULL,last_error=NULL WHERE id=?",
                (subject, iso(), message_id, application_id),
            )

    def mark_failed(self, application_id: int, error: str) -> None:
        retry = utcnow() + timedelta(hours=24)
        with self.connect() as con:
            con.execute(
                "UPDATE applications SET status='failed',last_error=?,next_attempt_at=? WHERE id=?",
                (error[:1000], iso(retry), application_id),
            )

    def stats(self) -> dict[str, int]:
        with self.connect() as con:
            return {
                "cities": int(con.execute("SELECT COUNT(*) n FROM cities WHERE active=1").fetchone()["n"]),
                "companies": int(con.execute("SELECT COUNT(*) n FROM companies WHERE active=1").fetchone()["n"]),
                "contacts": int(con.execute("SELECT COUNT(*) n FROM contacts WHERE active=1").fetchone()["n"]),
                "sent": int(con.execute("SELECT COUNT(*) n FROM applications WHERE status='sent'").fetchone()["n"]),
                "failed": int(con.execute("SELECT COUNT(*) n FROM applications WHERE status='failed'").fetchone()["n"]),
            }
