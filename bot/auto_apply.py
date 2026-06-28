# bot/auto_apply.py
"""
تقديم تلقائي على الوظائف عبر واتساب
"""

import os
import re
import logging
from urllib.parse import quote

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from message_templates import build_cover_letter

logger = logging.getLogger(__name__)

# ==================== إعدادات ====================

WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")

# ==================== الدوال الرئيسية ====================

async def auto_apply_whatsapp(job: dict, bot, chat_id: int) -> dict:
    """
    التقديم على وظيفة عبر واتساب

    Args:
        job: بيانات الوظيفة (dict)
        bot: كائن البوت
        chat_id: معرف المحادثة

    Returns:
        dict: {"success": bool, "error": str, "link": str}
    """
    try:
        # 1. التحقق من وجود رقم
        phone = job.get("contact_phone")
        if not phone:
            return {"success": False, "error": "مفيش رقم واتساب في الوظيفة"}

        # 2. تنظيف الرقم
        clean_phone = clean_phone_number(phone)
        if not clean_phone:
            return {"success": False, "error": "رقم غير صالح"}

        # 3. بناء الرسالة
        message = build_cover_letter(job)
        if not message:
            return {"success": False, "error": "مفيش رسالة جاهزة"}

        # 4. بناء الرابط
        encoded_msg = quote(message)
        wa_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"

        # 5. إرسال رابط واتساب للمستخدم
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🚀 <b>جاهز للتقديم على:</b>\n"
                f"📌 {job['title']}\n"
                f"🏢 {job.get('company', 'غير محدد')}\n\n"
                f"📱 اضغط على الزر لفتح واتساب وإرسال الرسالة:"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 فتح واتساب", url=wa_link)
            ]]),
            parse_mode="HTML"
        )

        # 6. إرسال الـ CV لو موجود
        cv_file_id = get_cv_file_id()
        if cv_file_id:
            await bot.send_document(
                chat_id=chat_id,
                document=cv_file_id,
                caption=f"📎 الـ CV الخاص بك - للتقديم على {job['title']}"
            )

        # 7. تسجيل التقديم
        from db import update_status
        update_status(job["id"], "applied")
        logger.info(f"✅ تم التقديم على {job['title']} عبر واتساب: {clean_phone}")

        return {"success": True, "link": wa_link}

    except Exception as e:
        logger.error(f"❌ فشل التقديم التلقائي: {e}")
        return {"success": False, "error": str(e)}


# ==================== دوال مساعدة ====================

def clean_phone_number(phone: str) -> str:
    """
    تنظيف رقم الهاتف للتنسيق الدولي
    """
    if not phone:
        return ""

    # إزالة كل ما ليس رقم
    clean = re.sub(r"\D", "", phone)

    # التأكد من أن الرقم 11 رقم (رقم مصري)
    if len(clean) == 11 and clean.startswith("0"):
        # 01012345678 → 201012345678
        return "2" + clean[1:]

    if len(clean) == 12 and clean.startswith("20"):
        # 201012345678 → 201012345678
        return clean

    if len(clean) == 10:
        # 1012345678 → 201012345678
        return "20" + clean

    return clean


def get_cv_file_id() -> str:
    """
    جلب معرف ملف الـ CV من الإعدادات
    """
    try:
        from db import get_setting
        return get_setting("cv_file_id") or os.environ.get("CV_FILE_ID", "")
    except Exception as e:
        logger.error(f"❌ فشل جلب CV: {e}")
        return os.environ.get("CV_FILE_ID", "")
