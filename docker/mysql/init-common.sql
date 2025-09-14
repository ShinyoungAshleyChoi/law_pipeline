-- MySQL Blue/Green 공통 초기화 스크립트
-- Blue, Green 양쪽 DB 컨테이너에서 동일하게 실행됩니다.
-- Docker 컨테이너 시작 시 자동으로 실행됩니다.

USE legal_db;

-- 블루그린 설정 확인 및 업데이트
-- 처음에는 Blue가 기본 활성 환경입니다.

UPDATE blue_green_config 
SET config_value = 'BLUE', updated_by = 'MYSQL_INIT' 
WHERE config_key = 'ACTIVE_DATABASE';

UPDATE blue_green_config 
SET config_value = NOW(), updated_by = 'MYSQL_INIT' 
WHERE config_key = 'SWITCH_TIMESTAMP' AND config_value = '';

UPDATE blue_green_config 
SET config_value = 'IDLE', updated_by = 'MYSQL_INIT' 
WHERE config_key = 'SYNC_STATUS';

UPDATE blue_green_config 
SET config_value = 'PENDING', updated_by = 'MYSQL_INIT' 
WHERE config_key = 'DATA_VALIDATION_STATUS';

-- 초기화 완료 로그
INSERT INTO blue_green_config (config_key, config_value, description, updated_by) VALUES
('MYSQL_INIT_COMPLETED', NOW(), 'MySQL 컨테이너 초기화 완료 시간', 'MYSQL_INIT')
ON DUPLICATE KEY UPDATE 
    config_value = NOW(), 
    updated_by = 'MYSQL_INIT';

-- 테스트 데이터 (개발 환경용, 운영 환경에서는 제거)
-- 블루그린 동작 테스트를 위한 샘플 데이터
INSERT INTO law_list (
    law_id, law_name_korean, promulgation_date, enforcement_date, 
    ministry_name, law_type_name, revision_type
) VALUES
('LAW-TEST-001', '블루그린 테스트 법령 1', '20250101', '20250101', '법무부', '법률', '제정'),
('LAW-TEST-002', '블루그린 테스트 법령 2', '20250101', '20250101', '기획재정부', '시행령', '개정')
ON DUPLICATE KEY UPDATE law_name_korean = VALUES(law_name_korean);

INSERT INTO law_content (
    law_id, law_name_korean, promulgation_date, enforcement_date, 
    article_no, article_title, article_content
) VALUES
('LAW-TEST-001', '블루그린 테스트 법령 1', '20250101', '20250101', 
 '1', '목적', '이 법은 블루그린 배포 테스트를 목적으로 한다.'),
('LAW-TEST-002', '블루그린 테스트 법령 2', '20250101', '20250101', 
 '1', '정의', '이 령에서 사용하는 용어의 뜻은 다음과 같다.')
ON DUPLICATE KEY UPDATE law_name_korean = VALUES(law_name_korean);

INSERT INTO law_articles (
    law_key, law_id, law_name_korean, promulgation_date, enforcement_date, 
    article_no, article_title, article_content
) VALUES
('TEST-KEY-001', 'LAW-TEST-001', '블루그린 테스트 법령 1', '20250101', '20250101', 
 '1', '목적', '이 법은 블루그린 배포 테스트를 목적으로 한다.'),
('TEST-KEY-002', 'LAW-TEST-002', '블루그린 테스트 법령 2', '20250101', '20250101', 
 '1', '정의', '이 령에서 사용하는 용어의 뜻은 다음과 같다.')
ON DUPLICATE KEY UPDATE law_name_korean = VALUES(law_name_korean);

-- 레코드 카운트 초기화
UPDATE blue_green_config 
SET config_value = (SELECT COUNT(*) FROM law_list), updated_by = 'MYSQL_INIT' 
WHERE config_key = 'BLUE_RECORD_COUNT';

UPDATE blue_green_config 
SET config_value = (SELECT COUNT(*) FROM law_list), updated_by = 'MYSQL_INIT' 
WHERE config_key = 'GREEN_RECORD_COUNT';

-- 초기화 완료 확인
SELECT 
    'MySQL Blue-Green 초기화 완료' as status,
    COUNT(*) as config_count 
FROM blue_green_config;

-- 현재 설정값 출력
SELECT 
    config_key, 
    config_value, 
    updated_at, 
    updated_by 
FROM blue_green_config 
ORDER BY config_key;
