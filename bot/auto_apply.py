# bot/auto_apply.py
"""
تقديم تلقائي على الوظائف عبر واتساب (مساعد للمستخدم، لا يرسل تلقائياً)
"""

import os
import re
import logging
from urllib.parse import quote
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

# جلب رقم واتساب الاحتياطي من متغيرات البيئة (يستخدم لو مفيش رقم في الوظيفة)
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")


async def auto_apply_whatsapp(job: dict, bot, chat_id: int) -> dict:
    """
    يقوم بتجهيز رابط واتساب جاهز للتقديم على الوظيفة:
    - يبعت رابط واتساب جاهز بالرسالة
    - يبعت الـ CV (لو موجود)
    - يسجل التقديم في قاعدة البيانات (يتم التحديث من خارج الدالة)
    """
    try:
        phone = job.get("contact_phone")
        if not phone:
            # استخدام رقم احتياطي من env
            if WHATSAPP_NUMBER:
                phone = WHATSAPP_NUMBER
                logger.info(f"⚠️ استخدام رقم احتياطي: {phone}")
            else:
                return {"success": False, "error": "مفيش رقم واتساب في الوظيفة"}

        # تنظيف الرقم (إزالة كل ما ليس رقماً)
        clean_phone = re.sub(r"\D", "", phone)

        # تحويل الرقم إلى صيغة دولية (مصر)
        if clean_phone.startswith("0"):
            # 01012345678 → 201012345678
            clean_phone = "20" + clean_phone[1:]
        elif clean_phone.startswith("20"):
            # 201012345678 → 201012345678 (كما هو)
            pass
        else:
            # لو بدأ بأي شيء آخر، نعتبره مصري ونضيف 20
            if len(clean_phone) == 11 and clean_phone.startswith("10"):
                clean_phone = "20" + clean_phone
            elif len(clean_phone) == 10 and clean_phone.startswith("1"):
                clean_phone = "20" + clean_phone
            else:
                clean_phone = "20" + clean_phone

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
            from db import get_setting
            cv_file_id = get_setting("cv_file_id")

        if cv_file_id:
            await bot.send_document(
                chat_id=chat_id,
                document=cv_file_id,
                caption=f"📎 الـ CV الخاص بك - للتقديم على {job['title']}"
            )

        logger.info(f"✅ تم تجهيز التقديم على {job['title']} عبر واتساب: {clean_phone}")

        return {"success": True, "link": wa_link}

    except Exception as e:
        logger.error(f"❌ فشل التقديم التلقائي: {e}")
        return {"success": False, "error": str(e)}
