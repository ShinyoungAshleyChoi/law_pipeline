# 데이터베이스 스키마

법제처 데이터 파이프라인의 MySQL 데이터베이스 스키마입니다.

## 구조

```
database/
├── __init__.py
├── connection.py    # 데이터베이스 연결 관리
├── models.py       # 데이터 모델 정의
├── schema.sql      # 데이터베이스 스키마
└── README.md
```

## 테이블 구조

### 1. laws (법령 기본 정보)
- **목적**: 법령의 기본 정보와 버전 관리
- **주요 컬럼**:
  - `id`: 내부 시퀀스 ID (Primary Key) - 성능 최적화용
  - `law_id`: 법령ID (각 법령마다 고유하게 존재) - 비즈니스 키
  - `law_master_no`: 법령마스터번호 (법령 개정시마다 변경) - 버전별 고유 키
  - `enforcement_date`: 시행일 (최신성 판단 기준)
  - `is_latest`: 최신 버전 여부

### ID 설계 철학
**왜 law_master_no를 PK로 사용하지 않고 별도 id를 생성했는가?**

1. **성능 최적화**
   - `law_master_no`는 VARCHAR(50)로 문자열 기반 키
   - 숫자 기반 AUTO_INCREMENT `id`가 인덱스 성능에서 우수
   - JOIN 연산 시 정수형이 문자열보다 빠름

2. **외부 의존성 분리**
   - `law_master_no`는 외부 시스템(법제처)에서 제공하는 값
   - 외부 시스템 변경에 영향받지 않는 내부 키 필요
   - 데이터 마이그레이션이나 시스템 통합 시 유연성 확보

3. **확장성 고려**
   - 향후 다른 법령 시스템과의 통합 가능성
   - 내부 시스템 간 참조 시 일관된 키 체계 유지
   - 샤딩이나 분산 처리 시 숫자 키가 유리

4. **데이터 품질 관리**
   - `law_master_no`가 중복되거나 변경되는 경우에도 내부 무결성 유지
   - 외부 데이터 오류 시에도 시스템 안정성 보장

### 2. articles (조항 상세 정보)
- **목적**: 법령의 조항 상세 내용 저장
- **주요 컬럼**:
  - `law_master_no`: 법령마스터번호 (법령과 조항 매핑 키)
  - `article_no`: 조항번호
  - `article_content`: 조항 내용
  - `parent_article_no`: 상위 조항번호 (계층 구조)

### 3. law_versions (법령 버전 이력)
- **목적**: 법령 개정 이력 추적 및 최신성 관리
- **주요 컬럼**:
  - `law_id`: 법령ID (불변 식별자)
  - `law_master_no`: 법령마스터번호 (버전별 식별자)
  - `version_no`: 버전 번호
  - `enforcement_date`: 시행일

### 4. batch_jobs (배치 작업 이력)
- **목적**: 배치 작업 실행 이력 및 증분 업데이트 추적
- **주요 컬럼**:
  - `job_id`: 배치 작업 고유 ID
  - `job_type`: 작업 유형 (FULL_SYNC, INCREMENTAL_SYNC, VALIDATION)
  - `status`: 작업 상태 (PENDING, RUNNING, SUCCESS, FAILED)
  - `last_sync_date`: 마지막 동기화 기준일

### 5. sync_status (동기화 상태)
- **목적**: 동기화 상태 추적 및 증분 업데이트 기준점 관리
- **주요 컬럼**:
  - `sync_type`: 동기화 유형 (FULL, INCREMENTAL)
  - `last_sync_date`: 마지막 성공한 동기화 날짜
  - `last_enforcement_date`: 마지막으로 처리된 시행일

## 사용법

### 1. 스키마 생성

```bash
# MySQL에 직접 실행
mysql -u username -p database_name < src/legal_data_pipeline/database/schema.sql
```

### 2. 프로그래밍 방식 사용

```python
from src.legal_data_pipeline.database import db_connection, Law, Article

# 연결 테스트
db_connection.test_connection()

# 데이터베이스 세션 사용
with db_connection.get_session() as session:
    # SQLAlchemy 세션 사용
    pass

# 직접 연결 사용
with db_connection.get_connection() as conn:
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM laws")
    result = cursor.fetchone()
    cursor.close()
```

## 인덱스 전략

### 성능 최적화 인덱스
- **laws 테이블**: 
  - `idx_law_id_latest`: 법령ID + 최신 여부 (빠른 최신 법령 조회)
  - `idx_enforcement_date`: 시행일 (날짜 범위 검색)
  - `idx_latest_laws`: 최신 여부 + 시행일 (최신 법령 목록)

- **articles 테이블**:
  - `idx_law_master_no`: 법령마스터번호 (법령-조항 관계 조회)
  - `unique_article`: 법령마스터번호 + 조항번호 (중복 방지)

- **law_versions 테이블**:
  - `idx_law_id_latest`: 법령ID + 최신 여부 (버전 관리)
  - `unique_version`: 법령ID + 버전번호 (버전 고유성)

## 데이터 무결성 관리

### 논리적 외래키 관계 (물리적 제약조건 없음)
- `articles.law_master_no` → `laws.law_master_no` (법령-조항 관계)
- `law_versions.law_master_no` → `laws.law_master_no` (법령-버전 관계)

### 물리적 외래키를 사용하지 않는 이유
1. **외부 API 데이터 불완전성**: 법제처 API에서 제공하는 데이터가 항상 완벽하지 않을 수 있음
2. **배치 처리 안정성**: 일부 데이터 누락으로 인한 전체 배치 실패 방지
3. **점진적 데이터 적재**: 참조 데이터가 나중에 도착하는 경우에도 처리 가능
4. **성능 최적화**: 대용량 배치 처리 시 제약조건 검사 오버헤드 제거

### 데이터 무결성 보장 방법
- 애플리케이션 레벨에서 참조 무결성 검증
- 배치 작업 후 데이터 검증 단계 수행
- 고아 레코드(orphaned records) 정기 정리 작업

## 데이터 모델

데이터 모델은 `models.py`에 정의되어 있으며, 다음과 같은 클래스를 제공합니다:

- `Law`: 법령 기본 정보
- `Article`: 조항 상세 정보  
- `LawVersion`: 법령 버전 관리
- `BatchJob`: 배치 작업 정보
- `SyncStatus`: 동기화 상태

## 데이터 모델

데이터 모델은 `models.py`에 정의되어 있습니다:

- `Law`: 법령 기본 정보
- `Article`: 조항 상세 정보  
- `LawVersion`: 법령 버전 관리
- `BatchJob`: 배치 작업 정보
- `SyncStatus`: 동기화 상태