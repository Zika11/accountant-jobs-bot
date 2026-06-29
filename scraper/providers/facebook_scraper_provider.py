# scraper/providers/facebook_scraper_provider.py

import os
import re
import time
import logging
from facebook_scraper import get_posts
from .base import JobProvider

logger = logging.getLogger(__name__)

class FacebookScraperProvider(JobProvider):
    source_name = "facebook"

    def __init__(self, max_experience_years=None):
        self.max_experience_years = max_experience_years
        # ملف الكوكيز بتاع حسابك الشخصي
        self.cookies_file = os.environ.get("FACEBOOK_COOKIES_FILE", "facebook_cookies.txt")
        # الجروبات اللي انت حاطط IDsها
        self.groups = [g.strip() for g in os.environ.get("FACEBOOK_GROUPS", "").split(",") if g.strip()]

    def fetch_jobs(self, search_term: str, max_pages: int = 1) -> list:
        jobs = []
        if not self.groups:
            print("⚠️ فيسبوك: مفيش جروبات محددة")
            return jobs

        # تأكد من وجود ملف الكوكيز
        if not os.path.exists(self.cookies_file):
            print(f"⚠️ فيسبوك: ملف الكوكيز '{self.cookies_file}' مش موجود!")
            print("📌 لازم تعمل Export للكوكيز من متصفحك وتحطهم في الملف")
            return jobs

        print(f"🔍 فيسبوك: جاري جلب المنشورات من {len(self.groups)} جروب...")

        for group_id in self.groups:
            print(f"  📂 جروب: {group_id}")
            try:
                # جلب المنشورات من الجروب باستخدام الكوكيز
                posts = list(get_posts(
                    group_id,
                    group=True,
                    pages=max_pages,
                    cookies=self.cookies_file,
                    extra_info=False,
                    timeout=30
                ))

                if not posts:
                    print(f"    ⚠️ مفيش منشورات في الجروب (يمكن خاص أو الكوكيز مش شغال)")
                    continue

                print(f"    ✅ {len(posts)} منشور")

                for post in posts:
                    text = post.get('text', '')
                    if not text:
                        continue

                    # فحص إذا كان المنشور عن وظيفة
                    if not self._is_job_post(text, search_term):
                        continue

                    # تحويل المنشور إلى وظيفة
                    job = self._parse_post_to_job(post)
                    if job:
                        jobs.append(self._normalize_job(job))

            except Exception as e:
                print(f"    ❌ فشل: {e}")

            time.sleep(1)  # تجنب الحظر

        print(f"✅ فيسبوك: تم جمع {len(jobs)} وظيفة")
        return jobs

    def _is_job_post(self, text: str, search_term: str) -> bool:
        """التحقق من أن المنشور عن وظيفة"""
        keywords = [
            "وظيفة", "مطلوب", "فرصة عمل", "شغل", "توظيف",
            "محاسب", "accountant", "finance", "محاسبة",
            search_term
        ]
        text_lower = text.lower()
        return any(keyword in text_lower for keyword in keywords)

    def _parse_post_to_job(self, post: dict) -> dict:
        """تحويل منشور فيسبوك إلى صيغة وظيفة"""
        text = post.get('text', '')

        # استخراج المسمى الوظيفي (أول سطر)
        lines = text.split('\n')
        title = lines[0].strip() if lines else "وظيفة من فيسبوك"
        if len(title) > 200:
            title = title[:200]

        # استخراج الشركة
        company_match = re.search(r'(?:شركة|جهة|مكان العمل)\s*[:]\s*(.+)', text, re.IGNORECASE)
        company = company_match.group(1).strip() if company_match else ""

        # استخراج الموقع
        location_match = re.search(r'(?:مكان|عنوان|منطقة|المكان)\s*[:]\s*(.+)', text, re.IGNORECASE)
        location = location_match.group(1).strip() if location_match else ""

        # استخراج رقم الهاتف
        phone_match = re.search(r'(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}', text)
        phone = None
        if phone_match:
            digits = re.sub(r"\D", "", phone_match.group(0))
            if digits.startswith("20"):
                digits = "0" + digits[2:]
            phone = digits

        # استخراج الإيميل
        email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
        email = email_match.group(0) if email_match else None

        # استخراج الخبرة (لو موجودة)
        exp_match = re.search(r'خبرة\s*(\d+)\s*سنوات', text, re.IGNORECASE)
        min_exp = None
        experience = ""
        if exp_match:
            min_exp = int(exp_match.group(1))
            experience = f"{min_exp} سنوات"

        return {
            "title": title,
            "company": company,
            "location": location,
            "posted": str(post.get('time', '')),
            "url": post.get('post_url', ''),
            "experience": experience,
            "min_experience": min_exp,
            "contact_email": email,
            "contact_phone": phone,
        }
