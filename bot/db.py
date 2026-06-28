# bot/db.py
"""
اتصال بقاعدة بيانات Supabase
يدعم الآن جداول: jobs, settings, user_profiles
"""

import os
from datetime import datetime, timedelta, timezone
from supabase import create_client, Client
from typing import List, Dict, Optional, Any

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "لازم تحدد SUPABASE_URL و SUPABASE_KEY في الـ environment variables أو ملف .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


# ========== دوال الوظائف (jobs) ==========

def insert_jobs(jobs: List[Dict]) -> int:
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


def get_unnotified_jobs(limit: int = 20) -> List[Dict]:
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


def get_jobs_by_status(status: str, limit: int = 20) -> List[Dict]:
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


def get_pending_jobs(limit: int = 20) -> List[Dict]:
    return get_jobs_by_status("pending", limit=limit)


def mark_notified(job_id: str) -> None:
    client = get_client()
    client.table("jobs").update({"notified": True}).eq("id", job_id).execute()


def update_status(job_id: str, status: str) -> None:
    client = get_client()
    client.table("jobs").update({"status": status}).eq("id", job_id).execute()


def get_job_by_id(job_id: str) -> Optional[Dict]:
    client = get_client()
    result = client.table("jobs").select("*").eq("id", job_id).limit(1).execute()
    return result.data[0] if result.data else None


def search_jobs(keyword: str, limit: int = 15) -> List[Dict]:
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


def get_stats() -> Dict:
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
        "by_source": source_counts,
    }


def expire_old_jobs(days: int = 14) -> int:
    """يحوّل أي وظيفة لسه pending وعدى عليها أكتر من X يوم لحالة expired"""
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


# ========== دوال الإعدادات (settings) ==========

def get_setting(key: str) -> Optional[str]:
    client = get_client()
    result = client.table("settings").select("value").eq("key", key).limit(1).execute()
    return result.data[0]["value"] if result.data else None


def set_setting(key: str, value: str) -> None:
    client = get_client()
    client.table("settings").upsert({"key": key, "value": value}, on_conflict="key").execute()


# ========== دوال ملفات المستخدمين (user_profiles) ==========

def get_user_profile(user_id: str) -> Optional[Dict]:
    """جلب ملف المستخدم كاملاً"""
    client = get_client()
    result = client.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
    return result.data[0] if result.data else None


def create_or_update_user_profile(user_id: str, data: Dict) -> Dict:
    """إنشاء أو تحديث ملف المستخدم. data يمكن أن تحتوي على:
    name, experience_years, skills, preferred_locations, expected_salary, cv_text, cv_file_id
    """
    client = get_client()
    # تأكد من وجود user_id
    data['user_id'] = user_id
    data['updated_at'] = datetime.now(timezone.utc).isoformat()
    result = client.table("user_profiles").upsert(data, on_conflict="user_id").execute()
    return result.data[0] if result.data else {}


def update_user_cv_text(user_id: str, cv_text: str) -> None:
    """تحديث نص الـ CV المستخرج من الملف"""
    client = get_client()
    client.table("user_profiles").update({
        "cv_text": cv_text,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("user_id", user_id).execute()


def update_user_cv_file_id(user_id: str, file_id: str) -> None:
    """تحديث معرف ملف الـ CV في تليجرام"""
    client = get_client()
    client.table("user_profiles").update({
        "cv_file_id": file_id,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }).eq("user_id", user_id).execute()


def get_all_users_with_profiles(limit: int = 100) -> List[Dict]:
    """جلب كل المستخدمين الذين لديهم ملفات شخصية (للاستخدام في الإحصائيات أو التنبيهات)"""
    client = get_client()
    result = client.table("user_profiles").select("*").limit(limit).execute()
    return result.data or []


def delete_user_profile(user_id: str) -> None:
    """حذف ملف مستخدم"""
    client = get_client()
    client.table("user_profiles").delete().eq("user_id", user_id).execute()


# ========== دوال مساعدة للذكاء والتوصيات ==========

def get_jobs_for_user(user_id: str, limit: int = 20) -> List[Dict]:
    """
    تجلب الوظائف الأكثر ملاءمة لمستخدم بناءً على ملفه الشخصي.
    هذه دالة بسيطة، يمكن تطويرها لاستخدام AI.
    """
    profile = get_user_profile(user_id)
    if not profile:
        return get_pending_jobs(limit=limit)

    # فلترة بسيطة حسب سنوات الخبرة
    max_exp = profile.get('experience_years')
    jobs = get_pending_jobs(limit=limit * 2)  # نجيب ضعف العدد للفلترة

    if max_exp is not None:
        filtered = []
        for job in jobs:
            min_exp = job.get('min_experience')
            if min_exp is None or min_exp <= max_exp:
                filtered.append(job)
        jobs = filtered

    # لو في مهارات مفضلة، ممكن نضيف فلترة حسب الكلمات المفتاحية
    skills = profile.get('skills', [])
    if skills:
        scored_jobs = []
        for job in jobs:
            title = job.get('title', '').lower()
            desc = job.get('experience', '').lower()
            score = 0
            for skill in skills:
                if skill.lower() in title or skill.lower() in desc:
                    score += 1
            scored_jobs.append((job, score))
        # رتب حسب النقاط
        scored_jobs.sort(key=lambda x: x[1], reverse=True)
        jobs = [j for j, _ in scored_jobs[:limit]]
    else:
        jobs = jobs[:limit]

    return jobs
