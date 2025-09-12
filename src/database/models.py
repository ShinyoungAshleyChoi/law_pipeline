"""데이터베이스 모델 정의"""
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, List
from enum import Enum

class JobStatus(Enum):
    """배치 작업 상태"""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"

class JobType(Enum):
    """배치 작업 유형"""
    FULL_SYNC = "FULL_SYNC"
    INCREMENTAL_SYNC = "INCREMENTAL_SYNC"
    VALIDATION = "VALIDATION"

class SyncType(Enum):
    """동기화 유형"""
    FULL = "FULL"
    INCREMENTAL = "INCREMENTAL"

@dataclass
class LawList:
    """법령 목록 조회 모델 (API 응답 기반)"""
    id: Optional[int] = None
    # API 응답 필드들
    target: Optional[str] = None  # 검색서비스 대상
    keyword: Optional[str] = None  # 검색어
    section: Optional[str] = None  # 검색범위
    total_cnt: Optional[int] = None  # 검색건수
    page: Optional[int] = None  # 결과페이지번호
    law_id: Optional[int] = None  # 법령ID
    law_serial_no: Optional[int] = None  # 법령일련번호
    current_history_code: Optional[str] = None  # 현행연혁코드
    law_name_korean: Optional[str] = None  # 법령명한글
    law_abbr_name: Optional[str] = None  # 법령약칭명
    promulgation_date: Optional[int] = None  # 공포일자 (YYYYMMDD)
    promulgation_no: Optional[int] = None  # 공포번호
    revision_type: Optional[str] = None  # 제개정구분명
    ministry_name: Optional[str] = None  # 소관부처명
    ministry_code: Optional[int] = None  # 소관부처코드
    law_type_name: Optional[str] = None  # 법령구분명
    joint_ministry_type: Optional[str] = None  # 공동부령구분
    joint_promulgation_no: Optional[str] = None  # 공포번호(공동부령의 공포번호)
    enforcement_date: Optional[int] = None  # 시행일자 (YYYYMMDD)
    self_other_law_yn: Optional[str] = None  # 자법타법여부
    law_detail_link: Optional[str] = None  # 법령상세링크
    # 내부 관리 필드
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class LawContent:
    """법령 본문 조회 모델 (API 응답 기반)"""
    id: Optional[int] = None
    # 기본 법령 정보
    law_id: Optional[int] = None  # 법령ID
    promulgation_date: Optional[int] = None  # 공포일자 (YYYYMMDD)
    promulgation_no: Optional[int] = None  # 공포번호
    language: Optional[str] = None  # 언어종류
    law_type: Optional[str] = None  # 법종구분
    law_type_code: Optional[str] = None  # 법종구분코드
    law_name_korean: Optional[str] = None  # 법령명_한글
    law_name_hanja: Optional[str] = None  # 법령명_한자
    law_abbr_name: Optional[str] = None  # 법령명약칭
    title_change_yn: Optional[str] = None  # 제명변경여부
    korean_law_yn: Optional[str] = None  # 한글법령여부
    chapter_section_no: Optional[int] = None  # 편장절관 일련번호
    ministry_code: Optional[int] = None  # 소관부처코드
    ministry_name: Optional[str] = None  # 소관부처명
    phone_number: Optional[str] = None  # 전화번호
    enforcement_date: Optional[int] = None  # 시행일자 (YYYYMMDD)
    revision_type: Optional[str] = None  # 제개정구분
    appendix_edit_yn: Optional[str] = None  # 별표편집여부
    promulgated_law_yn: Optional[str] = None  # 공포법령여부
    department_name: Optional[str] = None  # 부서명
    department_phone: Optional[str] = None  # 부서연락처
    joint_ministry_type: Optional[str] = None  # 공동부령구분
    joint_type_code: Optional[str] = None  # 구분코드(공동부령구분 구분코드)
    joint_promulgation_no: Optional[str] = None  # 공포번호(공동부령의 공포번호)
    
    # 조문 정보
    article_no: Optional[int] = None  # 조문번호
    article_sub_no: Optional[int] = None  # 조문가지번호
    article_yn: Optional[str] = None  # 조문여부
    article_title: Optional[str] = None  # 조문제목
    article_enforcement_date: Optional[int] = None  # 조문시행일자
    article_revision_type: Optional[str] = None  # 조문제개정유형
    article_move_before: Optional[int] = None  # 조문이동이전
    article_move_after: Optional[int] = None  # 조문이동이후
    article_change_yn: Optional[str] = None  # 조문변경여부
    article_content: Optional[str] = None  # 조문내용
    
    # 항 정보
    paragraph_no: Optional[int] = None  # 항번호
    paragraph_revision_type: Optional[str] = None  # 항제개정유형
    paragraph_revision_date_str: Optional[str] = None  # 항제개정일자문자열
    paragraph_content: Optional[str] = None  # 항내용
    
    # 호 정보
    item_no: Optional[int] = None  # 호번호
    item_content: Optional[str] = None  # 호내용
    
    # 참고자료 및 부칙
    article_reference: Optional[str] = None  # 조문참고자료
    addendum_promulgation_date: Optional[int] = None  # 부칙공포일자
    addendum_promulgation_no: Optional[int] = None  # 부칙공포번호
    addendum_content: Optional[str] = None  # 부칙내용
    
    # 별표 정보
    appendix_no: Optional[int] = None  # 별표번호
    appendix_sub_no: Optional[int] = None  # 별표가지번호
    appendix_type: Optional[str] = None  # 별표구분
    appendix_title: Optional[str] = None  # 별표제목
    appendix_form_file_link: Optional[str] = None  # 별표서식파일링크
    appendix_hwp_filename: Optional[str] = None  # 별표HWP파일명
    appendix_pdf_file_link: Optional[str] = None  # 별표서식PDF파일링크
    appendix_pdf_filename: Optional[str] = None  # 별표PDF파일명
    appendix_image_filename: Optional[str] = None  # 별표이미지파일명
    appendix_content: Optional[str] = None  # 별표내용
    
    # 개정 정보
    revision_content: Optional[str] = None  # 개정문내용
    revision_reason: Optional[str] = None  # 제개정이유내용
    
    # 내부 관리 필드
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

