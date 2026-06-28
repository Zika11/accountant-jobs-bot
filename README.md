# بوت وظائف المحاسبة (Wuzzuf)

البوت ده بيجمع وظائف "محاسب" من Wuzzuf يوميًا، ويبعتلك رسالة واحدة مجمّعة بالوظائف الجديدة، وكل وظيفة تقدر تفتح تفاصيلها وتشوف أزرار:
🔗 فتح الوظيفة | 📩 واتساب | 📧 إيميل | 📝 رسالة جاهزة | 💾 حفظ | 🗑 تجاهل

**الإرسال نفسه بإيدك دايمًا** - البوت يجهزلك الرسالة والرابط بس، وانت اللي تضغط إرسال.

---

## ⚠️ ملاحظة مهمة قبل ما تبدأ

Wuzzuf معظم وظائفه بتتقدم ليها من خلال نظام التقديم الداخلي بتاعه (زرار "Apply")، ومش كل وظيفة بتحط إيميل أو رقم تليفون في الوصف.
يعني زرار "واتساب" و"إيميل" هيظهروا بس لو السكريبت لقى رقم/إيميل مكتوب فعليًا في وصف الوظيفة. لو ملقى حاجة، هيظهر زرار "فتح الوظيفة" بس، وتقدّم من صفحة Wuzzuf مباشرة (ينفعك تستخدم زرار "الرسالة الجاهزة" وتنسخها في خانة الرسالة بتاعة التقديم).

---

## الخطوات بالترتيب

### 1) Supabase (قاعدة البيانات - مجانية)
1. اعمل حساب على [supabase.com](https://supabase.com) وعمل مشروع جديد.
2. روح SQL Editor > New query، وانسخ فيه محتوى ملف `supabase_schema.sql` من المشروع وشغّله (Run).
3. من Project Settings > API، خد نسختين:
   - `Project URL` → ده `SUPABASE_URL`
   - `service_role` key → ده `SUPABASE_KEY`

### 2) بوت تليجرام
1. افتح تليجرام وابحث عن `@BotFather`.
2. ابعتله `/newbot` واتبع الخطوات (اسم البوت + username ينتهي بـ bot).
3. هيعطيك توكن شكله زي: `123456:ABC-DEF...` → ده `BOT_TOKEN`.

### 3) تجربة محلية (على لابتوبك) - اختياري بس مفيد
```bash
git clone <رابط الريبو بتاعك على GitHub>
cd accountant-jobs-bot
pip install -r requirements.txt
cp .env.example .env
# افتح .env واملأ القيم اللي جمعتها فوق
python scraper/wuzzuf_scraper.py     # يجمع الوظائف ويحفظها في Supabase
python bot/bot.py                    # يشغل البوت محليًا للتجربة
```
ابعت `/start` للبوت في تليجرام، هيرد عليك بـ `chat_id` بتاعك - خده، تحتاجه في الخطوة الجاية.

### 4) رفع المشروع على GitHub
```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin <رابط الريبو بتاعك>
git push -u origin main
```
⚠️ ملف `.env` متستبعد أوتوماتيك بفضل `.gitignore` - متحطش بياناتك السرية في كود عام (Public repo).

### 5) GitHub Secrets (لتشغيل السكرابر يوميًا)
في صفحة الريبو على GitHub: Settings > Secrets and variables > Actions > New repository secret
- أضف `SUPABASE_URL`
- أضف `SUPABASE_KEY`
- أضف `BOT_TOKEN` (نفس توكن البوت)
- أضف `TELEGRAM_CHAT_ID` (اللي خدته من /start)

آخر اتنين دول مش إلزاميين، بس لو حطيتهم هيبعتلك السكرابر تنبيه على تليجرام لو فشل (أو رسالة تأكيد لو نجح).

الـ workflow في `.github/workflows/scrape.yml` هيشغل السكرابر تلقائيًا كل يوم الساعة 9 صباحًا (توقيت مصر)، وتقدر كمان تشغله يدويًا من تبويب Actions > Daily Wuzzuf Scrape > Run workflow.

### 6) Railway (تشغيل البوت 24/7)
1. اعمل حساب على [railway.app](https://railway.app) (مجاني لحد سقف استخدام معين).
2. New Project > Deploy from GitHub repo > اختار الريبو بتاعك.
3. Railway هيكتشف `Procfile` و `requirements.txt` لوحده.
4. من تبويب Variables، ضيف كل المتغيرات اللي في `.env.example`:
   - `SUPABASE_URL`, `SUPABASE_KEY`
   - `BOT_TOKEN`
   - `TELEGRAM_CHAT_ID` (اللي خدته من خطوة /start)
   - `APPLICANT_NAME`, `APPLICANT_PHONE`, `APPLICANT_EMAIL`, `APPLICANT_SUMMARY`
   - اختياري: `MAX_EXPERIENCE_YEARS` (لو عايز تستبعد الوظائف اللي تطلب خبرة أكتر من اللي عندك)
5. Deploy. البوت هيفضل شغال ويبعتلك رسالة وظائف جديدة كل 6 ساعات تلقائيًا (تقدر تغيّر `NOTIFY_INTERVAL_SECONDS`).

---

## أوامر البوت
- `/start` — تسجيل + معرفة chat_id بتاعك
- `/jobs` — يجيبلك آخر الوظائف فورًا (رسالة مجمّعة + تفاصيل عند الطلب)
- `/search كلمة` — بحث في الوظائف، مثلاً: `/search محاسب أول`
- `/saved` — الوظائف اللي حفظتها قبل كده
- `/ignored` — الوظائف اللي تجاهلتها قبل كده
- `/stats` — إحصائيات عامة (إجمالي، محفوظة، فيها تواصل مباشر... إلخ)
- `/setcv` — تبعت ملف CV (PDF) مرة واحدة، وبعدها البوت يبعته جنب كل رسالة تقديم

---

## إضافات ممكنة بعدين
- إضافة Forasna كمصدر تاني للوظائف
- لوحة تحكم (Dashboard) بصفحة ويب بدل ما يكون كله جوه تليجرام
- دعم عدة مستخدمين (لو حبيت تشارك البوت مع زمايلك)
