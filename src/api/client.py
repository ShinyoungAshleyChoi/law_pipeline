"""법제처 API 클라이언트"""
import time
import requests
import json
from datetime import date, datetime
from typing import List, Optional, Dict, Any

from .models import LawListItem, LawContent, LawArticle, APIHealthStatus, IncrementalUpdateResult
from ..config import config
from ..logging_config import get_logger
from ..notifications.slack_service import slack_service

logger = get_logger(__name__)

class APIError(Exception):
    """API 오류"""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code

class LegalAPIClient:
    """법제처 API 클라이언트"""
    
    def __init__(self):
        self.base_url = config.api.base_url
        self.oc_id = "choishin0"  # OC 파라미터용 ID
        self.timeout = config.api.timeout
        self.max_retries = config.api.max_retries
        self.retry_delay = config.api.retry_delay
        
        # 세션 설정
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Legal-Data-Pipeline/1.0',
            'Accept': 'application/json'
        })
    
    def _make_request(self, endpoint: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """API 요청 실행"""
        url = f"{self.base_url}{endpoint}"
        params['OC'] = self.oc_id  # OC 파라미터에 ID 설정
        params['type'] = 'json'  # JSON 형식으로 요청
        
        for attempt in range(self.max_retries + 1):
            try:
                response = self.session.get(url, params=params, timeout=self.timeout)
                
                if response.status_code != 200:
                    raise APIError(f"HTTP {response.status_code} 오류", response.status_code)
                
                # JSON 파싱
                try:
                    data = response.json()
                    
                    # API 오류 응답 확인
                    if 'errCode' in data and data['errCode'] != '0':
                        error_msg = data.get('errMsg', '알 수 없는 오류')
                        api_error_msg = f"API 오류 (코드: {data['errCode']}): {error_msg}"
                        
                        # 슬랙 알림 전송
                        slack_service.send_error_alert(
                            title="법제처 API 응답 오류",
                            message=f"엔드포인트: {endpoint}\n{api_error_msg}",
                            context={
                                'endpoint': endpoint,
                                'params': params,
                                'error_code': data['errCode'],
                                'error_message': error_msg
                            }
                        )
                        
                        raise APIError(api_error_msg)
                    
                    return data
                    
                except json.JSONDecodeError as e:
                    error_msg = f"JSON 파싱 실패: {str(e)}"
                    
                    # 슬랙 알림 전송
                    slack_service.send_error_alert(
                        title="법제처 API JSON 파싱 실패",
                        message=f"엔드포인트: {endpoint}\n{error_msg}",
                        context={
                            'endpoint': endpoint,
                            'params': params,
                            'error': str(e),
                            'response_preview': response.text[:500] if 'response' in locals() else None
                        }
                    )
                    
                    raise APIError(error_msg)
                
            except requests.exceptions.RequestException as e:
                if attempt == self.max_retries:
                    error_msg = f"API 요청 실패: {str(e)}"
                    # 슬랙 알림 전송
                    slack_service.send_error_alert(
                        title="법제처 API 요청 실패",
                        message=f"엔드포인트: {endpoint}\n오류: {error_msg}",
                        context={
                            'endpoint': endpoint,
                            'params': params,
                            'attempt': attempt + 1,
                            'error': str(e)
                        }
                    )
                    raise APIError(error_msg)
                
                time.sleep(self.retry_delay * (2 ** attempt))
        
        error_msg = "최대 재시도 횟수 초과"
        # 슬랙 알림 전송
        slack_service.send_error_alert(
            title="법제처 API 최대 재시도 초과",
            message=f"엔드포인트: {endpoint}\n최대 재시도 횟수({self.max_retries})를 초과했습니다.",
            context={
                'endpoint': endpoint,
                'params': params,
                'max_retries': self.max_retries
            }
        )
        raise APIError(error_msg)
    
    def collect_law_list(self, last_sync_date: Optional[date] = None) -> List[LawListItem]:
        """현행법령 목록 조회"""
        logger.info("현행법령 목록 수집 시작", last_sync_date=last_sync_date)
        
        params = {'target': 'law'}
        
        if last_sync_date:
            params['lastSyncDate'] = last_sync_date.strftime('%Y%m%d')
        
        try:
            data = self._make_request('/getLawList', params)
            
            laws = []
            law_list = data.get('lawList', [])
            
            for law_data in law_list:
                try:
                    law_id = law_data.get('lawId')
                    law_master_no = law_data.get('lawMasterNo')
                    law_name = law_data.get('lawName')
                    enforcement_date_str = law_data.get('enforcementDate')
                    
                    if not all([law_id, law_master_no, law_name, enforcement_date_str]):
                        logger.warning("필수 필드 누락", law_data=law_data)
                        continue
                    
                    enforcement_date = datetime.strptime(enforcement_date_str, '%Y%m%d').date()
                    
                    # 선택적 필드
                    law_type = law_data.get('lawType')
                    promulgation_date_str = law_data.get('promulgationDate')
                    promulgation_date = None
                    if promulgation_date_str:
                        try:
                            promulgation_date = datetime.strptime(promulgation_date_str, '%Y%m%d').date()
                        except ValueError:
                            logger.warning("공포일 파싱 실패", 
                                         law_id=law_id, 
                                         promulgation_date_str=promulgation_date_str)
                    
                    laws.append(LawListItem(
                        law_id=law_id,
                        law_master_no=law_master_no,
                        law_name=law_name,
                        enforcement_date=enforcement_date,
                        law_type=law_type,
                        promulgation_date=promulgation_date
                    ))
                    
                except Exception as e:
                    logger.warning("법령 항목 파싱 실패", error=str(e), law_data=law_data)
                    continue
            
            logger.info("현행법령 목록 수집 완료", count=len(laws))
            return laws
            
        except Exception as e:
            logger.error("현행법령 목록 수집 실패", error=str(e))
            # 슬랙 알림 전송
            slack_service.send_error_alert(
                title="현행법령 목록 수집 실패",
                message=f"마지막 동기화 날짜: {last_sync_date}\n오류: {str(e)}",
                context={
                    'last_sync_date': str(last_sync_date) if last_sync_date else None,
                    'error': str(e),
                    'function': 'collect_law_list'
                }
            )
            raise
    
    def collect_law_content(self, law_id: str) -> LawContent:
        """현행법령 본문 조회"""
        logger.debug("현행법령 본문 수집 시작", law_id=law_id)
        
        params = {'target': 'law', 'lawId': law_id}
        
        try:
            data = self._make_request('/getLawContent', params)
            
            law_data = data.get('law')
            if not law_data:
                raise APIError(f"법령 데이터를 찾을 수 없음: {law_id}")
            
            law_id_resp = law_data.get('lawId')
            law_master_no = law_data.get('lawMasterNo')
            law_name = law_data.get('lawName')
            content = law_data.get('lawContent', '')
            enforcement_date_str = law_data.get('enforcementDate')
            
            if not all([law_id_resp, law_master_no, law_name, enforcement_date_str]):
                raise APIError(f"필수 필드 누락: {law_id}")
            
            enforcement_date = datetime.strptime(enforcement_date_str, '%Y%m%d').date()
            
            # 선택적 필드
            law_type = law_data.get('lawType')
            promulgation_date_str = law_data.get('promulgationDate')
            promulgation_date = None
            if promulgation_date_str:
                try:
                    promulgation_date = datetime.strptime(promulgation_date_str, '%Y%m%d').date()
                except ValueError:
                    logger.warning("공포일 파싱 실패", law_id=law_id)
            
            law_content = LawContent(
                law_id=law_id_resp,
                law_master_no=law_master_no,
                law_name=law_name,
                content=content,
                enforcement_date=enforcement_date,
                law_type=law_type,
                promulgation_date=promulgation_date
            )
            
            logger.debug("현행법령 본문 수집 완료", law_id=law_id)
            return law_content
            
        except Exception as e:
            logger.error("현행법령 본문 수집 실패", law_id=law_id, error=str(e))
            # 슬랙 알림 전송
            slack_service.send_error_alert(
                title="현행법령 본문 수집 실패",
                message=f"법령ID: {law_id}\n오류: {str(e)}",
                context={
                    'law_id': law_id,
                    'error': str(e),
                    'function': 'collect_law_content'
                }
            )
            raise
    
    def collect_law_articles(self, law_master_no: str) -> List[LawArticle]:
        """현행법령 조항호목 조회"""
        logger.debug("현행법령 조항 수집 시작", law_master_no=law_master_no)
        
        params = {'target': 'law', 'lawMasterNo': law_master_no}
        
        try:
            data = self._make_request('/getLawArticles', params)
            
            articles = []
            article_list = data.get('articleList', [])
            
            for idx, article_data in enumerate(article_list):
                try:
                    article_no = article_data.get('articleNo')
                    article_content = article_data.get('articleContent')
                    
                    if not all([article_no, article_content]):
                        logger.warning("조항 필수 필드 누락", 
                                     law_master_no=law_master_no,
                                     article_data=article_data)
                        continue
                    
                    # 선택적 필드
                    article_title = article_data.get('articleTitle')
                    parent_article_no = article_data.get('parentArticleNo')
                    
                    articles.append(LawArticle(
                        law_master_no=law_master_no,
                        article_no=article_no,
                        article_content=article_content,
                        article_title=article_title,
                        parent_article_no=parent_article_no,
                        article_order=idx + 1
                    ))
                    
                except Exception as e:
                    logger.warning("조항 파싱 실패", 
                                 law_master_no=law_master_no,
                                 error=str(e),
                                 article_data=article_data)
                    continue
            
            logger.debug("현행법령 조항 수집 완료", 
                        law_master_no=law_master_no,
                        count=len(articles))
            return articles
            
        except Exception as e:
            logger.error("현행법령 조항 수집 실패", 
                        law_master_no=law_master_no,
                        error=str(e))
            # 슬랙 알림 전송
            slack_service.send_error_alert(
                title="현행법령 조항 수집 실패",
                message=f"법령마스터번호: {law_master_no}\n오류: {str(e)}",
                context={
                    'law_master_no': law_master_no,
                    'error': str(e),
                    'function': 'collect_law_articles'
                }
            )
            raise
    
    def collect_incremental_updates(self, last_sync_date: date) -> IncrementalUpdateResult:
        """증분 업데이트 데이터 수집"""
        logger.info("증분 업데이트 수집 시작", last_sync_date=last_sync_date)
        
        try:
            # 1. 업데이트된 법령 목록 조회
            updated_laws = self.collect_law_list(last_sync_date)
            
            # 2. 새로운 법령마스터번호 추출
            new_law_master_nos = list(set(law.law_master_no for law in updated_laws))
            
            result = IncrementalUpdateResult(
                updated_laws=updated_laws,
                new_law_master_nos=new_law_master_nos,
                total_updated_count=len(updated_laws),
                last_update_date=date.today()
            )
            
            logger.info("증분 업데이트 수집 완료",
                       updated_count=result.total_updated_count,
                       new_master_nos_count=len(result.new_law_master_nos))
            
            return result
            
        except Exception as e:
            logger.error("증분 업데이트 수집 실패", error=str(e))
            # 슬랙 알림 전송
            slack_service.send_error_alert(
                title="증분 업데이트 수집 실패",
                message=f"마지막 동기화 날짜: {last_sync_date}\n오류: {str(e)}",
                context={
                    'last_sync_date': str(last_sync_date),
                    'error': str(e),
                    'function': 'collect_incremental_updates'
                }
            )
            raise
    
    def health_check(self) -> APIHealthStatus:
        """API 상태 확인"""
        start_time = time.time()
        
        try:
            params = {'target': 'law', 'numOfRows': '1'}
            self._make_request('/getLawList', params)
            
            return APIHealthStatus(
                is_healthy=True,
                response_time_ms=int((time.time() - start_time) * 1000),
                last_check=datetime.now()
            )
        except Exception as e:
            # 헬스체크 실패 시 슬랙 알림 전송
            slack_service.send_error_alert(
                title="법제처 API 헬스체크 실패",
                message=f"API 상태 확인 중 오류가 발생했습니다.\n오류: {str(e)}",
                context={
                    'error': str(e),
                    'function': 'health_check',
                    'response_time_ms': int((time.time() - start_time) * 1000)
                }
            )
            
            return APIHealthStatus(
                is_healthy=False,
                response_time_ms=int((time.time() - start_time) * 1000),
                last_check=datetime.now(),
                error_message=str(e)
            )
    
    def close(self):
        """세션 종료"""
        if self.session:
            self.session.close()

# 전역 API 클라이언트 인스턴스
api_client = LegalAPIClient()