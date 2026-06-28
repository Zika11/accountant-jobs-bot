from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class JobProvider(ABC):
    """واجهة موحدة لجلب الوظائف من أي موقع"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        """اسم المصدر (يظهر في قاعدة البيانات)"""
        pass

    @abstractmethod
    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> List[Dict]:
        """
        يرجع قائمة بالوظائف بتنسيق موحد:
        {
            'title': str,
            'company': str,
            'location': str,
            'posted': str,
            'url': str,
            'experience': str,          # نص الخبرة (مثل '1-3 Yrs')
            'min_experience': int,      # القيمة الرقمية للفلترة (أو None)
            'contact_email': Optional[str],
            'contact_phone': Optional[str],
            'source': str               # سيتم تعبئته تلقائياً من source_name
        }
        """
        pass

    def _normalize_job(self, job: Dict) -> Dict:
        """تطبيع الحقول للتأكد من وجود كل المفاتيح"""
        defaults = {
            'title': '',
            'company': '',
            'location': '',
            'posted': '',
            'url': '',
            'experience': '',
            'min_experience': None,
            'contact_email': None,
            'contact_phone': None,
        }
        normalized = {**defaults, **job}
        normalized['source'] = self.source_name
        return normalized
