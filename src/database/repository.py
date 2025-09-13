"""실제 API 응답 기반 데이터베이스 저장소 계층 구현"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime
import uuid
from contextlib import contextmanager
from mysql.connector import Error as MySQLError
import structlog

from .connection import db_connection
from .models import (
    LawList, LawContent, LawArticle, BatchJob, SyncStatus, DatabaseStats,
    JobStatus, JobType, SyncType,
    dict_to_law_list, dict_to_law_content, dict_to_law_article,
    dict_to_batch_job, dict_to_sync_status
)
from ..logging_config import get_logger

logger = get_logger(__name__)

class LegalDataRepository:
    """법령 데이터 저장소 클래스 (실제 API 응답 기반)"""
    
    def __init__(self):
        self._current_connection = None
        self._transaction_active = False
    
    @contextmanager
    def transaction(self):
        """트랜잭션 컨텍스트 매니저"""
        if self._transaction_active:
            # 이미 트랜잭션이 활성화된 경우 중첩 트랜잭션 지원
            yield
            return
            
        with db_connection.get_connection() as conn:
            self._current_connection = conn
            self._transaction_active = True
            
            try:
                conn.start_transaction()
                logger.debug("트랜잭션 시작")
                yield
                conn.commit()
                logger.debug("트랜잭션 커밋 완료")
                
            except Exception as e:
                conn.rollback()
                logger.error("트랜잭션 롤백", error=str(e))
                raise
            finally:
                self._current_connection = None
                self._transaction_active = False
    
    def _get_connection(self):
        """현재 연결 반환 (트랜잭션 중이면 현재 연결, 아니면 새 연결)"""
        if self._current_connection:
            return self._current_connection
        return db_connection.get_connection()
    
    # ==================== 법령 목록 CRUD 연산 ====================
    
    def save_law_list(self, law_list: LawList) -> bool:
        """법령 목록 데이터 저장/업데이트"""
        try:
            if self._transaction_active:
                return self._save_law_list_with_connection(self._current_connection, law_list)
            else:
                with db_connection.get_connection() as conn:
                    return self._save_law_list_with_connection(conn, law_list)
                    
        except Exception as e:
            logger.error("법령 목록 저장 실패", law_id=law_list.law_id, error=str(e))
            return False
    
    def _save_law_list_with_connection(self, conn, law_list: LawList) -> bool:
        """연결을 사용하여 법령 목록 저장"""
        cursor = conn.cursor()
        try:
            # 기존 법령 확인 (law_id 기준)
            if law_list.law_id:
                check_sql = "SELECT id FROM law_list WHERE law_id = %s"
                cursor.execute(check_sql, (law_list.law_id,))
                existing = cursor.fetchone()
                
                if existing:
                    # 업데이트
                    update_sql = """
                    UPDATE law_list SET 
                        law_name_korean = %s, law_abbr_name = %s, 
                        enforcement_date = %s, ministry_name = %s,
                        law_type_name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE law_id = %s
                    """
                    cursor.execute(update_sql, (
                        law_list.law_name_korean, law_list.law_abbr_name,
                        law_list.enforcement_date, law_list.ministry_name,
                        law_list.law_type_name, law_list.law_id
                    ))
                    logger.debug("법령 목록 업데이트 완료", law_id=law_list.law_id)
                else:
                    # 삽입
                    insert_sql = """
                    INSERT INTO law_list (
                        target, keyword, section, total_cnt, page, law_id, law_serial_no,
                        current_history_code, law_name_korean, law_abbr_name, promulgation_date,
                        promulgation_no, revision_type, ministry_name, ministry_code,
                        law_type_name, joint_ministry_type, joint_promulgation_no,
                        enforcement_date, self_other_law_yn, law_detail_link
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        law_list.target, law_list.keyword, law_list.section,
                        law_list.total_cnt, law_list.page, law_list.law_id,
                        law_list.law_serial_no, law_list.current_history_code,
                        law_list.law_name_korean, law_list.law_abbr_name,
                        law_list.promulgation_date, law_list.promulgation_no,
                        law_list.revision_type, law_list.ministry_name,
                        law_list.ministry_code, law_list.law_type_name,
                        law_list.joint_ministry_type, law_list.joint_promulgation_no,
                        law_list.enforcement_date, law_list.self_other_law_yn,
                        law_list.law_detail_link
                    ))
                    logger.debug("법령 목록 삽입 완료", law_id=law_list.law_id)
            
            return cursor.rowcount > 0
            
        finally:
            cursor.close()
    
    def get_law_list_by_id(self, law_id: int) -> Optional[LawList]:
        """법령ID로 법령 목록 조회"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                sql = "SELECT * FROM law_list WHERE law_id = %s"
                cursor.execute(sql, (law_id,))
                result = cursor.fetchone()
                cursor.close()
                
                if result:
                    return dict_to_law_list(result)
                return None
                
        except Exception as e:
            logger.error("법령 목록 조회 실패", law_id=law_id, error=str(e))
            return None
    
    # ==================== 법령 본문 CRUD 연산 ====================
    
    def save_law_content(self, law_content: LawContent) -> bool:
        """법령 본문 데이터 저장/업데이트"""
        try:
            if self._transaction_active:
                return self._save_law_content_with_connection(self._current_connection, law_content)
            else:
                with db_connection.get_connection() as conn:
                    return self._save_law_content_with_connection(conn, law_content)
                    
        except Exception as e:
            logger.error("법령 본문 저장 실패", law_id=law_content.law_id, error=str(e))
            return False
    
    def _save_law_content_with_connection(self, conn, law_content: LawContent) -> bool:
        """연결을 사용하여 법령 본문 저장"""
        cursor = conn.cursor()
        try:
            insert_sql = """
            INSERT INTO law_content (
                law_id, promulgation_date, promulgation_no, language, law_type, law_type_code,
                law_name_korean, law_name_hanja, law_abbr_name, title_change_yn, korean_law_yn,
                chapter_section_no, ministry_code, ministry_name, phone_number, enforcement_date,
                revision_type, appendix_edit_yn, promulgated_law_yn, department_name, department_phone,
                joint_ministry_type, joint_type_code, joint_promulgation_no, article_no, article_sub_no,
                article_yn, article_title, article_enforcement_date, article_revision_type,
                article_move_before, article_move_after, article_change_yn, article_content,
                paragraph_no, paragraph_revision_type, paragraph_revision_date_str, paragraph_content,
                item_no, item_content, article_reference, addendum_promulgation_date, addendum_promulgation_no,
                addendum_content, appendix_no, appendix_sub_no, appendix_type, appendix_title,
                appendix_form_file_link, appendix_hwp_filename, appendix_pdf_file_link, appendix_pdf_filename,
                appendix_image_filename, appendix_content, revision_content, revision_reason
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """
            cursor.execute(insert_sql, (
                law_content.law_id, law_content.promulgation_date, law_content.promulgation_no,
                law_content.language, law_content.law_type, law_content.law_type_code,
                law_content.law_name_korean, law_content.law_name_hanja, law_content.law_abbr_name,
                law_content.title_change_yn, law_content.korean_law_yn, law_content.chapter_section_no,
                law_content.ministry_code, law_content.ministry_name, law_content.phone_number,
                law_content.enforcement_date, law_content.revision_type, law_content.appendix_edit_yn,
                law_content.promulgated_law_yn, law_content.department_name, law_content.department_phone,
                law_content.joint_ministry_type, law_content.joint_type_code, law_content.joint_promulgation_no,
                law_content.article_no, law_content.article_sub_no, law_content.article_yn,
                law_content.article_title, law_content.article_enforcement_date, law_content.article_revision_type,
                law_content.article_move_before, law_content.article_move_after, law_content.article_change_yn,
                law_content.article_content, law_content.paragraph_no, law_content.paragraph_revision_type,
                law_content.paragraph_revision_date_str, law_content.paragraph_content, law_content.item_no,
                law_content.item_content, law_content.article_reference, law_content.addendum_promulgation_date,
                law_content.addendum_promulgation_no, law_content.addendum_content, law_content.appendix_no,
                law_content.appendix_sub_no, law_content.appendix_type, law_content.appendix_title,
                law_content.appendix_form_file_link, law_content.appendix_hwp_filename, law_content.appendix_pdf_file_link,
                law_content.appendix_pdf_filename, law_content.appendix_image_filename, law_content.appendix_content,
                law_content.revision_content, law_content.revision_reason
            ))
            
            logger.debug("법령 본문 삽입 완료", law_id=law_content.law_id)
            return cursor.rowcount > 0
            
        finally:
            cursor.close()
    
    def get_law_content_by_id(self, law_id: int) -> List[LawContent]:
        """법령ID로 법령 본문 조회 (여러 조문이 있을 수 있음)"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                sql = "SELECT * FROM law_content WHERE law_id = %s ORDER BY article_no, paragraph_no, item_no"
                cursor.execute(sql, (law_id,))
                results = cursor.fetchall()
                cursor.close()
                
                return [dict_to_law_content(row) for row in results]
                
        except Exception as e:
            logger.error("법령 본문 조회 실패", law_id=law_id, error=str(e))
            return []
    
    # ==================== 법령 조항조목 CRUD 연산 ====================
    
    def save_law_article(self, law_article: LawArticle) -> bool:
        """법령 조항조목 데이터 저장/업데이트"""
        try:
            if self._transaction_active:
                return self._save_law_article_with_connection(self._current_connection, law_article)
            else:
                with db_connection.get_connection() as conn:
                    return self._save_law_article_with_connection(conn, law_article)
                    
        except Exception as e:
            logger.error("법령 조항조목 저장 실패", law_id=law_article.law_id, error=str(e))
            return False
    
    def _save_law_article_with_connection(self, conn, law_article: LawArticle) -> bool:
        """연결을 사용하여 법령 조항조목 저장"""
        cursor = conn.cursor()
        try:
            insert_sql = """
            INSERT INTO law_articles (
                law_key, law_id, promulgation_date, promulgation_no, language, law_name_korean,
                law_name_hanja, law_type_code, law_type_name, title_change_yn, korean_law_yn,
                chapter_section_no, ministry_code, ministry_name, phone_number, enforcement_date,
                revision_type, proposal_type, decision_type, previous_law_name, article_enforcement_date,
                article_enforcement_date_str, appendix_enforcement_date_str, appendix_edit_yn,
                promulgated_law_yn, enforcement_date_edit_yn, article_no, article_yn, article_title,
                article_enforcement_date_detail, article_move_before, article_move_after, article_change_yn,
                article_content, paragraph_no, paragraph_content, item_no, item_content, subitem_no, subitem_content
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                law_name_korean = VALUES(law_name_korean),
                article_content = VALUES(article_content),
                paragraph_content = VALUES(paragraph_content),
                item_content = VALUES(item_content),
                subitem_content = VALUES(subitem_content),
                updated_at = CURRENT_TIMESTAMP
            """
            cursor.execute(insert_sql, (
                law_article.law_key, law_article.law_id, law_article.promulgation_date,
                law_article.promulgation_no, law_article.language, law_article.law_name_korean,
                law_article.law_name_hanja, law_article.law_type_code, law_article.law_type_name,
                law_article.title_change_yn, law_article.korean_law_yn, law_article.chapter_section_no,
                law_article.ministry_code, law_article.ministry_name, law_article.phone_number,
                law_article.enforcement_date, law_article.revision_type, law_article.proposal_type,
                law_article.decision_type, law_article.previous_law_name, law_article.article_enforcement_date,
                law_article.article_enforcement_date_str, law_article.appendix_enforcement_date_str,
                law_article.appendix_edit_yn, law_article.promulgated_law_yn, law_article.enforcement_date_edit_yn,
                law_article.article_no, law_article.article_yn, law_article.article_title,
                law_article.article_enforcement_date_detail, law_article.article_move_before,
                law_article.article_move_after, law_article.article_change_yn, law_article.article_content,
                law_article.paragraph_no, law_article.paragraph_content, law_article.item_no,
                law_article.item_content, law_article.subitem_no, law_article.subitem_content
            ))
            
            logger.debug("법령 조항조목 저장 완료", law_key=law_article.law_key, article_no=law_article.article_no)
            return cursor.rowcount > 0
            
        finally:
            cursor.close()
    
    def get_law_articles_by_law_key(self, law_key: int) -> List[LawArticle]:
        """법령키로 조항조목 목록 조회"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                sql = """
                SELECT * FROM law_articles 
                WHERE law_key = %s 
                ORDER BY article_no, paragraph_no, item_no, subitem_no
                """
                cursor.execute(sql, (law_key,))
                results = cursor.fetchall()
                cursor.close()
                
                return [dict_to_law_article(row) for row in results]
                
        except Exception as e:
            logger.error("법령 조항조목 조회 실패", law_key=law_key, error=str(e))
            return []
    
    # ==================== 배치 작업 관리 ====================
    
    def create_batch_job(self, job_type: JobType, last_sync_date: Optional[date] = None) -> str:
        """새 배치 작업 생성"""
        job_id = f"{job_type.value}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        
        batch_job = BatchJob(
            job_id=job_id,
            job_type=job_type,
            status=JobStatus.PENDING,
            start_time=datetime.now(),
            last_sync_date=last_sync_date
        )
        
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                insert_sql = """
                INSERT INTO batch_jobs (job_id, job_type, status, start_time, last_sync_date)
                VALUES (%s, %s, %s, %s, %s)
                """
                cursor.execute(insert_sql, (
                    batch_job.job_id, batch_job.job_type.value, batch_job.status.value,
                    batch_job.start_time, batch_job.last_sync_date
                ))
                cursor.close()
                
                logger.info("배치 작업 생성 완료", job_id=job_id, job_type=job_type.value)
                return job_id
                
        except Exception as e:
            logger.error("배치 작업 생성 실패", job_type=job_type.value, error=str(e))
            raise
    
    def update_batch_job_status(self, job_id: str, status: JobStatus, 
                               processed_laws: int = 0, processed_articles: int = 0,
                               error_count: int = 0, error_details: Optional[str] = None) -> bool:
        """배치 작업 상태 업데이트"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                end_time = datetime.now() if status in [JobStatus.SUCCESS, JobStatus.FAILED] else None
                
                update_sql = """
                UPDATE batch_jobs SET 
                    status = %s, end_time = %s, processed_laws = %s, 
                    processed_articles = %s, error_count = %s, error_details = %s
                WHERE job_id = %s
                """
                cursor.execute(update_sql, (
                    status.value, end_time, processed_laws, processed_articles,
                    error_count, error_details, job_id
                ))
                cursor.close()
                
                logger.debug("배치 작업 상태 업데이트", 
                           job_id=job_id, 
                           status=status.value,
                           processed_laws=processed_laws,
                           processed_articles=processed_articles)
                
                return cursor.rowcount > 0
                
        except Exception as e:
            logger.error("배치 작업 상태 업데이트 실패", job_id=job_id, error=str(e))
            return False
    
    def get_batch_job(self, job_id: str) -> Optional[BatchJob]:
        """배치 작업 조회"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                sql = "SELECT * FROM batch_jobs WHERE job_id = %s"
                cursor.execute(sql, (job_id,))
                result = cursor.fetchone()
                cursor.close()
                
                if result:
                    return dict_to_batch_job(result)
                return None
                
        except Exception as e:
            logger.error("배치 작업 조회 실패", job_id=job_id, error=str(e))
            return None
    
    def get_recent_batch_jobs(self, limit: int = 20) -> List[BatchJob]:
        """최근 배치 작업 목록 조회"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                sql = """
                SELECT * FROM batch_jobs 
                ORDER BY start_time DESC 
                LIMIT %s
                """
                cursor.execute(sql, (limit,))
                results = cursor.fetchall()
                cursor.close()
                
                return [dict_to_batch_job(row) for row in results]
                
        except Exception as e:
            logger.error("최근 배치 작업 조회 실패", limit=limit, error=str(e))
            return []
    
    def get_failed_batch_jobs(self, days: int = 7) -> List[BatchJob]:
        """실패한 배치 작업 목록 조회"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor(dictionary=True)
                
                sql = """
                SELECT * FROM batch_jobs 
                WHERE status = %s 
                AND start_time >= DATE_SUB(CURRENT_DATE, INTERVAL %s DAY)
                ORDER BY start_time DESC
                """
                cursor.execute(sql, (JobStatus.FAILED.value, days))
                results = cursor.fetchall()
                cursor.close()
                
                return [dict_to_batch_job(row) for row in results]
                
        except Exception as e:
            logger.error("실패한 배치 작업 조회 실패", days=days, error=str(e))
            return []
    
    # ==================== 동기화 상태 관리 ====================
    
    def get_last_sync_date(self, sync_type: str = "INCREMENTAL") -> Optional[date]:
        """마지막 동기화 날짜 조회"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                sql = "SELECT last_sync_date FROM sync_status WHERE sync_type = %s"
                cursor.execute(sql, (sync_type,))
                result = cursor.fetchone()
                cursor.close()
                
                if result and result[0]:
                    return result[0]
                return None
                
        except Exception as e:
            logger.error("마지막 동기화 날짜 조회 실패", sync_type=sync_type, error=str(e))
            return None
    
    def update_sync_status(self, sync_type: str, sync_date: date, 
                          total_laws_count: int = 0, total_articles_count: int = 0,
                          last_enforcement_date: Optional[date] = None) -> bool:
        """동기화 상태 업데이트"""
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # 기존 레코드 확인
                check_sql = "SELECT id FROM sync_status WHERE sync_type = %s"
                cursor.execute(check_sql, (sync_type,))
                existing = cursor.fetchone()
                
                if existing:
                    # 업데이트
                    update_sql = """
                    UPDATE sync_status SET 
                        last_sync_date = %s, last_enforcement_date = %s,
                        total_laws_count = %s, total_articles_count = %s,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE sync_type = %s
                    """
                    cursor.execute(update_sql, (
                        sync_date, last_enforcement_date, total_laws_count, 
                        total_articles_count, sync_type
                    ))
                else:
                    # 삽입
                    insert_sql = """
                    INSERT INTO sync_status (sync_type, last_sync_date, last_enforcement_date,
                                           total_laws_count, total_articles_count)
                    VALUES (%s, %s, %s, %s, %s)
                    """
                    cursor.execute(insert_sql, (
                        sync_type, sync_date, last_enforcement_date,
                        total_laws_count, total_articles_count
                    ))
                
                cursor.close()
                
                logger.info("동기화 상태 업데이트 완료", 
                          sync_type=sync_type, 
                          sync_date=sync_date,
                          total_laws=total_laws_count,
                          total_articles=total_articles_count)
                
                return True
                
        except Exception as e:
            logger.error("동기화 상태 업데이트 실패", sync_type=sync_type, error=str(e))
            return False
    
    # ==================== 통계 및 모니터링 ====================
    
    def get_database_stats(self) -> DatabaseStats:
        """데이터베이스 통계 정보 조회"""
        stats = DatabaseStats()
        
        try:
            with db_connection.get_connection() as conn:
                cursor = conn.cursor()
                
                # 총 법령 목록 수
                cursor.execute("SELECT COUNT(DISTINCT law_id) FROM law_list")
                stats.total_laws = cursor.fetchone()[0]
                
                # 총 법령 본문 수
                cursor.execute("SELECT COUNT(DISTINCT law_id) FROM law_content")
                content_count = cursor.fetchone()[0]
                
                # 총 조항조목 수
                cursor.execute("SELECT COUNT(*) FROM law_articles")
                stats.total_articles = cursor.fetchone()[0]
                
                # 마지막 동기화 날짜
                cursor.execute("SELECT last_sync_date FROM sync_status WHERE sync_type = 'INCREMENTAL'")
                result = cursor.fetchone()
                if result and result[0]:
                    stats.last_sync_date = result[0]
                
                cursor.close()
                
                logger.debug("데이터베이스 통계 조회 완료", 
                           total_laws=stats.total_laws,
                           total_articles=stats.total_articles)
                
        except Exception as e:
            logger.error("데이터베이스 통계 조회 실패", error=str(e))
        
        return stats