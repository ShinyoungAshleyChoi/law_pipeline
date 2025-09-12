# 알림 시스템 사용 가이드

법제처 데이터 파이프라인의 알림 시스템은 슬랙을 통해 다양한 유형의 알림을 발송합니다.

## 주요 기능

### 1. 오류 유형별 알림 템플릿 및 분류 로직
- API 연결 오류
- API 응답 오류  
- 데이터 검증 오류
- 데이터베이스 오류
- 데이터 처리 오류
- 시스템 오류

### 2. 긴급 알림 및 에스컬레이션 로직
- 시스템 오류 발생 시 즉시 긴급 알림
- @channel 멘션을 통한 즉시 확인 요청

## 사용 방법

### 기본 사용법

```python
from src.notifications import (
    notify_error,
    notify_batch_success,
    notify_batch_failure,
    notify_critical
)

# 1. 오류 알림
try:
    # 작업 수행
    pass
except Exception as e:
    notify_error(e, job_name="법령_데이터_수집", error_details="상세 오류 정보")

# 2. 배치 성공 알림
notify_batch_success(
    job_name="법령_데이터_동기화",
    processed_laws=150,
    processed_articles=1250,
    duration="00:05:30"
)

# 3. 배치 실패 알림
notify_batch_failure(
    job_name="법령_데이터_동기화",
    error_message="API 연결 실패"
)

# 4. 긴급 알림
notify_critical("연속 3회 배치 작업 실패 발생")
```

### 특정 오류 유형별 알림

```python
from src.notifications import (
    notify_api_error,
    notify_database_error,
    notify_validation_error,
    notify_system_error
)

# API 오류
notify_api_error("법제처_API", "연결 타임아웃", retry_count=3)

# 데이터베이스 오류
notify_database_error("INSERT", "중복 키 오류", table_name="laws")

# 데이터 검증 오류
notify_validation_error("법령데이터", "필수 필드 누락", affected_records=5)

# 시스템 오류 (긴급)
notify_system_error("메모리_관리자", "메모리 부족")
```

### 데코레이터 사용

```python
from src.notifications import with_error_notification, with_batch_notification

# 오류 발생 시 자동 알림
@with_error_notification(job_name="법령_데이터_수집")
def collect_law_data():
    # 작업 수행
    pass

# 배치 작업 결과 자동 알림
@with_batch_notification(job_name="법령_데이터_동기화")
def sync_law_data():
    # 작업 수행
    return {
        'processed_laws': 150,
        'processed_articles': 1250
    }
```

## 알림 템플릿

### 오류 알림 템플릿
- 🚨 일반 오류
- 🔌 API 연결 오류
- 📡 API 응답 오류
- 📋 데이터 검증 오류
- 🗄️ 데이터베이스 오류
- ⚙️ 데이터 처리 오류
- 💻 시스템 오류 (긴급)

### 배치 작업 알림 템플릿
- ✅ 배치 작업 성공
- ❌ 배치 작업 실패

### 긴급 알림 템플릿
- 🔥 긴급 알림 (@channel 멘션 포함)

## 설정

알림 설정은 `config/notification.yaml` 파일에서 관리됩니다:

```yaml
slack:
  bot_token: ${SLACK_BOT_TOKEN}
  channel_id: ${SLACK_CHANNEL_ID}
  webhook_url: ${SLACK_WEBHOOK_URL}
  enable_notifications: true
  retry_attempts: 3
  retry_delay: 5
  timeout: 30
```

## 테스트

알림 시스템을 테스트하려면:

```bash
python scripts/test_notifications.py
```

## 요구사항 매핑

- **요구사항 6.1**: API 호출 실패 시 관리자 알림 → `notify_api_error()`
- **요구사항 6.2**: 데이터 적재 실패 시 오류 상세 정보와 함께 알림 → `notify_database_error()`
- **요구사항 6.3**: 배치 작업 실패 시 실패 원인과 함께 알림 → `notify_batch_failure()`
- **요구사항 6.4**: 연속적인 실패 발생 시 긴급 알림 → `notify_critical()`
- **요구사항 6.5**: 알림 발송 시 알림 이력 기록 → 로깅 시스템을 통해 기록