@dataclass
class LawArticle:
    """현행법령 조항조목 조회 모델 (API 응답 기반)"""
    id: Optional[int] = None
    # 기본 법령 정보
    law_key: Optional[int] = None  # 법령키
    law_id: Optional[int] = None  # 법령ID
    promulgation_date: Optional[int] = None  # 공포일자 (YYYYMMDD)
    promulgation_no: Optional[int] = None  # 공포번호
    language: Optional[str] = None  # 언어 구분
    law_name_korean: Optional[str] = None  # 법령명_한글
    law_name_hanja: Optional[str] = None  # 법령명_한자
    law_type_code: Optional[str] = None  # 법종구분코드
    law_type_name: Optional[str] = None  # 법종구분명
    title_change_yn: Optional[str] = None  # 제명변경여부
    korean_law_yn: Optional[str] = None  # 한글법령여부
    chapter_section_no: Optional[int] = None  # 편장절관
    ministry_code: Optional[int] = None  # 소관부처 코드
    ministry_name: Optional[str] = None  # 소관부처명
    phone_number: Optional[str] = None  # 전화번호
    enforcement_date: Optional[int] = None  # 시행일자 (YYYYMMDD)
    revision_type: Optional[str] = None  # 제개정구분명
    proposal_type: Optional[str] = None  # 제안구분
    decision_type: Optional[str] = None  # 의결구분
    previous_law_name: Optional[str] = None  # 이전법령명
    article_enforcement_date: Optional[str] = None  # 조문별시행일자
    article_enforcement_date_str: Optional[str] = None  # 조문시행일자문자열
    appendix_enforcement_date_str: Optional[str] = None  # 별표시행일자문자열
    appendix_edit_yn: Optional[str] = None  # 별표편집여부
    promulgated_law_yn: Optional[str] = None  # 공포법령여부
    enforcement_date_edit_yn: Optional[str] = None  # 시행일기준편집여부
    
    # 조문 정보
    article_no: Optional[int] = None  # 조문번호
    article_yn: Optional[str] = None  # 조문여부
    article_title: Optional[str] = None  # 조문제목
    article_enforcement_date_detail: Optional[str] = None  # 조문시행일자
    article_move_before: Optional[int] = None  # 조문이동이전번호
    article_move_after: Optional[int] = None  # 조문이동이후번호
    article_change_yn: Optional[str] = None  # 조문변경여부
    article_content: Optional[str] = None  # 조문내용
    
    # 항, 호, 목 정보
    paragraph_no: Optional[int] = None  # 항번호
    paragraph_content: Optional[str] = None  # 항내용
    item_no: Optional[int] = None  # 호번호
    item_content: Optional[str] = None  # 호내용
    subitem_no: Optional[str] = None  # 목번호
    subitem_content: Optional[str] = None  # 목내용
    
    # 내부 관리 필드
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

