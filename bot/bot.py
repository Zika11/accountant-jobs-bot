"""
بوت تليجرام لمتابعة وظائف المحاسبة

الأوامر:
- /start    تسجيل + يطلعلك chat_id بتاعك
- /jobs     آخر الوظائف المتاحة (رسالة واحدة مجمّعة + تفاصيل عند الطلب)
- /search   بحث بكلمة معينة، مثلاً: /search محاسب أول
- /saved    الوظائف المحفوظة
- /ignored  الوظائف المتجاهلة
- /stats    إحصائيات عامة
- /setcv    حفظ ملف CV (PDF) عشان يتبعت جنب كل رسالة تقديم

كل وظيفة بتظهر بأزرار: فتح الوظيفة / تجهيز واتساب / تجهيز إيميل / رسالة جاهزة / حفظ / تجاهل
كل فترة (NOTIFY_INTERVAL_SECONDS) البوت يبعت رسالة واحدة مجمّعة بأي وظيفة جديدة.
"""

import logging
import os

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
)
from message_templates import build_cover_letter, build_whatsapp_link, build_mailto_link

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")  # نحطه بعد أول /start
NOTIFY_INTERVAL_SECONDS = int(os.environ.get("NOTIFY_INTERVAL_SECONDS", 6 * 60 * 60))


# ---------- عرض الوظيفة ----------

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
    """رسالة واحدة فيها كل الوظائف، وكل وظيفة بزرار 'تفاصيل' يفتح كارتها كاملة"""
    lines = [header, ""]
    keyboard_rows = []
    for i, job in enumerate(jobs, start=1):
        exp = f" — {job['experience']}" if job.get("experience") else ""
        contact_mark = " 📞" if (job.get("contact_email") or job.get("contact_phone")) else ""
        lines.append(f"{i}. {job['title']} | {job.get('company') or '-'}{exp}{contact_mark}")
        keyboard_rows.append([InlineKeyboardButton(f"📋 تفاصيل وظيفة {i}", callback_data=f"detail:{job['id']}")])

    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


# ---------- الأوامر ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    logger.info(f"📩 استلمت /start من: {chat_id}")
    await update.message.reply_text(
        "أهلاً! 👋\n"
        "البوت ده هيبعتلك وظائف محاسبة جديدة بشكل دوري.\n\n"
        f"chat_id بتاعك هو: {chat_id}\n"
        "لو دي أول مرة، خد الرقم ده وحطه في متغير TELEGRAM_CHAT_ID في الـ Railway "
        "عشان البوت يعرف يبعتلك تلقائيًا، وبعدين أعمل Redeploy.\n\n"
        "الأوامر المتاحة:\n"
        "/jobs — آخر الوظائف المتاحة\n"
        "/search كلمة — بحث في الوظائف\n"
        "/saved — الوظائف المحفوظة\n"
        "/ignored — الوظائف المتجاهلة\n"
        "/stats — إحصائيات عامة\n"
        "/setcv — حفظ ملف CV عشان يتبعت جنب كل رسالة"
    )


async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_pending_jobs(limit=15)
    if not jobs:
        await update.message.reply_text("لا يوجد وظائف جديدة دلوقتي. حاول تاني بعد قليل 🙏")
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f"📋 آخر الوظائف المتاحة ({len(jobs)}):")


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("اكتب كلمة البحث بعد الأمر، مثلاً:\n/search محاسب أول")
        return
    keyword = " ".join(context.args)
    jobs = search_jobs(keyword, limit=10)
    if not jobs:
        await update.message.reply_text(f'مفيش نتايج لكلمة البحث "{keyword}".')
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f'🔍 نتايج البحث عن "{keyword}":')


async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs_by_status("saved", limit=15)
    if not jobs:
        await update.message.reply_text("لسه مفيش وظائف محفوظة.")
        return
    for job in jobs:
        await update.message.reply_text(
            format_job_text(job), reply_markup=build_job_keyboard(job, show_actions=False)
        )


async def ignored_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    jobs = get_jobs_by_status("ignored", limit=15)
    if not jobs:
        await update.message.reply_text("لسه مفيش وظائف متجاهلة.")
        return
    for job in jobs:
        await update.message.reply_text(
            format_job_text(job), reply_markup=build_job_keyboard(job, show_actions=False)
        )


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    s = get_stats()
    text = (
        "📊 إحصائيات:\n"
        f"إجمالي الوظائف: {s['total']}\n"
        f"قيد الانتظار: {s['pending']}\n"
        f"محفوظة: {s['saved']}\n"
        f"متجاهلة: {s['ignored']}\n"
        f"منتهية: {s['expired']}\n"
        f"فيها وسيلة تواصل مباشرة: {s['with_contact']}"
    )
    await update.message.reply_text(text)


async def setcv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["awaiting_cv"] = True
    await update.message.reply_text("تمام، ابعتلي ملف الـ CV بصيغة PDF دلوقتي 📎")


async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get("awaiting_cv"):
        return
    doc = update.message.document
    if not doc or doc.mime_type != "application/pdf":
        await update.message.reply_text("محتاج ملف PDF بس 🙏 جرب تاني.")
        return
    set_setting("cv_file_id", doc.file_id)
    context.user_data["awaiting_cv"] = False
    await update.message.reply_text("✅ تم حفظ الـ CV، هبعته لك جنب كل رسالة تقديم.")


# ---------- الأزرار ----------

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    action, job_id = query.data.split(":", 1)

    if action == "detail":
        job = get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("معلش، الوظيفة دي مش موجودة دلوقتي.")
            return
        await query.message.reply_text(
            format_job_text(job), reply_markup=build_job_keyboard(job)
        )
        return

    if action == "letter":
        job = get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("معلش، مش لاقي تفاصيل الوظيفة دي.")
            return
        await query.message.reply_text(build_cover_letter(job))
        return

    if action in ("prep_wa", "prep_email"):
        job = get_job_by_id(job_id)
        if not job:
            await query.message.reply_text("معلش، الوظيفة دي مش موجودة دلوقتي.")
            return

        cv_file_id = get_setting("cv_file_id")
        if cv_file_id:
            await context.bot.send_document(
                chat_id=query.message.chat_id, document=cv_file_id, caption="📎 الـ CV بتاعك - جاهز ترفقه"
            )

        if action == "prep_wa":
            link = build_whatsapp_link(job)
            label = "📩 فتح واتساب"
        else:
            link = build_mailto_link(job)
            label = "📧 فتح الإيميل"

        if not link:
            await query.message.reply_text("معلش، الوظيفة دي مفيهاش وسيلة تواصل مباشرة.")
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


# ---------- الإشعار الدوري ----------

async def push_new_jobs(context: ContextTypes.DEFAULT_TYPE):
    if not TELEGRAM_CHAT_ID:
        logger.warning("TELEGRAM_CHAT_ID لسه مش متحدد - مش هقدر أبعت تلقائيًا")
        return
    jobs = get_unnotified_jobs(limit=20)
    if not jobs:
        return
    try:
        await send_jobs_digest(context, TELEGRAM_CHAT_ID, jobs, f"🆕 وظائف جديدة ({len(jobs)}):")
        for job in jobs:
            mark_notified(job["id"])
    except Exception as e:
        logger.error(f"فشل إرسال تنبيه الوظائف الجديدة: {e}")


# ---------- معالج الأخطاء العام ----------

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"⚠️ حصل خطأ: {context.error}")


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
