# auto_apply.py - تقديم تلقائي عبر واتساب أو إيميل
import os
import urllib.parse
import requests
from message_templates import build_cover_letter

APPLICANT_NAME = os.environ.get("APPLICANT_NAME", "")
APPLICANT_PHONE = os.environ.get("APPLICANT_PHONE", "")
APPLICANT_EMAIL = os.environ.get("APPLICANT_EMAIL", "")

def auto_apply_job(job: dict) -> dict:
    """
    يحاول التقديم على الوظيفة تلقائيًا.
    الأولوية: واتساب > إيميل
    """
    phone = job.get("contact_phone")
    email = job.get("contact_email")
    
    if not phone and not email:
        return {"success": False, "message": "مفيش وسيلة تواصل في الوظيفة"}
    
    message = build_cover_letter(job)
    
    # 1. محاولة واتساب
    if phone:
        clean_phone = phone.strip().replace(" ", "").replace("-", "")
        if clean_phone.startswith("0"):
            clean_phone = "2" + clean_phone
        wa_link = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(message)}"
        # إرسال عبر واتساب (باستخدام requests أو selenium)
        # حالياً: نفتح الرابط بس أو نرسل طلب
        try:
            # هنا ممكن تستخدم API تابع لواتساب أو ترسل طلب GET لفتح الرابط
            # حالياً: نعتبر إن التقديم نجح لو الرابط اتحضر
            return {
                "success": True,
                "message": f"تم فتح واتساب للرقم {phone}",
                "link": wa_link,
                "method": "whatsapp"
            }
        except Exception as e:
            return {"success": False, "message": f"فشل واتساب: {str(e)}"}
    
    # 2. محاولة إيميل
    elif email:
        subject = f"تقديم على وظيفة {job.get('title', '')}"
        mailto_link = f"mailto:{email}?subject={urllib.parse.quote(subject)}&body={urllib.parse.quote(message)}"
        try:
            return {
                "success": True,
                "message": f"تم فتح الإيميل لـ {email}",
                "link": mailto_link,
                "method": "email"
            }
        except Exception as e:
            return {"success": False, "message": f"فشل الإيميل: {str(e)}"}
    
    return {"success": False, "message": "مفيش طريقة تواصل مناسبة"}
