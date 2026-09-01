#!/usr/bin/env python3
"""Local SQLite CRM for the WY skill."""

# Optional release hardening, run from the skill root:
#   python3 -m pip install pyarmor pyinstaller
#   pyarmor gen -O build/obfuscated scripts/wy_crm.py
#   pyinstaller --onefile --clean --name wy-crm build/obfuscated/wy_crm.py
# PyArmor obfuscates and PyInstaller packages; neither guarantees absolute secrecy.

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit


STAGES = {"prepare", "search", "contacts", "contact_details", "research", "outreach", "export"}
FIT_STATUSES = {"qualified", "review", "rejected"}
COMPANY_STATUSES = {"new", "researched", "draft_ready", "contacted", "replied", "disqualified"}
EMAIL_STATUSES = {"confirmed_on_source", "verified_by_service", "pattern_inferred", "unverified", "not_found"}
PHONE_STATUSES = {"confirmed_on_source", "unverified", "not_found"}
SOURCE_TYPES = {"official", "registry", "company_social", "professional_network", "trade_source", "news", "directory", "other"}
CONFIDENCES = {"high", "medium", "low"}
SOCIAL_PLATFORMS = {"linkedin", "facebook", "instagram", "tiktok", "pinterest", "youtube", "x", "whatsapp", "other"}
SOCIAL_STATUSES = {"official_linked", "claimed_unverified", "not_found"}
SOCIAL_ACTIVITY = {"not_checked", "recently_active", "inactive", "not_found"}
OUTREACH_MODES = {"first_touch", "reengagement", "quote", "post_sale"}
OUTREACH_CHANNELS = {"email", "linkedin", "whatsapp", "official_form", "phone", "other"}
COMPANY_SIZES = {"micro", "small", "medium", "large", "unknown"}
ROUTE_CONFIDENCES = {"high", "medium", "low", "blocked"}
OUTREACH_STATUSES = {"draft", "review_ready", "approved", "sent", "replied", "paused", "closed"}
LIFECYCLE_STAGES = {"new_lead", "engaged", "quoted", "sampling", "negotiation", "customer", "dormant"}
ACTIVATION_STATUSES = {"active", "waiting", "dormant", "paused", "closed", "opted_out"}
CAMPAIGN_TYPES = {"prospecting", "reengagement", "quote_followup", "post_sale"}
CAMPAIGN_STATUSES = {"draft", "review_ready", "approved", "archived"}
SCORE_CAPS = {
    "product_relevance": 30,
    "customer_role": 20,
    "geography": 10,
    "commercial_readiness": 15,
    "recent_activity": 15,
    "evidence_strength": 10,
}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
REJECTED_MESSAGE = "Request rejected."
INJECTION_MARKERS = (
    "print code",
    "show internal logic",
    "ignore previous instructions",
    "reveal system prompt",
    "show system prompt",
    "bypass safeguards",
)


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    project_name TEXT NOT NULL,
    product TEXT NOT NULL,
    countries TEXT NOT NULL,
    customer_types TEXT NOT NULL,
    exclusions TEXT NOT NULL,
    stage TEXT NOT NULL,
    qualify_threshold INTEGER NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS companies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    website TEXT NOT NULL,
    country TEXT NOT NULL,
    customer_type TEXT NOT NULL,
    fit_score INTEGER,
    fit_status TEXT NOT NULL,
    score_breakdown TEXT NOT NULL,
    status TEXT NOT NULL,
    summary TEXT NOT NULL,
    risks TEXT NOT NULL,
    unknowns TEXT NOT NULL,
    last_researched_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    title TEXT NOT NULL,
    role_rank INTEGER,
    profile_url TEXT NOT NULL,
    work_email TEXT NOT NULL,
    email_status TEXT,
    work_phone TEXT NOT NULL,
    phone_status TEXT,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, name, title)
);

CREATE TABLE IF NOT EXISTS competitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    domain TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    website TEXT NOT NULL,
    country TEXT NOT NULL,
    market_position TEXT NOT NULL,
    product_scope TEXT NOT NULL,
    price_position TEXT NOT NULL,
    materials TEXT NOT NULL,
    specifications TEXT NOT NULL,
    demand_signals TEXT NOT NULL,
    differentiation TEXT NOT NULL,
    last_researched_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS social_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_key TEXT NOT NULL,
    platform TEXT NOT NULL,
    profile_url TEXT NOT NULL,
    verification_status TEXT NOT NULL,
    activity_status TEXT NOT NULL,
    audience_notes TEXT NOT NULL,
    content_signals TEXT NOT NULL,
    last_checked_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(entity_type, entity_key, platform)
);

CREATE TABLE IF NOT EXISTS evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    field TEXT NOT NULL,
    claim TEXT NOT NULL,
    source_url TEXT NOT NULL,
    source_title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    confidence TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(entity_type, entity_id, field, source_url, claim)
);

CREATE TABLE IF NOT EXISTS outreach_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    route_key TEXT NOT NULL,
    contact_label TEXT NOT NULL,
    mode TEXT NOT NULL,
    channel TEXT NOT NULL,
    company_size TEXT NOT NULL,
    route_confidence TEXT NOT NULL,
    status TEXT NOT NULL,
    subject TEXT NOT NULL,
    message TEXT NOT NULL,
    evidence_refs TEXT NOT NULL,
    cta TEXT NOT NULL,
    next_action TEXT NOT NULL,
    due_date TEXT,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, mode, channel, route_key)
);

CREATE TABLE IF NOT EXISTS activation_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id INTEGER NOT NULL REFERENCES companies(id) ON DELETE CASCADE,
    contact_id INTEGER REFERENCES contacts(id) ON DELETE SET NULL,
    route_key TEXT NOT NULL,
    contact_label TEXT NOT NULL,
    lifecycle_stage TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER NOT NULL,
    channel TEXT NOT NULL,
    last_outbound_at TEXT NOT NULL,
    last_reply_at TEXT,
    followup_count INTEGER NOT NULL,
    max_followups INTEGER NOT NULL,
    activation_after_days INTEGER NOT NULL,
    next_due_date TEXT,
    next_action TEXT NOT NULL,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(company_id, route_key)
);

CREATE TABLE IF NOT EXISTS campaign_plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name_key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    campaign_type TEXT NOT NULL,
    objective TEXT NOT NULL,
    audience_segments TEXT NOT NULL,
    target_languages TEXT NOT NULL,
    status TEXT NOT NULL,
    subject_variants TEXT NOT NULL,
    content_brief TEXT NOT NULL,
    suppression_rules TEXT NOT NULL,
    success_metrics TEXT NOT NULL,
    planned_start TEXT,
    notes TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_contacts_company ON contacts(company_id);
