# bot/bot.py
"""
بوت تليجرام لتقديم الوظائف تلقائياً (شخصي)
"""

import asyncio
import logging
import os
import time
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from db import (
    get_unnotified_jobs,
    get_pending_jobs,
    get_jobs_by_status,
    get_job_by_id,
    search_jobs,
    get_stats,
    get_setting,
    set_setting,
    mark_notified,
    update_status,
    upsert_user_profile,
    get_user_profile,
)
from message_templates import build_cover_letter, build_whatsapp_link, build_mailto_link
from auto_apply import auto_apply_whatsapp

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ALLOWED_USER_IDS = os.environ.get("ALLOWED_USER_IDS", "").split(",")
AUTO_APPLY_ENABLED = os.environ.get("AUTO_APPLY_ENABLED", "false").lower() == "true"
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")

NOTIFY_INTERVAL_SECONDS = int(os.environ.get("NOTIFY_INTERVAL_SECONDS", 6 * 60 * 60))


# ---------- التحقق من المستخدم ----------
def is_allowed_user(user_id: int) -> bool:
    return str(user_id) in ALLOWED_USER_IDS


# ---------- عرض الوظيفة ----------
def format_job_text(job: dict) -> str:
    lines = [f"📌 {job['title']}"]
    if job.get("company"):
        lines.append(f"🏢 {job['company']}")
    if job.get("location"):
        lines.append(f"📍 {job['location']}")
    if job.get("experience"):
        lines.append(f"🎓 {job['experience']}")
    if job.get("salary_min") or job.get("salary_max"):
        salary = f"{job.get('salary_min', '')} - {job.get('salary_max', '')}".strip(" -")
        lines.append(f"💰 {salary} جنيه")
    if job.get("job_type"):
        lines.append(f"💼 {job['job_type']}")
    if job.get("posted"):
        lines.append(f"🕒 {job['posted']}")
    if job.get("source"):
        lines.append(f"🌐 المصدر: {job['source']}")
    if job.get("auto_applied"):
        lines.append("✅ تم التقديم تلقائياً")
    return "\n".join(lines)


def build_job_keyboard(job: dict, show_actions: bool = True) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("🔗 فتح الوظيفة", url=job["url"])]]
    
    contact_row = []
    if job.get("contact_phone"):
        contact_row.append(InlineKeyboardButton("📩 واتساب", callback_data=f"prep_wa:{job['id']}"))
    if job.get("contact_email"):
        contact_row.append(InlineKeyboardButton("📧 إيميل", callback_data=f"prep_email:{job['id']}"))
    if contact_row:
        buttons.append(contact_row)
    
    if AUTO_APPLY_ENABLED and job.get("contact_phone"):
        buttons.append([InlineKeyboardButton("🚀 تقديم تلقائي", callback_data=f"auto_apply:{job['id']}")])
    
    buttons.append([InlineKeyboardButton("📝 الرسالة الجاهزة", callback_data=f"letter:{job['id']}")])
    
    if show_actions:
        buttons.append([
            InlineKeyboardButton("💾 حفظ", callback_data=f"save:{job['id']}"),
            InlineKeyboardButton("🗑 تجاهل", callback_data=f"ignore:{job['id']}"),
        ])
    return InlineKeyboardMarkup(buttons)


async def send_jobs_digest(context: ContextTypes.DEFAULT_TYPE, chat_id, jobs: list[dict], header: str):
    lines = [header, ""]
    keyboard_rows = []
    for i, job in enumerate(jobs, start=1):
        exp = f" — {job['experience']}" if job.get("experience") else ""
        contact_mark = " 📞" if (job.get("contact_email") or job.get("contact_phone")) else ""
        src = f" [{job.get('source', '')}]" if job.get('source') else ""
        auto_mark = " 🤖" if job.get("auto_applied") else ""
        lines.append(f"{i}. {job['title']} | {job.get('company') or '-'}{exp}{contact_mark}{src}{auto_mark}")
        keyboard_rows.append([InlineKeyboardButton(f"📋 تفاصيل {i}", callback_data=f"detail:{job['id']}")])
    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


