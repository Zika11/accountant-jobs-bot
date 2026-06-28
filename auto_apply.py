# auto_apply.py
"""
تقديم تلقائي على الوظائف عبر واتساب
"""

import os
import re
import asyncio
import logging
from urllib.parse import quote
from message_templates import build_cover_letter

logger = logging.getLogger(__name__)

WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")


async def auto_apply_whatsapp(job: dict, bot, chat_id) -> dict:
    """
    يقوم بالتقديم على الوظيفة عبر واتساب
    - يرسل الـ CV
    - يرسل رسالة التقديم
    """
    try:
        phone = job.get("contact_phone")
        if not phone:
            return {"success": False, "error": "مفيش رقم واتساب"}
        
        # تنظيف الرقم
        clean_phone = re.sub(r"\D", "", phone)
        if clean_phone.startswith("0"):
            clean_phone = "2" + clean_phone[1:]
        elif clean_phone.startswith("20"):
            clean_phone = clean_phone
        
        # بناء رابط واتساب
        message = build_cover_letter(job)
        encoded_msg = quote(message)
        wa_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"
        
        # إرسال رابط واتساب للمستخدم عشان يضغط عليه
        await bot.send_message(
            chat_id=chat_id,
            text=f"🚀 جاهز للتقديم على {job['title']} في {job.get('company', '')}",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 افتح واتساب للتقديم", url=wa_link)
            ]])
        )
        
        # إرسال الـ CV
        cv_file_id = os.environ.get("CV_FILE_ID")
        if cv_file_id:
            await bot.send_document(
                chat_id=chat_id,
                document=cv_file_id,
                caption=f"📎 CV للتقديم على {job['title']}"
            )
        
        # تسجيل التقديم
        log_application(job["id"], "whatsapp", clean_phone)
        
        return {"success": True, "link": wa_link}
        
    except Exception as e:
        logger.error(f"❌ فشل التقديم التلقائي: {e}")
        return {"success": False, "error": str(e)}


def log_application(job_id: str, method: str, contact: str):
    """تسجيل عملية التقديم في قاعدة البيانات"""
    try:
        from db import update_status
        update_status(job_id, "applied")
        logger.info(f"✅ تم التقديم على {job_id} عبر {method} -> {contact}")
    except Exception as e:
        logger.error(f"❌ فشل تسجيل التقديم: {e}")
