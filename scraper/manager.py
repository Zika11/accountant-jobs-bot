# scraper/manager.py
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from providers.wuzzuf import WuzzufProvider
from providers.forasna import ForasnaProvider
from providers.bayt import BaytProvider
from providers.indeed import IndeedProvider
from providers.egypt_providers import (
    JobzellaProvider,
    EgyptianJobsProvider,
    CareerEgyptProvider,
    TelegramProvider,
    FacebookProvider,
)

# إضافة مسار البوت للاستيراد
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "bot"))


def get_all_providers():
    location_filter = [loc.strip() for loc in os.environ.get("LOCATION_FILTER", "Cairo,Giza").split(',') if loc.strip()]
    max_exp = os.environ.get("MAX_EXPERIENCE_YEARS")
    max_exp = int(max_exp) if max_exp and max_exp.isdigit() else None

    providers = [
        # الموجودة
        WuzzufProvider(location_filter=location_filter, max_experience_years=max_exp),
        ForasnaProvider(max_experience_years=max_exp),
        BaytProvider(max_experience_years=max_exp),
        IndeedProvider(max_experience_years=max_exp),
        
        # الجديدة (مصرية)
        JobzellaProvider(max_experience_years=max_exp),
        EgyptianJobsProvider(max_experience_years=max_exp),
        CareerEgyptProvider(max_experience_years=max_exp),
        
        # تليجرام وفيسبوك
        TelegramProvider(),
        FacebookProvider(),
    ]
    return providers


def collect_all_jobs(search_term="محاسب", max_pages=3):
    providers = get_all_providers()
    all_jobs = []
    failed_providers = []
    
    print(f"🔄 بدء جمع الوظائف من {len(providers)} مصدر...")
    
    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        futures = {
            executor.submit(p.fetch_jobs, search_term, max_pages): p.source_name 
            for p in providers
        }
        
        for future in as_completed(futures):
            source = futures[future]
            try:
                jobs = future.result(timeout=120)
                all_jobs.extend(jobs)
                print(f"✅ {source}: {len(jobs)} وظيفة")
            except Exception as e:
                error_msg = f"{source} فشل: {str(e)}"
                print(f"⚠️ {error_msg}")
                failed_providers.append({
                    "source": source,
                    "error": str(e),
                    "traceback": traceback.format_exc(),
                    "timestamp": datetime.now().isoformat()
                })

    # إزالة التكرار حسب الرابط
    seen = set()
    unique = []
    for job in all_jobs:
        if job['url'] not in seen:
            seen.add(job['url'])
            unique.append(job)
    
    # تسجيل الفشل في قاعدة البيانات
    if failed_providers:
        try:
            from db import get_client
            client = get_client()
            for fail in failed_providers:
                client.table("scraper_logs").insert(fail).execute()
        except Exception as e:
            print(f"⚠️ فشل تسجيل الأخطاء: {e}")
    
    return unique


def main():
    from db import insert_jobs, expire_old_jobs
    from dotenv import load_dotenv
    load_dotenv()

    search_term = os.environ.get("SEARCH_TERM", "محاسب")
    max_pages = int(os.environ.get("MAX_PAGES", 2))  # خليها 2 عشان السرعة
    
    print(f"🔄 بدء جمع الوظائف: {search_term}")
    start_time = time.time()
    
    jobs = collect_all_jobs(search_term, max_pages)
    elapsed = time.time() - start_time
    
    print(f"✅ تم جمع {len(jobs)} وظيفة في {elapsed:.1f} ثانية")

    try:
        count = insert_jobs(jobs)
        print(f"✅ تم حفظ {count} وظيفة جديدة في Supabase")
        expired = expire_old_jobs(days=int(os.environ.get("EXPIRE_DAYS", 14)))
        if expired:
            print(f"🧹 تم إغلاق {expired} وظيفة قديمة")
    except Exception as e:
        print(f"⚠️ فشل الحفظ في Supabase: {e}")
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
