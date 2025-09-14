"""실제 API 응답 기반 데이터베이스 저장소 계층 구현"""
from typing import List, Optional, Dict, Any, Tuple
from datetime import date, datetime
import uuid
from contextlib import contextmanager
import mysql.connector
from mysql.connector import Error as MySQLError
import structlog

from .connection import db_connection
from .models import (
    LawList, LawContent, LawArticle, BatchJob, SyncStatus, DatabaseStats,
    JobStatus, JobType, SyncType,
    dict_to_law_list, dict_to_law_content, dict_to_law_article,
    dict_to_batch_job, dict_to_sync_status
)
from logging_config import get_logger

logger = get_logger(__name__)

class LegalDataRepository:
    """법령 데이터 저장소 클래스 (실제 API 응답 기반)"""
    
    def __init__(self, target_db_host: str = "mysql-green"):
        self._current_connection = None
        self._transaction_active = False
        self.target_db_host = target_db_host  # 타겟 DB 호스트 저장
    
    @contextmanager
    def transaction(self):
        """트랜잭션 컨텍스트 매니저"""
        if self._transaction_active:
            # 이미 트랜잭션이 활성화된 경우 중첩 트랜잭션 지원
            logger.debug("중첩 트랜잭션 사용")
            yield
            return
            
        logger.debug("새 트랜잭션 시작 시도", target_db=self.target_db_host)
        
        try:
            # 타겟 DB 호스트로 연결 생성
            with self._get_target_connection() as conn:
                logger.debug("데이터베이스 연결 획득 성공", target_db=self.target_db_host)
                self._current_connection = conn
                self._transaction_active = True
                
                try:
                    conn.start_transaction()
                    logger.debug("트랜잭션 시작 성공")
                    yield
                    conn.commit()
                    logger.debug("트랜잭션 커밋 완료")
                    
                except Exception as e:
                    logger.error("트랜잭션 처리 중 에러 발생", 
                               error=str(e), 
                               error_type=type(e).__name__,
                               target_db=self.target_db_host,
                               connection_active=conn.is_connected() if hasattr(conn, 'is_connected') else 'unknown')
                    
                    try:
                        conn.rollback()
                        logger.error("트랜잭션 롤백 완료", error=str(e))
                    except Exception as rollback_error:
                        logger.error("트랜잭션 롤백도 실패", 
                                   original_error=str(e),
                                   rollback_error=str(rollback_error))
                    raise
                    
                finally:
                    self._current_connection = None
                    self._transaction_active = False
                    
        except Exception as e:
            logger.error("데이터베이스 연결 획득 실패", 
                       error=str(e), 
                       error_type=type(e).__name__,
                       target_db=self.target_db_host)
            raise
    
    @contextmanager
    def _get_target_connection(self):
        """타겟 DB로의 직접 연결 생성"""
        import mysql.connector
        
        # 타겟 DB별 연결 설정
        db_config = {
            'user': 'legal_user',
            'password': 'legal_pass_2024!',
            'database': 'legal_db',
            'host': self.target_db_host,
            'port': 3306,
            'charset': 'utf8mb4',
            'autocommit': True,
            'connection_timeout': 30
        }
        
        connection = None
        try:
            logger.debug("타겟 DB 직접 연결 시작", target_db=self.target_db_host)
            connection = mysql.connector.connect(**db_config)
            logger.debug("타겟 DB 연결 성공", target_db=self.target_db_host)
            yield connection
            
        except mysql.connector.Error as e:
            logger.error("타겟 DB 연결 실패", 
                        target_db=self.target_db_host,
                        mysql_error=str(e))
            if connection:
                try:
                    connection.rollback()
                except Exception:
                    pass
            raise
            
        finally:
            if connection and connection.is_connected():
                connection.close()
                logger.debug("타겟 DB 연결 종료", target_db=self.target_db_host)
    
    def _get_connection(self):
        """현재 연결 반환 (트랜잭션 중이면 현재 연결, 아니면 새 연결)"""
        if self._current_connection:
            return self._current_connection
        # 기존 db_connection 대신 타겟 DB로 직접 연결
        return self._get_target_connection()
    
    # ==================== 법령 목록 CRUD 연산 ====================
    
    def save_law_list(self, law_list: LawList) -> bool:
        """법령 목록 데이터 저장/업데이트"""
        logger.debug("법령 목록 저장 시작", 
                    law_id=getattr(law_list, 'law_id', None),
                    law_name=getattr(law_list, 'law_name_korean', None),
                    target_db=self.target_db_host)
        
        # 입력 데이터 검증
        if not hasattr(law_list, 'law_id') or not law_list.law_id:
            logger.error("법령ID가 없습니다", data=vars(law_list))
            return False
            
        try:
            if self._transaction_active:
                logger.debug("트랜잭션 내에서 저장")
                return self._save_law_list_with_connection(self._current_connection, law_list)
            else:
                logger.debug("새 연결로 저장")
                with self._get_target_connection() as conn:
                    return self._save_law_list_with_connection(conn, law_list)
                    
        except mysql.connector.Error as e:
            logger.error("MySQL 에러 발생", 
                        law_id=getattr(law_list, 'law_id', None), 
                        mysql_error_code=e.errno,
                        mysql_error_msg=e.msg,
                        target_db=self.target_db_host,
                        data=vars(law_list))
            return False
        except Exception as e:
            logger.error("법령 목록 저장 실패", 
                        law_id=getattr(law_list, 'law_id', None), 
                        data=vars(law_list), 
                        error=str(e),
                        target_db=self.target_db_host,
                        error_type=type(e).__name__)
            return False
    
    def _save_law_list_with_connection(self, conn, law_list: LawList) -> bool:
        """연결을 사용하여 법령 목록 저장"""
        logger.debug("연결을 통한 법령 목록 저장 시작", law_id=getattr(law_list, 'law_id', None))
        
        cursor = conn.cursor()
        try:
            # 기존 법령 확인 (law_id 기준)
            if law_list.law_id:
                logger.debug("기존 법령 확인 중", law_id=law_list.law_id)
                check_sql = "SELECT id FROM law_list WHERE law_id = %s"
                cursor.execute(check_sql, (law_list.law_id,))
                existing = cursor.fetchone()
                
                if existing:
                    logger.debug("기존 법령 발견, 업데이트 실행", law_id=law_list.law_id, existing_id=existing[0])
                    # 업데이트
                    update_sql = """
                    UPDATE law_list SET 
                        law_name_korean = %s, law_abbr_name = %s, 
                        enforcement_date = %s, ministry_name = %s,
                        law_type_name = %s, updated_at = CURRENT_TIMESTAMP
                    WHERE law_id = %s
                    """
                    update_params = (
                        getattr(law_list, 'law_name_korean', None), 
                        getattr(law_list, 'law_abbr_name', None),
                        getattr(law_list, 'enforcement_date', None), 
                        getattr(law_list, 'ministry_name', None),
                        getattr(law_list, 'law_type_name', None), 
                        getattr(law_list, 'law_id', None)
                    )
                    logger.debug("업데이트 파라미터", params=update_params)
                    cursor.execute(update_sql, update_params)
                    logger.debug("법령 목록 업데이트 완료", law_id=getattr(law_list, 'law_id', None), rowcount=cursor.rowcount)
                else:
                    logger.debug("새 법령, 삽입 실행", law_id=law_list.law_id)
                    # 삽입 - 실제로 사용하는 필드만
                    insert_sql = """
                    INSERT INTO law_list (
                        law_id, law_name_korean, enforcement_date, 
                        promulgation_date, law_type_name, ministry_name
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """
                    insert_params = (
                        getattr(law_list, 'law_id', None),
                        getattr(law_list, 'law_name_korean', None), 
                        getattr(law_list, 'enforcement_date', None),
                        getattr(law_list, 'promulgation_date', None),
                        getattr(law_list, 'law_type_name', None),
                        getattr(law_list, 'ministry_name', None)
                    )
                    logger.debug("삽입 파라미터", params=insert_params)
                    cursor.execute(insert_sql, insert_params)
                    logger.debug("법령 목록 삽입 완료", law_id=getattr(law_list, 'law_id', None), rowcount=cursor.rowcount)
            
            success = cursor.rowcount > 0
            logger.debug("저장 결과", success=success, rowcount=cursor.rowcount)
            return success
            
        except mysql.connector.Error as e:
            logger.error("MySQL 쿼리 실행 에러", 
                        law_id=getattr(law_list, 'law_id', None),
                        mysql_error_code=e.errno,
                        mysql_error_msg=e.msg,
                        target_db=self.target_db_host,
                        sql_state=getattr(e, 'sqlstate', None))
            raise
        except Exception as e:
            logger.error("법령 목록 저장 중 예외 발생", 
                        law_id=getattr(law_list, 'law_id', None),
                        error=str(e),
                        error_type=type(e).__name__)
            raise
        finally:
            cursor.close()
            logger.debug("커서 닫기 완료")
    
    def get_law_list_by_id(self, law_id: str) -> Optional[LawList]:
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
                with self._get_target_connection() as conn:
                    return self._save_law_content_with_connection(conn, law_content)
                    
        except Exception as e:
            logger.error("법령 본문 저장 실패", 
                        law_id=getattr(law_content, 'law_id', None), 
                        target_db=self.target_db_host,
                        error=str(e))
            return False
    
    def _save_law_content_with_connection(self, conn, law_content: LawContent) -> bool:
        """연결을 사용하여 법령 본문 저장"""
        cursor = conn.cursor()
        try:
            # 실제로 사용하는 필드만으로 간단한 INSERT 구문 사용
            insert_sql = """
            INSERT INTO law_content (
                law_id, law_name_korean, article_content, 
                enforcement_date, promulgation_date
            ) VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                law_name_korean = VALUES(law_name_korean),
                article_content = VALUES(article_content),
                enforcement_date = VALUES(enforcement_date),
                promulgation_date = VALUES(promulgation_date),
                updated_at = CURRENT_TIMESTAMP
            """
            
            # 실제로 설정된 필드만 전달 (5개)
            cursor.execute(insert_sql, (
                getattr(law_content, 'law_id', None),
                getattr(law_content, 'law_name_korean', None), 
                getattr(law_content, 'article_content', None),
                getattr(law_content, 'enforcement_date', None),
                getattr(law_content, 'promulgation_date', None)
            ))
            
            logger.debug("법령 본문 저장 완료", 
                        law_id=getattr(law_content, 'law_id', None),
                        target_db=self.target_db_host)
            return cursor.rowcount > 0
            
        finally:
            cursor.close()
    
    def get_law_content_by_id(self, law_id: str) -> List[LawContent]:
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
                with self._get_target_connection() as conn:
                    return self._save_law_article_with_connection(conn, law_article)
                    
        except Exception as e:
            logger.error("법령 조항조목 저장 실패", 
                        law_id=getattr(law_article, 'law_id', None),
                        target_db=self.target_db_host, 
                        error=str(e))
            return False
    
    def _save_law_article_with_connection(self, conn, law_article: LawArticle) -> bool:
        """연결을 사용하여 법령 조항조목 저장"""
        cursor = conn.cursor()
        try:
            insert_sql = """
            INSERT INTO law_articles (
                law_key, law_id, article_no, article_title, article_content
            ) VALUES (%s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                law_id = VALUES(law_id),
                article_title = VALUES(article_title),
                article_content = VALUES(article_content),
                updated_at = CURRENT_TIMESTAMP
            """
            cursor.execute(insert_sql, (
                getattr(law_article, 'law_key', None), 
                getattr(law_article, 'law_id', None),
                getattr(law_article, 'article_no', None),
                getattr(law_article, 'article_title', None), 
                getattr(law_article, 'article_content', None)
            ))
            
            logger.debug("법령 조항조목 저장 완료", 
                        law_key=getattr(law_article, 'law_key', None), 
                        article_no=getattr(law_article, 'article_no', None),
                        target_db=self.target_db_host)
            return cursor.rowcount > 0
            
        finally:
            cursor.close()
    
    def get_law_articles_by_law_key(self, law_key: str) -> List[LawArticle]:
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
                               processed_laws: str = "0", processed_articles: str = "0",
                               error_count: str = "0", error_details: Optional[str] = None) -> bool:
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
                    status.value, end_time, str(processed_laws), str(processed_articles),
                    str(error_count), error_details, job_id
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
                          total_laws_count: str = "0", total_articles_count: str = "0",
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
                        sync_date, last_enforcement_date, str(total_laws_count), 
                        str(total_articles_count), sync_type
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
                        str(total_laws_count), str(total_articles_count)
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