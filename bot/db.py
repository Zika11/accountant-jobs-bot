# bot/db.py
"""
اتصال بسيط بقاعدة بيانات Supabase
بيستخدمه الـ scraper (للحفظ) والبوت (للقراءة والتحديث)
"""

import os
from supabase import create_client, Client

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "لازم تحدد SUPABASE_URL و SUPABASE_KEY في الـ environment variables أو ملف .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def insert_jobs(jobs: list[dict]) -> int:
    """
    يضيف وظائف جديدة، ويتجاهل أي وظيفة موجودة بالفعل (نفس الرابط).
    يتوقع أن كل وظيفة تحتوي على مفتاح 'source' (إن لم يكن، يضع 'unknown').
    """
    if not jobs:
        return 0
    # تأكد من وجود source
    for job in jobs:
        if 'source' not in job:
            job['source'] = 'unknown'
    client = get_client()
    result = client.table("jobs").upsert(jobs, on_conflict="url", ignore_duplicates=True).execute()
    return len(result.data) if result.data else 0


def get_unnotified_jobs(limit: int = 20) -> list[dict]:
    client = get_client()
    result = (
        client.table("jobs")
        .select("*")
        .eq("notified", False)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_jobs_by_status(status: str, limit: int = 20) -> list[dict]:
    client = get_client()
    result = (
        client.table("jobs")
        .select("*")
        .eq("status", status)
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_pending_jobs(limit: int = 20) -> list[dict]:
    return get_jobs_by_status("pending", limit=limit)


def mark_notified(job_id: str):
    client = get_client()
    client.table("jobs").update({"notified": True}).eq("id", job_id).execute()


def update_status(job_id: str, status: str):
    client = get_client()
    client.table("jobs").update({"status": status}).eq("id", job_id).execute()


def get_job_by_id(job_id: str) -> dict | None:
    client = get_client()
    result = client.table("jobs").select("*").eq("id", job_id).limit(1).execute()
    return result.data[0] if result.data else None


def search_jobs(keyword: str, limit: int = 15) -> list[dict]:
    """بحث بكلمة في العنوان أو الشركة أو المكان أو المصدر"""
    client = get_client()
    keyword = keyword.replace(",", " ").replace("%", " ").strip()
    pattern = f"%{keyword}%"
    result = (
        client.table("jobs")
        .select("*")
        .or_(f"title.ilike.{pattern},company.ilike.{pattern},location.ilike.{pattern},source.ilike.{pattern}")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []


def get_stats() -> dict:
    client = get_client()
    result = client.table("jobs").select("status,contact_email,contact_phone,source").execute()
    rows = result.data or []
    # إحصائيات إضافية حسب المصدر
    source_counts = {}
    for r in rows:
        src = r.get('source', 'unknown')
        source_counts[src] = source_counts.get(src, 0) + 1

    return {
        "total": len(rows),
        "pending": sum(1 for r in rows if r.get("status") == "pending"),
        "saved": sum(1 for r in rows if r.get("status") == "saved"),
        "ignored": sum(1 for r in rows if r.get("status") == "ignored"),
        "expired": sum(1 for r in rows if r.get("status") == "expired"),
        "with_contact": sum(1 for r in rows if r.get("contact_email") or r.get("contact_phone")),
        "by_source": source_counts,  # إحصائيات إضافية حسب المصدر
    }


def expire_old_jobs(days: int = 14) -> int:
    """يحوّل أي وظيفة لسه pending وعدى عليها أكتر من X يوم لحالة expired"""
    from datetime import datetime, timedelta, timezone

    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    result = (
        client.table("jobs")
        .update({"status": "expired"})
        .eq("status", "pending")
        .lt("created_at", cutoff)
        .execute()
    )
    return len(result.data) if result.data else 0


def get_setting(key: str) -> str | None:
    client = get_client()
    result = client.table("settings").select("value").eq("key", key).limit(1).execute()
    return result.data[0]["value"] if result.data else None


def set_setting(key: str, value: str):
    client = get_client()
    client.table("settings").upsert({"key": key, "value": value}, on_conflict="key").execute()
