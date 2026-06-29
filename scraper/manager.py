# scraper/manager.py
"""
مدير جمع الوظائف من جميع المصادر
"""

import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# إضافة المسارات المطلوبة
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/bot')
sys.path.insert(0, '/app/scraper')
sys.path.insert(0, '/app/scraper/providers')

from providers.wuzzuf import WuzzufProvider
from providers.forasna import ForasnaProvider
from providers.bayt import BaytProvider
from providers.indeed import IndeedProvider

# محاولة استيراد المصادر المصرية (لو مش موجودة، نتجاوزها)
try:
    from providers.egypt_providers import (
        JobzellaProvider,
        EgyptianJobsProvider,
        CareerEgyptProvider,
        TelegramProvider,
        FacebookProvider,
    )
    EGYPT_PROVIDERS_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ مصر providers مش موجودة: {e}")
    EGYPT_PROVIDERS_AVAILABLE = False

from db import insert_jobs, expire_old_jobs, log_scraper_error


def get_all_providers():
    """إرجاع قائمة بكل المصادر المتاحة"""
    location_filter = [loc.strip() for loc in os.environ.get("LOCATION_FILTER", "Cairo,Giza,Menoufia").split(',') if loc.strip()]
    max_exp = os.environ.get("MAX_EXPERIENCE_YEARS")
    max_exp = int(max_exp) if max_exp and max_exp.isdigit() else 3

    providers = []

    # المصادر الأساسية (موجودة دائماً)
    providers.append(WuzzufProvider(location_filter=location_filter, max_experience_years=max_exp))
    providers.append(ForasnaProvider(max_experience_years=max_exp))
    providers.append(BaytProvider(max_experience_years=max_exp))
    providers.append(IndeedProvider(max_experience_years=max_exp))

    # المصادر المصرية (لو متاحة)
    if EGYPT_PROVIDERS_AVAILABLE:
        providers.append(JobzellaProvider(max_experience_years=max_exp))
        providers.append(EgyptianJobsProvider(max_experience_years=max_exp))
        providers.append(CareerEgyptProvider(max_experience_years=max_exp))
        providers.append(TelegramProvider())
        providers.append(FacebookProvider())

    return providers


def collect_all_jobs(search_term="محاسب حديث التخرج", max_pages=3):
    """جمع الوظائف من جميع المصادر بالتوازي"""
    providers = get_all_providers()
    all_jobs = []
    failed_providers = []

    print(f"🔄 بدء جمع الوظائف من {len(providers)} مصدر...")
    print(f"🔍 كلمة البحث: {search_term}")
    print(f"📄 عدد الصفحات: {max_pages}")
    print("-" * 50)

    with ThreadPoolExecutor(max_workers=min(len(providers), 5)) as executor:
        futures = {executor.submit(p.fetch_jobs, search_term, max_pages): p.source_name for p in providers}

        for future in as_completed(futures):
            source = futures[future]
            try:
                jobs = future.result(timeout=120)
                all_jobs.extend(jobs)
                print(f"✅ {source}: {len(jobs)} وظيفة")
            except Exception as e:
                error_msg = f"{source} فشل: {str(e)[:100]}"
                print(f"⚠️ {error_msg}")
                failed_providers.append({
                    "source": source,
                    "error": str(e)[:500],
                    "traceback": traceback.format_exc()[:1000],
                    "timestamp": datetime.now().isoformat()
                })

    # إزالة التكرار حسب الرابط
    seen = set()
    unique = []
    for job in all_jobs:
        if job.get('url') and job['url'] not in seen:
            seen.add(job['url'])
            unique.append(job)

    # تسجيل الأخطاء في قاعدة البيانات
    if failed_providers:
        for fail in failed_providers:
            try:
                log_scraper_error(
                    source=fail["source"],
                    error=fail["error"],
                    traceback_text=fail["traceback"]
                )
            except Exception as e:
                print(f"⚠️ فشل تسجيل خطأ {fail['source']}: {e}")

    return unique


def main():
    """الدالة الرئيسية"""
    from dotenv import load_dotenv
    load_dotenv()

    search_term = os.environ.get("SEARCH_TERM", "محاسب حديث التخرج")
    max_pages = int(os.environ.get("MAX_PAGES", 3))

    start_time = time.time()
    jobs = collect_all_jobs(search_term, max_pages)
    elapsed = time.time() - start_time

    print("-" * 50)
    print(f"✅ تم جمع {len(jobs)} وظيفة في {elapsed:.1f} ثانية")

    if not jobs:
        print("⚠️ مفيش وظائف! جرب تغير كلمة البحث أو تزيد عدد الصفحات.")
        return

    try:
        count = insert_jobs(jobs)
        print(f"✅ تم حفظ {count} وظيفة جديدة في Supabase")

        expired = expire_old_jobs(days=int(os.environ.get("EXPIRE_DAYS", 14)))
        if expired:
            print(f"🧹 تم إغلاق {expired} وظيفة قديمة")

    except Exception as e:
        print(f"⚠️ فشل الحفظ في Supabase: {e}")
        # حفظ في CSV كخطة بديلة
        import csv
        with open("all_jobs.csv", "w", newline="", encoding="utf-8-sig") as f:
            if jobs:
                writer = csv.DictWriter(f, fieldnames=jobs[0].keys())
                writer.writeheader()
                writer.writerows(jobs)
        print("💾 تم حفظ الوظائف في all_jobs.csv")

    # إرسال إشعار
    bot_token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("ALLOWED_USER_IDS", "").split(",")[0] if os.environ.get("ALLOWED_USER_IDS") else None

    if bot_token and chat_id and os.environ.get("NOTIFY_ON_SUCCESS", "true").lower() == "true":
        import requests
        contacts_found = sum(1 for j in jobs if j.get("contact_email") or j.get("contact_phone"))
        sources = set(j.get('source', 'unknown') for j in jobs)
        text = (
            f"✅ تم جمع {len(jobs)} وظيفة محاسبة\n"
            f"📞 {contacts_found} فيها وسيلة تواصل\n"
            f"🌐 المصادر: {', '.join(sources)}\n"
            f"⏱️ {elapsed:.1f} ثانية"
        )
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={"chat_id": chat_id, "text": text},
                timeout=10,
            )
        except Exception as e:
            print(f"⚠️ فشل إرسال الإشعار: {e}")


if __name__ == "__main__":
    main()
