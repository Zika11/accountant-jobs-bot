# bot/message_templates.py
"""
توليد رسائل جاهزة للتقديم على الوظائف
"""

import os
import urllib.parse

# ==================== بيانات مقدم الطلب ====================
APPLICANT_NAME = os.environ.get("APPLICANT_NAME", "اسمك")
APPLICANT_PHONE = os.environ.get("APPLICANT_PHONE", "")
APPLICANT_EMAIL = os.environ.get("APPLICANT_EMAIL", "")
APPLICANT_SUMMARY = os.environ.get(
    "APPLICANT_SUMMARY",
    "محاسب بخبرة في القيد المزدوج والتسويات البنكية وإعداد القوائم المالية."
)


def build_cover_letter(job: dict) -> str:
    """
    بناء رسالة تقديم مخصصة للوظيفة
    """
    title = job.get("title", "الوظيفة المعلنة")
    company = job.get("company") or "شركتكم الموقرة"

    # إضافة تفاصيل إضافية لو موجودة
    details = ""
    if job.get("experience"):
        details += f"\n- الخبرة المطلوبة: {job['experience']}"
    if job.get("location"):
        details += f"\n- الموقع: {job['location']}"

    # بناء الرسالة
    message = f"""السلام عليكم ورحمة الله وبركاته،

بالإشارة إلى إعلانكم عن وظيفة "{title}" في {company}، يسرني التقدم لهذا المنصب.

{APPLICANT_SUMMARY}

تفاصيلي الشخصية:{details}
- الاسم: {APPLICANT_NAME}
- الهاتف: {APPLICANT_PHONE}
- البريد الإلكتروني: {APPLICANT_EMAIL}

أرفق لكم سيرتي الذاتية، وآمل أن تنال إعجابكم. أنا على استعداد للمقابلة في أي وقت يناسبكم.

شاكراً حسن تعاونكم،
{APPLICANT_NAME}"""

    return message.strip()


def build_whatsapp_link(job: dict) -> str | None:
    """
    بناء رابط واتساب جاهز بالرسالة
    """
    phone = job.get("contact_phone")
    if not phone:
        return None

    # تنظيف الرقم
    import re
    clean_phone = re.sub(r"\D", "", phone)
    if clean_phone.startswith("0"):
        clean_phone = "20" + clean_phone[1:]

    text = urllib.parse.quote(build_cover_letter(job))
    return f"https://wa.me/{clean_phone}?text={text}"


def build_mailto_link(job: dict) -> str | None:
    """
    بناء رابط إيميل جاهز بالرسالة
    """
    email = job.get("contact_email")
    if not email:
        return None

    subject = urllib.parse.quote(f"تقديم على وظيفة {job.get('title', '')}")
    body = urllib.parse.quote(build_cover_letter(job))
    return f"mailto:{email}?subject={subject}&body={body}"
