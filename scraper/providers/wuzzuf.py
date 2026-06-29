# scraper/providers/wuzzuf.py
import re
import time
from urllib.parse import quote
import requests
from bs4 import BeautifulSoup
from .base import JobProvider

class WuzzufProvider(JobProvider):  # ✅ الاسم الصحيح
    source_name = "wuzzuf"

    def __init__(self, location_filter=None, max_experience_years=None):
        self.location_filter = location_filter or []
        self.max_experience_years = max_experience_years
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        self.search_url = "https://wuzzuf.net/search/jobs/?q={query}&start={page}"
        self.email_re = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
        self.phone_re = re.compile(r"(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}")
        self.phone_context_re = re.compile(
            r"(?:واتساب|واتس|للتواصل|تواصل|اتصل|موبايل|تليفون|رقم)\D{0,15}((?:\+?20|0)?\s*1[0-9](?:[\s\-]?[0-9]){8})"
        )
        self.exp_range_re = re.compile(r"(\d+)\s*-\s*(\d+)\s*Yrs?\s*of\s*Exp", re.IGNORECASE)
        self.exp_plus_re = re.compile(r"(\d+)\+\s*Yrs?\s*of\s*Exp", re.IGNORECASE)
        self.exp_arabic_re = re.compile(r'خبرة\s*(\d+)\s*سنوات', re.IGNORECASE)
        self.exp_more_than_re = re.compile(r'أكثر من\s*(\d+)\s*سنوات', re.IGNORECASE)

    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> list:
        all_jobs = []
        for page in range(max_pages):
            url = self.search_url.format(query=quote(search_term), page=page)
            try:
                html = self._fetch_html(url)
            except Exception as e:
                print(f"⚠️ Wuzzuf فشل في الصفحة {page}: {e}")
                break
            page_jobs = self._parse_listing_page(html)
            if not page_jobs:
                break
            for job in page_jobs:
                if not self._location_matches(job.get('location', '')):
                    continue
                if not self._experience_matches(job):
                    continue
                days_old = job.get('days_old', 99)
                if days_old > 10:
                    continue
                details = self._extract_contact_info(job['url'])
                job.update(details)
                all_jobs.append(self._normalize_job(job))
            time.sleep(2)
        all_jobs.sort(key=lambda x: x.get('days_old', 99))
        return all_jobs

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

    def _parse_listing_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        jobs = []
        seen = set()
        for link in soup.find_all("a", href=re.compile(r"/jobs/p/")):
            title = link.get_text(strip=True)
            href = link.get("href", "")
            if not title or href in seen:
                continue
            seen.add(href)
            full_url = href if href.startswith("http") else f"https://wuzzuf.net{href}"
            card = link
            for _ in range(3):
                if card.parent:
                    card = card.parent
            full_card_text = card.get_text(separator=" ", strip=True)
            parts = [p for p in card.get_text(separator="|", strip=True).split("|") if p]
            company, location, posted = "", "", ""
            for part in parts:
                if re.search(r"\bago\b", part, re.IGNORECASE) or "منذ" in part:
                    posted = part
                elif "Egypt" in part:
                    company, location = (part.split(" - ", 1) + [""])[:2] if " - " in part else ("", part)
            job = {
                "title": title,
                "company": company.strip(),
                "location": location.strip(),
                "posted": posted.strip(),
                "url": full_url,
            }
            exp_info = self._extract_experience(full_card_text)
            job.update(exp_info)
            job['days_old'] = self._parse_posted_date(posted)
            job['source'] = 'wuzzuf'
            jobs.append(job)
        return jobs

    def _extract_experience(self, card_text: str) -> dict:
        range_match = self.exp_range_re.search(card_text)
        if range_match:
            min_exp = int(range_match.group(1))
            return {"experience": f"{min_exp} - {range_match.group(2)} Yrs", "min_experience": min_exp}
        plus_match = self.exp_plus_re.search(card_text)
        if plus_match:
            min_exp = int(plus_match.group(1))
            return {"experience": f"{min_exp}+ Yrs", "min_experience": min_exp}
        arabic_match = self.exp_arabic_re.search(card_text)
        if arabic_match:
            min_exp = int(arabic_match.group(1))
            return {"experience": f"{min_exp} سنوات", "min_experience": min_exp}
        more_than_match = self.exp_more_than_re.search(card_text)
        if more_than_match:
            min_exp = int(more_than_match.group(1))
            return {"experience": f"{min_exp}+ سنوات", "min_experience": min_exp}
        if "entry level" in card_text.lower():
            return {"experience": "Entry Level", "min_experience": 0}
        return {"experience": "", "min_experience": 99}

    def _parse_posted_date(self, posted_text: str) -> int:
        if not posted_text:
            return 99
        posted_text = posted_text.lower()
        days_match = re.search(r'(\d+)\s*يوم', posted_text)
        if days_match:
            return int(days_match.group(1))
        hours_match = re.search(r'(\d+)\s*ساعة', posted_text)
        if hours_match:
            return 0
        mins_match = re.search(r'(\d+)\s*دقيقة', posted_text)
        if mins_match:
            return 0
        if 'today' in posted_text or 'اليوم' in posted_text:
            return 0
        if 'yesterday' in posted_text or 'أمس' in posted_text:
            return 1
        return 99

    def _extract_contact_info(self, job_url):
        try:
            html = self._fetch_html(job_url)
        except:
            return {}
        text = BeautifulSoup(html, "html.parser").get_text(" ")
        email_match = self.email_re.search(text)
        phone_match = self.phone_context_re.search(text)
        if not phone_match:
            phone_match = self.phone_re.search(text)
        raw_phone = phone_match.group(1) if phone_match and phone_match.groups() else (phone_match.group(0) if phone_match else None)
        clean_phone = None
        if raw_phone:
            digits = re.sub(r"\D", "", raw_phone)
            if digits.startswith("20"):
                digits = "0" + digits[2:]
            clean_phone = digits
        return {
            "contact_email": email_match.group(0) if email_match else None,
            "contact_phone": clean_phone,
        }

    def _location_matches(self, location):
        if not self.location_filter:
            return True
        return any(loc.lower() in location.lower() for loc in self.location_filter)

    def _experience_matches(self, job):
        if self.max_experience_years is None:
            return True
        min_exp = job.get('min_experience')
        if min_exp is None:
            return False
        return min_exp <= self.max_experience_years