# ---------- الأوامر ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ هذا البوت للاستخدام الشخصي فقط.")
        return
    
    logger.info(f"📩 استلمت /start من: {chat_id} (user_id: {user_id})")
    
    upsert_user_profile(str(user_id), {
        "name": update.effective_user.full_name or "أحمد",
        "chat_id": str(chat_id),
        "phone": os.environ.get("APPLICANT_PHONE", ""),
        "email": os.environ.get("APPLICANT_EMAIL", ""),
    })
    
    await update.message.reply_text(
        "أهلاً أحمد! 👋\n"
        "البوت جاهز للتقديم على وظائف المحاسبة.\n\n"
        "⚙️ الإعدادات الحالية:\n"
        f"🤖 التقديم التلقائي: {'✅ مفعل' if AUTO_APPLY_ENABLED else '❌ معطل'}\n"
        f"📱 رقم واتساب: {WHATSAPP_NUMBER}\n\n"
        "📌 الأوامر المتاحة:\n"
        "/jobs — عرض الوظائف الجديدة\n"
        "/search كلمة — بحث في الوظائف\n"
        "/saved — الوظائف المحفوظة\n"
        "/stats — إحصائيات\n"
        "/setcv — رفع ملف CV (PDF)\n"
        "/profile — عرض ملفك الشخصي\n"
        "/auto_on — تشغيل التقديم التلقائي\n"
        "/auto_off — إيقاف التقديم التلقائي"
    )


async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    
    jobs = get_pending_jobs(limit=15)
    if not jobs:
        await update.message.reply_text("لا يوجد وظائف جديدة دلوقتي 🙏")
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f"📋 آخر الوظائف ({len(jobs)}):")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    
    if not context.args:
        await update.message.reply_text("اكتب كلمة البحث، مثلاً:\n/search محاسب أول")
        return
    keyword = " ".join(context.args)
    jobs = search_jobs(keyword, limit=10)
    if not jobs:
        await update.message.reply_text(f'مفيش نتايج لـ "{keyword}".')
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f'🔍 نتايج "{keyword}":')


async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    jobs = get_jobs_by_status("saved", limit=15)
    if not jobs:
        await update.message.reply_text("مفيش وظائف محفوظة.")
        return
    for job in jobs:
        await update.message.reply_text(
            format_job_text(job), reply_markup=build_job_keyboard(job, show_actions=False)
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    s = get_stats()
    text = (
        "📊 إحصائيات:\n"
        f"📌 إجمالي الوظائف: {s['total']}\n"
        f"⏳ قيد الانتظار: {s['pending']}\n"
        f"💾 محفوظة: {s['saved']}\n"
        f"🗑 متجاهلة: {s['ignored']}\n"
        f"✅ تم التقديم: {s.get('applied', 0)}\n"
        f"📞 فيها وسيلة تواصل: {s['with_contact']}\n"
    )
    await update.message.reply_text(text)


async def setcv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    context.user_data["awaiting_cv"] = True
    await update.message.reply_text("📎 ابعتلي ملف الـ CV بصيغة PDF")


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    if not context.user_data.get("awaiting_cv"):
        return
    doc = update.message.document
    if not doc or doc.mime_type != "application/pdf":
        await update.message.reply_text("محتاج ملف PDF بس 🙏")
        return
    file_id = doc.file_id
    set_setting("cv_file_id", file_id)
    upsert_user_profile(str(user_id), {"cv_file_id": file_id})
    context.user_data["awaiting_cv"] = False
    await update.message.reply_text("✅ تم حفظ الـ CV")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not is_allowed_user(int(user_id)):
        return
    profile = get_user_profile(user_id)
    if not profile:
        await update.message.reply_text("مفيش ملف شخصي. استخدم /start")
        return
    text = (
        "👤 ملفك الشخصي:\n"
        f"الاسم: {profile.get('name', 'غير محدد')}\n"
        f"الخبرة: {profile.get('experience_years', 0)} سنوات\n"
        f"المهارات: {', '.join(profile.get('skills', [])) or 'لا يوجد'}\n"
        f"المناطق: {', '.join(profile.get('preferred_locations', [])) or 'لا يوجد'}\n"
        f"الراتب المتوقع: {profile.get('expected_salary', 'غير محدد')}\n"
        f"📱 الهاتف: {profile.get('phone', 'غير محدد')}\n"
        f"📧 الإيميل: {profile.get('email', 'غير محدد')}\n"
        f"CV: {'✅ موجود' if profile.get('cv_file_id') else '❌ غير مرفوع'}"
    )
    await update.message.reply_text(text)


async def auto_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    upsert_user_profile(str(user_id), {"auto_apply": True})
    await update.message.reply_text("✅ تم تشغيل التقديم التلقائي")


async def auto_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        return
    upsert_user_profile(str(user_id), {"auto_apply": False})
    await update.message.reply_text("❌ تم إيقاف التقديم التلقائي")


# ---------- الأزرار ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح")
        return
    
    query = update.callback_query
    await query.answer()
    action, job_id = query.data.split(":", 1)

    if action == "detail":
        job = get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("الوظيفة مش موجودة.")
            return
        await query.message.reply_text(
            format_job_text(job), reply_markup=build_job_keyboard(job)
        )
        return

    if action == "auto_apply":
        job = get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("الوظيفة مش موجودة.")
            return
        
        if not job.get("contact_phone"):
            await query.message.reply_text("مفيش رقم واتساب للتقديم.")
            return
        
        result = await auto_apply_whatsapp(job, context.bot, query.message.chat_id)
        
        if result["success"]:
            update_status(job_id, "applied")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ تم التقديم على {job['title']} بنجاح!")
        else:
            await query.message.reply_text(f"❌ فشل التقديم: {result['error']}")
        return

    if action == "letter":
        job = get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("مش لاقي تفاصيل الوظيفة.")
            return
        await query.message.reply_text(build_cover_letter(job))
        return

    if action in ("prep_wa", "prep_email"):
        job = get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("الوظيفة مش موجودة.")
            return

        cv_file_id = get_setting("cv_file_id")
        if cv_file_id:
            await context.bot.send_document(
                chat_id=query.message.chat_id, document=cv_file_id, caption="📎 الـ CV"
            )

        if action == "prep_wa":
            link = build_whatsapp_link(job)
            label = "📩 فتح واتساب"
        else:
            link = build_mailto_link(job)
            label = "📧 فتح الإيميل"

        if not link:
            await query.message.reply_text("مفيش وسيلة تواصل.")
            return

        await query.message.reply_text(
            build_cover_letter(job),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(label, url=link)]]),
        )
        return

    if action == "save":
        update_status(job_id, "saved")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("💾 تم الحفظ.")
        return

    if action == "ignore":
        update_status(job_id, "ignored")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("🗑 تم التجاهل.")
        return


