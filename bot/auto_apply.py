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

# رقم واتساب الاحتياطي من البيئة (يُستخدم فقط لو الوظيفة مفيهاش رقم)
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")


def clean_phone_number(phone: str) -> str:
    """
    تنظيف رقم الهاتف وتحويله إلى صيغة دولية (مصر)
    مثال: 01091882926 -> 201091882926
    """
    if not phone:
        return ""

    # إزالة كل ما هو ليس رقم
    digits = re.sub(r"\D", "", phone)

    # إذا كان الرقم فارغاً
    if not digits:
        return ""

    # إذا كان الرقم يبدأ بـ 0 (مثل 010...)، نحذف الـ 0 ونضيف 20
    if digits.startswith("0"):
        digits = "20" + digits[1:]

    # إذا كان الرقم يبدأ بـ 20، نتركه كما هو (دولي)
    elif digits.startswith("20"):
        pass

    # إذا كان الرقم يبدأ بـ 2 (مثل 2010...)، نضيف 0 في البداية (نادر)
    elif digits.startswith("2") and not digits.startswith("20"):
        digits = "20" + digits

    # إذا كان الرقم يبدأ بـ 1 (مثل 1091882926)، نضيف 20
    elif digits.startswith("1"):
        digits = "20" + digits

    # إذا كان الرقم طويلاً (12 رقم)، نأخذ آخر 11 رقم
    if len(digits) > 12:
        digits = digits[-11:]

    return digits


async def auto_apply_whatsapp(job: dict, bot, chat_id: int) -> dict:
    """
    يقوم بالتقديم على الوظيفة عبر واتساب:
    - يبعت رابط واتساب جاهز بالرسالة
    - يبعت الـ CV (لو موجود)
    - يسجل التقديم في قاعدة البيانات
    """
    try:
        # الحصول على رقم الهاتف من الوظيفة
        phone = job.get("contact_phone") or WHATSAPP_NUMBER

        if not phone:
            return {"success": False, "error": "مفيش رقم واتساب في الوظيفة"}

        # تنظيف الرقم
        clean_phone = clean_phone_number(phone)
        if not clean_phone:
            return {"success": False, "error": "رقم الهاتف غير صالح"}

        # بناء رسالة التقديم
        message = build_cover_letter(job)
        encoded_msg = quote(message)
        wa_link = f"https://wa.me/{clean_phone}?text={encoded_msg}"

        # إرسال رابط واتساب للمستخدم
        await bot.send_message(
            chat_id=chat_id,
            text=(
                f"🚀 جاهز للتقديم على **{job['title']}** في {job.get('company', 'شركة')}\n\n"
                f"📱 اضغط على الزر لفتح واتساب وإرسال الرسالة:"
            ),
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("📱 فتح واتساب", url=wa_link)
            ]]),
            parse_mode="Markdown"
        )

        # إرسال الـ CV لو موجود
        cv_file_id = os.environ.get("CV_FILE_ID")
        if not cv_file_id:
            # جلب من قاعدة البيانات
            try:
                from db import get_setting
                cv_file_id = get_setting("cv_file_id")
            except:
                pass

        if cv_file_id:
            await bot.send_document(
                chat_id=chat_id,
                document=cv_file_id,
                caption=f"📎 الـ CV الخاص بك - للتقديم على {job['title']}"
            )

        # تحديث الحالة في قاعدة البيانات (مرة واحدة فقط)
        try:
            from db import update_status
            update_status(job["id"], "applied")
        except Exception as e:
            logger.error(f"⚠️ فشل تحديث الحالة: {e}")

        logger.info(f"✅ تم التقديم على {job['title']} عبر واتساب: {clean_phone}")
        return {"success": True, "link": wa_link}

    except Exception as e:
        logger.error(f"❌ فشل التقديم التلقائي: {e}")
        return {"success": False, "error": str(e)}
