def auto_apply(job_url, user_profile):
    # افتح المتصفح باستخدام selenium
    driver = webdriver.Chrome()
    driver.get(job_url)
    # ابحث عن حقول الإدخال واملأها
    # ...
    # ثم أرسل السيرة الذاتية (رفع ملف)
    # ...
    return "تم التقديم بنجاح (محاكاة)"
