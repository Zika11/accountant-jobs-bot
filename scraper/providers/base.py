# scraper/providers/base.py
from abc import ABC, abstractmethod
from typing import List, Dict, Optional

class JobProvider(ABC):
    """واجهة موحدة لجلب الوظائف من أي موقع"""

    @property
    @abstractmethod
    def source_name(self) -> str:
        pass

    @abstractmethod
    def fetch_jobs(self, search_term: str, max_pages: int = 3) -> List[Dict]:
        pass

    def _normalize_job(self, job: Dict) -> Dict:
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

    def _location_matches(self, location: str) -> bool:
        location_filter = getattr(self, 'location_filter', [])
        if not location_filter or not location:
            return True
        location_lower = location.lower()
        return any(loc.lower() in location_lower for loc in location_filter)

    def _experience_matches(self, job: Dict) -> bool:
        max_exp = getattr(self, 'max_experience_years', None)
        if max_exp is None:
            return True
        min_exp = job.get('min_experience')
        if min_exp is None:
            return True
        return min_exp <= max_exp
