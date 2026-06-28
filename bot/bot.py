# bot/bot.py - نسخة شخصية (تدعم مستخدم واحد فقط + تقديم تلقائي)
import asyncio
import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from db import (
    get_unnotified_jobs, get_pending_jobs, get_jobs_by_status, get_job_by_id,
    search_jobs, get_stats, get_setting, set_setting, mark_notified, update_status,
    mark_applied, get_applied_jobs
)
from message_templates import build_cover_letter, build_whatsapp_link, build_mailto_link
from auto_apply import auto_apply_job

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # المستخدم الوحيد
NOTIFY_INTERVAL_SECONDS = int(os.environ.get("NOTIFY_INTERVAL_SECONDS", 3600))  # كل ساعة بدل 6

AUTO_APPLY_ENABLED = os.environ.get("AUTO_APPLY_ENABLED", "false").lower() == "true"
AUTO_APPLY_PHONE = os.environ.get("APPLICANT_PHONE", "")
AUTO_APPLY_EMAIL = os.environ.get("APPLICANT_EMAIL", "")
AUTO_APPLY_NAME = os.environ.get("APPLICANT_NAME", "")

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
        lines.append(f"🕒 {job['job_type']}")
    if job.get("source"):
        lines.append(f"🌐 المصدر: {job['source']}")
    # إضافة حالة التقديم لو موجودة
    if job.get("applied") == True:
        lines.append("✅ **تم التقديم عليها**")
    return "\n".join(lines)

def build_job_keyboard(job: dict, show_actions: bool = True) -> InlineKeyboardMarkup:
    buttons = [[InlineKeyboardButton("🔗 فتح الوظيفة", url=job["url"])]]
    
    # أزرار التواصل المباشر
    contact_row = []
    if job.get("contact_phone"):
        contact_row.append(InlineKeyboardButton("📩 واتساب", callback_data=f"prep_wa:{job['id']}"))
    if job.get("contact_email"):
        contact_row.append(InlineKeyboardButton("📧 إيميل", callback_data=f"prep_email:{job['id']}"))
    if contact_row:
        buttons.append(contact_row)
    
    # أزرار الإجراءات
    buttons.append([InlineKeyboardButton("📝 الرسالة الجاهزة", callback_data=f"letter:{job['id']}")])
    
    if show_actions:
        action_row = []
        if job.get("applied") != True:  # لو مش مقدم عليها
            action_row.append(InlineKeyboardButton("🎯 قدم تلقائيًا", callback_data=f"auto_apply:{job['id']}"))
        action_row.append(InlineKeyboardButton("💾 حفظ", callback_data=f"save:{job['id']}"))
        action_row.append(InlineKeyboardButton("🗑 تجاهل", callback_data=f"ignore:{job['id']}"))
        buttons.append(action_row)
    
    return InlineKeyboardMarkup(buttons)

async def send_jobs_digest(context, chat_id, jobs: list[dict], header: str):
    if not jobs:
        return
    lines = [header, ""]
    keyboard_rows = []
    for i, job in enumerate(jobs, start=1):
        exp = f" — {job['experience']}" if job.get("experience") else ""
        contact_mark = " 📞" if (job.get("contact_email") or job.get("contact_phone")) else ""
        src = f" [{job.get('source', '')}]" if job.get('source') else ""
        applied_mark = " ✅مقدم" if job.get("applied") else ""
        lines.append(f"{i}. {job['title']} | {job.get('company') or '-'}{exp}{contact_mark}{src}{applied_mark}")
        keyboard_rows.append([InlineKeyboardButton(f"📋 تفاصيل وظيفة {i}", callback_data=f"detail:{job['id']}")])
    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )

