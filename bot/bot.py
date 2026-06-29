# bot/bot.py
"""
بوت تليجرام لتقديم الوظائف تلقائياً (شخصي)
يدعم: محاسب، محاسب حديث التخرج، فلترة خبرة 0-3 سنوات
"""

import asyncio
import logging
import os
import subprocess
import sys
from typing import List, Dict, Optional

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from telegram.constants import ParseMode, UpdateType
from dotenv import load_dotenv
load_dotenv()

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get("BOT_TOKEN")
ALLOWED_USER_IDS = [x.strip() for x in os.environ.get("ALLOWED_USER_IDS", "").split(",") if x.strip()]
AUTO_APPLY_ENABLED = os.environ.get("AUTO_APPLY_ENABLED", "false").lower() == "true"
WHATSAPP_NUMBER = os.environ.get("WHATSAPP_NUMBER", "")
NOTIFY_INTERVAL_SECONDS = int(os.environ.get("NOTIFY_INTERVAL_SECONDS", 6 * 60 * 60))


def is_allowed_user(user_id: int) -> bool:
    return str(user_id) in ALLOWED_USER_IDS

def format_job_text(job: dict, show_apply_status: bool = True) -> str:
    lines = [f"📌 {job['title']}"]
    if job.get("company"):
        lines.append(f"🏢 {job['company']}")
    if job.get("location"):
        lines.append(f"📍 {job['location']}")
    if job.get("experience"):
        lines.append(f"🎓 {job['experience']}")
    if job.get("salary_min") or job.get("salary_max"):
        salary_min = job.get('salary_min', '')
        salary_max = job.get('salary_max', '')
        if salary_min and salary_max:
            lines.append(f"💰 {salary_min} - {salary_max} جنيه")
        elif salary_min:
            lines.append(f"💰 من {salary_min} جنيه")
        elif salary_max:
            lines.append(f"💰 حتى {salary_max} جنيه")
    if job.get("job_type"):
        lines.append(f"💼 {job['job_type']}")
    if job.get("posted"):
        lines.append(f"🕒 {job['posted']}")
    if job.get("source"):
        lines.append(f"🌐 المصدر: {job['source']}")
    if show_apply_status and job.get("status"):
        status_map = {
            "pending": "⏳ قيد الانتظار",
            "saved": "💾 محفوظة",
            "ignored": "🗑 متجاهلة",
            "applied": "✅ تم التقديم",
            "expired": "⏰ منتهية"
        }
        lines.append(f"📌 الحالة: {status_map.get(job['status'], job['status'])}")
    return "\n".join(lines)

def build_job_keyboard(job: dict, show_actions: bool = True, auto_apply_enabled: bool = None) -> InlineKeyboardMarkup:
    if auto_apply_enabled is None:
        auto_apply_enabled = AUTO_APPLY_ENABLED
    buttons = []
    buttons.append([InlineKeyboardButton("🔗 فتح الوظيفة", url=job["url"])])
    contact_row = []
    if job.get("contact_phone"):
        contact_row.append(InlineKeyboardButton("📩 واتساب", callback_data=f"prep_wa:{job['id']}"))
    if job.get("contact_email"):
        contact_row.append(InlineKeyboardButton("📧 إيميل", callback_data=f"prep_email:{job['id']}"))
    if contact_row:
        buttons.append(contact_row)
    if auto_apply_enabled and job.get("contact_phone"):
        if job.get("status") != "applied":
            buttons.append([InlineKeyboardButton("🚀 تقديم تلقائي", callback_data=f"auto_apply:{job['id']}")])
        else:
            buttons.append([InlineKeyboardButton("✅ تم التقديم", callback_data="already_applied")])
    buttons.append([InlineKeyboardButton("📝 الرسالة الجاهزة", callback_data=f"letter:{job['id']}")])
    if show_actions and job.get("status") != "applied":
        actions_row = []
        if job.get("status") != "saved":
            actions_row.append(InlineKeyboardButton("💾 حفظ", callback_data=f"save:{job['id']}"))
        if job.get("status") != "ignored":
            actions_row.append(InlineKeyboardButton("🗑 تجاهل", callback_data=f"ignore:{job['id']}"))
        if actions_row:
            buttons.append(actions_row)
    return InlineKeyboardMarkup(buttons)

