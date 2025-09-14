-- 법제처 데이터 파이프라인 데이터베이스 스키마 (실제 API 응답 기반)
-- 법령 목록, 법령 본문, 조항조목 정보, 배치 작업, 동기화 상태 테이블 생성

-- 법령 목록 정보 테이블 (법령 목록 조회 API 응답 기반)
CREATE TABLE IF NOT EXISTS law_list (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    -- API 응답 필드들
    target VARCHAR(100) COMMENT '검색서비스 대상',
    keyword VARCHAR(500) COMMENT '검색어',
    section VARCHAR(100) COMMENT '검색범위',
    total_cnt VARCHAR(20) COMMENT '검색건수',
    page VARCHAR(20) COMMENT '결과페이지번호',
    law_id VARCHAR(100) COMMENT '법령ID',
    law_serial_no VARCHAR(100) COMMENT '법령일련번호',
    current_history_code VARCHAR(50) COMMENT '현행연혁코드',
    law_name_korean VARCHAR(1000) COMMENT '법령명한글',
    law_abbr_name VARCHAR(500) COMMENT '법령약칭명',
    promulgation_date VARCHAR(20) COMMENT '공포일자 (YYYYMMDD)',
    promulgation_no VARCHAR(50) COMMENT '공포번호',
    revision_type VARCHAR(100) COMMENT '제개정구분명',
    ministry_name VARCHAR(200) COMMENT '소관부처명',
    ministry_code VARCHAR(50) COMMENT '소관부처코드',
    law_type_name VARCHAR(100) COMMENT '법령구분명',
    joint_ministry_type VARCHAR(100) COMMENT '공동부령구분',
    joint_promulgation_no VARCHAR(100) COMMENT '공포번호(공동부령의 공포번호)',
    enforcement_date VARCHAR(20) COMMENT '시행일자 (YYYYMMDD)',
    self_other_law_yn VARCHAR(10) COMMENT '자법타법여부',
    law_detail_link TEXT COMMENT '법령상세링크',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 인덱스
    INDEX idx_law_id (law_id),
    INDEX idx_law_serial_no (law_serial_no),
    INDEX idx_law_name_korean (law_name_korean(100)),
    INDEX idx_enforcement_date (enforcement_date),
    INDEX idx_ministry_code (ministry_code),
    INDEX idx_law_type_name (law_type_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='법령 목록 정보 - 법령 목록 조회 API 응답 저장';

-- 법령 본문 정보 테이블 (법령 본문 조회 API 응답 기반)
CREATE TABLE IF NOT EXISTS law_content (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    -- 기본 법령 정보
    law_id VARCHAR(100) COMMENT '법령ID',
    promulgation_date VARCHAR(20) COMMENT '공포일자 (YYYYMMDD)',
    promulgation_no VARCHAR(50) COMMENT '공포번호',
    language VARCHAR(50) COMMENT '언어종류',
    law_type VARCHAR(100) COMMENT '법종구분',
    law_type_code VARCHAR(50) COMMENT '법종구분코드',
    law_name_korean VARCHAR(1000) COMMENT '법령명_한글',
    law_name_hanja VARCHAR(1000) COMMENT '법령명_한자',
    law_abbr_name VARCHAR(500) COMMENT '법령명약칭',
    title_change_yn VARCHAR(10) COMMENT '제명변경여부',
    korean_law_yn VARCHAR(10) COMMENT '한글법령여부',
    chapter_section_no VARCHAR(50) COMMENT '편장절관 일련번호',
    ministry_code VARCHAR(50) COMMENT '소관부처코드',
    ministry_name VARCHAR(200) COMMENT '소관부처명',
    phone_number VARCHAR(50) COMMENT '전화번호',
    enforcement_date VARCHAR(20) COMMENT '시행일자 (YYYYMMDD)',
    revision_type VARCHAR(100) COMMENT '제개정구분',
    appendix_edit_yn VARCHAR(10) COMMENT '별표편집여부',
    promulgated_law_yn VARCHAR(10) COMMENT '공포법령여부',
    department_name VARCHAR(200) COMMENT '부서명',
    department_phone VARCHAR(50) COMMENT '부서연락처',
    joint_ministry_type VARCHAR(100) COMMENT '공동부령구분',
    joint_type_code VARCHAR(50) COMMENT '구분코드(공동부령구분 구분코드)',
    joint_promulgation_no VARCHAR(100) COMMENT '공포번호(공동부령의 공포번호)',
    
    -- 조문 정보
    article_no VARCHAR(20) COMMENT '조문번호',
    article_sub_no VARCHAR(20) COMMENT '조문가지번호',
    article_yn VARCHAR(10) COMMENT '조문여부',
    article_title VARCHAR(1000) COMMENT '조문제목',
    article_enforcement_date VARCHAR(20) COMMENT '조문시행일자',
    article_revision_type VARCHAR(100) COMMENT '조문제개정유형',
    article_move_before VARCHAR(20) COMMENT '조문이동이전',
    article_move_after VARCHAR(20) COMMENT '조문이동이후',
    article_change_yn VARCHAR(10) COMMENT '조문변경여부',
    article_content LONGTEXT COMMENT '조문내용',
    
    -- 항 정보
    paragraph_no VARCHAR(20) COMMENT '항번호',
    paragraph_revision_type VARCHAR(100) COMMENT '항제개정유형',
    paragraph_revision_date_str VARCHAR(100) COMMENT '항제개정일자문자열',
    paragraph_content LONGTEXT COMMENT '항내용',
    
    -- 호 정보
    item_no VARCHAR(20) COMMENT '호번호',
    item_content LONGTEXT COMMENT '호내용',
    
    -- 참고자료 및 부칙
    article_reference LONGTEXT COMMENT '조문참고자료',
    addendum_promulgation_date VARCHAR(20) COMMENT '부칙공포일자',
    addendum_promulgation_no VARCHAR(50) COMMENT '부칙공포번호',
    addendum_content LONGTEXT COMMENT '부칙내용',
    
    -- 별표 정보
    appendix_no VARCHAR(20) COMMENT '별표번호',
    appendix_sub_no VARCHAR(20) COMMENT '별표가지번호',
    appendix_type VARCHAR(100) COMMENT '별표구분',
    appendix_title VARCHAR(1000) COMMENT '별표제목',
    appendix_form_file_link TEXT COMMENT '별표서식파일링크',
    appendix_hwp_filename VARCHAR(500) COMMENT '별표HWP파일명',
    appendix_pdf_file_link TEXT COMMENT '별표서식PDF파일링크',
    appendix_pdf_filename VARCHAR(500) COMMENT '별표PDF파일명',
    appendix_image_filename VARCHAR(500) COMMENT '별표이미지파일명',
    appendix_content LONGTEXT COMMENT '별표내용',
    
    -- 개정 정보
    revision_content LONGTEXT COMMENT '개정문내용',
    revision_reason LONGTEXT COMMENT '제개정이유내용',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 인덱스
    INDEX idx_law_id (law_id),
    INDEX idx_enforcement_date (enforcement_date),
    INDEX idx_article_no (article_no),
    INDEX idx_law_name_korean (law_name_korean(100)),
    INDEX idx_ministry_code (ministry_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='법령 본문 정보 - 법령 본문 조회 API 응답 저장';

-- 현행법령 조항조목 정보 테이블 (현행법령 조항조목 조회 API 응답 기반)
CREATE TABLE IF NOT EXISTS law_articles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    -- 기본 법령 정보
    law_key VARCHAR(50) COMMENT '법령키',
    law_id VARCHAR(100) COMMENT '법령ID',
    promulgation_date VARCHAR(20) COMMENT '공포일자 (YYYYMMDD)',
    promulgation_no VARCHAR(50) COMMENT '공포번호',
    language VARCHAR(50) COMMENT '언어 구분',
    law_name_korean VARCHAR(1000) COMMENT '법령명_한글',
    law_name_hanja VARCHAR(1000) COMMENT '법령명_한자',
    law_type_code VARCHAR(50) COMMENT '법종구분코드',
    law_type_name VARCHAR(100) COMMENT '법종구분명',
    title_change_yn VARCHAR(10) COMMENT '제명변경여부',
    korean_law_yn VARCHAR(10) COMMENT '한글법령여부',
    chapter_section_no VARCHAR(50) COMMENT '편장절관',
    ministry_code VARCHAR(50) COMMENT '소관부처 코드',
    ministry_name VARCHAR(200) COMMENT '소관부처명',
    phone_number VARCHAR(50) COMMENT '전화번호',
    enforcement_date VARCHAR(20) COMMENT '시행일자 (YYYYMMDD)',
    revision_type VARCHAR(100) COMMENT '제개정구분명',
    proposal_type VARCHAR(100) COMMENT '제안구분',
    decision_type VARCHAR(100) COMMENT '의결구분',
    previous_law_name VARCHAR(1000) COMMENT '이전법령명',
    article_enforcement_date VARCHAR(100) COMMENT '조문별시행일자',
    article_enforcement_date_str VARCHAR(100) COMMENT '조문시행일자문자열',
    appendix_enforcement_date_str VARCHAR(100) COMMENT '별표시행일자문자열',
    appendix_edit_yn VARCHAR(10) COMMENT '별표편집여부',
    promulgated_law_yn VARCHAR(10) COMMENT '공포법령여부',
    enforcement_date_edit_yn VARCHAR(10) COMMENT '시행일기준편집여부',
    
    -- 조문 정보
    article_no VARCHAR(20) COMMENT '조문번호',
    article_yn VARCHAR(10) COMMENT '조문여부',
    article_title VARCHAR(1000) COMMENT '조문제목',
    article_enforcement_date_detail VARCHAR(100) COMMENT '조문시행일자',
    article_move_before VARCHAR(20) COMMENT '조문이동이전번호',
    article_move_after VARCHAR(20) COMMENT '조문이동이후번호',
    article_change_yn VARCHAR(10) COMMENT '조문변경여부',
    article_content LONGTEXT COMMENT '조문내용',
    
    -- 항, 호, 목 정보
    paragraph_no VARCHAR(20) COMMENT '항번호',
    paragraph_content LONGTEXT COMMENT '항내용',
    item_no VARCHAR(20) COMMENT '호번호',
    item_content LONGTEXT COMMENT '호내용',
    subitem_no VARCHAR(50) COMMENT '목번호',
    subitem_content LONGTEXT COMMENT '목내용',
    
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 인덱스
    INDEX idx_law_key (law_key),
    INDEX idx_law_id (law_id),
    INDEX idx_enforcement_date (enforcement_date),
    INDEX idx_article_no (article_no),
    INDEX idx_law_name_korean (law_name_korean(100)),
    INDEX idx_ministry_code (ministry_code),
    
    -- 제약조건 (법령키 + 조문번호 + 항번호 + 호번호 + 목번호로 유니크)
    UNIQUE KEY unique_article_detail (law_key, article_no, paragraph_no, item_no, subitem_no)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='현행법령 조항조목 정보 - 현행법령 조항조목 조회 API 응답 저장';

-- 배치 작업 이력 테이블
CREATE TABLE IF NOT EXISTS batch_jobs (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    job_id VARCHAR(100) NOT NULL COMMENT '배치 작업 고유 ID',
    job_type ENUM('FULL_SYNC', 'INCREMENTAL_SYNC', 'VALIDATION') NOT NULL COMMENT '작업 유형',
    status ENUM('PENDING', 'RUNNING', 'SUCCESS', 'FAILED') NOT NULL COMMENT '작업 상태',
    start_time TIMESTAMP NOT NULL COMMENT '작업 시작 시간',
    end_time TIMESTAMP NULL COMMENT '작업 종료 시간',
    last_sync_date DATE COMMENT '마지막 동기화 기준일',
    processed_laws VARCHAR(20) DEFAULT '0' COMMENT '처리된 법령 수',
    processed_articles VARCHAR(20) DEFAULT '0' COMMENT '처리된 조항 수',
    error_count VARCHAR(20) DEFAULT '0' COMMENT '오류 발생 수',
    error_details TEXT COMMENT '오류 상세 정보',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- 제약조건
    UNIQUE KEY unique_job_id (job_id),
    
    -- 인덱스
    INDEX idx_job_type_status (job_type, status),
    INDEX idx_start_time (start_time),
    INDEX idx_last_sync_date (last_sync_date),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='배치 작업 실행 이력 및 증분 업데이트 추적';

-- 동기화 상태 관리 테이블
CREATE TABLE IF NOT EXISTS sync_status (
    id INT PRIMARY KEY AUTO_INCREMENT,
    sync_type ENUM('FULL', 'INCREMENTAL') NOT NULL COMMENT '동기화 유형',
    last_sync_date DATE NOT NULL COMMENT '마지막 성공한 동기화 날짜',
    last_enforcement_date DATE COMMENT '마지막으로 처리된 시행일',
    total_laws_count VARCHAR(20) DEFAULT '0' COMMENT '총 법령 수',
    total_articles_count VARCHAR(20) DEFAULT '0' COMMENT '총 조항 수',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    
    -- 제약조건
    UNIQUE KEY unique_sync_type (sync_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='동기화 상태 추적 - 증분 업데이트 기준점 관리';

-- 블루그린 배포 상태 관리 테이블
CREATE TABLE IF NOT EXISTS blue_green_config (
    id INT PRIMARY KEY AUTO_INCREMENT,
    config_key VARCHAR(100) NOT NULL COMMENT '설정 키',
    config_value VARCHAR(500) NOT NULL COMMENT '설정 값',
    description TEXT COMMENT '설정 설명',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    updated_by VARCHAR(100) COMMENT '수정자 (배치명, 사용자명)',
    
    -- 제약조건
    UNIQUE KEY unique_config_key (config_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci 
COMMENT='블루그린 배포 상태 및 환경 설정 관리';

-- 블루그린 초기 설정 데이터 삽입
INSERT INTO blue_green_config (config_key, config_value, description, updated_by) VALUES
('ACTIVE_DATABASE', 'BLUE', '현재 활성화된 데이터베이스 환경 (BLUE/GREEN)', 'SYSTEM'),
('SWITCH_TIMESTAMP', '', '마지막 블루그린 스위칭 시간', 'SYSTEM'),
('DATA_VALIDATION_STATUS', 'PENDING', '데이터 검증 상태 (PENDING/VALID/INVALID)', 'SYSTEM'),
('BLUE_RECORD_COUNT', '0', 'Blue 환경의 총 레코드 수', 'SYSTEM'),
('GREEN_RECORD_COUNT', '0', 'Green 환경의 총 레코드 수', 'SYSTEM'),
('SYNC_STATUS', 'IDLE', '동기화 상태 (IDLE/SYNCING/COMPLETED/FAILED)', 'SYSTEM')
ON DUPLICATE KEY UPDATE 
    description=VALUES(description), 
    updated_by=VALUES(updated_by);

-- 물리적 외래키 제약조건 없음 (외부 API 데이터 불완전성 대응)
-- 논리적 관계: articles.law_master_no → laws.law_master_no
-- 논리적 관계: law_versions.law_master_no → laws.law_master_no