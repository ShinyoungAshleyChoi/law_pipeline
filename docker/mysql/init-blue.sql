-- MySQL Blue 환경 초기화 스크립트

USE legal_db;

-- Blue 환경임을 표시하는 메타데이터 테이블
CREATE TABLE IF NOT EXISTS deployment_info (
    id INT PRIMARY KEY AUTO_INCREMENT,
    environment ENUM('blue', 'green') NOT NULL DEFAULT 'blue',
    version VARCHAR(50) NOT NULL DEFAULT '1.0.0',
    deployed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Blue 환경 정보 삽입
INSERT INTO deployment_info (environment, version, is_active) 
VALUES ('blue', '1.0.0', TRUE) 
ON DUPLICATE KEY UPDATE 
    version = VALUES(version),
    deployed_at = CURRENT_TIMESTAMP,
    updated_at = CURRENT_TIMESTAMP;

-- 초기 동기화 상태 설정 (Blue 환경)
INSERT INTO sync_status (sync_type, last_sync_date, total_laws_count, total_articles_count)
VALUES 
    ('FULL', CURDATE() - INTERVAL 1 DAY, 0, 0),
    ('INCREMENTAL', CURDATE() - INTERVAL 1 DAY, 0, 0)
ON DUPLICATE KEY UPDATE 
    updated_at = CURRENT_TIMESTAMP;

-- 인덱스 최적화 설정
SET GLOBAL innodb_stats_on_metadata = OFF;
SET GLOBAL innodb_stats_sample_pages = 8;

-- Blue 환경 설정 완료 로그
INSERT INTO batch_jobs (job_id, job_type, status, start_time, end_time, processed_laws, processed_articles, error_count)
VALUES (
    CONCAT('BLUE_INIT_', DATE_FORMAT(NOW(), '%Y%m%d_%H%i%s')),
    'VALIDATION',
    'SUCCESS',
    NOW(),
    NOW(),
    0,
    0,
    0
);

-- 성능 통계 수집 활성화
ANALYZE TABLE law_list, law_content, law_articles, batch_jobs, sync_status;

SELECT 'Blue environment initialized successfully' as status;
