"""
سكريبت جمع وظائف "محاسب" من Wuzzuf
"""

import csv
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
load_dotenv()

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "bot"))

SEARCH_TERM = os.environ.get("SEARCH_TERM", "محاسب")
MAX_PAGES = int(os.environ.get("MAX_PAGES", 3))
DELAY_BETWEEN_REQUESTS = float(os.environ.get("DELAY_BETWEEN_REQUESTS", 2.0))
MAX_RETRIES = int(os.environ.get("MAX_RETRIES", 3))
RETRY_BASE_DELAY = float(os.environ.get("RETRY_BASE_DELAY", 3.0))
OUTPUT_CSV = "wuzzuf_jobs.csv"

LOCATION_FILTER = [
    loc.strip() for loc in os.environ.get("LOCATION_FILTER", "Cairo,Giza,Menoufia").split(",") if loc.strip()
]

_max_exp_raw = os.environ.get("MAX_EXPERIENCE_YEARS", "").strip()
MAX_EXPERIENCE_YEARS = int(_max_exp_raw) if _max_exp_raw.isdigit() else None
EXPIRE_DAYS = int(os.environ.get("EXPIRE_DAYS", 14))
BOT_TOKEN = os.environ.get("BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
NOTIFY_ON_SUCCESS = os.environ.get("NOTIFY_ON_SUCCESS", "true").lower() == "true"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
}

SEARCH_URL = "https://wuzzuf.net/search/jobs/?q={query}&start={page}"
EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(r"(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}")
PHONE_CONTEXT_RE = re.compile(
    r"(?:واتساب|واتس|للتواصل|تواصل|اتصل|موبايل|تليفون|رقم)\D{0,15}((?:\+?20|0)?\s*1[0-9](?:[\s\-]?[0-9]){8})"
)
EXPERIENCE_RANGE_RE = re.compile(r"(\d+)\s*-\s*(\d+)\s*Yrs?\s*of\s*Exp", re.IGNORECASE)
EXPERIENCE_PLUS_RE = re.compile(r"(\d+)\+\s*Yrs?\s*of\s*Exp", re.IGNORECASE)

ARABIC_DIGITS = "٠١٢٣٤٥٦٧٨٩"
WESTERN_DIGITS = "0123456789"
ARABIC_TO_WESTERN = str.maketrans(ARABIC_DIGITS, WESTERN_DIGITS)


def normalize_digits(text: str) -> str:
    return text.translate(ARABIC_TO_WESTERN)


def clean_phone(raw: str) -> str:
    digits = re.sub(r"\D", "", raw)
    if digits.startswith("20"):
        digits = "0" + digits[2:]
    return digits


def extract_experience(card_text: str) -> dict:
    range_match = EXPERIENCE_RANGE_RE.search(card_text)
    if range_match:
        min_exp = int(range_match.group(1))
        max_exp = int(range_match.group(2))
        return {"experience": f"{min_exp} - {max_exp} Yrs of Exp", "min_experience": min_exp}
    plus_match = EXPERIENCE_PLUS_RE.search(card_text)
    if plus_match:
        min_exp = int(plus_match.group(1))
        return {"experience": f"{min_exp}+ Yrs of Exp", "min_experience": min_exp}
    if "entry level" in card_text.lower():
        return {"experience": "Entry Level", "min_experience": 0}
    return {"experience": "", "min_experience": None}


def fetch_html(url: str) -> str:
    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            last_error = e
            if attempt < MAX_RETRIES:
                wait = RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  ⏳ محاولة {attempt} فشلت ({e}) - بنحاول تاني بعد {wait:.0f} ثانية")
                time.sleep(wait)
    raise last_error


def parse_listing_page(html: str) -> list[dict]:
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
            if re.search(r"\bago\b", part, re.IGNORECASE):
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
        job.update(extract_experience(full_card_text))
        job["source"] = "wuzzuf"
        jobs.append(job)
    return jobs


def location_matches(location: str) -> bool:
    if not LOCATION_FILTER:
        return True
    return any(loc.lower() in location.lower() for loc in LOCATION_FILTER)


def experience_matches(job: dict) -> bool:
    if MAX_EXPERIENCE_YEARS is None:
        return True
    min_exp = job.get("min_experience")
    if min_exp is None:
        return True
    return min_exp <= MAX_EXPERIENCE_YEARS


