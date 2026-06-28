import logging
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from db import (
    get_unnotified_jobs, get_pending_jobs, get_jobs_by_status, get_job_by_id,
    search_jobs, get_stats, get_setting, set_setting, mark_notified, update_status
)
from message_templates import build_cover_letter, build_whatsapp_link, build_mailto_link

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
NOTIFY_INTERVAL_SECONDS = int(os.environ.get("NOTIFY_INTERVAL_SECONDS", 6 * 60 * 60))

def format_job_text(job: dict) -> str:
    lines = [f"📌 {job['title']}"]
    if job.get("company"):
        lines.append(f"🏢 {job['company']}")
    if job.get("location"):
        lines.append(f"📍 {job['location']}")
    if job.get("experience"):
        lines.append(f"🎓 {job['experience']}")
    if job.get("posted"):
        lines.append(f"🕒 {job['posted']}")
    if job.get("source"):
        lines.append(f"🌐 المصدر: {job['source']}")
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
        exp = f" — {job['experience']}" if job.get('experience') else ""
        contact_mark = " 📞" if (job.get('contact_email') or job.get('contact_phone')) else ""
        src = f" [{job.get('source', '')}]" if job.get('source') else ""
        lines.append(f"{i}. {job['title']} | {job.get('company') or '-'}{exp}{contact_mark}{src}")
        keyboard_rows.append([InlineKeyboardButton(f"📋 تفاصيل وظيفة {i}", callback_data=f"detail:{job['id']}")])
    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )

# بقية دوال الأوامر والأزرار كما هي (start, jobs, search, saved, ignored, stats, setcv, button_handler, push_new_jobs)
# ... (نفس الكود القديم مع تغيير format_job_text في التفاصيل)
# ...

def main():
    if not BOT_TOKEN:
        raise RuntimeError("لازم تحدد BOT_TOKEN في متغيرات البيئة")
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("jobs", jobs_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("saved", saved_command))
    app.add_handler(CommandHandler("ignored", ignored_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("setcv", setcv_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    app.job_queue.run_repeating(push_new_jobs, interval=NOTIFY_INTERVAL_SECONDS, first=15)
    logger.info("البوت شغال...")
    app.run_polling()

if __name__ == "__main__":
    main()
