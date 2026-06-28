# scraper/manager.py
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from providers.wuzzuf import WuzzufProvider
from providers.forasna import ForasnaProvider
from providers.bayt import BaytProvider
from providers.indeed import IndeedProvider


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
    with ThreadPoolExecutor(max_workers=len(providers)) as executor:
        futures = [executor.submit(p.fetch_jobs, search_term, max_pages) for p in providers]
        for future in futures:
            try:
                jobs = future.result()
                all_jobs.extend(jobs)
            except Exception as e:
                print(f"⚠️ فشل أحد المزودات: {e}")

    seen = set()
    unique = []
    for job in all_jobs:
        if job['url'] not in seen:
            seen.add(job['url'])
            unique.append(job)
    return unique


def main():
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "bot"))
    from db import insert_jobs, expire_old_jobs
    from dotenv import load_dotenv
    load_dotenv()

    search_term = os.environ.get("SEARCH_TERM", "محاسب")
    max_pages = int(os.environ.get("MAX_PAGES", 3))
    jobs = collect_all_jobs(search_term, max_pages)
    print(f"✅ تم جمع {len(jobs)} وظيفة من جميع المصادر")

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
        print("💾 تم حفظ الوظائف في all_jobs.csv محلياً")

    bot_token = os.environ.get("BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if bot_token and chat_id and os.environ.get("NOTIFY_ON_SUCCESS", "true").lower() == "true":
        import requests
        contacts_found = sum(1 for j in jobs if j.get("contact_email") or j.get("contact_phone"))
        sources = set(j.get('source', 'unknown') for j in jobs)
        text = (
            f"✅ تم جمع {len(jobs)} وظيفة محاسبة اليوم ({contacts_found} منها فيها وسيلة تواصل مباشرة).\n"
            f"المصادر: {', '.join(sources)}"
        )
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
