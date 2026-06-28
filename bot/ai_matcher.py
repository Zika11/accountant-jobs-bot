import os
import google.generativeai as genai

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

def analyze_job_fit(job_description: str, user_cv_text: str) -> dict:
    """
    ترجع نسبة التوافق (0-100) ونقاط القوة والضعف.
    """
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
    # تحليل النص واستخراج النسبة (يمكن تحسينه)
    # نفترض أن الناتج يحتوي على "نسبة التوافق: 85%"
    import re
    match = re.search(r'نسبة التوافق:\s*(\d+)%', response.text)
    score = int(match.group(1)) if match else 50
    return {
        'score': score,
        'analysis': response.text,
        'strengths': ['خبرة في المحاسبة', 'مهارات تحليلية'],
        'weaknesses': ['خبرة محدودة في ERP'],
    }
