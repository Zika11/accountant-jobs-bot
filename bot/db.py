# bot/db.py
"""
اتصال بقاعدة بيانات Supabase
يدعم: jobs, settings, user_profiles, scraper_logs
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, List, Any

from supabase import create_client, Client

# ==================== إعدادات ====================

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ==================== عميل Supabase (Singleton) ====================

_CLIENT: Optional[Client] = None


def get_client() -> Client:
    """إرجاع عميل Supabase (نسخة واحدة فقط)"""
    global _CLIENT
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError("لازم تحدد SUPABASE_URL و SUPABASE_KEY في environment variables")
    if _CLIENT is None:
        _CLIENT = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _CLIENT


# ==================== دوال الوظائف (jobs) ====================

def insert_jobs(jobs: List[Dict]) -> int:
    """إدراج أو تحديث وظائف جديدة (تجاهل المكرر حسب الرابط)"""
    if not jobs:
        return 0

    for job in jobs:
        if 'source' not in job:
            job['source'] = 'unknown'
        if 'status' not in job:
            job['status'] = 'pending'
        if 'notified' not in job:
            job['notified'] = False

    client = get_client()
    try:
        # ✅ أهم تغيير: شيل ignore_duplicates=True عشان يحدث البيانات
        result = client.table("jobs").upsert(jobs, on_conflict="url").execute()
        return len(result.data) if result.data else 0
    except Exception as e:
        print(f"⚠️ فشل insert_jobs: {e}")
        return 0


def get_unnotified_jobs(limit: int = 20) -> List[Dict]:
    """جلب الوظائف الجديدة (غير مُبلغ عنها)"""
    client = get_client()
    try:
        result = (
            client.table("jobs")
            .select("*")
            .eq("notified", False)
            .eq("status", "pending")
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"⚠️ فشل get_unnotified_jobs: {e}")
        return []


def get_jobs_by_status(status: str, limit: int = 20) -> List[Dict]:
    """جلب الوظائف حسب الحالة"""
    client = get_client()
    try:
        result = (
            client.table("jobs")
            .select("*")
            .eq("status", status)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"⚠️ فشل get_jobs_by_status: {e}")
        return []


def get_pending_jobs(limit: int = 20) -> List[Dict]:
    """جلب الوظائف قيد الانتظار"""
    return get_jobs_by_status("pending", limit)


def mark_notified(job_id: str) -> bool:
    """تحديد وظيفة كـ 'تم الإبلاغ عنها' """
    client = get_client()
    try:
        client.table("jobs").update({"notified": True}).eq("id", job_id).execute()
        return True
    except Exception as e:
        print(f"⚠️ فشل mark_notified: {e}")
        return False


def update_status(job_id: str, status: str) -> bool:
    """تحديث حالة وظيفة"""
    valid_statuses = ["pending", "saved", "ignored", "applied", "expired"]
    if status not in valid_statuses:
        print(f"⚠️ حالة غير صالحة: {status}")
        return False

    client = get_client()
    try:
        client.table("jobs").update({"status": status}).eq("id", job_id).execute()
        return True
    except Exception as e:
        print(f"⚠️ فشل update_status: {e}")
        return False


def get_job_by_id(job_id: str) -> Optional[Dict]:
    """جلب وظيفة بواسطة الـ ID"""
    client = get_client()
    try:
        result = client.table("jobs").select("*").eq("id", job_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"⚠️ فشل get_job_by_id: {e}")
        return None


def search_jobs(keyword: str, limit: int = 15) -> List[Dict]:
    """بحث في الوظائف (العنوان، الشركة، المكان، المصدر) - فقط pending و saved"""
    client = get_client()
    keyword = keyword.replace(",", " ").replace("%", " ").strip()
    pattern = f"%{keyword}%"

    try:
        result = (
            client.table("jobs")
            .select("*")
            .or_(f"title.ilike.{pattern},company.ilike.{pattern},location.ilike.{pattern},source.ilike.{pattern}")
            .in_("status", ["pending", "saved"])
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return result.data or []
    except Exception as e:
        print(f"⚠️ فشل search_jobs: {e}")
        return []


def get_stats() -> Dict:
    """جلب إحصائيات الوظائف (محسّن)"""
    client = get_client()
    try:
        statuses = ["pending", "saved", "ignored", "applied", "expired"]
        stats = {
            "total": 0,
            "pending": 0,
            "saved": 0,
            "ignored": 0,
            "applied": 0,
            "expired": 0,
            "with_contact": 0,
            "by_source": {}
        }

        for status in statuses:
            result = client.table("jobs").select("*", count="exact").eq("status", status).execute()
            stats[status] = result.count or 0
            stats["total"] += result.count or 0

        result = client.table("jobs").select("*", count="exact").or_(
            "contact_email.not.is.null,contact_phone.not.is.null"
        ).execute()
        stats["with_contact"] = result.count or 0

        result = client.table("jobs").select("source").execute()
        for row in result.data or []:
            src = row.get('source', 'unknown')
            stats["by_source"][src] = stats["by_source"].get(src, 0) + 1

        return stats
    except Exception as e:
        print(f"⚠️ فشل get_stats: {e}")
        return {
            "total": 0, "pending": 0, "saved": 0,
            "ignored": 0, "applied": 0, "expired": 0,
            "with_contact": 0, "by_source": {}
        }


def expire_old_jobs(days: int = 14) -> int:
    """تحويل الوظائف القديمة إلى expired"""
    client = get_client()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    try:
        result = (
            client.table("jobs")
            .update({"status": "expired"})
            .eq("status", "pending")
            .lt("created_at", cutoff)
            .execute()
        )
        return len(result.data) if result.data else 0
    except Exception as e:
        print(f"⚠️ فشل expire_old_jobs: {e}")
        return 0


# ==================== دوال الإعدادات (settings) ====================

def get_setting(key: str) -> Optional[str]:
    """جلب إعداد"""
    client = get_client()
    try:
        result = client.table("settings").select("value").eq("key", key).limit(1).execute()
        return result.data[0]["value"] if result.data else None
    except Exception as e:
        print(f"⚠️ فشل get_setting: {e}")
        return None


def set_setting(key: str, value: str):
    """تعيين إعداد"""
    client = get_client()
    try:
        client.table("settings").upsert({"key": key, "value": value}, on_conflict="key").execute()
    except Exception as e:
        print(f"⚠️ فشل set_setting: {e}")


# ==================== دوال الملفات الشخصية (user_profiles) ====================

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
) -> Optional[Dict]:
    """إنشاء ملف شخصي جديد"""
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
    try:
        result = client.table("user_profiles").insert(data).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"⚠️ فشل create_user_profile: {e}")
        return None


def get_user_profile(user_id: str) -> Optional[Dict]:
    """جلب ملف شخصي"""
    client = get_client()
    try:
        result = client.table("user_profiles").select("*").eq("user_id", user_id).limit(1).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"⚠️ فشل get_user_profile: {e}")
        return None


def update_user_profile(user_id: str, updates: Dict) -> Optional[Dict]:
    """تحديث ملف شخصي"""
    if not updates:
        return get_user_profile(user_id)

    client = get_client()
    try:
        result = client.table("user_profiles").update(updates).eq("user_id", user_id).execute()
        return result.data[0] if result.data else None
    except Exception as e:
        print(f"⚠️ فشل update_user_profile: {e}")
        return None


def upsert_user_profile(user_id: str, data: Dict) -> Optional[Dict]:
    """إنشاء أو تحديث ملف شخصي"""
    allowed_fields = [
        "name", "experience_years", "skills", "preferred_locations",
        "expected_salary", "cv_text", "cv_file_id", "chat_id",
        "phone", "email", "auto_apply"
    ]
    filtered_data = {k: v for k, v in data.items() if k in allowed_fields}

    existing = get_user_profile(user_id)
    if existing:
        updates = {k: v for k, v in filtered_data.items() if v is not None}
        return update_user_profile(user_id, updates) or existing
    else:
        return create_user_profile(user_id=user_id, **filtered_data)


def delete_user_profile(user_id: str) -> bool:
    """حذف ملف شخصي"""
    client = get_client()
    try:
        result = client.table("user_profiles").delete().eq("user_id", user_id).execute()
        return len(result.data) > 0
    except Exception as e:
        print(f"⚠️ فشل delete_user_profile: {e}")
        return False


# ==================== دوال سجلات الأخطاء (scraper_logs) ====================

def log_scraper_error(source: str, error: str, traceback_text: str = "") -> bool:
    """تسجيل خطأ في السكرابر"""
    client = get_client()
    try:
        data = {
            "source": source,
            "error": str(error)[:500],
            "traceback": traceback_text[:1000],
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        client.table("scraper_logs").insert(data).execute()
        return True
    except Exception as e:
        print(f"⚠️ فشل log_scraper_error: {e}")
        return False
