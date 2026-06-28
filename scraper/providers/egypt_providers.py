# scraper/providers/egypt_providers.py
"""
كل المزودات المصرية في ملف واحد:
- Jobzella (HTML)
- EgyptianJobs (HTML)
- CareerEgypt (HTML)
- Telegram (API)
- Facebook (RSS/API)
"""

import os
import re
import time
import requests
from bs4 import BeautifulSoup
from .base import JobProvider


# ============================================
# 1. Jobzella (موقع مصري)
# ============================================
class JobzellaProvider(JobProvider):
    source_name = "jobzella"

    def __init__(self, max_experience_years=None):
        self.max_experience_years = max_experience_years
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.base_url = "https://www.jobzella.com/en/jobs?keywords={query}&page={page}"

    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> list:
        jobs = []
        for page in range(1, max_pages + 1):
            url = self.base_url.format(query=search_term.replace(' ', '%20'), page=page)
            try:
                html = self._fetch_html(url)
            except Exception as e:
                print(f"⚠️ Jobzella صفحة {page} فشلت: {e}")
                break
            soup = BeautifulSoup(html, 'html.parser')
            for item in soup.select('li.job-item, .job-card, .job-listing'):
                title_elem = item.select_one('.job-title a, .title a, h2 a')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                url = title_elem.get('href')
                if url and not url.startswith('http'):
                    url = 'https://www.jobzella.com' + url
                company = item.select_one('.company-name, .company')
                company = company.text.strip() if company else ''
                location = item.select_one('.location, .city')
                location = location.text.strip() if location else ''
                exp_elem = item.select_one('.experience, .exp')
                experience = exp_elem.text.strip() if exp_elem else ''
                min_exp = None
                if experience:
                    nums = re.findall(r'\d+', experience)
                    if nums:
                        min_exp = int(nums[0])
                job = {
                    'title': title,
                    'company': company,
                    'location': location,
                    'posted': '',
                    'url': url,
                    'experience': experience,
                    'min_experience': min_exp,
                }
                job.update(self._extract_contact_info(url))
                jobs.append(self._normalize_job(job))
            time.sleep(1.5)
        return jobs

    def _fetch_html(self, url, retries=3):
        for attempt in range(1, retries+1):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                if attempt == retries:
                    raise
                time.sleep(3 * (2 ** (attempt-1)))

    def _extract_contact_info(self, url):
        try:
            html = self._fetch_html(url)
            text = BeautifulSoup(html, 'html.parser').get_text(' ')
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            phone_match = re.search(r'(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}', text)
            clean_phone = None
            if phone_match:
                digits = re.sub(r"\D", "", phone_match.group(0))
                if digits.startswith("20"):
                    digits = "0" + digits[2:]
                clean_phone = digits
            return {
                'contact_email': email_match.group(0) if email_match else None,
                'contact_phone': clean_phone,
            }
        except:
            return {}


# ============================================
# 2. EgyptianJobs (موقع مصري)
# ============================================
class EgyptianJobsProvider(JobProvider):
    source_name = "egyptianjobs"

    def __init__(self, max_experience_years=None):
        self.max_experience_years = max_experience_years
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.base_url = "https://egyptianjobs.com/search?q={query}&page={page}"

    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> list:
        jobs = []
        for page in range(1, max_pages + 1):
            url = self.base_url.format(query=search_term.replace(' ', '+'), page=page)
            try:
                html = self._fetch_html(url)
            except Exception as e:
                print(f"⚠️ EgyptianJobs صفحة {page} فشلت: {e}")
                break
            soup = BeautifulSoup(html, 'html.parser')
            for item in soup.select('.job-item, .job-card, .listing-item'):
                title_elem = item.select_one('.job-title a, .title a, h2 a')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                url = title_elem.get('href')
                if url and not url.startswith('http'):
                    url = 'https://egyptianjobs.com' + url
                company = item.select_one('.company-name, .company')
                company = company.text.strip() if company else ''
                location = item.select_one('.location, .city')
                location = location.text.strip() if location else ''
                exp_elem = item.select_one('.experience, .exp')
                experience = exp_elem.text.strip() if exp_elem else ''
                min_exp = None
                if experience:
                    nums = re.findall(r'\d+', experience)
                    if nums:
                        min_exp = int(nums[0])
                job = {
                    'title': title,
                    'company': company,
                    'location': location,
                    'posted': '',
                    'url': url,
                    'experience': experience,
                    'min_experience': min_exp,
                }
                job.update(self._extract_contact_info(url))
                jobs.append(self._normalize_job(job))
            time.sleep(1.5)
        return jobs

    def _fetch_html(self, url, retries=3):
        for attempt in range(1, retries+1):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                if attempt == retries:
                    raise
                time.sleep(3 * (2 ** (attempt-1)))

    def _extract_contact_info(self, url):
        try:
            html = self._fetch_html(url)
            text = BeautifulSoup(html, 'html.parser').get_text(' ')
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            phone_match = re.search(r'(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}', text)
            clean_phone = None
            if phone_match:
                digits = re.sub(r"\D", "", phone_match.group(0))
                if digits.startswith("20"):
                    digits = "0" + digits[2:]
                clean_phone = digits
            return {
                'contact_email': email_match.group(0) if email_match else None,
                'contact_phone': clean_phone,
            }
        except:
            return {}


