# scraper/providers/forasna.py
import re
import time
import requests
from bs4 import BeautifulSoup
from .base import JobProvider

class ForasnaProvider(JobProvider):
    source_name = "forasna"

    def __init__(self, max_experience_years=None):
        self.max_experience_years = max_experience_years
        self.headers = {"User-Agent": "Mozilla/5.0"}
        self.base_url = "https://forasna.com/jobs?q={query}&page={page}"

    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> list:
        jobs = []
        for page in range(1, max_pages + 1):
            url = self.base_url.format(query=search_term.replace(' ', '+'), page=page)
            try:
                html = requests.get(url, headers=self.headers, timeout=15).text
            except Exception as e:
                print(f"⚠️ Forasna صفحة {page} فشلت: {e}")
                break
            soup = BeautifulSoup(html, 'html.parser')
            for item in soup.select('.job-item, .card, .job-card'):
                title_elem = item.select_one('.job-title a, .title a, h2 a')
                if not title_elem:
                    continue
                title = title_elem.text.strip()
                url = title_elem.get('href')
                if not url.startswith('http'):
                    url = 'https://forasna.com' + url
                company = item.select_one('.company, .company-name')
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
            time.sleep(1)
        return jobs

    def _extract_contact_info(self, url):
        try:
            html = requests.get(url, headers=self.headers, timeout=15).text
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
