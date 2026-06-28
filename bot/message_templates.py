"""
توليد رسالة قصيرة مخصصة لكل وظيفة + روابط جاهزة للإرسال (واتساب / إيميل)
"""

import os
import urllib.parse

APPLICANT_NAME = os.environ.get("APPLICANT_NAME", "اسمك")
APPLICANT_PHONE = os.environ.get("APPLICANT_PHONE", "")
APPLICANT_EMAIL = os.environ.get("APPLICANT_EMAIL", "")
APPLICANT_SUMMARY = os.environ.get(
    "APPLICANT_SUMMARY", "محاسب بخبرة في القيد المزدوج والتسويات البنكية"
)


def build_cover_letter(job: dict) -> str:
    title = job.get("title", "الوظيفة")
    company = job.get("company") or "شركتكم"
    return (
        f"السلام عليكم،\n\n"
        f"بالإشارة لإعلانكم عن وظيفة {title} في {company}، "
        f"أتقدم لشغل هذا المنصب.\n\n"
        f"{APPLICANT_SUMMARY}\n\n"
        f"يسعدني إرسال السيرة الذاتية والتواصل معكم في أقرب وقت يناسبكم.\n\n"
        f"تحياتي،\n{APPLICANT_NAME}\n{APPLICANT_PHONE}\n{APPLICANT_EMAIL}"
    ).strip()


def build_whatsapp_link(job: dict) -> str | None:
    """لو لقينا رقم تليفون في وصف الوظيفة، نجهز رابط واتساب جاهز بالرسالة"""
    phone = job.get("contact_phone")
    if not phone:
        return None
    clean_phone = phone.strip().replace(" ", "").replace("-", "")
    if clean_phone.startswith("0"):
        clean_phone = "2" + clean_phone  # كود مصر
    text = urllib.parse.quote(build_cover_letter(job))
    return f"https://wa.me/{clean_phone}?text={text}"


def build_mailto_link(job: dict) -> str | None:
    """لو لقينا إيميل في وصف الوظيفة، نجهز رابط mailto جاهز"""
    email = job.get("contact_email")
    if not email:
        return None
    subject = urllib.parse.quote(f"تقديم على وظيفة {job.get('title', '')}")
    body = urllib.parse.quote(build_cover_letter(job))
    return f"mailto:{email}?subject={subject}&body={body}"