async def send_jobs_digest(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    jobs: List[dict],
    header: str,
    show_apply_status: bool = False
):
    if not jobs:
        return
    lines = [header, ""]
    keyboard_rows = []
    for i, job in enumerate(jobs, start=1):
        exp = f" — {job['experience']}" if job.get("experience") else ""
        contact_mark = " 📞" if (job.get("contact_email") or job.get("contact_phone")) else ""
        src = f" [{job.get('source', '')}]" if job.get('source') else ""
        status_mark = ""
        if job.get("status") == "applied":
            status_mark = " ✅"
        elif job.get("status") == "saved":
            status_mark = " 💾"
        lines.append(f"{i}. {job['title']} | {job.get('company') or '-'}{exp}{contact_mark}{src}{status_mark}")
        keyboard_rows.append([InlineKeyboardButton(f"📋 تفاصيل {i}", callback_data=f"detail:{job['id']}")])
    text = "\n".join(lines)
    if len(text) > 4000:
        parts = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for i, part in enumerate(parts):
            if i == 0:
                await context.bot.send_message(chat_id=chat_id, text=part, reply_markup=InlineKeyboardMarkup(keyboard_rows))
            else:
                await context.bot.send_message(chat_id=chat_id, text=part)
    else:
        await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=InlineKeyboardMarkup(keyboard_rows))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    name = update.effective_user.first_name or "صديقي"
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ هذا البوت للاستخدام الشخصي فقط.")
        return
    logger.info(f"📩 استلمت /start من: {chat_id} (المستخدم: {user_id})")
    upsert_user_profile(str(user_id), {
        "name": update.effective_user.full_name or name,
        "chat_id": str(chat_id),
        "phone": os.environ.get("APPLICANT_PHONE", ""),
        "email": os.environ.get("APPLICANT_EMAIL", ""),
    })
    reply = (
        f"أهلاً {name}! 👋\n"
        "البوت جاهز لتقديم الوظائف التلقائي.\n\n"
        "⚙️ الإعدادات الحالية:\n"
        f"🤖 التقديم التلقائي: {'✅ مفعل' if AUTO_APPLY_ENABLED else '❌ معطل'}\n"
        f"📱 رقم واتساب: {WHATSAPP_NUMBER or 'غير محدد'}\n\n"
        "📌 الأوامر المتاحة:\n"
        "/jobs — عرض الوظائف الجديدة\n"
        "/pending — الوظائف قيد الانتظار\n"
        "/applied — الوظائف المتقدّم عليها\n"
        "/saved — الوظائف المحفوظة\n"
        "/ignored — الوظائف المتجاهلة\n"
        "/search كلمة — بحث في الوظائف\n"
        "/stats — إحصائيات\n"
        "/setcv — رفع ملف CV (PDF)\n"
        "/profile — عرض ملفك الشخصي\n"
        "/auto_on — تشغيل التقديم التلقائي\n"
        "/auto_off — إيقاف التقديم التلقائي\n"
        "/scrape — تشغيل السكرابر يدوي\n"
        "/help — عرض المساعدة"
    )
    await update.message.reply_text(reply, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    help_text = (
        "📖 <b>دليل استخدام البوت</b>\n\n"
        "<b>أوامر العرض:</b>\n"
        "/jobs — آخر الوظائف المتاحة\n"
        "/pending — الوظائف قيد الانتظار\n"
        "/applied — الوظائف المتقدّم عليها\n"
        "/saved — الوظائف المحفوظة\n"
        "/ignored — الوظائف المتجاهلة\n"
        "/search كلمة — بحث في الوظائف\n\n"
        "<b>أوامر الإعدادات:</b>\n"
        "/profile — عرض ملفك الشخصي\n"
        "/setcv — رفع ملف CV (PDF)\n"
        "/auto_on — تشغيل التقديم التلقائي\n"
        "/auto_off — إيقاف التقديم التلقائي\n\n"
        "<b>أوامر إضافية:</b>\n"
        "/stats — إحصائيات عامة\n"
        "/scrape — تشغيل السكرابر يدوي\n"
        "/help — عرض هذه المساعدة\n\n"
        "💡 <b>نصيحة:</b> استخدم أزرار التفاصيل للوصول إلى خيارات التقديم والحفظ."
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    jobs = get_pending_jobs(limit=20)
    if not jobs:
        await update.message.reply_text("📭 لا يوجد وظائف جديدة دلوقتي 🙏")
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f"📋 آخر الوظائف ({len(jobs)}):")

async def pending_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    jobs = get_pending_jobs(limit=20)
    if not jobs:
        await update.message.reply_text("📭 مفيش وظائف قيد الانتظار.")
        return
    for job in jobs:
        await update.message.reply_text(
            format_job_text(job),
            reply_markup=build_job_keyboard(job, show_actions=True)
        )

async def applied_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    jobs = get_jobs_by_status("applied", limit=20)
    if not jobs:
        await update.message.reply_text("📭 مفيش وظائف متقدّم عليها.")
        return
    for job in jobs:
        await update.message.reply_text(
            format_job_text(job),
            reply_markup=build_job_keyboard(job, show_actions=False)
        )

async def saved_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    jobs = get_jobs_by_status("saved", limit=20)
    if not jobs:
        await update.message.reply_text("📭 مفيش وظائف محفوظة.")
        return
    for job in jobs:
        await update.message.reply_text(
            format_job_text(job),
            reply_markup=build_job_keyboard(job, show_actions=True)
        )

async def ignored_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    jobs = get_jobs_by_status("ignored", limit=20)
    if not jobs:
        await update.message.reply_text("📭 مفيش وظائف متجاهلة.")
        return
    for job in jobs:
        await update.message.reply_text(
            format_job_text(job),
            reply_markup=build_job_keyboard(job, show_actions=False)
        )

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    if not context.args:
        await update.message.reply_text("✏️ اكتب كلمة البحث، مثلاً:\n/search محاسب أول")
        return
    keyword = " ".join(context.args)
    jobs = search_jobs(keyword, limit=15)
    if not jobs:
        await update.message.reply_text(f'📭 مفيش نتايج لـ "{keyword}".')
        return
    await send_jobs_digest(context, update.effective_chat.id, jobs, f'🔍 نتايج البحث عن "{keyword}":')

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    stats = get_stats()
    text = (
        "📊 <b>إحصائيات الوظائف</b>\n"
        "─" * 20 + "\n"
        f"📌 الإجمالي: {stats['total']}\n"
        f"⏳ قيد الانتظار: {stats['pending']}\n"
        f"💾 محفوظة: {stats['saved']}\n"
        f"🗑 متجاهلة: {stats['ignored']}\n"
        f"✅ تم التقديم: {stats.get('applied', 0)}\n"
        f"📞 فيها وسيلة تواصل: {stats['with_contact']}\n"
    )
    if stats.get('by_source'):
        text += "\n<b>التوزيع حسب المصدر:</b>\n"
        for src, count in stats['by_source'].items():
            text += f"  • {src}: {count}\n"
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def setcv_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    context.user_data["awaiting_cv"] = True
    await update.message.reply_text("📎 ابعتلي ملف الـ CV بصيغة PDF")

async def document_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    if not context.user_data.get("awaiting_cv"):
        return
    doc = update.message.document
    if not doc or doc.mime_type != "application/pdf":
        await update.message.reply_text("📄 محتاج ملف PDF بس 🙏 جرب تاني.")
        return
    file_id = doc.file_id
    set_setting("cv_file_id", file_id)
    upsert_user_profile(str(user_id), {"cv_file_id": file_id})
    context.user_data["awaiting_cv"] = False
    await update.message.reply_text("✅ تم حفظ الـ CV بنجاح!")

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if not is_allowed_user(int(user_id)):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    profile = get_user_profile(user_id)
    if not profile:
        await update.message.reply_text("📭 مفيش ملف شخصي. استخدم /start")
        return
    text = (
        "👤 <b>ملفك الشخصي</b>\n"
        "─" * 20 + "\n"
        f"الاسم: {profile.get('name', 'غير محدد')}\n"
        f"الخبرة: {profile.get('experience_years', 0)} سنوات\n"
        f"المهارات: {', '.join(profile.get('skills', [])) or 'لا يوجد'}\n"
        f"المناطق: {', '.join(profile.get('preferred_locations', [])) or 'لا يوجد'}\n"
        f"الراتب المتوقع: {profile.get('expected_salary', 'غير محدد')}\n"
        f"📱 الهاتف: {profile.get('phone', 'غير محدد')}\n"
        f"📧 الإيميل: {profile.get('email', 'غير محدد')}\n"
        f"📎 CV: {'✅ موجود' if profile.get('cv_file_id') else '❌ غير مرفوع'}\n"
        f"🤖 التقديم التلقائي: {'✅ مفعل' if profile.get('auto_apply', True) else '❌ معطل'}"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.HTML)

async def auto_on_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    upsert_user_profile(str(user_id), {"auto_apply": True})
    await update.message.reply_text("✅ تم تشغيل التقديم التلقائي")

async def auto_off_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    upsert_user_profile(str(user_id), {"auto_apply": False})
    await update.message.reply_text("❌ تم إيقاف التقديم التلقائي")

async def scrape_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """أمر /scrape - تشغيل السكرابر يدوي عبر manager.py"""
    user_id = update.effective_user.id
    if not is_allowed_user(user_id):
        await update.message.reply_text("⛔ غير مسموح.")
        return
    await update.message.reply_text("🔄 جاري جمع الوظائف... استنى شوية ⏳")
    try:
        result = subprocess.run(
            [sys.executable, "scraper/manager.py"],
            capture_output=True,
            text=True,
            timeout=120
        )
        output = result.stdout[-500:] if result.stdout else result.stderr[-500:]
        if result.returncode == 0:
            await update.message.reply_text(f"✅ تم جمع الوظائف بنجاح!\n{output}")
        else:
            await update.message.reply_text(f"❌ فشل الجمع:\n{output}")
    except subprocess.TimeoutExpired:
        await update.message.reply_text("⏰ استغرق السكرابر وقتاً طويلاً. حاول مرة أخرى.")
    except Exception as e:
        await update.message.reply_text(f"❌ خطأ: {e}")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    if not is_allowed_user(user_id):
        await query.answer("⛔ غير مسموح", show_alert=True)
        await query.edit_message_text("⛔ هذا البوت للاستخدام الشخصي فقط.")
        return
    try:
        action, job_id = query.data.split(":", 1)
    except ValueError:
        await query.answer("❌ طلب غير صالح", show_alert=True)
        return
    if action == "already_applied":
        await query.answer("✅ تم التقديم على هذه الوظيفة بالفعل")
        return
    job = get_job_by_id(job_id)
    if not job:
        await query.edit_message_text("❌ الوظيفة غير موجودة")
        return
    if action == "detail":
        await query.message.reply_text(
            format_job_text(job, show_apply_status=True),
            reply_markup=build_job_keyboard(job, show_actions=True)
        )
        return
    if action == "auto_apply":
        if not job.get("contact_phone"):
            await query.answer("❌ مفيش رقم واتساب للتقديم")
            return
        result = await auto_apply_whatsapp(job, context.bot, chat_id)
        if result["success"]:
            update_status(job_id, "applied")
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text(f"✅ تم التقديم على {job['title']} بنجاح!")
        else:
            await query.message.reply_text(f"❌ فشل التقديم: {result['error']}")
        return
    if action == "letter":
        await query.message.reply_text(build_cover_letter(job))
        return
    if action in ("prep_wa", "prep_email"):
        cv_file_id = get_setting("cv_file_id")
        if cv_file_id:
            await context.bot.send_document(
                chat_id=chat_id,
                document=cv_file_id,
                caption="📎 الـ CV الخاص بك - جاهز للإرفاق"
            )
        if action == "prep_wa":
            link = build_whatsapp_link(job)
            label = "📩 فتح واتساب"
        else:
            link = build_mailto_link(job)
            label = "📧 فتح الإيميل"
        if not link:
            await query.message.reply_text("❌ مفيش وسيلة تواصل متاحة.")
            return
        await query.message.reply_text(
            build_cover_letter(job),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(label, url=link)]])
        )
        return
    if action == "save":
        update_status(job_id, "saved")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("💾 تم حفظ الوظيفة.")
        return
    if action == "ignore":
        update_status(job_id, "ignored")
        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("🗑 تم تجاهل الوظيفة.")
        return
    await query.answer("❌ إجراء غير معروف")

