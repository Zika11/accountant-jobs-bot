# bot/auto_apply.py
"""
تقديم تلقائي على الوظائف عبر واتساب
"""

import os
import re
import logging
from urllib.parse import quote
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# جلب رقم واتساب من متغيرات البيئة
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")


async def auto_apply_whatsapp(job: dict, bot, chat_id: int) -> dict:
    """
    يقوم بالتقديم على الوظيفة عبر واتساب:
    - يبعت رابط واتساب جاهز بالرسالة
    - يبعت الـ CV (لو موجود)
    - يسجل التقديم في قاعدة البيانات
    """
    try:
        phone = job.get("contact_phone")
        if not phone:
            return {"success": False, "error": "مفيش رقم واتساب في الوظيفة"}

        # تنظيف الرقم
        clean_phone = re.sub(r"\D", "", phone)
        if clean_phone.startswith("0"):
            clean_phone = "2" + clean_phone[1:]
        elif clean_phone.startswith("20"):
            clean_phone = clean_phone
        else:
            # لو الرقم مصري وبدأ بـ 010 مثلاً
            if len(clean_phone) == 11 and clean_phone.startswith("010"):
                clean_phone = "20" + clean_phone[1:]
            elif len(clean_phone) == 11 and clean_phone.startswith("011"):
                clean_phone = "20" + clean_phone[1:]

        # بناء رسالة التقديم
        from message_templates import build_cover_letter
        message = build_cover_letter(job)
        encoded_msg = quote(message)
        wa_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"

        # إرسال رابط واتساب للمستخدم
        await bot.send_message(
            chat_id=chat_id,
            text=f"🚀 جاهز للتقديم على **{job['title']}** في {job.get('company', '')}\n\n"
                 f"📱 اضغط على الزر لفتح واتساب وإرسال الرسالة:",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 افتح واتساب", url=wa_link)
            ]]),
            parse_mode="Markdown"
        )

        # إرسال الـ CV لو موجود
        cv_file_id = os.environ.get("CV_FILE_ID")
        if not cv_file_id:
            # جلب من قاعدة البيانات
            from db import get_setting
            cv_file_id = get_setting("cv_file_id")

        if cv_file_id:
            await bot.send_document(
                chat_id=chat_id,
                document=cv_file_id,
                caption=f"📎 الـ CV الخاص بك - للتقديم على {job['title']}"
            )

        # تسجيل التقديم في قاعدة البيانات (تحديث الحالة)
        from db import update_status
        update_status(job["id"], "applied")
        logger.info(f"✅ تم التقديم على {job['title']} عبر واتساب: {clean_phone}")

        return {"success": True, "link": wa_link}

    except Exception as e:
        logger.error(f"❌ فشل التقديم التلقائي: {e}")
        return {"success": False, "error": str(e)}
