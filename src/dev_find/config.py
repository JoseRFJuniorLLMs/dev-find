from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    value = os.getenv(name)
    return int(value) if value else default


@dataclass(frozen=True)
class Settings:
    db_path: Path = Path(os.getenv("DEV_FIND_DB", "./data/dev-find.db"))
    cities_file: Path = Path(os.getenv("CITIES_FILE", "config/cities.csv"))
    dry_run: bool = _bool("DRY_RUN", True)
    timezone: str = os.getenv("TIMEZONE", "America/Sao_Paulo")
    loop_seconds: int = _int("LOOP_SECONDS", 300)
    city_rescan_days: int = _int("CITY_RESCAN_DAYS", 7)
    max_results_per_query: int = _int("MAX_RESULTS_PER_QUERY", 20)
    max_pages_per_site: int = _int("MAX_PAGES_PER_SITE", 10)
    http_timeout_seconds: int = _int("HTTP_TIMEOUT_SECONDS", 15)
    crawl_delay_seconds: int = _int("CRAWL_DELAY_SECONDS", 2)
    user_agent: str = os.getenv("USER_AGENT", "dev-find/0.1")
    brave_search_api_key: str = os.getenv("BRAVE_SEARCH_API_KEY", "")

    max_emails_per_day: int = _int("MAX_EMAILS_PER_DAY", 8)
    min_send_interval_seconds: int = _int("MIN_SEND_INTERVAL_SECONDS", 1200)
    max_send_jitter_seconds: int = _int("MAX_SEND_JITTER_SECONDS", 1800)
    send_window_start: str = os.getenv("SEND_WINDOW_START", "08:30")
    send_window_end: str = os.getenv("SEND_WINDOW_END", "17:30")
    send_weekdays: tuple[int, ...] = tuple(
        int(x) for x in os.getenv("SEND_WEEKDAYS", "0,1,2,3,4").split(",") if x.strip()
    )
    max_send_attempts: int = _int("MAX_SEND_ATTEMPTS", 3)

    smtp_host: str = os.getenv("SMTP_HOST", "")
    smtp_port: int = _int("SMTP_PORT", 587)
    smtp_user: str = os.getenv("SMTP_USER", "")
    smtp_password: str = os.getenv("SMTP_PASSWORD", "")
    smtp_starttls: bool = _bool("SMTP_STARTTLS", True)
    smtp_ssl: bool = _bool("SMTP_SSL", False)
    from_email: str = os.getenv("FROM_EMAIL", "")
    from_name: str = os.getenv("FROM_NAME", "")

    applicant_name: str = os.getenv("APPLICANT_NAME", "")
    applicant_role: str = os.getenv("APPLICANT_ROLE", "Engenheiro de IA e Dados")
    applicant_city: str = os.getenv("APPLICANT_CITY", "")
    applicant_phone: str = os.getenv("APPLICANT_PHONE", "")
    applicant_email: str = os.getenv("APPLICANT_EMAIL", "")
    linkedin_url: str = os.getenv("LINKEDIN_URL", "")
    github_url: str = os.getenv("GITHUB_URL", "")
    cv_path: Path = Path(os.getenv("CV_PATH", "/opt/dev-find-private/cv.pdf"))
    email_template: Path = Path(os.getenv("EMAIL_TEMPLATE", "templates/application.txt"))
    email_subject: str = os.getenv("EMAIL_SUBJECT", "Candidatura | {role} | {name}")

    def ensure_runtime_dirs(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
