# bot/db.py
"""
اتصال بقاعدة بيانات Supabase
"""

import os
from supabase import create_client, Client
from typing import Optional, Dict, List

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("لازم تحدد SUPABASE_URL و SUPABASE_KEY")
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ===========================
# دوال الوظائف (jobs)
# ===========================

def insert_jobs(jobs: list[dict]) -> int:
    if not jobs:
        return 0
    for job in jobs:
        if 'source' not in job:
            job['source'] = 'unknown'
    client = get_client()
    result = client.table("jobs").upsert(jobs, on_conflict="url", ignore_duplicates=True).execute()
    return len(result.data) if result.data else 0


def get_unnotified_jobs(limit: int = 20) -> list[dict]:
    client = get_client()
    result = (client.table("jobs")
              .select("*")
              .eq("notified", False)
              .eq("status", "pending")
              .order("created_at", desc=True)
              .limit(limit)
              .execute())
    return result.data or []


def get_jobs_by_status(status: str, limit: int = 20) -> list[dict]:
    client = get_client()
    result = (client.table("jobs")
              .select("*")
              .eq("status", status)
              .order("created_at", desc=True)
              .limit(limit)
              .execute())
    return result.data or []


def get_pending_jobs(limit: int = 20) -> list[dict]:
    return get_jobs_by_status("pending", limit=limit)


def mark_notified(job_id: str):
    client = get_client()
    client.table("jobs").update({"notified": True}).eq("id", job_id).execute()


def update_status(job_id: str, status: str):
    client = get_client()
    client.table("jobs").update({"status": status}).eq("id", job_id).execute()


def get_job_by_id(job_id: str) -> Optional[dict]:
    client = get_client()
    result = client.table("jobs").select("*").eq("id", job_id).limit(1).execute()
    return result.data[0] if result.data else None


def search_jobs(keyword: str, limit: int = 15) -> list[dict]:
    client = get_client()
    keyword = keyword.replace(",", " ").replace("%", " ").strip()
    pattern = f"%{keyword}%"
    result = (client.table("jobs")
              .select("*")
              .or_(f"title.ilike.{pattern},company.ilike.{pattern},location.ilike.{pattern},source.ilike.{pattern}")
              .order("created_at", desc=True)
              .limit(limit)
              .execute())
    return result.data or []


def get_stats() -> dict:
    client = get_client()
    result = client.table("jobs").select("status,contact_email,contact_phone,source").execute()
    rows = result.data or []
    source_counts = {}
    applied = 0
    for r in rows:
        src = r.get('source', 'unknown')
        source_counts[src] = source_counts.get(src, 0) + 1
        if r.get('status') == 'applied':
            applied += 1
    return {
        "total": len(rows),
        "pending": sum(1 for r in rows if r.get("status") == "pending"),
        "saved": sum(1 for r in rows if r.get("status") == "saved"),
        "ignored": sum(1 for r in rows if r.get("status") == "ignored"),
        "expired": sum(1 for r in rows if r.get("status") == "expired"),
        "applied": applied,
        "with_contact": sum(1 for r in rows if r.get("contact_email") or r.get("contact_phone")),
        "by_source": source_counts,
    }


def expire_old_jobs(days: int = 14) -> int:
    from datetime import datetime, timedelta, timezone
    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (client.table("jobs")
              .update({"status": "expired"})
              .eq("status", "pending")
              .lt("created_at", cutoff)
              .execute())
    return len(result.data) if result.data else 0


# ===========================
# دوال الإعدادات (settings)
# ===========================

def get_setting(key: str) -> Optional[str]:
    client = get_client()
    result = client.table("settings").select("value").eq("key", key).limit(1).execute()
    return result.data[0]["value"] if result.data else None


def set_setting(key: str, value: str):
    client = get_client()
    client.table("settings").upsert({"key": key, "value": value}, on_conflict="key").execute()


# ===========================
# دوال الملفات الشخصية (user_profiles)
# ===========================

def create_user_profile(
    user_id: str,
    name: str = "",
    experience_years: int = 0,
    skills: List[str] = None,
    preferred_locations: List[str] = None,
    expected_salary: int = None,
    cv_text: str = "",
    cv_file_id: str = None,
    chat_id: str = None,
    phone: str = None,
    email: str = None,
    auto_apply: bool = True,
) -> dict:
    if skills is None:
        skills = []
    if preferred_locations is None:
        preferred_locations = []
    client = get_client()
    data = {
        "user_id": user_id,
        "name": name,
        "experience_years": experience_years,
        "skills": skills,
        "preferred_locations": preferred_locations,
        "expected_salary": expected_salary,
        "cv_text": cv_text,
        "cv_file_id": cv_file_id,
        "chat_id": chat_id,
        "phone": phone,
        "email": email,
        "auto_apply": auto_apply,
    }
    result = client.table("user_profiles").insert(data).execute()
    return result.data[0] if result.data else {}


def get_user_profile(user_id: str) -> Optional[dict]:
    client = get_client()
    result = (client.table("user_profiles")
              .select("*")
              .eq("user_id", user_id)
              .limit(1)
              .execute())
    return result.data[0] if result.data else None


def update_user_profile(user_id: str, updates: dict) -> Optional[dict]:
    client = get_client()
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    if not clean_updates:
        return get_user_profile(user_id)
    result = (client.table("user_profiles")
              .update(clean_updates)
              .eq("user_id", user_id)
              .execute())
    return result.data[0] if result.data else None


def upsert_user_profile(user_id: str, data: dict) -> dict:
    existing = get_user_profile(user_id)
    if existing:
        updates = {k: v for k, v in data.items() if v is not None}
        return update_user_profile(user_id, updates) or existing
    else:
        return create_user_profile(user_id=user_id, **data)


def get_allowed_users() -> list[dict]:
    client = get_client()
    result = client.table("user_profiles").select("user_id, chat_id, auto_apply").execute()
    return result.data or []


def delete_user_profile(user_id: str) -> bool:
    client = get_client()
    result = client.table("user_profiles").delete().eq("user_id", user_id).execute()
    return len(result.data) > 0