def extract_contact_info(job_url: str) -> dict:
    try:
        html = fetch_html(job_url)
    except requests.RequestException:
        return {}
    text = normalize_digits(BeautifulSoup(html, "html.parser").get_text(" "))
    email_match = EMAIL_RE.search(text)
    phone_match = PHONE_CONTEXT_RE.search(text)
    raw_phone = phone_match.group(1) if phone_match else None
    if not raw_phone:
        generic_match = PHONE_RE.search(text)
        raw_phone = generic_match.group(0) if generic_match else None
    return {
        "contact_email": email_match.group(0) if email_match else None,
        "contact_phone": clean_phone(raw_phone) if raw_phone else None,
    }


def collect_jobs() -> list[dict]:
    all_jobs = []
    for page in range(MAX_PAGES):
        print(f"📄 صفحة {page + 1} ...")
        try:
            html = fetch_html(SEARCH_URL.format(query=quote(SEARCH_TERM), page=page))
        except requests.RequestException as e:
            print(f"⚠️ فشل تحميل الصفحة بعد {MAX_RETRIES} محاولات: {e}")
            break
        page_jobs = parse_listing_page(html)
        if not page_jobs:
            print("لا يوجد وظائف أكتر — توقفنا.")
            break
        filtered_jobs = []
        for job in page_jobs:
            if not location_matches(job["location"]):
                continue
            if not experience_matches(job):
                continue
            filtered_jobs.append(job)
        if filtered_jobs:
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {executor.submit(extract_contact_info, job["url"]): job for job in filtered_jobs}
                for future in as_completed(futures):
                    job = futures[future]
                    job.update(future.result())
                    all_jobs.append(job)
        time.sleep(DELAY_BETWEEN_REQUESTS)
    return all_jobs


def save_csv(jobs: list[dict], path: str):
    if not jobs:
        return
    fieldnames = ["title", "company", "location", "experience", "posted", "url", "contact_email", "contact_phone", "source", "min_experience"]
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(jobs)


def push_to_supabase(jobs: list[dict]) -> bool:
    try:
        from db import insert_jobs
    except Exception as e:
        print(f"⚠️ مفيش اتصال بـ Supabase ({e}) - هحفظ في CSV بس")
        return False
    try:
        count = insert_jobs(jobs)
        print(f"✅ اتحفظ في Supabase: {count} وظيفة جديدة")
        return True
    except Exception as e:
        print(f"⚠️ فشل الحفظ في Supabase: {e}")
        return False


def notify_telegram(text: str):
    if not BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text},
            timeout=10,
        )
    except requests.RequestException as e:
        print(f"⚠️ فشل إرسال تنبيه تليجرام: {e}")


def main():
    try:
        jobs = collect_jobs()
    except Exception as e:
        print(f"❌ السكرابر فشل بالكامل: {e}")
        notify_telegram(f"❌ سكرابر Wuzzuf فشل اليوم:\n{e}")
        raise

    print(f"\n✅ إجمالي الوظائف بعد الفلترة: {len(jobs)}\n")
    for j in jobs:
        exp_text = f" | {j['experience']}" if j.get("experience") else ""
        print(f"- {j['title']} | {j['company']} | {j['location']}{exp_text}")
        print(f"  {j['url']}")
        if j.get("contact_email") or j.get("contact_phone"):
            print(f"  📧 {j.get('contact_email') or '-'}  📱 {j.get('contact_phone') or '-'}")
        print()

    pushed = push_to_supabase(jobs)
    if not pushed:
        save_csv(jobs, OUTPUT_CSV)
        print(f"💾 الوظائف محفوظة محليًا في: {OUTPUT_CSV}")
    else:
        try:
            from db import expire_old_jobs
            expired_count = expire_old_jobs(days=EXPIRE_DAYS)
            if expired_count:
                print(f"🧹 اتقفلت {expired_count} وظيفة قديمة (أكتر من {EXPIRE_DAYS} يوم)")
        except Exception as e:
            print(f"⚠️ فشل تنظيف الوظائف القديمة: {e}")

    if NOTIFY_ON_SUCCESS:
        contacts_found = sum(1 for j in jobs if j.get("contact_email") or j.get("contact_phone"))
        notify_telegram(
            f"✅ تم جمع {len(jobs)} وظيفة محاسبة اليوم ({contacts_found} منهم فيها وسيلة تواصل مباشرة).\n"
            f"استخدم /jobs في البوت عشان تشوفهم."
        )


if __name__ == "__main__":
    main()