# ============================================
# 3. CareerEgypt (موقع مصري)
# ============================================
class CareerEgyptProvider(JobProvider):
    source_name = "careeregypt"

    def __init__(self, max_experience_years=None):
        self.max_experience_years = max_experience_years
        self.headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        self.base_url = "https://www.careeregypt.com/jobs?keywords={query}&page={page}"

    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> list:
        jobs = []
        for page in range(1, max_pages + 1):
            url = self.base_url.format(query=search_term.replace(' ', '+'), page=page)
            try:
                html = self._fetch_html(url)
            except Exception as e:
                print(f"⚠️ CareerEgypt صفحة {page} فشلت: {e}")
                break
            soup = BeautifulSoup(html, 'html.parser')
            for item in soup.select('.job-item, .job-card, .card'):
                title_elem = item.select_one('.job-title a, .title a, h2 a')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                url = title_elem.get('href')
                if url and not url.startswith('http'):
                    url = 'https://www.careeregypt.com' + url
                company = item.select_one('.company-name, .company')
                company = company.text.strip() if company else ''
                location = item.select_one('.location, .city')
                location = location.text.strip() if location else ''
                exp_elem = item.select_one('.experience, .exp')
                experience = exp_elem.text.strip() if exp_elem else ''
                min_exp = None
                if experience:
                    nums = re.findall(r'\d+', experience)
                    if nums:
                        min_exp = int(nums[0])
                job = {
                    'title': title,
                    'company': company,
                    'location': location,
                    'posted': '',
                    'url': url,
                    'experience': experience,
                    'min_experience': min_exp,
                }
                job.update(self._extract_contact_info(url))
                jobs.append(self._normalize_job(job))
            time.sleep(1.5)
        return jobs

    def _fetch_html(self, url, retries=3):
        for attempt in range(1, retries+1):
            try:
                resp = requests.get(url, headers=self.headers, timeout=15)
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                if attempt == retries:
                    raise
                time.sleep(3 * (2 ** (attempt-1)))

    def _extract_contact_info(self, url):
        try:
            html = self._fetch_html(url)
            text = BeautifulSoup(html, 'html.parser').get_text(' ')
            email_match = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            phone_match = re.search(r'(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}', text)
            clean_phone = None
            if phone_match:
                digits = re.sub(r"\D", "", phone_match.group(0))
                if digits.startswith("20"):
                    digits = "0" + digits[2:]
                clean_phone = digits
            return {
                'contact_email': email_match.group(0) if email_match else None,
                'contact_phone': clean_phone,
            }
        except:
            return {}


