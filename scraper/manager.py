# scraper/manager.py - معدل لدعم جميع المصادر
import os
import sys
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from providers.wuzzuf import WuzzufProvider
from providers.forasna import ForasnaProvider
from providers.bayt import BaytProvider
from providers.indeed import IndeedProvider

# إضافة مسار البوت عشان نقدر نستورد db
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "bot"))

def get_all_providers():
    location_filter = [loc.strip() for loc in os.environ.get("LOCATION_FILTER", "Cairo,Giza").split(',') if loc.strip()]
    max_exp = os.environ.get("MAX_EXPERIENCE_YEARS")
    max_exp = int(max_exp) if max_exp and max_exp.isdigit() else None

    providers = [
        WuzzufProvider(location_filter=location_filter, max_experience_years=max_exp),
        ForasnaProvider(max_experience_years=max_exp),
        BaytProvider(max_experience_years=max_exp),
        IndeedProvider(max_experience_years=max_exp),
    ]
    return providers

def collect_all_jobs(search_term="محاسب", max_pages=3):
    providers = get_all_providers()
    all_jobs = []
    errors = []
    
    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        future_to_provider = {executor.submit(p.fetch_jobs, search_term, max_pages): p for p in providers}
        for future in as_completed(future_to_provider):
            provider = future_to_provider[future]
            try:
                jobs = future.result(timeout=60)
                all_jobs.extend(jobs)
                print(f"✅ {provider.source_name}: {len(jobs)} وظيفة")
            except Exception as e:
                error_msg = f"❌ {provider.source_name} فشل: {str(e)}"
                print(error_msg)
                errors.append({
                    "source": provider.source_name,
                    "error": str(e),
                    "traceback": traceback.format_exc()
                })
    
    # إزالة التكرار
    seen = set()
    unique = []
    for job in all_jobs:
        if job['url'] not in seen:
            seen.add(job['url'])
            unique.append(job)
    
    return unique, errors

def log_errors_to_db(errors):
    """تسجيل الأخطاء في قاعدة البيانات"""
    try:
        from db import get_client
        client = get_client()
        for err in errors:
            data = {
                "source": err["source"],
                "error_message": err["error"],
                "stack_trace": err["traceback"],
                "created_at": datetime.now().isoformat()
            }
            client.table("scraper_logs").insert(data).execute()
    except Exception as e:
        print(f"⚠️ فشل تسجيل الأخطاء: {e}")

def main():
    from db import insert_jobs, expire_old_jobs
    from dotenv import load_dotenv
    load_dotenv()

    search_term = os.environ.get("SEARCH_TERM", "محاسب")
    max_pages = int(os.environ.get("MAX_PAGES", 3))
    
    jobs, errors = collect_all_jobs(search_term, max_pages)
    print(f"\n✅ إجمالي الوظائف بعد الدمج: {len(jobs)}")
    
    if errors:
        print(f"\n⚠️ عدد المصادر الفاشلة: {len(errors)}")
        for err in errors:
            print(f"  - {err['source']}: {err['error']}")
        # تسجيل الأخطاء في قاعدة البيانات
        log_errors_to_db(errors)
    
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
        with open("all_jobs_backup.csv", "w", newline="", encoding="utf-8-sig") as f:
            if jobs:
                writer = csv.DictWriter(f, fieldnames=jobs[0].keys())
                writer.writeheader()
                writer.writerows(jobs)
        print("💾 تم حفظ نسخة احتياطية في all_jobs_backup.csv")
    
    # إشعار تليجرام
    bot_token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id and os.environ.get("NOTIFY_ON_SUCCESS", "true").lower() == "true":
        import requests
        contacts_found = sum(1 for j in jobs if j.get("contact_email") or j.get("contact_phone"))
        sources = set(j.get('source', 'unknown') for j in jobs)
        text = (
            f"✅ تم جمع {len(jobs)} وظيفة محاسبة\n"
            f"📞 {contacts_found} منها فيها وسيلة تواصل\n"
            f"🌐 المصادر: {', '.join(sources)}"
        )
        if errors:
            text += f"\n⚠️ {len(errors)} مصدر فشل: {', '.join(e['source'] for e in errors)}"
        try:
            requests.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                data={"chat_id": chat_id, "text": text},
                timeout=10,
            )
        except:
            pass

if __name__ == "__main__":
    main()
