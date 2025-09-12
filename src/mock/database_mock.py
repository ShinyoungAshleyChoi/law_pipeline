"""Mock 데이터베이스 연결"""
import sqlite3
import json
import uuid
from typing import Dict, Any, List, Optional, Union
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
import threading
from dataclasses import dataclass

from .data_generator import MockDataGenerator


@dataclass
class MockQueryResult:
    """Mock 쿼리 결과"""
    rows: List[Dict[str, Any]]
    rowcount: int
    description: List[str] = None
    
    def fetchall(self) -> List[Dict[str, Any]]:
        return self.rows
    
    def fetchone(self) -> Optional[Dict[str, Any]]:
        return self.rows[0] if self.rows else None
    
    def fetchmany(self, size: int) -> List[Dict[str, Any]]:
        return self.rows[:size]


class MockDatabaseConnection:
    """개발환경용 Mock 데이터베이스 연결"""
    
    def __init__(self, db_path: str = ":memory:", init_schema: bool = True):
        """
        Mock 데이터베이스 초기화
        
        Args:
            db_path: SQLite 데이터베이스 경로 (기본값: 메모리)
            init_schema: 스키마 초기화 여부
        """
        self.db_path = db_path
        self.data_generator = MockDataGenerator()
        self._local = threading.local()
        
        if init_schema:
            self._init_schema()
            self._populate_initial_data()
    
    def _get_connection(self) -> sqlite3.Connection:
        """스레드별 연결 획득"""
        if not hasattr(self._local, 'connection'):
            self._local.connection = sqlite3.connect(
                self.db_path, 
                check_same_thread=False,
                timeout=30.0
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection
    
    def _init_schema(self):
        """Mock 데이터베이스 스키마 초기화"""
        schema_sql = """
        -- 법률 문서 테이블
        CREATE TABLE IF NOT EXISTS legal_documents (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            doc_type TEXT NOT NULL,
            category TEXT,
            source TEXT,
            published_date TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            status TEXT DEFAULT 'active',
            metadata TEXT  -- JSON 형태로 저장
        );
        
        -- 문서 태그 테이블
        CREATE TABLE IF NOT EXISTS document_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT NOT NULL,
            tag TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (document_id) REFERENCES legal_documents(id),
            UNIQUE(document_id, tag)
        );
        
        -- 처리 로그 테이블  
        CREATE TABLE IF NOT EXISTS processing_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            document_id TEXT NOT NULL,
            action TEXT NOT NULL,  -- INSERT, UPDATE, DELETE
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            details TEXT,  -- JSON 형태로 저장
            status TEXT DEFAULT 'success',  -- success, error, pending
            error_message TEXT,
            FOREIGN KEY (document_id) REFERENCES legal_documents(id)
        );
        
        -- 동기화 상태 테이블
        CREATE TABLE IF NOT EXISTS sync_status (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,  -- api, file, manual
            last_sync_at TIMESTAMP,
            next_sync_at TIMESTAMP,
            total_processed INTEGER DEFAULT 0,
            successful_count INTEGER DEFAULT 0,
            error_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'idle',  -- idle, running, completed, failed
            details TEXT  -- JSON 형태로 저장
        );
        
        -- 인덱스 생성
        CREATE INDEX IF NOT EXISTS idx_legal_documents_type ON legal_documents(doc_type);
        CREATE INDEX IF NOT EXISTS idx_legal_documents_category ON legal_documents(category);
        CREATE INDEX IF NOT EXISTS idx_legal_documents_published ON legal_documents(published_date);
        CREATE INDEX IF NOT EXISTS idx_legal_documents_status ON legal_documents(status);
        CREATE INDEX IF NOT EXISTS idx_document_tags_tag ON document_tags(tag);
        CREATE INDEX IF NOT EXISTS idx_processing_logs_timestamp ON processing_logs(timestamp);
        CREATE INDEX IF NOT EXISTS idx_processing_logs_status ON processing_logs(status);
        """
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 스키마 실행
        for statement in schema_sql.split(';'):
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        
        conn.commit()
    
    def _populate_initial_data(self, count: int = 20):
        """초기 Mock 데이터 삽입"""
        documents = self.data_generator.generate_multiple_documents(count)
        
        for doc in documents:
            self.insert_document(doc)
        
        # 동기화 상태 초기 데이터
        self.execute("""
            INSERT OR IGNORE INTO sync_status (source_type, last_sync_at, status)
            VALUES (?, ?, ?)
        """, ('api', datetime.now(), 'completed'))
    
    def execute(self, query: str, params: tuple = None) -> MockQueryResult:
        """SQL 쿼리 실행"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # SELECT 쿼리의 경우 결과 반환
            if query.strip().upper().startswith('SELECT'):
                rows = [dict(row) for row in cursor.fetchall()]
                return MockQueryResult(rows=rows, rowcount=len(rows))
            else:
                # INSERT, UPDATE, DELETE 등
                conn.commit()
                return MockQueryResult(rows=[], rowcount=cursor.rowcount)
                
        except Exception as e:
            conn.rollback()
            raise e
    
    def executemany(self, query: str, params_list: List[tuple]) -> MockQueryResult:
        """여러 쿼리 실행"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        try:
            cursor.executemany(query, params_list)
            conn.commit()
            return MockQueryResult(rows=[], rowcount=cursor.rowcount)
        except Exception as e:
            conn.rollback()
            raise e
    
    @contextmanager
    def transaction(self):
        """트랜잭션 컨텍스트 매니저"""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
    
    # 비즈니스 로직 메서드들
    def insert_document(self, document: Dict[str, Any]) -> str:
        """문서 삽입"""
        doc_id = document['id']
        
        # 문서 본체 삽입
        self.execute("""
            INSERT OR REPLACE INTO legal_documents 
            (id, title, content, doc_type, category, source, published_date, status, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            doc_id,
            document['title'],
            document['content'],
            document['doc_type'],
            document['category'],
            document['source'],
            document['published_date'],
            document['status'],
            json.dumps(document.get('metadata', {}))
        ))
        
        # 태그 삽입
        if 'tags' in document:
            for tag in document['tags']:
                self.execute("""
                    INSERT OR IGNORE INTO document_tags (document_id, tag)
                    VALUES (?, ?)
                """, (doc_id, tag))
        
        # 처리 로그 기록
        self.log_processing(doc_id, 'INSERT', {'title': document['title']})
        
        return doc_id
    
    def update_document(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """문서 업데이트"""
        if not updates:
            return False
        
        # 동적 UPDATE 쿼리 생성
        set_clauses = []
        params = []
        
        for field, value in updates.items():
            if field == 'metadata':
                set_clauses.append(f"{field} = ?")
                params.append(json.dumps(value))
            elif field == 'tags':
                # 태그는 별도 처리
                continue
            else:
                set_clauses.append(f"{field} = ?")
                params.append(value)
        
        if set_clauses:
            set_clauses.append("updated_at = CURRENT_TIMESTAMP")
            params.append(doc_id)
            
            query = f"UPDATE legal_documents SET {', '.join(set_clauses)} WHERE id = ?"
            result = self.execute(query, tuple(params))
            
            if result.rowcount > 0:
                # 태그 업데이트
                if 'tags' in updates:
                    self.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))
                    for tag in updates['tags']:
                        self.execute("""
                            INSERT INTO document_tags (document_id, tag)
                            VALUES (?, ?)
                        """, (doc_id, tag))
                
                # 처리 로그 기록
                self.log_processing(doc_id, 'UPDATE', updates)
                return True
        
        return False
    
    def delete_document(self, doc_id: str) -> bool:
        """문서 삭제"""
        with self.transaction():
            # 관련 태그 삭제
            self.execute("DELETE FROM document_tags WHERE document_id = ?", (doc_id,))
            
            # 문서 삭제
            result = self.execute("DELETE FROM legal_documents WHERE id = ?", (doc_id,))
            
            if result.rowcount > 0:
                # 처리 로그 기록
                self.log_processing(doc_id, 'DELETE', {'deleted': True})
                return True
        
        return False
    
    def get_document(self, doc_id: str, include_tags: bool = True) -> Optional[Dict[str, Any]]:
        """문서 조회"""
        result = self.execute("""
            SELECT * FROM legal_documents WHERE id = ?
        """, (doc_id,))
        
        if not result.rows:
            return None
        
        document = result.rows[0]
        
        # 메타데이터 파싱
        if document['metadata']:
            document['metadata'] = json.loads(document['metadata'])
        
        # 태그 조회
        if include_tags:
            tags_result = self.execute("""
                SELECT tag FROM document_tags WHERE document_id = ?
            """, (doc_id,))
            document['tags'] = [row['tag'] for row in tags_result.rows]
        
        return document
    
    def search_documents(self, 
                        query: str = None, 
                        doc_type: str = None,
                        category: str = None,
                        status: str = None,
                        limit: int = 50,
                        offset: int = 0) -> List[Dict[str, Any]]:
        """문서 검색"""
        conditions = ["1=1"]  # 기본 조건
        params = []
        
        if query:
            conditions.append("(title LIKE ? OR content LIKE ?)")
            params.extend([f"%{query}%", f"%{query}%"])
        
        if doc_type:
            conditions.append("doc_type = ?")
            params.append(doc_type)
        
        if category:
            conditions.append("category = ?")
            params.append(category)
        
        if status:
            conditions.append("status = ?")
            params.append(status)
        
        params.extend([limit, offset])
        
        sql = f"""
            SELECT ld.*, GROUP_CONCAT(dt.tag) as tags
            FROM legal_documents ld
            LEFT JOIN document_tags dt ON ld.id = dt.document_id
            WHERE {' AND '.join(conditions)}
            GROUP BY ld.id
            ORDER BY ld.published_date DESC
            LIMIT ? OFFSET ?
        """
        
        result = self.execute(sql, tuple(params))
        
        # 태그 문자열을 리스트로 변환
        for doc in result.rows:
            if doc['metadata']:
                doc['metadata'] = json.loads(doc['metadata'])
            doc['tags'] = doc['tags'].split(',') if doc['tags'] else []
        
        return result.rows
    
    def get_recent_documents(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """최근 문서 조회"""
        result = self.execute("""
            SELECT ld.*, GROUP_CONCAT(dt.tag) as tags
            FROM legal_documents ld
            LEFT JOIN document_tags dt ON ld.id = dt.document_id
            WHERE ld.published_date >= datetime('now', '-{} days')
            GROUP BY ld.id
            ORDER BY ld.published_date DESC
            LIMIT ?
        """.format(days), (limit,))
        
        # 태그 처리
        for doc in result.rows:
            if doc['metadata']:
                doc['metadata'] = json.loads(doc['metadata'])
            doc['tags'] = doc['tags'].split(',') if doc['tags'] else []
        
        return result.rows
    
    def get_statistics(self) -> Dict[str, Any]:
        """데이터베이스 통계"""
        stats = {}
        
        # 전체 문서 수
        result = self.execute("SELECT COUNT(*) as total FROM legal_documents")
        stats['total_documents'] = result.rows[0]['total']
        
        # 문서 타입별 통계
        result = self.execute("""
            SELECT doc_type, COUNT(*) as count
            FROM legal_documents
            GROUP BY doc_type
        """)
        stats['by_doc_type'] = {row['doc_type']: row['count'] for row in result.rows}
        
        # 카테고리별 통계  
        result = self.execute("""
            SELECT category, COUNT(*) as count
            FROM legal_documents
            WHERE category IS NOT NULL
            GROUP BY category
        """)
        stats['by_category'] = {row['category']: row['count'] for row in result.rows}
        
        # 상태별 통계
        result = self.execute("""
            SELECT status, COUNT(*) as count
            FROM legal_documents
            GROUP BY status
        """)
        stats['by_status'] = {row['status']: row['count'] for row in result.rows}
        
        # 최근 처리 통계
        result = self.execute("""
            SELECT action, COUNT(*) as count
            FROM processing_logs
            WHERE timestamp >= datetime('now', '-7 days')
            GROUP BY action
        """)
        stats['recent_processing'] = {row['action']: row['count'] for row in result.rows}
        
        return stats
    
    def log_processing(self, doc_id: str, action: str, details: Dict[str, Any] = None, status: str = 'success', error_message: str = None):
        """처리 로그 기록"""
        self.execute("""
            INSERT INTO processing_logs (document_id, action, details, status, error_message)
            VALUES (?, ?, ?, ?, ?)
        """, (
            doc_id,
            action,
            json.dumps(details or {}),
            status,
            error_message
        ))
    
    def get_processing_logs(self, doc_id: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """처리 로그 조회"""
        if doc_id:
            result = self.execute("""
                SELECT * FROM processing_logs 
                WHERE document_id = ?
                ORDER BY timestamp DESC
                LIMIT ?
            """, (doc_id, limit))
        else:
            result = self.execute("""
                SELECT * FROM processing_logs
                ORDER BY timestamp DESC
                LIMIT ?
            """, (limit,))
        
        # details JSON 파싱
        for log in result.rows:
            if log['details']:
                log['details'] = json.loads(log['details'])
        
        return result.rows
    
    def update_sync_status(self, source_type: str, status: str, details: Dict[str, Any] = None):
        """동기화 상태 업데이트"""
        self.execute("""
            INSERT OR REPLACE INTO sync_status 
            (source_type, last_sync_at, status, details)
            VALUES (?, CURRENT_TIMESTAMP, ?, ?)
        """, (source_type, status, json.dumps(details or {})))
    
    def get_sync_status(self, source_type: str = None) -> List[Dict[str, Any]]:
        """동기화 상태 조회"""
        if source_type:
            result = self.execute("""
                SELECT * FROM sync_status WHERE source_type = ?
            """, (source_type,))
        else:
            result = self.execute("SELECT * FROM sync_status")
        
        # details JSON 파싱
        for status in result.rows:
            if status['details']:
                status['details'] = json.loads(status['details'])
        
        return result.rows
    
    def bulk_insert_documents(self, documents: List[Dict[str, Any]]) -> int:
        """대량 문서 삽입"""
        inserted_count = 0
        
        with self.transaction():
            for doc in documents:
                try:
                    self.insert_document(doc)
                    inserted_count += 1
                except Exception as e:
                    # 실패한 경우 로그만 기록하고 계속 진행
                    self.log_processing(
                        doc.get('id', 'unknown'),
                        'INSERT',
                        {'error': str(e)},
                        status='error',
                        error_message=str(e)
                    )
        
        return inserted_count
    
    def close(self):
        """연결 종료"""
        if hasattr(self._local, 'connection'):
            self._local.connection.close()
            del self._local.connection


# 팩토리 함수들
def create_mock_db_connection(db_path: str = ":memory:", populate: bool = True) -> MockDatabaseConnection:
    """Mock 데이터베이스 연결 생성"""
    return MockDatabaseConnection(db_path, init_schema=populate)


def create_persistent_mock_db(db_name: str = "mock_legal_db.sqlite") -> MockDatabaseConnection:
    """영구 Mock 데이터베이스 생성"""
    db_path = Path("sample_data") / db_name
    db_path.parent.mkdir(exist_ok=True)
    return MockDatabaseConnection(str(db_path), init_schema=True)


# Repository 패턴 Mock 구현
class MockLegalDocumentRepository:
    """Mock 법률 문서 Repository"""
    
    def __init__(self, db_connection: MockDatabaseConnection = None):
        self.db = db_connection or create_mock_db_connection()
    
    def save(self, document: Dict[str, Any]) -> str:
        """문서 저장"""
        return self.db.insert_document(document)
    
    def update(self, doc_id: str, updates: Dict[str, Any]) -> bool:
        """문서 업데이트"""
        return self.db.update_document(doc_id, updates)
    
    def delete(self, doc_id: str) -> bool:
        """문서 삭제"""
        return self.db.delete_document(doc_id)
    
    def find_by_id(self, doc_id: str) -> Optional[Dict[str, Any]]:
        """ID로 문서 검색"""
        return self.db.get_document(doc_id)
    
    def find_all(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """모든 문서 검색"""
        return self.db.search_documents(limit=limit, offset=offset)
    
    def search(self, query: str, **filters) -> List[Dict[str, Any]]:
        """문서 검색"""
        return self.db.search_documents(query=query, **filters)
    
    def find_recent(self, days: int = 30, limit: int = 20) -> List[Dict[str, Any]]:
        """최근 문서 검색"""
        return self.db.get_recent_documents(days, limit)
    
    def count_all(self) -> int:
        """전체 문서 수"""
        stats = self.db.get_statistics()
        return stats['total_documents']
    
    def get_stats(self) -> Dict[str, Any]:
        """통계 조회"""
        return self.db.get_statistics()


if __name__ == "__main__":
    # 테스트용 코드
    print("Mock 데이터베이스 테스트 시작...")
    
    # Mock DB 연결 생성
    db = create_mock_db_connection()
    
    # 통계 출력
    stats = db.get_statistics()
    print(f"총 문서 수: {stats['total_documents']}")
    print(f"문서 타입별: {stats['by_doc_type']}")
    print(f"카테고리별: {stats['by_category']}")
    
    # 검색 테스트
    recent_docs = db.get_recent_documents(30, 5)
    print(f"\n최근 30일 문서 {len(recent_docs)}개:")
    for doc in recent_docs:
        print(f"- {doc['id']}: {doc['title']}")
    
    # Repository 테스트
    repo = MockLegalDocumentRepository(db)
    search_results = repo.search("개인정보", limit=3)
    print(f"\n'개인정보' 검색 결과 {len(search_results)}개:")
    for doc in search_results:
        print(f"- {doc['id']}: {doc['title']}")
    
    print("\nMock 데이터베이스 테스트 완료!")