async def push_new_jobs(context: ContextTypes.DEFAULT_TYPE):
    if not ALLOWED_USER_IDS:
        return
    jobs = get_unnotified_jobs(limit=20)
    if not jobs:
        return
    for user_id in ALLOWED_USER_IDS:
        profile = get_user_profile(user_id)
        if not profile:
            continue
        chat_id = profile.get("chat_id")
        if not chat_id:
            continue
        auto_apply_enabled = profile.get("auto_apply", AUTO_APPLY_ENABLED)
        jobs_to_send = jobs.copy()
        if auto_apply_enabled:
            for job in jobs_to_send[:]:
                if job.get("contact_phone") and job.get("status") != "applied":
                    result = await auto_apply_whatsapp(job, context.bot, chat_id)
                    if result["success"]:
                        update_status(job["id"], "applied")
                        mark_notified(job["id"])
                        await context.bot.send_message(
                            chat_id=chat_id,
                            text=f"✅ تم التقديم تلقائياً على: {job['title']} - {job.get('company', '')}"
                        )
                        jobs_to_send.remove(job)
                    else:
                        logger.error(f"فشل التقديم على {job['title']}: {result['error']}")
        if jobs_to_send:
            await send_jobs_digest(
                context,
                chat_id,
                jobs_to_send,
                f"🆕 وظائف جديدة ({len(jobs_to_send)}):"
            )
            for job in jobs_to_send:
                mark_notified(job["id"])

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"⚠️ خطأ: {context.error}")
    if update and hasattr(update, 'effective_chat'):
        try:
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text="❌ عذرا، حدث خطأ. حاول مرة أخرى."
            )
        except:
            pass