# 기존 Article 모델은 LawArticle로 대체됨

# 기존 LawVersion 모델은 실제 API 응답에 맞게 LawList, LawContent, LawArticle로 분리됨

@dataclass
class BatchJob:
    """배치 작업 모델"""
    id: Optional[int] = None
    job_id: str = ""
    job_type: JobType = JobType.INCREMENTAL_SYNC
    status: JobStatus = JobStatus.PENDING
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    last_sync_date: Optional[date] = None
    processed_laws: int = 0
    processed_articles: int = 0
    error_count: int = 0
    error_details: Optional[str] = None
    created_at: Optional[datetime] = None
    
    def __post_init__(self):
        """데이터 검증"""
        if not self.job_id:
            raise ValueError("job_id는 필수 필드입니다")
    
    @property
    def duration_seconds(self) -> Optional[float]:
        """작업 실행 시간 (초)"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return None
    
    @property
    def is_completed(self) -> bool:
        """작업 완료 여부"""
        return self.status in [JobStatus.SUCCESS, JobStatus.FAILED]
    
    @property
    def is_successful(self) -> bool:
        """작업 성공 여부"""
        return self.status == JobStatus.SUCCESS

@dataclass
class SyncStatus:
    """동기화 상태 모델"""
    id: Optional[int] = None
    sync_type: SyncType = SyncType.INCREMENTAL
    last_sync_date: Optional[date] = None
    last_enforcement_date: Optional[date] = None
    total_laws_count: int = 0
    total_articles_count: int = 0
    updated_at: Optional[datetime] = None
    
    def __post_init__(self):
        """데이터 검증"""
        if not self.last_sync_date:
            raise ValueError("last_sync_date는 필수 필드입니다")

@dataclass
class DatabaseStats:
    """데이터베이스 통계 정보"""
    total_laws: int = 0
    total_articles: int = 0
    latest_laws: int = 0
    total_versions: int = 0
    last_sync_date: Optional[date] = None
    last_batch_job: Optional[BatchJob] = None
    
    @property
    def average_articles_per_law(self) -> float:
        """법령당 평균 조항 수"""
        if self.total_laws > 0:
            return self.total_articles / self.total_laws
        return 0.0

# 데이터 변환 유틸리티 함수들
def dict_to_law_list(data: dict) -> LawList:
    """딕셔너리를 LawList 객체로 변환 (법령 목록 조회 API 응답)"""
    return LawList(
        id=data.get('id'),
        target=data.get('target'),
        keyword=data.get('keyword'),
        section=data.get('section'),
        total_cnt=data.get('totalCnt'),
        page=data.get('page'),
        law_id=data.get('법령ID'),
        law_serial_no=data.get('법령일련번호'),
        current_history_code=data.get('현행연혁코드'),
        law_name_korean=data.get('법령명한글'),
        law_abbr_name=data.get('법령약칭명'),
        promulgation_date=data.get('공포일자'),
        promulgation_no=data.get('공포번호'),
        revision_type=data.get('제개정구분명'),
        ministry_name=data.get('소관부처명'),
        ministry_code=data.get('소관부처코드'),
        law_type_name=data.get('법령구분명'),
        joint_ministry_type=data.get('공동부령구분'),
        joint_promulgation_no=data.get('공포번호'),  # 공동부령의 공포번호
        enforcement_date=data.get('시행일자'),
        self_other_law_yn=data.get('자법타법여부'),
        law_detail_link=data.get('법령상세링크'),
        created_at=data.get('created_at'),
        updated_at=data.get('updated_at')
    )

def dict_to_law_content(data: dict) -> LawContent:
    """딕셔너리를 LawContent 객체로 변환 (법령 본문 조회 API 응답)"""
    return LawContent(
        id=data.get('id'),
        law_id=data.get('법령ID'),
        promulgation_date=data.get('공포일자'),
        promulgation_no=data.get('공포번호'),
        language=data.get('언어'),
        law_type=data.get('법종구분'),
        law_type_code=data.get('법종구분코드'),
        law_name_korean=data.get('법령명_한글'),
        law_name_hanja=data.get('법령명_한자'),
        law_abbr_name=data.get('법령명약칭'),
        title_change_yn=data.get('제명변경여부'),
        korean_law_yn=data.get('한글법령여부'),
        chapter_section_no=data.get('편장절관'),
        ministry_code=data.get('소관부처코드'),
        ministry_name=data.get('소관부처'),
        phone_number=data.get('전화번호'),
        enforcement_date=data.get('시행일자'),
        revision_type=data.get('제개정구분'),
        appendix_edit_yn=data.get('별표편집여부'),
        promulgated_law_yn=data.get('공포법령여부'),
        department_name=data.get('부서명'),
        department_phone=data.get('부서연락처'),
        joint_ministry_type=data.get('공동부령구분'),
        joint_type_code=data.get('구분코드'),
        joint_promulgation_no=data.get('공포번호'),  # 공동부령의 공포번호
        article_no=data.get('조문번호'),
        article_sub_no=data.get('조문가지번호'),
        article_yn=data.get('조문여부'),
        article_title=data.get('조문제목'),
        article_enforcement_date=data.get('조문시행일자'),
        article_revision_type=data.get('조문제개정유형'),
        article_move_before=data.get('조문이동이전'),
        article_move_after=data.get('조문이동이후'),
        article_change_yn=data.get('조문변경여부'),
        article_content=data.get('조문내용'),
        paragraph_no=data.get('항번호'),
        paragraph_revision_type=data.get('항제개정유형'),
        paragraph_revision_date_str=data.get('항제개정일자문자열'),
        paragraph_content=data.get('항내용'),
        item_no=data.get('호번호'),
        item_content=data.get('호내용'),
        article_reference=data.get('조문참고자료'),
        addendum_promulgation_date=data.get('부칙공포일자'),
        addendum_promulgation_no=data.get('부칙공포번호'),
        addendum_content=data.get('부칙내용'),
        appendix_no=data.get('별표번호'),
        appendix_sub_no=data.get('별표가지번호'),
        appendix_type=data.get('별표구분'),
        appendix_title=data.get('별표제목'),
        appendix_form_file_link=data.get('별표서식파일링크'),
        appendix_hwp_filename=data.get('별표HWP파일명'),
        appendix_pdf_file_link=data.get('별표서식PDF파일링크'),
        appendix_pdf_filename=data.get('별표PDF파일명'),
        appendix_image_filename=data.get('별표이미지파일명'),
        appendix_content=data.get('별표내용'),
        revision_content=data.get('개정문내용'),
        revision_reason=data.get('제개정이유내용'),
        created_at=data.get('created_at'),
        updated_at=data.get('updated_at')
    )

def dict_to_law_article(data: dict) -> LawArticle:
    """딕셔너리를 LawArticle 객체로 변환 (현행법령 조항조목 조회 API 응답)"""
    return LawArticle(
        id=data.get('id'),
        law_key=data.get('법령키'),
        law_id=data.get('법령ID'),
        promulgation_date=data.get('공포일자'),
        promulgation_no=data.get('공포번호'),
        language=data.get('언어'),
        law_name_korean=data.get('법령명_한글'),
        law_name_hanja=data.get('법령명_한자'),
        law_type_code=data.get('법종구분코드'),
        law_type_name=data.get('법종구분명'),
        title_change_yn=data.get('제명변경여부'),
        korean_law_yn=data.get('한글법령여부'),
        chapter_section_no=data.get('편장절관'),
        ministry_code=data.get('소관부처코드'),
        ministry_name=data.get('소관부처'),
        phone_number=data.get('전화번호'),
        enforcement_date=data.get('시행일자'),
        revision_type=data.get('제개정구분'),
        proposal_type=data.get('제안구분'),
        decision_type=data.get('의결구분'),
        previous_law_name=data.get('이전법령명'),
        article_enforcement_date=data.get('조문별시행일자'),
        article_enforcement_date_str=data.get('조문시행일자문자열'),
        appendix_enforcement_date_str=data.get('별표시행일자문자열'),
        appendix_edit_yn=data.get('별표편집여부'),
        promulgated_law_yn=data.get('공포법령여부'),
        enforcement_date_edit_yn=data.get('시행일기준편집여부'),
        article_no=data.get('조문번호'),
        article_yn=data.get('조문여부'),
        article_title=data.get('조문제목'),
        article_enforcement_date_detail=data.get('조문시행일자'),
        article_move_before=data.get('조문이동이전'),
        article_move_after=data.get('조문이동이후'),
        article_change_yn=data.get('조문변경여부'),
        article_content=data.get('조문내용'),
        paragraph_no=data.get('항번호'),
        paragraph_content=data.get('항내용'),
        item_no=data.get('호번호'),
        item_content=data.get('호내용'),
        subitem_no=data.get('목번호'),
        subitem_content=data.get('목내용'),
        created_at=data.get('created_at'),
        updated_at=data.get('updated_at')
    )

def dict_to_batch_job(data: dict) -> BatchJob:
    """딕셔너리를 BatchJob 객체로 변환"""
    return BatchJob(
        id=data.get('id'),
        job_id=data.get('job_id', ''),
        job_type=JobType(data.get('job_type', 'INCREMENTAL_SYNC')),
        status=JobStatus(data.get('status', 'PENDING')),
        start_time=data.get('start_time'),
        end_time=data.get('end_time'),
        last_sync_date=data.get('last_sync_date'),
        processed_laws=data.get('processed_laws', 0),
        processed_articles=data.get('processed_articles', 0),
        error_count=data.get('error_count', 0),
        error_details=data.get('error_details'),
        created_at=data.get('created_at')
    )

def dict_to_sync_status(data: dict) -> SyncStatus:
    """딕셔너리를 SyncStatus 객체로 변환"""
    return SyncStatus(
        id=data.get('id'),
        sync_type=SyncType(data.get('sync_type', 'INCREMENTAL')),
        last_sync_date=data.get('last_sync_date'),
        last_enforcement_date=data.get('last_enforcement_date'),
        total_laws_count=data.get('total_laws_count', 0),
        total_articles_count=data.get('total_articles_count', 0),
        updated_at=data.get('updated_at')
    )