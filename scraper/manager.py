cat > /app/scraper/manager.py << 'EOF'
import os
import sys
sys.path.insert(0, '/app')
sys.path.insert(0, '/app/bot')

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
from db import insert_jobs, expire_old_jobs

def get_all_providers():
    location_filter = ["Cairo", "Giza"]
    max_exp = 5
    return [
        WuzzufProvider(location_filter=location_filter, max_experience_years=max_exp),
        ForasnaProvider(max_experience_years=max_exp),
        BaytProvider(max_experience_years=max_exp),
        IndeedProvider(max_experience_years=max_exp),
        JobzellaProvider(max_experience_years=max_exp),
        EgyptianJobsProvider(max_experience_years=max_exp),
        CareerEgyptProvider(max_experience_years=max_exp),
        TelegramProvider(),
        FacebookProvider(),
    ]

def collect_all_jobs(search_term="محاسب", max_pages=3):
    all_jobs = []
    for provider in get_all_providers():
        try:
            jobs = provider.fetch_jobs(search_term, max_pages)
            all_jobs.extend(jobs)
            print(f"✅ {provider.source_name}: {len(jobs)} وظيفة")
        except Exception as e:
            print(f"⚠️ {provider.source_name} فشل: {e}")
    return all_jobs

def main():
    jobs = collect_all_jobs()
    print(f"✅ تم جمع {len(jobs)} وظيفة")
    count = insert_jobs(jobs)
    print(f"✅ تم حفظ {count} وظيفة جديدة")

if __name__ == "__main__":
    main()
EOF
