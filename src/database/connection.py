"""데이터베이스 연결 관리 모듈"""
import mysql.connector
from mysql.connector import pooling, Error
from sqlalchemy import create_engine
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine
else:
    Engine = None
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from typing import Optional, Generator, Any

from config import config
from logging_config import get_logger

logger = get_logger(__name__)

class DatabaseConnection:
    """데이터베이스 연결 관리자"""
    
    def __init__(self):
        self._engine: Optional[Any] = None
        self._session_factory: Optional[sessionmaker] = None
        self._connection_pool: Optional[pooling.MySQLConnectionPool] = None
        
    def initialize(self) -> None:
        """데이터베이스 연결 초기화"""
        try:
            db_config = config.database
            
            # SQLAlchemy 엔진 생성
            connection_string = (
                f"mysql+pymysql://{db_config.user}:{db_config.password}@"
                f"{db_config.host}:{db_config.port}/{db_config.name}"
                f"?charset={db_config.charset}"
            )
            
            self._engine = create_engine(
                connection_string,
                poolclass=QueuePool,
                pool_size=db_config.pool_size,
                max_overflow=db_config.max_overflow,
                pool_timeout=db_config.pool_timeout,
                pool_recycle=db_config.pool_recycle,
                echo=False  # SQL 로깅 비활성화 (운영 환경)
            )
            
            # 세션 팩토리 생성
            self._session_factory = sessionmaker(bind=self._engine)
            
            # MySQL Connector 연결 풀 생성 (직접 SQL 실행용)
            pool_config = {
                'pool_name': 'legal_data_pool',
                'pool_size': db_config.pool_size,
                'pool_reset_session': True,
                'host': db_config.host,
                'port': db_config.port,
                'database': db_config.name,
                'user': db_config.user,
                'password': db_config.password,
                'charset': db_config.charset,
                'autocommit': False,
                'time_zone': '+09:00'
            }
            
            self._connection_pool = pooling.MySQLConnectionPool(**pool_config)
            
            logger.info("데이터베이스 연결 초기화 완료", 
                       host=db_config.host, 
                       database=db_config.name,
                       pool_size=db_config.pool_size)
            
        except Exception as e:
            logger.error("데이터베이스 연결 초기화 실패", error=str(e))
            raise
    
    @property
    def engine(self) -> Any:
        """SQLAlchemy 엔진 반환"""
        if self._engine is None:
            self.initialize()
        return self._engine
    
    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """SQLAlchemy 세션 컨텍스트 매니저"""
        if self._session_factory is None:
            self.initialize()
        
        session = self._session_factory()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error("데이터베이스 세션 오류", error=str(e))
            raise
        finally:
            session.close()
    
    @contextmanager
    def get_connection(self) -> Generator[mysql.connector.MySQLConnection, None, None]:
        """MySQL Connector 연결 컨텍스트 매니저"""
        if self._connection_pool is None:
            logger.debug("연결 풀이 없어 초기화 시도")
            self.initialize()
        
        connection = None
        try:
            logger.debug("연결 풀에서 연결 획득 시도")
            connection = self._connection_pool.get_connection()
            logger.debug("연결 획득 성공", 
                        connection_id=connection.connection_id if hasattr(connection, 'connection_id') else 'unknown',
                        is_connected=connection.is_connected())
            yield connection
            logger.debug("연결 사용 완료")
            
        except Error as e:
            logger.error("MySQL 연결 에러 발생", 
                        mysql_error_code=e.errno if hasattr(e, 'errno') else 'unknown',
                        mysql_error_msg=e.msg if hasattr(e, 'msg') else str(e),
                        connection_available=connection is not None)
            
            if connection:
                try:
                    logger.debug("연결 롤백 시도")
                    connection.rollback()
                    logger.debug("연결 롤백 완료")
                except Exception as rollback_error:
                    logger.error("롤백 실패", error=str(rollback_error))
            raise
            
        except Exception as e:
            logger.error("일반 연결 오류", 
                        error=str(e), 
                        error_type=type(e).__name__,
                        connection_available=connection is not None)
            
            if connection:
                try:
                    connection.rollback()
                    logger.debug("예외 상황에서 롤백 완료")
                except Exception as rollback_error:
                    logger.error("예외 상황 롤백 실패", error=str(rollback_error))
            raise
            
        finally:
            if connection and connection.is_connected():
                logger.debug("연결 반납 시도")
                try:
                    connection.close()
                    logger.debug("연결 반납 완료")
                except Exception as close_error:
                    logger.error("연결 종료 실패", error=str(close_error))
            elif connection:
                logger.warning("이미 닫힌 연결")
    
    def test_connection(self) -> bool:
        """데이터베이스 연결 테스트"""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT 1")
                result = cursor.fetchone()
                cursor.close()
                
                if result and result[0] == 1:
                    logger.info("데이터베이스 연결 테스트 성공")
                    return True
                else:
                    logger.error("데이터베이스 연결 테스트 실패: 예상하지 못한 결과")
                    return False
                    
        except Exception as e:
            logger.error("데이터베이스 연결 테스트 실패", error=str(e))
            return False
    
    def close(self) -> None:
        """연결 풀 종료"""
        try:
            if self._engine:
                self._engine.dispose()
                logger.info("SQLAlchemy 엔진 종료 완료")
            
            # MySQL Connector 풀은 자동으로 정리됨
            logger.info("데이터베이스 연결 종료 완료")
            
        except Exception as e:
            logger.error("데이터베이스 연결 종료 중 오류", error=str(e))

# 전역 데이터베이스 연결 인스턴스
db_connection = DatabaseConnection()