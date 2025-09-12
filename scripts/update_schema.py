#!/usr/bin/env python3
"""데이터베이스 스키마 업데이트 스크립트"""

import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.database.connection import db_connection
from src.logging_config import get_logger

logger = get_logger(__name__)

def update_schema():
    """데이터베이스 스키마 업데이트"""
    try:
        with db_connection.get_connection() as conn:
            cursor = conn.cursor()
            
            # 스키마 파일 읽기
            schema_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'src', 'database', 'schema.sql')
            with open(schema_file, 'r', encoding='utf-8') as f:
                schema_sql = f.read()
            
            # SQL 문을 세미콜론으로 분리하여 실행
            statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]
            
            for statement in statements:
                if statement:
                    logger.info(f"실행 중: {statement[:100]}...")
                    cursor.execute(statement)
            
            conn.commit()
            cursor.close()
            
            logger.info("데이터베이스 스키마 업데이트 완료")
            return True
            
    except Exception as e:
        logger.error(f"스키마 업데이트 실패: {e}")
        return False

if __name__ == "__main__":
    success = update_schema()
    sys.exit(0 if success else 1)