# ============================================
# 4. تليجرام (API)
# ============================================
class TelegramProvider(JobProvider):
    source_name = "telegram"

    def __init__(self):
        self.bot_token = os.environ.get("TELEGRAM_BOT_TOKEN_FOR_SCRAPING")
        self.channels = os.environ.get("TELEGRAM_CHANNELS", "").split(",")
        self.base_url = f"https://api.telegram.org/bot{self.bot_token}"

    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> list:
        jobs = []
        if not self.bot_token or not self.channels or not self.channels[0]:
            print("⚠️ تليجرام: مفيش توكن أو قنوات محددة")
            return jobs

        for channel in self.channels:
            channel = channel.strip()
            if not channel:
                continue
            try:
                # جلب آخر الرسائل من القناة
                response = requests.get(
                    f"{self.base_url}/getUpdates",
                    params={"chat_id": f"@{channel}", "limit": 50},
                    timeout=30
                )
                data = response.json()
                if not data.get("ok"):
                    continue
                for msg in data.get("result", []):
                    text = msg.get("message", {}).get("text", "")
                    if search_term in text.lower() or "وظيفة" in text or "محاسب" in text:
                        job = self._parse_message(text, channel)
                        if job:
                            jobs.append(self._normalize_job(job))
            except Exception as e:
                print(f"⚠️ تليجرام ({channel}) فشل: {e}")
            time.sleep(1)
        return jobs

    def _parse_message(self, text: str, channel: str) -> dict:
        # استخراج المعلومات من الرسالة
        title_match = re.search(r"(?:وظيفة|مطلوب)\s*(.+?)(?:\n|$)", text, re.I)
        title = title_match.group(1).strip() if title_match else "وظيفة جديدة"
        
        company_match = re.search(r"(?:شركة|جهة)\s*[::]\s*(.+?)(?:\n|$)", text, re.I)
        company = company_match.group(1).strip() if company_match else ""
        
        location_match = re.search(r"(?:مكان|عنوان|منطقة)\s*[::]\s*(.+?)(?:\n|$)", text, re.I)
        location = location_match.group(1).strip() if location_match else ""
        
        # استخراج الرقم
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
        
        # استخراج الرابط (لو موجود)
        link_match = re.search(r'(https?://[^\s]+)', text)
        url = link_match.group(0) if link_match else f"https://t.me/{channel}"
        
        return {
            "title": title,
            "company": company,
            "location": location,
            "posted": "",
            "url": url,
            "experience": "",
            "min_experience": None,
            "contact_email": email,
            "contact_phone": phone,
        }


# ============================================
# 5. فيسبوك (RSS/API) - معدل لدعم 50 جروب
# ============================================
class FacebookProvider(JobProvider):
    source_name = "facebook"

    def __init__(self):
        self.access_token = os.environ.get("FACEBOOK_ACCESS_TOKEN")
        groups_raw = os.environ.get("FACEBOOK_GROUPS", "")
        # تقسيم الجروبات مع تجاهل القيم الفارغة
        self.groups = [g.strip() for g in groups_raw.split(",") if g.strip()]
        self.base_url = "https://graph.facebook.com/v18.0"
        self.max_groups_per_run = int(os.environ.get("FACEBOOK_MAX_GROUPS", 10))  # 🔥 حد أقصى 10 جروبات لكل تشغيلة

    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> list:
        jobs = []
        if not self.access_token or not self.groups:
            print("⚠️ فيسبوك: مفيش توكن أو جروبات محددة")
            return jobs

        # خذ أول max_groups_per_run جروب بس (عشان الأداء)
        active_groups = self.groups[:self.max_groups_per_run]
        print(f"📱 فيسبوك: هنجيب من {len(active_groups)} جروب (من أصل {len(self.groups)})")

        for group in active_groups:
            try:
                url = f"{self.base_url}/{group}/feed"
                params = {
                    "access_token": self.access_token,
                    "fields": "message,created_time,from,permalink_url",
                    "limit": 20
                }
                response = requests.get(url, params=params, timeout=60)  # زودنا الـ timeout
                data = response.json()
                
                if "error" in data:
                    print(f"⚠️ فيسبوك جروب {group} خطأ: {data['error'].get('message', '')}")
                    continue
                    
                for post in data.get("data", []):
                    text = post.get("message", "")
                    if not text:
                        continue
                    if search_term in text.lower() or "وظيفة" in text or "محاسب" in text or "مطلوب" in text:
                        job = self._parse_post(text, post)
                        if job:
                            jobs.append(self._normalize_job(job))
            except Exception as e:
                print(f"⚠️ فيسبوك جروب {group} فشل: {e}")
            time.sleep(1.5)  # تأخير بين الجروبات عشان ما نتعملش Block
        return jobs

    def _parse_post(self, text: str, post: dict) -> dict:
        # استخراج المعلومات
        title_match = re.search(r"(?:وظيفة|مطلوب|فرصة عمل)\s*(.+?)(?:\n|$)", text, re.I)
        title = title_match.group(1).strip() if title_match else "وظيفة جديدة"
        
        company_match = re.search(r"(?:شركة|جهة|لجهة)\s*[::\-]\s*(.+?)(?:\n|$)", text, re.I)
        company = company_match.group(1).strip() if company_match else ""
        
        location_match = re.search(r"(?:مكان|عنوان|منطقة|محافظة)\s*[::\-]\s*(.+?)(?:\n|$)", text, re.I)
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
            "title": title,
            "company": company,
            "location": location,
            "posted": post.get("created_time", ""),
            "url": post.get("permalink_url", ""),
            "experience": "",
            "min_experience": None,
            "contact_email": email,
            "contact_phone": phone,
        }