async def main():
    if not BOT_TOKEN:
        raise RuntimeError("❌ BOT_TOKEN مطلوب")
    if not ALLOWED_USER_IDS:
        logger.warning("⚠️ ALLOWED_USER_IDS غير محدد - البوت مش هيشتغل")
        return
    logger.info(f"🤖 بدء تشغيل البوت للمستخدم: {ALLOWED_USER_IDS[0]}")
    app = Application.builder().token(BOT_TOKEN).build()
    await app.bot.delete_webhook()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("jobs", jobs_command))
    app.add_handler(CommandHandler("pending", pending_command))
    app.add_handler(CommandHandler("applied", applied_command))
    app.add_handler(CommandHandler("saved", saved_command))
    app.add_handler(CommandHandler("ignored", ignored_command))
    app.add_handler(CommandHandler("search", search_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("setcv", setcv_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("auto_on", auto_on_command))
    app.add_handler(CommandHandler("auto_off", auto_off_command))
    app.add_handler(CommandHandler("scrape", scrape_command))
    app.add_handler(MessageHandler(filters.Document.ALL, document_handler))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_error_handler(error_handler)
    app.job_queue.run_repeating(push_new_jobs, interval=NOTIFY_INTERVAL_SECONDS, first=15)
    await app.initialize()
    await app.start()
    await app.updater.start_polling(
        drop_pending_updates=True,
        allowed_updates=Update.ALL_TYPES,
        bootstrap_retries=-1,
    )
    logger.info(f"✅ البوت شغال للمستخدم: {ALLOWED_USER_IDS[0]}")
    try:
        while True:
            await asyncio.sleep(3600)
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 تم إيقاف البوت")
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("🛑 تم إيقاف البوت بواسطة المستخدم")
