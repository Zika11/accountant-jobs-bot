"""
بوت تليجرام لمتابعة وظائف المحاسبة (متعدد المصادر)
مع توصيات ذكية وملف شخصي
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
    get_user_profile,
    upsert_user_profile,
    update_user_profile,
)
from message_templates import build_cover_letter, build_whatsapp_link, build_mailto_link
from ai_matcher import analyze_job_fit  # سننشئ هذا الملف لاحقاً

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

# ---------- الأوامر الأساسية ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = str(update.effective_user.id)
    logger.info(f"📩 استلمت /start من: {chat_id}")
    # تسجيل المستخدم في قاعدة البيانات (إذا لم يكن موجوداً)
    profile = get_user_profile(user_id)
    if not profile:
        upsert_user_profile({"user_id": user_id})
    await update.message.reply_text(
        "أهلاً! 👋\n"
        "البوت ده هيبعتلك وظائف محاسبة جديدة من منصات متعددة (Wuzzuf, Forasna, Bayt, Indeed) بشكل دوري.\n\n"
        f"chat_id بتاعك هو: {chat_id}\n"
        "لو دي أول مرة، خد الرقم ده وحطه في متغير TELEGRAM_CHAT_ID في الـ Railway "
        "عشان البوت يعرف يبعتلك تلقائيًا، وبعدين أعمل Redeploy.\n\n"
        "الأوامر المتاحة:\n"
        "/jobs — آخر الوظائف المتاحة\n"
        "/search كلمة — بحث في الوظائف\n"
        "/saved — الوظائف المحفوظة\n"
        "/ignored — الوظائف المتجاهلة\n"
        "/stats — إحصائيات عامة\n"
        "/setcv — حفظ ملف CV\n"
        "/setprofile — تعيين بياناتك الشخصية (الاسم، الخبرة، المهارات)\n"
        "/recommend — توصيات ذكية حسب ملفك الشخصي\n"
        "استخدم الأزرار أدناه للتنقل بسهولة:",
        reply_markup=main_menu_keyboard()
    )

def main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("📋 وظائف جديدة", callback_data="menu_jobs")],
        [InlineKeyboardButton("🔍 بحث متقدم", callback_data="menu_search")],
        [InlineKeyboardButton("👤 ملفي الشخصي", callback_data="menu_profile")],
        [InlineKeyboardButton("📊 إحصائيات", callback_data="menu_stats")],
    ]
    return InlineKeyboardMarkup(keyboard)

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

# ---------- ملف التعريف الشخصي ----------
async def setprofile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id) or {}
    # بناء رسالة تعليمات
    text = (
        "📝 **إعداد الملف الشخصي**\n"
        "أرسل بياناتك بهذا التنسيق:\n"
        "```\n"
        "الاسم: أحمد محمد\n"
        "سنوات الخبرة: 5\n"
        "المهارات: محاسبة, ERP, تحليل مالي\n"
        "المناطق المفضلة: القاهرة, الجيزة\n"
        "الراتب المتوقع: 15000\n"
        "```\n"
        "أو استخدم الأزرار لتعديل كل حقل على حدة."
    )
    # أزرار لتعديل كل حقل
    keyboard = [
        [InlineKeyboardButton("✏️ تعديل الاسم", callback_data="edit_name")],
        [InlineKeyboardButton("✏️ تعديل سنوات الخبرة", callback_data="edit_exp")],
        [InlineKeyboardButton("✏️ تعديل المهارات", callback_data="edit_skills")],
        [InlineKeyboardButton("✏️ تعديل المناطق", callback_data="edit_locations")],
        [InlineKeyboardButton("✏️ تعديل الراتب", callback_data="edit_salary")],
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="Markdown")

async def recommend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    profile = get_user_profile(user_id)
    if not profile or not profile.get('cv_text'):
        await update.message.reply_text("أولاً احفظ ملفك الشخصي باستخدام /setprofile وأرسل نص الـ CV الخاص بك (أو استخدم /setcv لرفع ملف PDF).")
        return
    jobs = get_pending_jobs(limit=20)
    if not jobs:
        await update.message.reply_text("لا توجد وظائف حالياً للتوصية.")
        return
    await update.message.reply_text("🔍 جاري تحليل الوظائف وتقييم التوافق...")
    recommendations = []
    for job in jobs:
        # بناء وصف بسيط للوظيفة
        desc = f"{job['title']} في {job['company']}، المطلوب: {job.get('experience', '')}"
        result = analyze_job_fit(desc, profile['cv_text'])
        recommendations.append((job, result))
    # ترتيب حسب النسبة
    recommendations.sort(key=lambda x: x[1]['score'], reverse=True)
    # إرسال أفضل 5
    count = 0
    for job, result in recommendations[:5]:
        text = f"📌 *{job['title']}* - {job['company']}\n"
        text += f"التوافق: {result['score']}%\n"
        text += f"{result['analysis'][:200]}...\n"
        text += f"🔗 {job['url']}"
        await update.message.reply_text(text, parse_mode="Markdown")
        count += 1
    if count == 0:
        await update.message.reply_text("لم يتم العثور على توصيات مناسبة حالياً.")

# ---------- إعدادات الـ CV ----------
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
    # حفظ file_id في settings (للاستخدام العام) وفي user_profiles (للمستخدم الحالي)
    file_id = doc.file_id
    set_setting("cv_file_id", file_id)
    user_id = str(update.effective_user.id)
    update_user_profile(user_id, {"cv_file_id": file_id})
    # بالإضافة إلى ذلك، يمكن استخراج النص من PDF إذا أردت (سنفعل لاحقاً)
    context.user_data["awaiting_cv"] = False
    await update.message.reply_text("✅ تم حفظ الـ CV، هبعته لك جنب كل رسالة تقديم ويمكن استخدامه في التوصيات.")

# ---------- معالج الأزرار (الموسع) ----------
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    # أزرار القائمة الرئيسية
    if data == "menu_jobs":
        await jobs_command(update, context)
        return
    elif data == "menu_search":
        await update.message.reply_text("استخدم الأمر /search كلمة للبحث.")
        return
    elif data == "menu_profile":
        await setprofile_command(update, context)
        return
    elif data == "menu_stats":
        await stats_command(update, context)
        return

    # أزرار تعديل الملف الشخصي (سننفذها لاحقاً)
    if data.startswith("edit_"):
        field = data.split("_")[1]
        await query.message.reply_text(f"أرسل القيمة الجديدة لـ {field}:")
        context.user_data["editing_field"] = field
        return

    # الأزرار العادية (تفاصيل، حفظ، تجاهل، إلخ)
    if ":" in data:
        action, job_id = data.split(":", 1)
        if action == "detail":
            job = get_job_by_id(job_id)
            if not job:
                await query.message.reply_text("معلش، الوظيفة دي مش موجودة دلوقتي.")
                return
            await query.message.reply_text(
                format_job_text(job), reply_markup=build_job_keyboard(job)
            )
            return
        elif action == "letter":
            job = get_job_by_id(job_id)
            if not job:
                await query.message.reply_text("معلش، مش لاقي تفاصيل الوظيفة دي.")
                return
            await query.message.reply_text(build_cover_letter(job))
            return
        elif action in ("prep_wa", "prep_email"):
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
        elif action == "save":
            update_status(job_id, "saved")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("💾 تم الحفظ.")
            return
        elif action == "ignore":
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

# ---------- معالج الأخطاء ----------
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
    app.add_handler(CommandHandler("setprofile", setprofile_command))
    app.add_handler(CommandHandler("recommend", recommend_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)

    app.job_queue.run_repeating(push_new_jobs, interval=NOTIFY_INTERVAL_SECONDS, first=15)

    logger.info("البوت شغال...")
    app.run_polling()

if __name__ == "__main__":
    main()