# ---------- الإشعار الدوري مع التقديم التلقائي ----------
async def push_new_jobs(context: ContextTypes.DEFAULT_TYPE):
    if not ALLOWED_USER_IDS:
        return
    
    for user_id in ALLOWED_USER_IDS:
        profile = get_user_profile(user_id)
        if not profile:
            continue
        
        chat_id = profile.get("chat_id")
        if not chat_id:
            continue
        
        auto_apply_enabled = profile.get("auto_apply", AUTO_APPLY_ENABLED)
        jobs = get_unnotified_jobs(limit=20)
        
        if not jobs:
            continue
        
        if auto_apply_enabled:
            for job in jobs:
                if job.get("contact_phone") and not job.get("auto_applied"):
                    result = await auto_apply_whatsapp(job, context.bot, chat_id)
                    if result["success"]:
                        update_status(job["id"], "applied")
                        mark_notified(job["id"])
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ تم التقديم تلقائياً على: {job['title']} - {job['company']}"
                        )
                    else:
                        logger.error(f"فشل التقديم على {job['title']}: {result['error']}")
        
        await send_jobs_digest(context, chat_id, jobs, f"🆕 وظائف جديدة ({len(jobs)}):")
        for job in jobs:
            if not job.get("auto_applied"):
                mark_notified(job["id"])


# ---------- معالج الأخطاء ----------
async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"⚠️ خطأ: {context.error}")


# ---------- التشغيل ----------
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN مطلوب")
    
    if not ALLOWED_USER_IDS or not ALLOWED_USER_IDS[0]:
        logger.warning("⚠️ ALLOWED_USER_IDS غير محدد - البوت مش هيشتغل لأي حد")
        return

    app = Application.builder().token(BOT_TOKEN).build()
    
    # حذف أي Webhook قديم
    await app.bot.delete_webhook()
    
    # إضافة معالجات
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jobs", jobs_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("saved", saved_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("setcv", setcv_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("auto_on", auto_on_command))
    app.add_handler(CommandHandler("auto_off", auto_off_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    # جدولة المهام
    app.job_queue.run_repeating(push_new_jobs, interval=NOTIFY_INTERVAL_SECONDS, first=15)

    logger.info(f"🤖 البوت شغال للمستخدم: {ALLOWED_USER_IDS[0]}")
    
    # بدء التطبيق
    await app.initialize()
    await app.start()
    
    # ✅ حل مشكلة Conflict: انتظر قليلاً ثم ابدأ polling مع تجاهل التحديثات المعلقة
    await asyncio.sleep(1)  # تأخير بسيط للتأكد من أن webhook محذوف تماماً
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=[],
        bootstrap_retries=-1,
    )
    
    # الانتظار حتى الإيقاف
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("تم إيقاف البوت")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
