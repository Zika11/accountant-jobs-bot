# scraper/providers/facebook_scraper_provider.py

import os
import re
from facebook_scraper import get_posts
from .base import JobProvider

class FacebookScraperProvider(JobProvider):
    source_name = "facebook"

    def __init__(self, max_experience_years=None):
        self.max_experience_years = max_experience_years
        self.cookies_file = os.environ.get("FACEBOOK_COOKIES_FILE", "facebook_cookies.txt")
        self.groups = [g.strip() for g in os.environ.get("FACEBOOK_GROUPS", "").split(",") if g.strip()]

    def fetch_jobs(self, search_term: str, max_pages: int = 1) -> list:
        jobs = []
        if not self.groups:
            print("⚠️ فيسبوك: مفيش جروبات محددة")
            return jobs

        if not os.path.exists(self.cookies_file):
            print(f"⚠️ فيسبوك: ملف الكوكيز '{self.cookies_file}' غير موجود")
            return jobs

        for group_id in self.groups:
            print(f"🔍 فيسبوك: جلب المنشورات من مجموعة {group_id}...")
            try:
                for post in get_posts(
                    group_id, 
                    group=True, 
                    pages=max_pages, 
                    cookies=self.cookies_file,
                    extra_info=False
                ):
                    text = post.get('text', '')
                    if not text:
                        continue

                    if not self._is_job_post(text, search_term):
                        continue

                    job = self._parse_post_to_job(post)
                    if job:
                        jobs.append(self._normalize_job(job))

            except Exception as e:
                print(f"⚠️ فيسبوك (المجموعة {group_id}) فشل: {e}")

        return jobs

    def _is_job_post(self, text: str, search_term: str) -> bool:
        keywords = ["وظيفة", "مطلوب", "فرصة عمل", "شغل", search_term]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)

    def _parse_post_to_job(self, post: dict) -> dict:
        text = post.get('text', '')
        title = text.split('\n')[0] if text else "وظيفة من فيسبوك"

        company_match = re.search(r'(?:شركة|جهة)\s*[:]\s*(.+)', text, re.IGNORECASE)
        company = company_match.group(1).strip() if company_match else ""

        location_match = re.search(r'(?:مكان|عنوان|منطقة)\s*[:]\s*(.+)', text, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else ""

        phone_match = re.search(r'(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}', text)
        phone = None
        if phone_match:
            digits = re.sub(r"\D", "", phone_match.group(0))
            if digits.startswith("20"):
                digits = "0" + digits[2:]
            phone = digits

        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        email = email_match.group(0) if email_match else None

        return {
            "title": title[:200],
            "company": company,
            "location": location,
            "posted": str(post.get('time')),
            "url": post.get('post_url', ''),
            "experience": "",
            "min_experience": None,
            "contact_email": email,
            "contact_phone": phone,
        }
