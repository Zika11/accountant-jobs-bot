import os
import re
import random

# سيتم استخدام Gemini إذا كان المفتاح موجوداً
try:
    import google.generativeai as genai
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    if GEMINI_API_KEY:
        genai.configure(api_key=GEMINI_API_KEY)
        USE_GEMINI = True
    else:
        USE_GEMINI = False
except ImportError:
    USE_GEMINI = False

def analyze_job_fit(job_description: str, user_cv_text: str) -> dict:
    """
    ترجع نسبة التوافق (0-100) ونقاط القوة والضعف.
    """
    if USE_GEMINI and GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"""
            قارن بين السيرة الذاتية التالية والوصف الوظيفي، وأعطِ:
            - نسبة التوافق (0-100)
            - 3 نقاط قوة
            - 3 نقاط ضعف
            - ملخص قصير

            السيرة الذاتية:
            {user_cv_text[:2000]}

            الوصف الوظيفي:
            {job_description[:2000]}
            """
            response = model.generate_content(prompt)
            text = response.text
            # استخراج النسبة
            match = re.search(r'نسبة التوافق:\s*(\d+)%', text)
            score = int(match.group(1)) if match else 50
            return {
                'score': score,
                'analysis': text,
                'strengths': ['تم التحليل بواسطة Gemini'],
                'weaknesses': []
            }
        except Exception as e:
            print(f"Gemini فشل: {e}")
            # في حال الفشل، ننتقل إلى الطريقة المبسطة
    
    # طريقة مبسطة (بدون AI): تحليل بسيط لكلمات مشتركة
    job_words = set(re.findall(r'\w+', job_description.lower()))
    cv_words = set(re.findall(r'\w+', user_cv_text.lower()))
    common = job_words.intersection(cv_words)
    score = int(len(common) / max(1, len(job_words)) * 100)
    # إضافة عشوائية بسيطة لتجنب النتائج المتطابقة
    score = min(100, score + random.randint(-5, 5))
    return {
        'score': score,
        'analysis': f"تحليل بسيط: يوجد {len(common)} كلمة مشتركة بين سيرتك الذاتية والوصف الوظيفي.",
        'strengths': ['تم استخدام طريقة تحليل بسيطة'],
        'weaknesses': ['للحصول على تحليل أدق، أضف مفتاح Gemini API']
    }