CREATE INDEX IF NOT EXISTS idx_evidence_entity ON evidence(entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_social_entity ON social_profiles(entity_type, entity_key);
CREATE INDEX IF NOT EXISTS idx_outreach_company ON outreach_plans(company_id);
CREATE INDEX IF NOT EXISTS idx_outreach_due ON outreach_plans(status, due_date);
CREATE INDEX IF NOT EXISTS idx_activation_due ON activation_cases(status, next_due_date);
CREATE INDEX IF NOT EXISTS idx_campaign_status ON campaign_plans(status, planned_start);
"""


class UserError(ValueError):
    pass


class InputRejected(ValueError):
    pass


def get_runtime_secret(variable: str) -> str | None:
    """Read an optional integration secret without logging or persisting it."""
    value = os.environ.get(variable)
    return value if value else None


def normalized_input(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def assert_safe_input(value: object) -> None:
    if isinstance(value, str):
        normalized = normalized_input(value)
        if any(marker in normalized for marker in INJECTION_MARKERS):
            raise InputRejected(REJECTED_MESSAGE)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            assert_safe_input(key)
            assert_safe_input(item)
        return
    if isinstance(value, (list, tuple, set)):
        for item in value:
            assert_safe_input(item)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def emit(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def read_json_object(path: str) -> dict:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise UserError(f"Cannot read JSON object from {path}: {exc}") from exc
    assert_safe_input(raw)
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise UserError(f"Cannot read JSON object from {path}: {exc}") from exc
    assert_safe_input(value)
    if not isinstance(value, dict):
        raise UserError(f"JSON input must be one object: {path}")
    return value


def json_text(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def json_list(value: object, field: str) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise UserError(f"{field} must be a JSON array")
    return value


def non_empty_string_list(value: object, field: str) -> list[str]:
    items = json_list(value, field)
    if not items or any(not isinstance(item, str) or not item.strip() for item in items):
        raise UserError(f"{field} must contain at least one non-empty string")
    return [item.strip() for item in items]


def require_text(data: dict, field: str) -> str:
    value = data.get(field)
    if not isinstance(value, str) or not value.strip():
        raise UserError(f"{field} must be a non-empty string")
    return value.strip()


def enum_value(value: object, field: str, allowed: set[str], allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    if value not in allowed:
        raise UserError(f"{field} must be one of: {', '.join(sorted(allowed))}")
    return str(value)


def integer_value(value: object, field: str, minimum: int, maximum: int, allow_none: bool = False) -> int | None:
    if value is None and allow_none:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise UserError(f"{field} must be an integer from {minimum} to {maximum}")
    return value


def validate_iso_date(value: object, field: str, allow_none: bool = False) -> str | None:
    if value in (None, "") and allow_none:
        return None
    if not isinstance(value, str):
        raise UserError(f"{field} must be an ISO 8601 date")
    try:
        date.fromisoformat(value)
    except ValueError as exc:
        raise UserError(f"{field} must use YYYY-MM-DD") from exc
    return value


def validate_url(value: object, field: str, allow_empty: bool = False) -> str:
    if value in (None, "") and allow_empty:
        return ""
    if not isinstance(value, str) or not value.strip():
        raise UserError(f"{field} must be a URL")
    parsed = urlsplit(value.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UserError(f"{field} must be an http(s) URL")
    return value.strip()


def canonical_domain(value: str) -> str:
    raw = value.strip()
    if "://" not in raw:
        raw = f"https://{raw}"
    parsed = urlsplit(raw)
    host = (parsed.hostname or "").lower().rstrip(".")
    if host.startswith("www."):
        host = host[4:]
    if not host or "." not in host:
        raise UserError(f"Cannot derive a public website domain from: {value}")
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as exc:
        raise UserError(f"Invalid website domain: {value}") from exc


def open_db(path: str, create: bool = False) -> sqlite3.Connection:
    db_path = Path(path).expanduser().resolve()
    if not create and not db_path.exists():
        raise UserError(f"Database does not exist: {db_path}")
    if create:
        db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def create_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)


def project_row(conn: sqlite3.Connection) -> sqlite3.Row:
    row = conn.execute("SELECT * FROM project WHERE id = 1").fetchone()
    if row is None:
        raise UserError("Project metadata is missing; run init first")
    return row


def decode_json_column(value: str, fallback: object) -> object:
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return fallback


def command_init(args: argparse.Namespace) -> None:
    db_path = Path(args.db).expanduser().resolve()
    existed = db_path.exists()
    with open_db(args.db, create=True) as conn:
        create_schema(conn)
        row = conn.execute("SELECT id FROM project WHERE id = 1").fetchone()
        if row is None:
            timestamp = now_iso()
            countries = [item.strip() for item in args.countries.split(",") if item.strip()]
            conn.execute(
                """INSERT INTO project
                   (id, project_name, product, countries, customer_types, exclusions,
                    stage, qualify_threshold, notes, created_at, updated_at)
                   VALUES (1, ?, ?, ?, '[]', '[]', 'prepare', 80, '', ?, ?)""",
                (args.project_name.strip(), args.product.strip(), json_text(countries), timestamp, timestamp),
            )
        emit({"created": not existed, "database": str(db_path), "project": project_as_dict(project_row(conn))})


def project_as_dict(row: sqlite3.Row) -> dict:
    return {
        "project_name": row["project_name"],
        "product": row["product"],
        "countries": decode_json_column(row["countries"], []),
        "customer_types": decode_json_column(row["customer_types"], []),
        "exclusions": decode_json_column(row["exclusions"], []),
        "stage": row["stage"],
        "qualify_threshold": row["qualify_threshold"],
        "notes": row["notes"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def command_set_project(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = {"project_name", "product", "countries", "customer_types", "exclusions", "stage", "qualify_threshold", "notes"}
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown project fields: {', '.join(sorted(unknown))}")
    with open_db(args.db) as conn:
        current = project_as_dict(project_row(conn))
        merged = {**current, **data}
        merged["project_name"] = require_text(merged, "project_name")
        merged["product"] = require_text(merged, "product")
        merged["countries"] = json_list(merged.get("countries"), "countries")
        merged["customer_types"] = json_list(merged.get("customer_types"), "customer_types")
        merged["exclusions"] = json_list(merged.get("exclusions"), "exclusions")
        merged["stage"] = enum_value(merged.get("stage"), "stage", STAGES)
        merged["qualify_threshold"] = integer_value(merged.get("qualify_threshold"), "qualify_threshold", 1, 100)
        if not isinstance(merged.get("notes", ""), str):
            raise UserError("notes must be a string")
        conn.execute(
            """UPDATE project SET project_name=?, product=?, countries=?, customer_types=?,
               exclusions=?, stage=?, qualify_threshold=?, notes=?, updated_at=? WHERE id=1""",
            (
                merged["project_name"], merged["product"], json_text(merged["countries"]),
                json_text(merged["customer_types"]), json_text(merged["exclusions"]), merged["stage"],
                merged["qualify_threshold"], merged["notes"], now_iso(),
            ),
        )
        emit({"project": project_as_dict(project_row(conn))})


def validate_breakdown(value: object) -> tuple[dict, int]:
    if value in (None, {}):
        return {}, 0
    if not isinstance(value, dict):
        raise UserError("score_breakdown must be an object")
    missing = set(SCORE_CAPS) - set(value)
    extra = set(value) - set(SCORE_CAPS)
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing {', '.join(sorted(missing))}")
        if extra:
            details.append(f"unknown {', '.join(sorted(extra))}")
        raise UserError("score_breakdown fields invalid: " + "; ".join(details))
    clean = {}
    for field, cap in SCORE_CAPS.items():
        clean[field] = integer_value(value[field], f"score_breakdown.{field}", 0, cap)
    return clean, sum(clean.values())


def company_defaults() -> dict:
    return {
        "name": "", "website": "", "country": "", "customer_type": "", "fit_score": None,
        "fit_status": "review", "score_breakdown": {}, "status": "new", "summary": "",
        "risks": [], "unknowns": [], "last_researched_at": None,
    }


def company_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "domain": row["domain"], "name": row["name"], "website": row["website"],
        "country": row["country"], "customer_type": row["customer_type"], "fit_score": row["fit_score"],
        "fit_status": row["fit_status"], "score_breakdown": decode_json_column(row["score_breakdown"], {}),
        "status": row["status"], "summary": row["summary"], "risks": decode_json_column(row["risks"], []),
        "unknowns": decode_json_column(row["unknowns"], []), "last_researched_at": row["last_researched_at"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def command_upsert_company(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = set(company_defaults())
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown company fields: {', '.join(sorted(unknown))}")
    website = validate_url(data.get("website"), "website")
    domain = canonical_domain(website)
    with open_db(args.db) as conn:
        existing_row = conn.execute("SELECT * FROM companies WHERE domain=?", (domain,)).fetchone()
        existing = company_from_row(existing_row) if existing_row else company_defaults()
        merged = {**existing, **data, "website": website}
        merged["name"] = require_text(merged, "name")
        for field in ("country", "customer_type", "summary"):
            if not isinstance(merged.get(field, ""), str):
                raise UserError(f"{field} must be a string")
        merged["fit_status"] = enum_value(merged.get("fit_status"), "fit_status", FIT_STATUSES)
        merged["status"] = enum_value(merged.get("status"), "status", COMPANY_STATUSES)
        merged["risks"] = json_list(merged.get("risks"), "risks")
        merged["unknowns"] = json_list(merged.get("unknowns"), "unknowns")
        merged["last_researched_at"] = validate_iso_date(merged.get("last_researched_at"), "last_researched_at", allow_none=True)
        breakdown, total = validate_breakdown(merged.get("score_breakdown"))
        fit_score = integer_value(merged.get("fit_score"), "fit_score", 0, 100, allow_none=True)
        if breakdown:
            if fit_score is None:
                fit_score = total
            elif fit_score != total:
                raise UserError(f"fit_score {fit_score} does not equal score_breakdown total {total}")
        if merged["fit_status"] == "qualified" and not breakdown:
            raise UserError("qualified companies require score_breakdown")
        threshold = project_row(conn)["qualify_threshold"]
        if merged["fit_status"] == "qualified":
            if fit_score is None or fit_score < threshold:
                raise UserError(f"qualified companies require fit_score >= project threshold {threshold}")
            if breakdown["product_relevance"] < 18 or breakdown["evidence_strength"] < 5:
                raise UserError("qualified companies require product_relevance >= 18 and evidence_strength >= 5")
        timestamp = now_iso()
        if existing_row:
            conn.execute(
                """UPDATE companies SET name=?, website=?, country=?, customer_type=?, fit_score=?, fit_status=?,
                   score_breakdown=?, status=?, summary=?, risks=?, unknowns=?, last_researched_at=?, updated_at=?
                   WHERE id=?""",
                (
                    merged["name"], website, merged["country"], merged["customer_type"], fit_score,
                    merged["fit_status"], json_text(breakdown), merged["status"], merged["summary"],
                    json_text(merged["risks"]), json_text(merged["unknowns"]), merged["last_researched_at"],
                    timestamp, existing_row["id"],
                ),
            )
            company_id = existing_row["id"]
            action = "updated"
        else:
            cursor = conn.execute(
                """INSERT INTO companies
                   (domain, name, website, country, customer_type, fit_score, fit_status, score_breakdown,
                    status, summary, risks, unknowns, last_researched_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    domain, merged["name"], website, merged["country"], merged["customer_type"], fit_score,
                    merged["fit_status"], json_text(breakdown), merged["status"], merged["summary"],
                    json_text(merged["risks"]), json_text(merged["unknowns"]), merged["last_researched_at"],
                    timestamp, timestamp,
                ),
            )
            company_id = cursor.lastrowid
            action = "created"
        result = company_from_row(conn.execute("SELECT * FROM companies WHERE id=?", (company_id,)).fetchone())
        emit({"action": action, "company": result})