# ---------- الأوامر ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = str(update.effective_chat.id)
    if chat_id != TELEGRAM_CHAT_ID:
        await update.message.reply_text("⚠️ هذا البوت شخصي لمالكه فقط.")
        return
    
    await update.message.reply_text(
        "أهلاً! 👋\n"
        "البوت ده مخصص ليك أنت بس لجمع وظائف المحاسبة وتقديمها تلقائيًا.\n\n"
        f"chat_id: {chat_id}\n\n"
        "الأوامر المتاحة:\n"
        "/jobs — آخر الوظائف المتاحة\n"
        "/applied — الوظائف اللي اتم التقديم عليها\n"
        "/search كلمة — بحث في الوظائف\n"
        "/stats — إحصائيات\n"
        "/setcv — رفع ملف CV (PDF)\n"
        "/auto_on — تشغيل التقديم التلقائي\n"
        "/auto_off — إيقاف التقديم التلقائي\n"
        "/status — حالة البوت والإعدادات"
    )

async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    jobs = get_pending_jobs(limit=15)
    if not jobs:
        await update.message.reply_text("لا يوجد وظائف جديدة دلوقتي 🙏")
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f"📋 آخر الوظائف ({len(jobs)})")

async def applied_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    jobs = get_applied_jobs(limit=15)
    if not jobs:
        await update.message.reply_text("مفيش وظائف اتم التقديم عليها لسه.")
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, "📋 الوظائف اللي اتم التقديم عليها")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    if not context.args:
        await update.message.reply_text("اكتب كلمة البحث، مثل: /search محاسب أول")
        return
    keyword = " ".join(context.args)
    jobs = search_jobs(keyword, limit=10)
    if not jobs:
        await update.message.reply_text(f'مفيش نتايج لـ "{keyword}".')
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f'🔍 نتايج البحث عن "{keyword}"')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    s = get_stats()
    auto_status = "✅ مفعل" if AUTO_APPLY_ENABLED else "❌ غير مفعل"
    text = (
        f"📊 إحصائيات:\n"
        f"إجمالي الوظائف: {s['total']}\n"
        f"قيد الانتظار: {s['pending']}\n"
        f"مقدم عليها: {s['applied']}\n"
        f"محفوظة: {s['saved']}\n"
        f"فيها وسيلة تواصل: {s['with_contact']}\n"
        f"التقديم التلقائي: {auto_status}\n"
        "التوزيع حسب المصدر:\n"
    )
    for src, count in s.get('by_source', {}).items():
        text += f"  {src}: {count}\n"
    await update.message.reply_text(text)

async def setcv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    context.user_data["awaiting_cv"] = True
    await update.message.reply_text("📎 ابعتلي ملف الـ CV بصيغة PDF")

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    if not context.user_data.get("awaiting_cv"):
        return
    doc = update.message.document
    if not doc or doc.mime_type != "application/pdf":
        await update.message.reply_text("محتاج PDF بس 🙏")
        return
    file_id = doc.file_id
    set_setting("cv_file_id", file_id)
    context.user_data["awaiting_cv"] = False
    await update.message.reply_text("✅ تم حفظ الـ CV")

async def auto_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    if not AUTO_APPLY_PHONE or not AUTO_APPLY_NAME:
        await update.message.reply_text("⚠️ لازم تحدد APPLICANT_NAME و APPLICANT_PHONE في ملف .env")
        return
    # نكتب الإعداد في قاعدة البيانات بدل ما نعدل env
    set_setting("auto_apply_enabled", "true")
    await update.message.reply_text("✅ تم تشغيل التقديم التلقائي. البوت هيقدم على أي وظيفة فيها رقم واتساب تلقائيًا.")

async def auto_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    set_setting("auto_apply_enabled", "false")
    await update.message.reply_text("❌ تم إيقاف التقديم التلقائي.")

async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if str(update.effective_chat.id) != TELEGRAM_CHAT_ID:
        return
    cv_file_id = get_setting("cv_file_id")
    auto_enabled = get_setting("auto_apply_enabled") == "true"
    text = (
        "⚙️ حالة البوت:\n"
        f"CV: {'✅ موجود' if cv_file_id else '❌ غير مرفوع'}\n"
        f"تقديم تلقائي: {'✅ مفعل' if auto_enabled else '❌ غير مفعل'}\n"
        f"المستخدم: {APPLICANT_NAME or 'غير محدد'}\n"
        f"رقم واتساب: {APPLICANT_PHONE or 'غير محدد'}\n"
        f"الإيميل: {APPLICANT_EMAIL or 'غير محدد'}"
    )
    await update.message.reply_text(text)

