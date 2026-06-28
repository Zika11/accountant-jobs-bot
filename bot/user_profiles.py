"""
ملف للتعامل مع جدول user_profiles في Supabase
بيحتوي على دوال: إنشاء، قراءة، تحديث، حذف للملف الشخصي للمستخدم
"""

import os
from supabase import create_client, Client
from typing import Optional, Dict, List

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")


def get_client() -> Client:
    if not SUPABASE_URL or not SUPABASE_KEY:
        raise RuntimeError(
            "لازم تحدد SUPABASE_URL و SUPABASE_KEY في الـ environment variables أو ملف .env"
        )
    return create_client(SUPABASE_URL, SUPABASE_KEY)


def create_user_profile(
    user_id: str,
    name: str = "",
    experience_years: int = 0,
    skills: List[str] = None,
    preferred_locations: List[str] = None,
    expected_salary: int = None,
    cv_text: str = "",
    cv_file_id: str = None,
) -> Dict:
    """
    ينشئ ملف شخصي جديد للمستخدم.
    يرجع البيانات المدخلة (مع created_at).
    """
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
    }
    result = client.table("user_profiles").insert(data).execute()
    return result.data[0] if result.data else {}


def get_user_profile(user_id: str) -> Optional[Dict]:
    """يجلب الملف الشخصي لمستخدم معين، أو None إذا لم يكن موجوداً."""
    client = get_client()
    result = (
        client.table("user_profiles")
        .select("*")
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None


def update_user_profile(user_id: str, updates: Dict) -> Optional[Dict]:
    """
    يحدث حقول محددة في الملف الشخصي للمستخدم.
    updates: dict فيه الحقول المطلوب تحديثها (مثل {"name": "أحمد", "experience_years": 5})
    يرجع البيانات المحدثة.
    """
    client = get_client()
    # حذف أي مفتاح None عشان ما يسبب مشكلة
    clean_updates = {k: v for k, v in updates.items() if v is not None}
    if not clean_updates:
        return get_user_profile(user_id)

    result = (
        client.table("user_profiles")
        .update(clean_updates)
        .eq("user_id", user_id)
        .execute()
    )
    return result.data[0] if result.data else None


def delete_user_profile(user_id: str) -> bool:
    """يحذف الملف الشخصي للمستخدم. يرجع True إذا تم الحذف بنجاح."""
    client = get_client()
    result = client.table("user_profiles").delete().eq("user_id", user_id).execute()
    return len(result.data) > 0


def update_cv_text(user_id: str, cv_text: str) -> Optional[Dict]:
    """تحديث نص الـ CV (المستخرج من ملف PDF مثلاً)."""
    return update_user_profile(user_id, {"cv_text": cv_text})


def update_cv_file_id(user_id: str, cv_file_id: str) -> Optional[Dict]:
    """تحديث file_id الخاص بـ CV في تليجرام."""
    return update_user_profile(user_id, {"cv_file_id": cv_file_id})


def add_skill(user_id: str, skill: str) -> Optional[Dict]:
    """يضيف مهارة جديدة لقائمة المهارات (تجنب التكرار)."""
    profile = get_user_profile(user_id)
    if not profile:
        return None
    skills = profile.get("skills", [])
    if skill not in skills:
        skills.append(skill)
    return update_user_profile(user_id, {"skills": skills})


def remove_skill(user_id: str, skill: str) -> Optional[Dict]:
    """يزيل مهارة من القائمة."""
    profile = get_user_profile(user_id)
    if not profile:
        return None
    skills = profile.get("skills", [])
    if skill in skills:
        skills.remove(skill)
    return update_user_profile(user_id, {"skills": skills})


def add_location_preference(user_id: str, location: str) -> Optional[Dict]:
    """يضيف مدينة مفضلة."""
    profile = get_user_profile(user_id)
    if not profile:
        return None
    locs = profile.get("preferred_locations", [])
    if location not in locs:
        locs.append(location)
    return update_user_profile(user_id, {"preferred_locations": locs})


def remove_location_preference(user_id: str, location: str) -> Optional[Dict]:
    """يزيل مدينة مفضلة."""
    profile = get_user_profile(user_id)
    if not profile:
        return None
    locs = profile.get("preferred_locations", [])
    if location in locs:
        locs.remove(location)
    return update_user_profile(user_id, {"preferred_locations": locs})