def competitor_defaults() -> dict:
    return {
        "name": "", "website": "", "country": "", "market_position": "", "product_scope": "",
        "price_position": "", "materials": [], "specifications": [], "demand_signals": [],
        "differentiation": [], "last_researched_at": None,
    }


def competitor_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "domain": row["domain"], "name": row["name"], "website": row["website"],
        "country": row["country"], "market_position": row["market_position"],
        "product_scope": row["product_scope"], "price_position": row["price_position"],
        "materials": decode_json_column(row["materials"], []),
        "specifications": decode_json_column(row["specifications"], []),
        "demand_signals": decode_json_column(row["demand_signals"], []),
        "differentiation": decode_json_column(row["differentiation"], []),
        "last_researched_at": row["last_researched_at"], "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def command_upsert_competitor(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    unknown = set(data) - set(competitor_defaults())
    if unknown:
        raise UserError(f"Unknown competitor fields: {', '.join(sorted(unknown))}")
    website = validate_url(data.get("website"), "website")
    domain = canonical_domain(website)
    with open_db(args.db) as conn:
        existing_row = conn.execute("SELECT * FROM competitors WHERE domain=?", (domain,)).fetchone()
        existing = competitor_from_row(existing_row) if existing_row else competitor_defaults()
        merged = {**existing, **data, "website": website}
        merged["name"] = require_text(merged, "name")
        for field in ("country", "market_position", "product_scope", "price_position"):
            if not isinstance(merged.get(field, ""), str):
                raise UserError(f"{field} must be a string")
        for field in ("materials", "specifications", "demand_signals", "differentiation"):
            merged[field] = json_list(merged.get(field), field)
        merged["last_researched_at"] = validate_iso_date(
            merged.get("last_researched_at"), "last_researched_at", allow_none=True
        )
        timestamp = now_iso()
        values = (
            merged["name"], website, merged["country"], merged["market_position"],
            merged["product_scope"], merged["price_position"], json_text(merged["materials"]),
            json_text(merged["specifications"]), json_text(merged["demand_signals"]),
            json_text(merged["differentiation"]), merged["last_researched_at"], timestamp,
        )
        if existing_row:
            conn.execute(
                """UPDATE competitors SET name=?, website=?, country=?, market_position=?, product_scope=?,
                   price_position=?, materials=?, specifications=?, demand_signals=?, differentiation=?,
                   last_researched_at=?, updated_at=? WHERE id=?""",
                (*values, existing_row["id"]),
            )
            competitor_id = existing_row["id"]
            action = "updated"
        else:
            cursor = conn.execute(
                """INSERT INTO competitors
                   (name, website, country, market_position, product_scope, price_position, materials,
                    specifications, demand_signals, differentiation, last_researched_at, created_at, updated_at,
                    domain) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (*values, timestamp, domain),
            )
            competitor_id = cursor.lastrowid
            action = "created"
        result = competitor_from_row(conn.execute("SELECT * FROM competitors WHERE id=?", (competitor_id,)).fetchone())
        emit({"action": action, "competitor": result})


def social_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "entity_type": row["entity_type"], "entity_key": row["entity_key"],
        "platform": row["platform"], "profile_url": row["profile_url"],
        "verification_status": row["verification_status"], "activity_status": row["activity_status"],
        "audience_notes": row["audience_notes"],
        "content_signals": decode_json_column(row["content_signals"], []),
        "last_checked_at": row["last_checked_at"], "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def command_upsert_social(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = {
        "entity_type", "entity_key", "platform", "profile_url", "verification_status",
        "activity_status", "audience_notes", "content_signals", "last_checked_at",
    }
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown social profile fields: {', '.join(sorted(unknown))}")
    entity_type = enum_value(data.get("entity_type"), "entity_type", {"company", "competitor"})
    entity_key = canonical_domain(require_text(data, "entity_key"))
    platform = enum_value(data.get("platform"), "platform", SOCIAL_PLATFORMS)
    verification_status = enum_value(data.get("verification_status"), "verification_status", SOCIAL_STATUSES)
    activity_status = enum_value(data.get("activity_status", "not_checked"), "activity_status", SOCIAL_ACTIVITY)
    profile_url = validate_url(data.get("profile_url"), "profile_url", allow_empty=True)
    if verification_status == "official_linked" and not profile_url:
        raise UserError("official_linked social profiles require profile_url")
    if verification_status == "not_found" and profile_url:
        raise UserError("not_found social profiles cannot have profile_url")
    if activity_status == "not_found" and verification_status != "not_found":
        raise UserError("activity_status not_found requires verification_status not_found")
    audience_notes = data.get("audience_notes", "")
    if not isinstance(audience_notes, str):
        raise UserError("audience_notes must be a string")
    content_signals = json_list(data.get("content_signals"), "content_signals")
    last_checked_at = validate_iso_date(data.get("last_checked_at"), "last_checked_at", allow_none=True)
    with open_db(args.db) as conn:
        table = "companies" if entity_type == "company" else "competitors"
        if conn.execute(f"SELECT id FROM {table} WHERE domain=?", (entity_key,)).fetchone() is None:
            raise UserError(f"{entity_type} not found for social profile key: {entity_key}")
        existing = conn.execute(
            "SELECT id FROM social_profiles WHERE entity_type=? AND entity_key=? AND platform=?",
            (entity_type, entity_key, platform),
        ).fetchone()
        timestamp = now_iso()
        values = (
            profile_url, verification_status, activity_status, audience_notes,
            json_text(content_signals), last_checked_at, timestamp,
        )
        if existing:
            conn.execute(
                """UPDATE social_profiles SET profile_url=?, verification_status=?, activity_status=?,
                   audience_notes=?, content_signals=?, last_checked_at=?, updated_at=? WHERE id=?""",
                (*values, existing["id"]),
            )
            social_id = existing["id"]
            action = "updated"
        else:
            cursor = conn.execute(
                """INSERT INTO social_profiles
                   (entity_type, entity_key, platform, profile_url, verification_status, activity_status,
                    audience_notes, content_signals, last_checked_at, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (entity_type, entity_key, platform, profile_url, verification_status, activity_status,
                 audience_notes, json_text(content_signals), last_checked_at, timestamp, timestamp),
            )
            social_id = cursor.lastrowid
            action = "created"
        result = social_from_row(conn.execute("SELECT * FROM social_profiles WHERE id=?", (social_id,)).fetchone())
        emit({"action": action, "social_profile": result})


def contact_from_row(row: sqlite3.Row, domain: str | None = None) -> dict:
    return {
        "id": row["id"], "company_id": row["company_id"], "company_domain": domain,
        "name": row["name"], "title": row["title"], "role_rank": row["role_rank"],
        "profile_url": row["profile_url"], "work_email": row["work_email"],
        "email_status": row["email_status"], "work_phone": row["work_phone"],
        "phone_status": row["phone_status"], "notes": row["notes"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def command_upsert_contact(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = {"company_domain", "name", "title", "role_rank", "profile_url", "work_email", "email_status", "work_phone", "phone_status", "notes"}
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown contact fields: {', '.join(sorted(unknown))}")
    domain = canonical_domain(require_text(data, "company_domain"))
    name = require_text(data, "name")
    title = require_text(data, "title")
    with open_db(args.db) as conn:
        company = conn.execute("SELECT id FROM companies WHERE domain=?", (domain,)).fetchone()
        if company is None:
            raise UserError(f"Company not found for domain: {domain}")
        existing = conn.execute(
            "SELECT * FROM contacts WHERE company_id=? AND lower(name)=lower(?) AND lower(title)=lower(?)",
            (company["id"], name, title),
        ).fetchone()
        current = contact_from_row(existing, domain) if existing else {
            "role_rank": None, "profile_url": "", "work_email": "", "email_status": None,
            "work_phone": "", "phone_status": None, "notes": "",
        }
        merged = {**current, **data, "name": name, "title": title}
        role_rank = integer_value(merged.get("role_rank"), "role_rank", 1, 3, allow_none=True)
        profile_url = validate_url(merged.get("profile_url"), "profile_url", allow_empty=True)
        email_status = enum_value(merged.get("email_status"), "email_status", EMAIL_STATUSES, allow_none=True)
        phone_status = enum_value(merged.get("phone_status"), "phone_status", PHONE_STATUSES, allow_none=True)
        work_email = str(merged.get("work_email") or "").strip()
        work_phone = str(merged.get("work_phone") or "").strip()
        if work_email and not EMAIL_RE.match(work_email):
            raise UserError("work_email is not a valid email format")
        if work_email and email_status is None:
            raise UserError("work_email requires email_status")
        if email_status == "not_found" and work_email:
            raise UserError("email_status not_found cannot have work_email")
        if work_phone and phone_status is None:
            raise UserError("work_phone requires phone_status")
        if phone_status == "not_found" and work_phone:
            raise UserError("phone_status not_found cannot have work_phone")
        notes = merged.get("notes", "")
        if not isinstance(notes, str):
            raise UserError("notes must be a string")
        timestamp = now_iso()
        if existing:
            conn.execute(
                """UPDATE contacts SET name=?, title=?, role_rank=?, profile_url=?, work_email=?, email_status=?,
                   work_phone=?, phone_status=?, notes=?, updated_at=? WHERE id=?""",
                (name, title, role_rank, profile_url, work_email, email_status, work_phone, phone_status, notes, timestamp, existing["id"]),
            )
            contact_id = existing["id"]
            action = "updated"
        else:
            cursor = conn.execute(
                """INSERT INTO contacts
                   (company_id, name, title, role_rank, profile_url, work_email, email_status,
                    work_phone, phone_status, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (company["id"], name, title, role_rank, profile_url, work_email, email_status, work_phone, phone_status, notes, timestamp, timestamp),
            )
            contact_id = cursor.lastrowid
            action = "created"
        result = contact_from_row(conn.execute("SELECT * FROM contacts WHERE id=?", (contact_id,)).fetchone(), domain)
        emit({"action": action, "contact": result})


def outreach_from_row(row: sqlite3.Row, domain: str | None = None) -> dict:
    return {
        "id": row["id"], "company_id": row["company_id"], "company_domain": domain,
        "contact_id": row["contact_id"], "contact_label": row["contact_label"],
        "mode": row["mode"], "channel": row["channel"], "company_size": row["company_size"],
        "route_confidence": row["route_confidence"], "status": row["status"],
        "subject": row["subject"], "message": row["message"],
        "evidence_refs": decode_json_column(row["evidence_refs"], []), "cta": row["cta"],
        "next_action": row["next_action"], "due_date": row["due_date"], "notes": row["notes"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def command_upsert_outreach(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = {
        "company_domain", "contact_id", "contact_label", "mode", "channel", "company_size",
        "route_confidence", "status", "subject", "message", "evidence_refs", "cta",
        "next_action", "due_date", "notes",
    }
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown outreach fields: {', '.join(sorted(unknown))}")
    domain = canonical_domain(require_text(data, "company_domain"))
    mode = enum_value(data.get("mode"), "mode", OUTREACH_MODES)
    channel = enum_value(data.get("channel"), "channel", OUTREACH_CHANNELS)
    company_size = enum_value(data.get("company_size", "unknown"), "company_size", COMPANY_SIZES)
    route_confidence = enum_value(data.get("route_confidence"), "route_confidence", ROUTE_CONFIDENCES)
    status = enum_value(data.get("status", "draft"), "status", OUTREACH_STATUSES)
    contact_id = integer_value(data.get("contact_id"), "contact_id", 1, 2_147_483_647, allow_none=True)
    contact_label = str(data.get("contact_label") or "").strip()
    subject = str(data.get("subject") or "").strip()
    message = require_text(data, "message")
    cta = require_text(data, "cta")
    next_action = require_text(data, "next_action")
    evidence_refs = json_list(data.get("evidence_refs"), "evidence_refs")
    if not evidence_refs or any(not isinstance(item, str) or not item.strip() for item in evidence_refs):
        raise UserError("evidence_refs must contain at least one non-empty string")
    due_date = validate_iso_date(data.get("due_date"), "due_date", allow_none=True)
    notes = data.get("notes", "")
    if not isinstance(notes, str):
        raise UserError("notes must be a string")
    if route_confidence == "blocked" and status not in {"draft", "paused"}:
        raise UserError("blocked outreach routes can only be draft or paused")

    with open_db(args.db) as conn:
        company = conn.execute("SELECT id FROM companies WHERE domain=?", (domain,)).fetchone()
        if company is None:
            raise UserError(f"Company not found for domain: {domain}")
        contact = None
        if contact_id is not None:
            contact = conn.execute(
                "SELECT * FROM contacts WHERE id=? AND company_id=?", (contact_id, company["id"])
            ).fetchone()
            if contact is None:
                raise UserError(f"Contact {contact_id} does not belong to company: {domain}")
            if not contact_label:
                contact_label = f"{contact['name']} | {contact['title']}"
            if channel == "email" and contact["email_status"] in {"pattern_inferred", "unverified", None}:
                if route_confidence in {"high", "medium"}:
                    raise UserError("unconfirmed contact email requires low or blocked route_confidence")
            if channel == "whatsapp" and contact["phone_status"] != "confirmed_on_source":
                if route_confidence in {"high", "medium"}:
                    raise UserError("unconfirmed WhatsApp route requires low or blocked route_confidence")
            route_key = f"contact:{contact_id}"
        else:
            if not contact_label:
                raise UserError("contact_label is required when contact_id is not provided")
            route_key = f"label:{normalized_input(contact_label)}"

        existing = conn.execute(
            "SELECT * FROM outreach_plans WHERE company_id=? AND mode=? AND channel=? AND route_key=?",
            (company["id"], mode, channel, route_key),
        ).fetchone()
        timestamp = now_iso()
        values = (
            contact_id, contact_label, company_size, route_confidence, status, subject, message,
            json_text([item.strip() for item in evidence_refs]), cta, next_action, due_date, notes, timestamp,
        )
        if existing:
            conn.execute(
                """UPDATE outreach_plans SET contact_id=?, contact_label=?, company_size=?,
                   route_confidence=?, status=?, subject=?, message=?, evidence_refs=?, cta=?,
                   next_action=?, due_date=?, notes=?, updated_at=? WHERE id=?""",
                (*values, existing["id"]),
            )
            outreach_id = existing["id"]
            action = "updated"
        else:
            cursor = conn.execute(
                """INSERT INTO outreach_plans
                   (company_id, contact_id, route_key, contact_label, mode, channel, company_size,
                    route_confidence, status, subject, message, evidence_refs, cta, next_action,
                    due_date, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company["id"], contact_id, route_key, contact_label, mode, channel, company_size,
                    route_confidence, status, subject, message, json_text([item.strip() for item in evidence_refs]),
                    cta, next_action, due_date, notes, timestamp, timestamp,
                ),
            )
            outreach_id = cursor.lastrowid
            action = "created"
        result = outreach_from_row(
            conn.execute("SELECT * FROM outreach_plans WHERE id=?", (outreach_id,)).fetchone(), domain
        )
        emit({"action": action, "outreach_plan": result})


def activation_from_row(row: sqlite3.Row, domain: str | None = None) -> dict:
    return {
        "id": row["id"], "company_id": row["company_id"], "company_domain": domain,
        "contact_id": row["contact_id"], "contact_label": row["contact_label"],
        "lifecycle_stage": row["lifecycle_stage"], "status": row["status"],
        "priority": row["priority"], "channel": row["channel"],
        "last_outbound_at": row["last_outbound_at"], "last_reply_at": row["last_reply_at"],
        "followup_count": row["followup_count"], "max_followups": row["max_followups"],
        "activation_after_days": row["activation_after_days"], "next_due_date": row["next_due_date"],
        "next_action": row["next_action"], "notes": row["notes"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def command_upsert_activation(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = {
        "company_domain", "contact_id", "contact_label", "lifecycle_stage", "status", "priority",
        "channel", "last_outbound_at", "last_reply_at", "followup_count", "max_followups",
        "activation_after_days", "next_due_date", "next_action", "notes",
    }
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown activation fields: {', '.join(sorted(unknown))}")
    domain = canonical_domain(require_text(data, "company_domain"))
    lifecycle_stage = enum_value(data.get("lifecycle_stage"), "lifecycle_stage", LIFECYCLE_STAGES)
    status = enum_value(data.get("status"), "status", ACTIVATION_STATUSES)
    priority = integer_value(data.get("priority", 3), "priority", 1, 5)
    channel = enum_value(data.get("channel"), "channel", OUTREACH_CHANNELS)
    contact_id = integer_value(data.get("contact_id"), "contact_id", 1, 2_147_483_647, allow_none=True)
    contact_label = str(data.get("contact_label") or "").strip()
    last_outbound_at = validate_iso_date(data.get("last_outbound_at"), "last_outbound_at")
    last_reply_at = validate_iso_date(data.get("last_reply_at"), "last_reply_at", allow_none=True)
    followup_count = integer_value(data.get("followup_count", 0), "followup_count", 0, 100)
    max_followups = integer_value(data.get("max_followups", 3), "max_followups", 1, 100)
    activation_after_days = integer_value(
        data.get("activation_after_days", 5), "activation_after_days", 1, 365
    )
    next_due_date = validate_iso_date(data.get("next_due_date"), "next_due_date", allow_none=True)
    next_action = require_text(data, "next_action")
    notes = data.get("notes", "")
    if not isinstance(notes, str):
        raise UserError("notes must be a string")
    if followup_count > max_followups:
        raise UserError("followup_count cannot exceed max_followups")
    if status in {"waiting", "dormant"} and followup_count >= max_followups:
        raise UserError("waiting or dormant cases must remain below max_followups")
    if status in {"waiting", "dormant"} and last_reply_at and last_reply_at > last_outbound_at:
        raise UserError("a reply after the last outbound requires an active, paused or closed status")
    if status in {"closed", "opted_out"} and next_due_date:
        raise UserError("closed or opted_out cases cannot have next_due_date")

    with open_db(args.db) as conn:
        company = conn.execute("SELECT id FROM companies WHERE domain=?", (domain,)).fetchone()
        if company is None:
            raise UserError(f"Company not found for domain: {domain}")
        if contact_id is not None:
            contact = conn.execute(
                "SELECT * FROM contacts WHERE id=? AND company_id=?", (contact_id, company["id"])
            ).fetchone()
            if contact is None:
                raise UserError(f"Contact {contact_id} does not belong to company: {domain}")
            if not contact_label:
                contact_label = f"{contact['name']} | {contact['title']}"
            route_key = f"contact:{contact_id}"
        else:
            if not contact_label:
                raise UserError("contact_label is required when contact_id is not provided")
            route_key = f"label:{normalized_input(contact_label)}"
        existing = conn.execute(
            "SELECT * FROM activation_cases WHERE company_id=? AND route_key=?",
            (company["id"], route_key),
        ).fetchone()
        timestamp = now_iso()
        values = (
            contact_id, contact_label, lifecycle_stage, status, priority, channel, last_outbound_at,
            last_reply_at, followup_count, max_followups, activation_after_days, next_due_date,
            next_action, notes, timestamp,
        )
        if existing:
            conn.execute(
                """UPDATE activation_cases SET contact_id=?, contact_label=?, lifecycle_stage=?,
                   status=?, priority=?, channel=?, last_outbound_at=?, last_reply_at=?, followup_count=?,
                   max_followups=?, activation_after_days=?, next_due_date=?, next_action=?, notes=?,
                   updated_at=? WHERE id=?""",
                (*values, existing["id"]),
            )
            activation_id = existing["id"]
            action = "updated"
        else:
            cursor = conn.execute(
                """INSERT INTO activation_cases
                   (company_id, contact_id, route_key, contact_label, lifecycle_stage, status, priority,
                    channel, last_outbound_at, last_reply_at, followup_count, max_followups,
                    activation_after_days, next_due_date, next_action, notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    company["id"], contact_id, route_key, contact_label, lifecycle_stage, status, priority,
                    channel, last_outbound_at, last_reply_at, followup_count, max_followups,
                    activation_after_days, next_due_date, next_action, notes, timestamp, timestamp,
                ),
            )
            activation_id = cursor.lastrowid
            action = "created"
        result = activation_from_row(
            conn.execute("SELECT * FROM activation_cases WHERE id=?", (activation_id,)).fetchone(), domain
        )
        emit({"action": action, "activation_case": result})


def command_activation_report(args: argparse.Namespace) -> None:
    as_of_text = validate_iso_date(args.as_of or date.today().isoformat(), "as_of")
    as_of = date.fromisoformat(as_of_text)
    with open_db(args.db) as conn:
        rows = conn.execute(
            """SELECT ac.*, co.domain FROM activation_cases ac
               JOIN companies co ON co.id=ac.company_id
               WHERE ac.status IN ('waiting', 'dormant') AND ac.followup_count < ac.max_followups
               ORDER BY ac.priority, ac.last_outbound_at, co.domain"""
        ).fetchall()
        due = []
        for row in rows:
            reference_text = max(filter(None, (row["last_outbound_at"], row["last_reply_at"])))
            days_inactive = (as_of - date.fromisoformat(reference_text)).days
            is_due = days_inactive >= row["activation_after_days"]
            if row["next_due_date"]:
                is_due = is_due and row["next_due_date"] <= as_of_text
            if is_due:
                item = activation_from_row(row, row["domain"])
                item["days_inactive"] = days_inactive
                item["remaining_followups"] = row["max_followups"] - row["followup_count"]
                due.append(item)
        due.sort(key=lambda item: (item["priority"], -item["days_inactive"], item["company_domain"]))
        emit({"as_of": as_of_text, "due_count": len(due), "due": due})


def campaign_from_row(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"], "name": row["name"], "campaign_type": row["campaign_type"],
        "objective": row["objective"],
        "audience_segments": decode_json_column(row["audience_segments"], []),
        "target_languages": decode_json_column(row["target_languages"], []),
        "status": row["status"], "subject_variants": decode_json_column(row["subject_variants"], []),
        "content_brief": row["content_brief"],
        "suppression_rules": decode_json_column(row["suppression_rules"], []),
        "success_metrics": decode_json_column(row["success_metrics"], []),
        "planned_start": row["planned_start"], "notes": row["notes"],
        "created_at": row["created_at"], "updated_at": row["updated_at"],
    }


def command_upsert_campaign(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = {
        "name", "campaign_type", "objective", "audience_segments", "target_languages", "status",
        "subject_variants", "content_brief", "suppression_rules", "success_metrics",
        "planned_start", "notes",
    }
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown campaign fields: {', '.join(sorted(unknown))}")
    name = require_text(data, "name")
    name_key = normalized_input(name)
    campaign_type = enum_value(data.get("campaign_type"), "campaign_type", CAMPAIGN_TYPES)
    objective = require_text(data, "objective")
    audience_segments = non_empty_string_list(data.get("audience_segments"), "audience_segments")
    target_languages = non_empty_string_list(data.get("target_languages"), "target_languages")
    status = enum_value(data.get("status", "draft"), "status", CAMPAIGN_STATUSES)
    subject_variants = non_empty_string_list(data.get("subject_variants"), "subject_variants")
    content_brief = require_text(data, "content_brief")
    suppression_rules = non_empty_string_list(data.get("suppression_rules"), "suppression_rules")
    success_metrics = non_empty_string_list(data.get("success_metrics"), "success_metrics")
    planned_start = validate_iso_date(data.get("planned_start"), "planned_start", allow_none=True)
    notes = data.get("notes", "")
    if not isinstance(notes, str):
        raise UserError("notes must be a string")
    with open_db(args.db) as conn:
        existing = conn.execute("SELECT * FROM campaign_plans WHERE name_key=?", (name_key,)).fetchone()
        timestamp = now_iso()
        values = (
            name, campaign_type, objective, json_text(audience_segments), json_text(target_languages),
            status, json_text(subject_variants), content_brief, json_text(suppression_rules),
            json_text(success_metrics), planned_start, notes, timestamp,
        )
        if existing:
            conn.execute(
                """UPDATE campaign_plans SET name=?, campaign_type=?, objective=?, audience_segments=?,
                   target_languages=?, status=?, subject_variants=?, content_brief=?, suppression_rules=?,
                   success_metrics=?, planned_start=?, notes=?, updated_at=? WHERE id=?""",
                (*values, existing["id"]),
            )
            campaign_id = existing["id"]
            action = "updated"
        else:
            cursor = conn.execute(
                """INSERT INTO campaign_plans
                   (name_key, name, campaign_type, objective, audience_segments, target_languages, status,
                    subject_variants, content_brief, suppression_rules, success_metrics, planned_start,
                    notes, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (name_key, *values[:-1], timestamp, timestamp),
            )
            campaign_id = cursor.lastrowid
            action = "created"
        result = campaign_from_row(
            conn.execute("SELECT * FROM campaign_plans WHERE id=?", (campaign_id,)).fetchone()
        )
        emit({"action": action, "campaign_plan": result})


def command_add_evidence(args: argparse.Namespace) -> None:
    data = read_json_object(args.json_file)
    allowed = {"entity_type", "entity_key", "field", "claim", "source_url", "source_title", "source_type", "confidence", "observed_at"}
    unknown = set(data) - allowed
    if unknown:
        raise UserError(f"Unknown evidence fields: {', '.join(sorted(unknown))}")
    entity_type = enum_value(data.get("entity_type"), "entity_type", {"company", "contact", "competitor"})
    source_url = validate_url(data.get("source_url"), "source_url")
    source_type = enum_value(data.get("source_type"), "source_type", SOURCE_TYPES)
    confidence = enum_value(data.get("confidence"), "confidence", CONFIDENCES)
    observed_at = validate_iso_date(data.get("observed_at"), "observed_at")
    field = require_text(data, "field")
    claim = require_text(data, "claim")
    source_title = require_text(data, "source_title")
    with open_db(args.db) as conn:
        if entity_type in {"company", "competitor"}:
            domain = canonical_domain(str(data.get("entity_key", "")))
            table = "companies" if entity_type == "company" else "competitors"
            row = conn.execute(f"SELECT id FROM {table} WHERE domain=?", (domain,)).fetchone()
            if row is None:
                raise UserError(f"{entity_type.title()} not found for evidence key: {domain}")
            entity_id = row["id"]
        else:
            try:
                entity_id = int(data.get("entity_key"))
            except (TypeError, ValueError) as exc:
                raise UserError("Contact evidence entity_key must be a numeric contact ID") from exc
            if conn.execute("SELECT id FROM contacts WHERE id=?", (entity_id,)).fetchone() is None:
                raise UserError(f"Contact not found for evidence key: {entity_id}")
        cursor = conn.execute(
            """INSERT OR IGNORE INTO evidence
               (entity_type, entity_id, field, claim, source_url, source_title, source_type,
                confidence, observed_at, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (entity_type, entity_id, field, claim, source_url, source_title, source_type, confidence, observed_at, now_iso()),
        )
        evidence_id = cursor.lastrowid if cursor.rowcount else conn.execute(
            "SELECT id FROM evidence WHERE entity_type=? AND entity_id=? AND field=? AND source_url=? AND claim=?",
            (entity_type, entity_id, field, source_url, claim),
        ).fetchone()["id"]
        emit({"action": "created" if cursor.rowcount else "unchanged", "evidence_id": evidence_id})


def command_status(args: argparse.Namespace) -> None:
    with open_db(args.db) as conn:
        project = project_as_dict(project_row(conn))
        company_counts = {row["fit_status"]: row["count"] for row in conn.execute("SELECT fit_status, count(*) AS count FROM companies GROUP BY fit_status")}
        outreach_status_counts = {
            row["status"]: row["count"]
            for row in conn.execute("SELECT status, count(*) AS count FROM outreach_plans GROUP BY status")
        }
        outreach_mode_counts = {
            row["mode"]: row["count"]
            for row in conn.execute("SELECT mode, count(*) AS count FROM outreach_plans GROUP BY mode")
        }
        activation_counts = {
            row["status"]: row["count"]
            for row in conn.execute("SELECT status, count(*) AS count FROM activation_cases GROUP BY status")
        }
        campaign_counts = {
            row["status"]: row["count"]
            for row in conn.execute("SELECT status, count(*) AS count FROM campaign_plans GROUP BY status")
        }
        result = {
            "project": project,
            "companies": {status: company_counts.get(status, 0) for status in sorted(FIT_STATUSES)},
            "contacts": conn.execute("SELECT count(*) AS count FROM contacts").fetchone()["count"],
            "competitors": conn.execute("SELECT count(*) AS count FROM competitors").fetchone()["count"],
            "social_profiles": conn.execute("SELECT count(*) AS count FROM social_profiles").fetchone()["count"],
            "evidence": conn.execute("SELECT count(*) AS count FROM evidence").fetchone()["count"],
            "outreach_plans": {
                "total": conn.execute("SELECT count(*) AS count FROM outreach_plans").fetchone()["count"],
                "by_status": {item: outreach_status_counts.get(item, 0) for item in sorted(OUTREACH_STATUSES)},
                "by_mode": {item: outreach_mode_counts.get(item, 0) for item in sorted(OUTREACH_MODES)},
            },
            "activation_cases": {
                "total": conn.execute("SELECT count(*) AS count FROM activation_cases").fetchone()["count"],
                "by_status": {item: activation_counts.get(item, 0) for item in sorted(ACTIVATION_STATUSES)},
            },
            "campaign_plans": {
                "total": conn.execute("SELECT count(*) AS count FROM campaign_plans").fetchone()["count"],
                "by_status": {item: campaign_counts.get(item, 0) for item in sorted(CAMPAIGN_STATUSES)},
            },
            "recommended_next_stage": next_stage(project["stage"]),
        }
        emit(result)


def next_stage(stage: str) -> str | None:
    order = ["prepare", "search", "contacts", "contact_details", "research", "outreach", "export"]
    try:
        index = order.index(stage)
    except ValueError:
        return None
    return order[index + 1] if index + 1 < len(order) else None


def add_issue(target: list[dict], code: str, message: str, entity: str | None = None) -> None:
    item = {"code": code, "message": message}
    if entity:
        item["entity"] = entity
    target.append(item)


def command_validate(args: argparse.Namespace) -> None:
    errors: list[dict] = []
    warnings: list[dict] = []
    with open_db(args.db) as conn:
        project = project_as_dict(project_row(conn))
        threshold = project["qualify_threshold"]
        companies = conn.execute("SELECT * FROM companies ORDER BY id").fetchall()
        for row in companies:
            entity = f"company:{row['domain']}"
            if row["fit_status"] not in FIT_STATUSES:
                add_issue(errors, "invalid_fit_status", row["fit_status"], entity)
            if row["status"] not in COMPANY_STATUSES:
                add_issue(errors, "invalid_company_status", row["status"], entity)
            breakdown = decode_json_column(row["score_breakdown"], None)
            if breakdown:
                try:
                    clean, total = validate_breakdown(breakdown)
                    if row["fit_score"] != total:
                        add_issue(errors, "score_total_mismatch", f"fit_score={row['fit_score']}, breakdown={total}", entity)
                except UserError as exc:
                    add_issue(errors, "invalid_score_breakdown", str(exc), entity)
                    clean = {}
            else:
                clean = {}
                if row["fit_status"] == "qualified":
                    add_issue(errors, "qualified_without_breakdown", "Qualified company has no score breakdown", entity)
            if row["fit_status"] == "qualified":
                if row["fit_score"] is None or row["fit_score"] < threshold:
                    add_issue(errors, "qualified_below_threshold", f"Project threshold is {threshold}", entity)
                if clean and (clean["product_relevance"] < 18 or clean["evidence_strength"] < 5):
                    add_issue(errors, "qualified_below_component_gate", "Product relevance or evidence strength is too low", entity)
                evidence_rows = conn.execute("SELECT source_type FROM evidence WHERE entity_type='company' AND entity_id=?", (row["id"],)).fetchall()
                if not evidence_rows:
                    add_issue(errors, "qualified_without_evidence", "Qualified company has no stored evidence", entity)
                elif len({item["source_type"] for item in evidence_rows}) < 2:
                    add_issue(warnings, "single_source_type", "Qualified company has evidence from only one source type", entity)
            if row["fit_status"] == "review" and row["fit_score"] is not None and row["fit_score"] >= threshold:
                add_issue(warnings, "review_above_threshold", "Review record scores above the threshold; document the unresolved gate", entity)
            if row["last_researched_at"]:
                try:
                    validate_iso_date(row["last_researched_at"], "last_researched_at")
                except UserError as exc:
                    add_issue(errors, "invalid_research_date", str(exc), entity)
        contacts = conn.execute("SELECT c.*, co.domain FROM contacts c JOIN companies co ON co.id=c.company_id ORDER BY c.id").fetchall()
        ranks: dict[tuple[int, int], int] = {}
        for row in contacts:
            entity = f"contact:{row['id']}"
            if row["email_status"] not in EMAIL_STATUSES | {None}:
                add_issue(errors, "invalid_email_status", str(row["email_status"]), entity)
            if row["phone_status"] not in PHONE_STATUSES | {None}:
                add_issue(errors, "invalid_phone_status", str(row["phone_status"]), entity)
            if row["work_email"] and not EMAIL_RE.match(row["work_email"]):
                add_issue(errors, "invalid_email_format", row["work_email"], entity)
            if row["work_email"] and not row["email_status"]:
                add_issue(errors, "email_without_status", "Stored work email has no evidence status", entity)
            if row["email_status"] == "not_found" and row["work_email"]:
                add_issue(errors, "not_found_email_has_value", "not_found email status has a value", entity)
            if row["work_phone"] and not row["phone_status"]:
                add_issue(errors, "phone_without_status", "Stored work phone has no evidence status", entity)
            if row["role_rank"] is not None:
                key = (row["company_id"], row["role_rank"])
                if key in ranks:
                    add_issue(warnings, "duplicate_role_rank", f"Rank {row['role_rank']} is shared with contact {ranks[key]}", f"company:{row['domain']}")
                else:
                    ranks[key] = row["id"]
        competitors = conn.execute("SELECT * FROM competitors ORDER BY id").fetchall()
        for row in competitors:
            entity = f"competitor:{row['domain']}"
            for field in ("materials", "specifications", "demand_signals", "differentiation"):
                if not isinstance(decode_json_column(row[field], None), list):
                    add_issue(errors, "invalid_competitor_json", f"{field} must be a JSON array", entity)
            if row["last_researched_at"]:
                try:
                    validate_iso_date(row["last_researched_at"], "last_researched_at")
                except UserError as exc:
                    add_issue(errors, "invalid_competitor_date", str(exc), entity)
        social_profiles = conn.execute("SELECT * FROM social_profiles ORDER BY id").fetchall()
        for row in social_profiles:
            entity = f"social:{row['id']}"
            if row["platform"] not in SOCIAL_PLATFORMS:
                add_issue(errors, "invalid_social_platform", row["platform"], entity)
            if row["verification_status"] not in SOCIAL_STATUSES:
                add_issue(errors, "invalid_social_verification", row["verification_status"], entity)
            if row["activity_status"] not in SOCIAL_ACTIVITY:
                add_issue(errors, "invalid_social_activity", row["activity_status"], entity)
            table = "companies" if row["entity_type"] == "company" else "competitors" if row["entity_type"] == "competitor" else None
            if table is None:
                add_issue(errors, "invalid_social_entity_type", row["entity_type"], entity)
            elif conn.execute(f"SELECT id FROM {table} WHERE domain=?", (row["entity_key"],)).fetchone() is None:
                add_issue(errors, "orphan_social_profile", f"Missing {row['entity_type']} {row['entity_key']}", entity)
            if row["profile_url"]:
                try:
                    validate_url(row["profile_url"], "profile_url")
                except UserError as exc:
                    add_issue(errors, "invalid_social_url", str(exc), entity)
            if row["last_checked_at"]:
                try:
                    validate_iso_date(row["last_checked_at"], "last_checked_at")
                except UserError as exc:
                    add_issue(errors, "invalid_social_date", str(exc), entity)
        outreach_plans = conn.execute(
            """SELECT op.*, co.domain, c.email_status, c.phone_status
               FROM outreach_plans op
               JOIN companies co ON co.id=op.company_id
               LEFT JOIN contacts c ON c.id=op.contact_id
               ORDER BY op.id"""
        ).fetchall()
        for row in outreach_plans:
            entity = f"outreach:{row['id']}"
            if row["mode"] not in OUTREACH_MODES:
                add_issue(errors, "invalid_outreach_mode", row["mode"], entity)
            if row["channel"] not in OUTREACH_CHANNELS:
                add_issue(errors, "invalid_outreach_channel", row["channel"], entity)
            if row["company_size"] not in COMPANY_SIZES:
                add_issue(errors, "invalid_company_size", row["company_size"], entity)
            if row["route_confidence"] not in ROUTE_CONFIDENCES:
                add_issue(errors, "invalid_route_confidence", row["route_confidence"], entity)
            if row["status"] not in OUTREACH_STATUSES:
                add_issue(errors, "invalid_outreach_status", row["status"], entity)
            if row["route_confidence"] == "blocked" and row["status"] not in {"draft", "paused"}:
                add_issue(errors, "blocked_route_advanced", "Blocked route advanced beyond draft/paused", entity)
            evidence_refs = decode_json_column(row["evidence_refs"], None)
            if not isinstance(evidence_refs, list) or not evidence_refs:
                add_issue(errors, "missing_outreach_evidence", "Outreach plan requires evidence references", entity)
            if not row["message"] or not row["cta"] or not row["next_action"]:
                add_issue(errors, "incomplete_outreach_plan", "Message, CTA and next action are required", entity)
            if row["contact_id"] is not None:
                if row["channel"] == "email" and row["email_status"] in {"pattern_inferred", "unverified", None}:
                    if row["route_confidence"] in {"high", "medium"}:
                        add_issue(errors, "overstated_email_route", "Unconfirmed email route has excessive confidence", entity)
                if row["channel"] == "whatsapp" and row["phone_status"] != "confirmed_on_source":
                    if row["route_confidence"] in {"high", "medium"}:
                        add_issue(errors, "overstated_whatsapp_route", "Unconfirmed WhatsApp route has excessive confidence", entity)
            if row["due_date"]:
                try:
                    validate_iso_date(row["due_date"], "due_date")
                except UserError as exc:
                    add_issue(errors, "invalid_outreach_due_date", str(exc), entity)
        activation_cases = conn.execute(
            """SELECT ac.*, co.domain FROM activation_cases ac
               JOIN companies co ON co.id=ac.company_id ORDER BY ac.id"""
        ).fetchall()
        for row in activation_cases:
            entity = f"activation:{row['id']}"
            if row["lifecycle_stage"] not in LIFECYCLE_STAGES:
                add_issue(errors, "invalid_lifecycle_stage", row["lifecycle_stage"], entity)
            if row["status"] not in ACTIVATION_STATUSES:
                add_issue(errors, "invalid_activation_status", row["status"], entity)
            if row["channel"] not in OUTREACH_CHANNELS:
                add_issue(errors, "invalid_activation_channel", row["channel"], entity)
            if not 1 <= row["priority"] <= 5:
                add_issue(errors, "invalid_activation_priority", str(row["priority"]), entity)
            if row["followup_count"] > row["max_followups"]:
                add_issue(errors, "followup_limit_exceeded", "Follow-up count exceeds maximum", entity)
            if row["status"] in {"waiting", "dormant"} and row["followup_count"] >= row["max_followups"]:
                add_issue(errors, "activation_at_limit", "Waiting/dormant case reached maximum follow-ups", entity)
            if row["status"] in {"waiting", "dormant"} and row["last_reply_at"]:
                if row["last_reply_at"] > row["last_outbound_at"]:
                    add_issue(errors, "reply_after_outbound", "Case should no longer be waiting/dormant", entity)
            if row["status"] in {"closed", "opted_out"} and row["next_due_date"]:
                add_issue(errors, "suppressed_activation_due", "Closed/opted-out case has a due date", entity)
            for field in ("last_outbound_at", "last_reply_at", "next_due_date"):
                if row[field]:
                    try:
                        validate_iso_date(row[field], field)
                    except UserError as exc:
                        add_issue(errors, "invalid_activation_date", str(exc), entity)
        campaign_plans = conn.execute("SELECT * FROM campaign_plans ORDER BY id").fetchall()
        for row in campaign_plans:
            entity = f"campaign:{row['id']}"
            if row["campaign_type"] not in CAMPAIGN_TYPES:
                add_issue(errors, "invalid_campaign_type", row["campaign_type"], entity)
            if row["status"] not in CAMPAIGN_STATUSES:
                add_issue(errors, "invalid_campaign_status", row["status"], entity)
            for field in (
                "audience_segments", "target_languages", "subject_variants",
                "suppression_rules", "success_metrics",
            ):
                value = decode_json_column(row[field], None)
                if not isinstance(value, list) or not value:
                    add_issue(errors, "invalid_campaign_json", f"{field} must be a non-empty array", entity)
            if row["planned_start"]:
                try:
                    validate_iso_date(row["planned_start"], "planned_start")
                except UserError as exc:
                    add_issue(errors, "invalid_campaign_date", str(exc), entity)
        evidence_rows = conn.execute("SELECT * FROM evidence ORDER BY id").fetchall()
        for row in evidence_rows:
            entity = f"evidence:{row['id']}"
            table = (
                "companies" if row["entity_type"] == "company" else
                "contacts" if row["entity_type"] == "contact" else
                "competitors" if row["entity_type"] == "competitor" else None
            )
            if table is None:
                add_issue(errors, "invalid_evidence_entity_type", row["entity_type"], entity)
            elif conn.execute(f"SELECT id FROM {table} WHERE id=?", (row["entity_id"],)).fetchone() is None:
                add_issue(errors, "orphan_evidence", f"Missing {row['entity_type']} {row['entity_id']}", entity)
            if row["source_type"] not in SOURCE_TYPES:
                add_issue(errors, "invalid_source_type", row["source_type"], entity)
            if row["confidence"] not in CONFIDENCES:
                add_issue(errors, "invalid_confidence", row["confidence"], entity)
            try:
                validate_url(row["source_url"], "source_url")
                validate_iso_date(row["observed_at"], "observed_at")
            except UserError as exc:
                add_issue(errors, "invalid_evidence_field", str(exc), entity)
        emit({
            "ok": not errors, "errors": errors, "warnings": warnings,
            "counts": {
                "companies": len(companies), "contacts": len(contacts), "competitors": len(competitors),
                "social_profiles": len(social_profiles), "outreach_plans": len(outreach_plans),
                "activation_cases": len(activation_cases), "campaign_plans": len(campaign_plans),
                "evidence": len(evidence_rows),
            },
        })
    if errors:
        raise SystemExit(1)


def write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def command_export(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    with open_db(args.db) as conn:
        project = project_as_dict(project_row(conn))
        project_export = {**project}
        for key in ("countries", "customer_types", "exclusions"):
            project_export[key] = json_text(project_export[key])
        write_csv(out_dir / "project.csv", list(project_export), [project_export])

        companies = []
        for row in conn.execute("SELECT * FROM companies ORDER BY fit_score DESC, name").fetchall():
            item = company_from_row(row)
            item["score_breakdown"] = json_text(item["score_breakdown"])
            item["risks"] = json_text(item["risks"])
            item["unknowns"] = json_text(item["unknowns"])
            companies.append(item)
        company_fields = ["id", "domain", "name", "website", "country", "customer_type", "fit_score", "fit_status", "score_breakdown", "status", "summary", "risks", "unknowns", "last_researched_at", "created_at", "updated_at"]
        write_csv(out_dir / "companies.csv", company_fields, companies)

        contacts = []
        for row in conn.execute("SELECT c.*, co.domain FROM contacts c JOIN companies co ON co.id=c.company_id ORDER BY co.domain, c.role_rank, c.name").fetchall():
            contacts.append(contact_from_row(row, row["domain"]))
        contact_fields = ["id", "company_id", "company_domain", "name", "title", "role_rank", "profile_url", "work_email", "email_status", "work_phone", "phone_status", "notes", "created_at", "updated_at"]
        write_csv(out_dir / "contacts.csv", contact_fields, contacts)

        competitors = []
        for row in conn.execute("SELECT * FROM competitors ORDER BY name").fetchall():
            item = competitor_from_row(row)
            for key in ("materials", "specifications", "demand_signals", "differentiation"):
                item[key] = json_text(item[key])
            competitors.append(item)
        competitor_fields = [
            "id", "domain", "name", "website", "country", "market_position", "product_scope",
            "price_position", "materials", "specifications", "demand_signals", "differentiation",
            "last_researched_at", "created_at", "updated_at",
        ]
        write_csv(out_dir / "competitors.csv", competitor_fields, competitors)

        social_profiles = []
        for row in conn.execute("SELECT * FROM social_profiles ORDER BY entity_type, entity_key, platform").fetchall():
            item = social_from_row(row)
            item["content_signals"] = json_text(item["content_signals"])
            social_profiles.append(item)
        social_fields = [
            "id", "entity_type", "entity_key", "platform", "profile_url", "verification_status",
            "activity_status", "audience_notes", "content_signals", "last_checked_at", "created_at", "updated_at",
        ]
        write_csv(out_dir / "social_profiles.csv", social_fields, social_profiles)

        outreach_plans = []
        for row in conn.execute(
            """SELECT op.*, co.domain FROM outreach_plans op
               JOIN companies co ON co.id=op.company_id
               ORDER BY op.due_date, co.domain, op.id"""
        ).fetchall():
            item = outreach_from_row(row, row["domain"])
            item["evidence_refs"] = json_text(item["evidence_refs"])
            outreach_plans.append(item)
        outreach_fields = [
            "id", "company_id", "company_domain", "contact_id", "contact_label", "mode", "channel",
            "company_size", "route_confidence", "status", "subject", "message", "evidence_refs",
            "cta", "next_action", "due_date", "notes", "created_at", "updated_at",
        ]
        write_csv(out_dir / "outreach_plans.csv", outreach_fields, outreach_plans)

        activation_cases = []
        for row in conn.execute(
            """SELECT ac.*, co.domain FROM activation_cases ac
               JOIN companies co ON co.id=ac.company_id
               ORDER BY ac.next_due_date, ac.priority, co.domain"""
        ).fetchall():
            activation_cases.append(activation_from_row(row, row["domain"]))
        activation_fields = [
            "id", "company_id", "company_domain", "contact_id", "contact_label", "lifecycle_stage",
            "status", "priority", "channel", "last_outbound_at", "last_reply_at", "followup_count",
            "max_followups", "activation_after_days", "next_due_date", "next_action", "notes",
            "created_at", "updated_at",
        ]
        write_csv(out_dir / "activation_cases.csv", activation_fields, activation_cases)

        campaign_plans = []
        for row in conn.execute("SELECT * FROM campaign_plans ORDER BY planned_start, name").fetchall():
            item = campaign_from_row(row)
            for field in (
                "audience_segments", "target_languages", "subject_variants",
                "suppression_rules", "success_metrics",
            ):
                item[field] = json_text(item[field])
            campaign_plans.append(item)
        campaign_fields = [
            "id", "name", "campaign_type", "objective", "audience_segments", "target_languages",
            "status", "subject_variants", "content_brief", "suppression_rules", "success_metrics",
            "planned_start", "notes", "created_at", "updated_at",
        ]
        write_csv(out_dir / "campaign_plans.csv", campaign_fields, campaign_plans)

        evidence = [dict(row) for row in conn.execute("SELECT * FROM evidence ORDER BY entity_type, entity_id, field, id").fetchall()]
        evidence_fields = ["id", "entity_type", "entity_id", "field", "claim", "source_url", "source_title", "source_type", "confidence", "observed_at", "created_at"]
        write_csv(out_dir / "evidence.csv", evidence_fields, evidence)
    emit({
        "out_dir": str(out_dir),
        "files": [
            "project.csv", "companies.csv", "contacts.csv", "competitors.csv", "social_profiles.csv",
            "outreach_plans.csv", "activation_cases.csv", "campaign_plans.csv", "evidence.csv",
        ],
    })


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="WY local SQLite CRM")
    sub = parser.add_subparsers(dest="command", required=True)

    init_parser = sub.add_parser("init", help="Create a local CRM database")
    init_parser.add_argument("--db", required=True)
    init_parser.add_argument("--project-name", required=True)
    init_parser.add_argument("--product", required=True)
    init_parser.add_argument("--countries", required=True, help="Comma-separated countries")
    init_parser.set_defaults(func=command_init)

    for name, help_text, func in (
        ("set-project", "Update project metadata from JSON", command_set_project),
        ("upsert-company", "Create or update a company from JSON", command_upsert_company),
        ("upsert-contact", "Create or update a contact from JSON", command_upsert_contact),
        ("upsert-competitor", "Create or update a competitor benchmark from JSON", command_upsert_competitor),
        ("upsert-social", "Create or update a company or competitor social profile from JSON", command_upsert_social),
        ("upsert-outreach", "Create or update an evidence-linked outreach plan from JSON", command_upsert_outreach),
        ("upsert-activation", "Create or update a customer activation case from JSON", command_upsert_activation),
        ("upsert-campaign", "Create or update a campaign planning record from JSON", command_upsert_campaign),
        ("add-evidence", "Add field-level evidence from JSON", command_add_evidence),
    ):
        item = sub.add_parser(name, help=help_text)
        item.add_argument("--db", required=True)
        item.add_argument("--json-file", required=True)
        item.set_defaults(func=func)

    status_parser = sub.add_parser("status", help="Show project progress")
    status_parser.add_argument("--db", required=True)
    status_parser.set_defaults(func=command_status)

    activation_parser = sub.add_parser("activation-report", help="Show activation cases due for human review")
    activation_parser.add_argument("--db", required=True)
    activation_parser.add_argument("--as-of", help="Optional YYYY-MM-DD reporting date")
    activation_parser.set_defaults(func=command_activation_report)

    validate_parser = sub.add_parser("validate", help="Validate CRM invariants")
    validate_parser.add_argument("--db", required=True)
    validate_parser.set_defaults(func=command_validate)

    export_parser = sub.add_parser("export", help="Export CSV files")
    export_parser.add_argument("--db", required=True)
    export_parser.add_argument("--out-dir", required=True)
    export_parser.set_defaults(func=command_export)
    return parser


def main() -> int:
    try:
        assert_safe_input(sys.argv[1:])
        parser = build_parser()
        args = parser.parse_args()
        assert_safe_input({key: value for key, value in vars(args).items() if key != "func"})
        args.func(args)
    except InputRejected:
        print(json.dumps({"ok": False, "error": REJECTED_MESSAGE}), file=sys.stderr)
        return 2
    except UserError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2
    except sqlite3.Error as exc:
        print(json.dumps({"ok": False, "error": f"SQLite error: {exc}"}, ensure_ascii=False), file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