# ---------- الأزرار ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    chat_id = str(update.effective_chat.id)
    if chat_id != TELEGRAM_CHAT_ID:
        await query.message.reply_text("⚠️ هذا البوت شخصي.")
        return
    
    action, job_id = query.data.split(":", 1)
    job = get_job_by_id(job_id)
    if not job:
        await query.message.reply_text("الوظيفة مش موجودة.")
        return

    if action == "detail":
        await query.message.reply_text(format_job_text(job), reply_markup=build_job_keyboard(job))
        return

    if action == "letter":
        await query.message.reply_text(build_cover_letter(job))
        return

    if action in ("prep_wa", "prep_email"):
        cv_file_id = get_setting("cv_file_id")
        if cv_file_id:
            await context.bot.send_document(chat_id, cv_file_id, caption="📎 الـ CV")
        if action == "prep_wa":
            link = build_whatsapp_link(job)
            label = "📩 فتح واتساب"
        else:
            link = build_mailto_link(job)
            label = "📧 فتح الإيميل"
        if not link:
            await query.message.reply_text("مفيش وسيلة تواصل مباشرة.")
            return
        await query.message.reply_text(build_cover_letter(job), reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(label, url=link)]]))
        return

    if action == "auto_apply":
        # تقديم تلقائي
        auto_enabled = get_setting("auto_apply_enabled") == "true"
        if not auto_enabled:
            await query.message.reply_text("⚠️ التقديم التلقائي غير مفعل. استخدم /auto_on")
            return
        if not job.get("contact_phone") and not job.get("contact_email"):
            await query.message.reply_text("⚠️ مفيش وسيلة تواصل في الوظيفة دي.")
            return
        
        result = auto_apply_job(job)
        if result.get("success"):
            mark_applied(job_id)
            await query.message.reply_text(f"✅ {result['message']}")
        else:
            await query.message.reply_text(f"❌ فشل التقديم: {result['message']}")
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

# ---------- الإشعار الدوري ----------
async def push_new_jobs(context: ContextTypes.DEFAULT_TYPE):
    if not TELEGRAM_CHAT_ID:
        return
    jobs = get_unnotified_jobs(limit=20)
    if not jobs:
        return
    try:
        # التقديم التلقائي للوظائف الجديدة
        auto_enabled = get_setting("auto_apply_enabled") == "true"
        if auto_enabled:
            for job in jobs:
                if (job.get("contact_phone") or job.get("contact_email")):
                    result = auto_apply_job(job)
                    if result.get("success"):
                        mark_applied(job["id"])
                        await context.bot.send_message(TELEGRAM_CHAT_ID, f"✅ تم التقديم على: {job['title']} - {job['company']}")
        
        # إرسال القائمة
        await send_jobs_digest(context, TELEGRAM_CHAT_ID, jobs, f"🆕 وظائف جديدة ({len(jobs)})")
        for job in jobs:
            if not job.get("applied"):
                mark_notified(job["id"])
    except Exception as e:
        logger.error(f"فشل الإشعار: {e}")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"⚠️ خطأ: {context.error}")

# ---------- التشغيل ----------
async def main():
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN مطلوب")
    app = Application.builder().token(BOT_TOKEN).build()
    await app.bot.delete_webhook()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jobs", jobs_command))
    app.add_handler(CommandHandler("applied", applied_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("setcv", setcv_command))
    app.add_handler(CommandHandler("auto_on", auto_on_command))
    app.add_handler(CommandHandler("auto_off", auto_off_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    
    app.job_queue.run_repeating(push_new_jobs, interval=NOTIFY_INTERVAL_SECONDS, first=15)
    logger.info("البوت شغال...")
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("تم الإيقاف")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
