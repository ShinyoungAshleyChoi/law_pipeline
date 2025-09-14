"""API 데이터 모델"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List

@dataclass
class LawListItem:
    """현행법령 목록 항목"""
    law_id: str
    law_master_no: str
    law_name: str
    enforcement_date: date
    law_type: Optional[str] = None
    promulgation_date: Optional[date] = None
    ministry_name: Optional[str] = None
    revision_type: Optional[str] = None

@dataclass  
class LawContent:
    """현행법령 본문"""
    law_id: str
    law_master_no: str
    law_name: str
    content: str
    enforcement_date: date
    law_type: Optional[str] = None
    promulgation_date: Optional[date] = None

@dataclass
class LawArticle:
    """법령 조항"""
    law_master_no: str
    article_no: str
    article_content: str
    article_title: Optional[str] = None
    parent_article_no: Optional[str] = None
    article_order: int = 0

@dataclass
class APIHealthStatus:
    """API 상태"""
    is_healthy: bool
    response_time_ms: int
    last_check: datetime
    error_message: Optional[str] = None

@dataclass
class IncrementalUpdateResult:
    """증분 업데이트 결과"""
    updated_laws: List[LawListItem]
    new_law_master_nos: List[str]
    total_updated_count: int
    last_update_date: date