# bot/bot.py
"""
بوت تليجرام لمتابعة وظائف المحاسبة (متعدد المصادر)
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
    upsert_user_profile,
    get_user_profile,
)
from message_templates import build_cover_letter, build_whatsapp_link, build_mailto_link

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
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
        exp = f" — {job['experience']}" if job.get("experience") else ""
        contact_mark = " 📞" if (job.get("contact_email") or job.get("contact_phone")) else ""
        src = f" [{job.get('source', '')}]" if job.get('source') else ""
        lines.append(f"{i}. {job['title']} | {job.get('company') or '-'}{exp}{contact_mark}{src}")
        keyboard_rows.append([InlineKeyboardButton(f"📋 تفاصيل وظيفة {i}", callback_data=f"detail:{job['id']}")])
    await context.bot.send_message(
        chat_id=chat_id,
        text="\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard_rows),
    )


# ---------- الأوامر ----------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    logger.info(f"📩 استلمت /start من: {chat_id} (user_id: {user_id})")

    # تسجيل المستخدم تلقائياً (إنشاء ملف شخصي فارغ)
    profile = get_user_profile(user_id)
    if not profile:
        upsert_user_profile(user_id, {"name": update.effective_user.full_name or ""})
        logger.info(f"✅ تم إنشاء ملف شخصي للمستخدم {user_id}")

    await update.message.reply_text(
        "أهلاً! 👋\n"
        "البوت ده بيجمع وظائف محاسبة من منصات متعددة (Wuzzuf, Forasna, Bayt, Indeed).\n\n"
        f"chat_id بتاعك هو: {chat_id}\n"
        "لو دي أول مرة، خد الرقم ده وحطه في متغير TELEGRAM_CHAT_ID في الـ Railway.\n\n"
        "الأوامر المتاحة:\n"
        "/jobs — آخر الوظائف المتاحة\n"
        "/search كلمة — بحث في الوظائف\n"
        "/saved — الوظائف المحفوظة\n"
        "/ignored — الوظائف المتجاهلة\n"
        "/stats — إحصائيات عامة\n"
        "/setcv — حفظ ملف CV (PDF)\n"
        "/profile — عرض أو تحديث ملفك الشخصي\n"
        "/recommend — توصيات ذكية بناءً على ملفك الشخصي"
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
        f"فيها وسيلة تواصل مباشرة: {s['with_contact']}\n"
        "التوزيع حسب المصدر:\n"
    )
    for src, count in s.get('by_source', {}).items():
        text += f"  {src}: {count}\n"
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
    file_id = doc.file_id
    user_id = str(update.effective_user.id)
    # حفظ file_id في settings (للاستخدام العام) وفي user_profile
    set_setting("cv_file_id", file_id)
    upsert_user_profile(user_id, {"cv_file_id": file_id})
    context.user_data["awaiting_cv"] = False
    await update.message.reply_text("✅ تم حفظ الـ CV، هبعته لك جنب كل رسالة تقديم.")


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    if not profile:
        await update.message.reply_text("مفيش ملف شخصي مسجل. استخدم /start لإنشاء واحد.")
        return
    text = (
        "👤 ملفك الشخصي:\n"
        f"الاسم: {profile.get('name', 'غير محدد')}\n"
        f"سنوات الخبرة: {profile.get('experience_years', 0)}\n"
        f"المهارات: {', '.join(profile.get('skills', [])) or 'لا يوجد'}\n"
        f"المناطق المفضلة: {', '.join(profile.get('preferred_locations', [])) or 'لا يوجد'}\n"
        f"الراتب المتوقع: {profile.get('expected_salary', 'غير محدد')}\n"
        f"ملف CV: {'✅ موجود' if profile.get('cv_file_id') else '❌ غير مرفوع'}\n"
        "لتحديث أي حقل استخدم:\n"
        "/update name <الاسم>\n"
        "/update experience <عدد السنوات>\n"
        "/update skills <مهارة1,مهارة2>\n"
        "/update locations <مدينة1,مدينة2>\n"
        "/update salary <المبلغ>"
    )
    await update.message.reply_text(text)


async def update_profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if len(context.args) < 2:
        await update.message.reply_text(
            "استخدم الأمر هكذا:\n"
            "/update name أحمد\n"
            "/update experience 5\n"
            "/update skills محاسبة,تحليل\n"
            "/update locations القاهرة,الجيزة\n"
            "/update salary 15000"
        )
        return
    field = context.args[0].lower()
    value = " ".join(context.args[1:])
    updates = {}
    if field == "name":
        updates["name"] = value
    elif field == "experience":
        try:
            updates["experience_years"] = int(value)
        except ValueError:
            await update.message.reply_text("الخبرة لازم تكون رقم.")
            return
    elif field == "skills":
        updates["skills"] = [s.strip() for s in value.split(",") if s.strip()]
    elif field == "locations":
        updates["preferred_locations"] = [s.strip() for s in value.split(",") if s.strip()]
    elif field == "salary":
        try:
            updates["expected_salary"] = int(value)
        except ValueError:
            await update.message.reply_text("الراتب لازم يكون رقم.")
            return
    else:
        await update.message.reply_text("حقل غير معروف. اختر: name, experience, skills, locations, salary")
        return
    upsert_user_profile(user_id, updates)
    await update.message.reply_text("✅ تم تحديث ملفك الشخصي.")


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


# ---------- التشغيل ----------

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
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("update", update_profile_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(push_new_jobs, interval=NOTIFY_INTERVAL_SECONDS, first=15)

    logger.info("البوت شغال...")
    app.run_polling()


if __name__ == "__main__":
    main()
