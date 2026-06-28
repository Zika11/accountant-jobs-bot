# test_scraper.py
"""
سكريبت اختبار بسيط لجمع وظيفة واحدة من Wuzzuf
"""

import os
import sys
import requests
from bs4 import BeautifulSoup

# إعدادات بسيطة
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

def test_wuzzuf():
    print("🔍 جاري اختبار Wuzzuf...")
    url = "https://wuzzuf.net/search/jobs/?q=محاسب&start=0"
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        print(f"✅ تم تحميل الصفحة بنجاح (حجم: {len(response.text)} حرف)")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # جلب أول وظيفة
        links = soup.find_all("a", href=True)
        job_links = [a for a in links if "/jobs/p/" in a.get("href", "")]
        print(f"✅ عدد الوظائف في الصفحة: {len(job_links)}")
        
        if job_links:
            first_job = job_links[0]
            title = first_job.text.strip()
            href = first_job.get("href")
            full_url = href if href.startswith("http") else f"https://wuzzuf.net{href}"
            print(f"📌 أول وظيفة: {title}")
            print(f"🔗 الرابط: {full_url}")
            
            # محاولة جلب تفاصيل الوظيفة
            print("🔍 جاري جلب تفاصيل الوظيفة...")
            detail_response = requests.get(full_url, headers=HEADERS, timeout=15)
            detail_soup = BeautifulSoup(detail_response.text, 'html.parser')
            text = detail_soup.get_text(' ')
            
            # بحث عن إيميل أو رقم
            import re
            email = re.search(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', text)
            phone = re.search(r'(?:\+?20|0)\s*1[0-9](?:[\s\-]?[0-9]){8}', text)
            
            print(f"📧 إيميل: {email.group(0) if email else 'غير موجود'}")
            print(f"📱 رقم: {phone.group(0) if phone else 'غير موجود'}")
            
            return True
        else:
            print("❌ مفيش وظائف في الصفحة! ممكن هيكل الموقع اتغير.")
            return False
            
    except Exception as e:
        print(f"❌ فشل الاختبار: {e}")
        return False

def test_supabase():
    print("🔍 جاري اختبار اتصال Supabase...")
    try:
        # استيراد من db
        sys.path.append(os.path.join(os.path.dirname(__file__), "bot"))
        from db import get_client, insert_jobs
        
        client = get_client()
        print("✅ تم الاتصال بـ Supabase بنجاح")
        
        # محاولة قراءة جدول jobs
        result = client.table("jobs").select("*").limit(1).execute()
        print(f"✅ عدد الوظائف في قاعدة البيانات: {len(result.data)}")
        return True
    except Exception as e:
        print(f"❌ فشل اتصال Supabase: {e}")
        return False

def test_telegram():
    print("🔍 جاري اختبار تليجرام...")
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN_FOR_SCRAPING")
    if not bot_token:
        print("❌ TELEGRAM_BOT_TOKEN_FOR_SCRAPING غير موجود")
        return False
    
    try:
        response = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe",
            timeout=10
        )
        if response.json().get("ok"):
            print("✅ بوت تليجرام شغال")
            return True
        else:
            print("❌ بوت تليجرام مش شغال")
            return False
    except Exception as e:
        print(f"❌ فشل اختبار تليجرام: {e}")
        return False

def main():
    print("=" * 50)
    print("🧪 اختبار مكونات البوت")
    print("=" * 50)
    
    # اختبار 1: Wuzzuf
    wuzzuf_ok = test_wuzzuf()
    print("-" * 50)
    
    # اختبار 2: Supabase
    supabase_ok = test_supabase()
    print("-" * 50)
    
    # اختبار 3: تليجرام
    telegram_ok = test_telegram()
    print("-" * 50)
    
    print("📊 ملخص النتائج:")
    print(f"  ✅ Wuzzuf: {'شغال' if wuzzuf_ok else 'فاشل'}")
    print(f"  ✅ Supabase: {'شغال' if supabase_ok else 'فاشل'}")
    print(f"  ✅ تليجرام: {'شغال' if telegram_ok else 'فاشل'}")
    
    if wuzzuf_ok and supabase_ok:
        print("\n✅ كل حاجة شغالة! المشكلة في السكرابر نفسه.")
        print("🔧 الحل: هحتاج أحدث الـ selectors بتاعة Wuzzuf.")
    elif wuzzuf_ok and not supabase_ok:
        print("\n❌ مشكلة في Supabase (متغيرات البيئة أو الاتصال).")
    elif not wuzzuf_ok and supabase_ok:
        print("\n❌ مشكلة في Wuzzuf (الموقع غير متاح أو هيكله اتغير).")
    else:
        print("\n❌ مشاكل متعددة. راجع الإعدادات.")

if __name__ == "__main__":
    main()
