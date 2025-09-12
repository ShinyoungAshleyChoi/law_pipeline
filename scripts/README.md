# 데이터 적재 스크립트 사용 가이드

이 디렉토리에는 법제처 데이터 파이프라인의 데이터 적재 및 관리를 위한 스크립트들이 포함되어 있습니다.

## 스크립트 목록

### 1. 전체 초기 데이터 적재 (`full_data_load.py`)

전체 법령 데이터를 처음부터 적재하는 스크립트입니다.

```bash
# Mock 데이터를 사용한 전체 적재 (기본값)
uv run python scripts/full_data_load.py

# 실제 API를 사용한 전체 적재
uv run python scripts/full_data_load.py --use-api

# 배치 크기 지정
uv run python scripts/full_data_load.py --batch-size 50

# 상세 로그 출력
uv run python scripts/full_data_load.py --verbose
```

**주요 기능:**
- 법령 목록, 본문, 조항 데이터 전체 적재
- 배치 단위 처리로 메모리 효율성 확보
- 트랜잭션 관리로 데이터 일관성 보장
- 진행률 및 결과 통계 제공

### 2. 증분 업데이트 (`incremental_update.py`)

마지막 동기화 이후 변경된 데이터만 업데이트하는 스크립트입니다.

```bash
# Mock 데이터를 사용한 증분 업데이트 (기본값)
uv run python scripts/incremental_update.py

# 실제 API를 사용한 증분 업데이트
uv run python scripts/incremental_update.py --use-api

# 특정 날짜 기준 증분 업데이트
uv run python scripts/incremental_update.py --target-date 2024-01-15

# 상세 로그 출력
uv run python scripts/incremental_update.py --verbose
```

**주요 기능:**
- 마지막 동기화 날짜 기준 변경 데이터 식별
- 기존 법령 업데이트 및 새 법령 추가
- 조항 데이터 증분 업데이트
- 동기화 상태 추적 및 관리

### 3. 데이터 검증 (`data_validation.py`)

데이터베이스의 데이터 정합성 및 일관성을 검증하는 스크립트입니다.

```bash
# 기본 검증 실행
uv run python scripts/data_validation.py

# 문제 자동 수정 포함
uv run python scripts/data_validation.py --fix

# 요약만 출력
uv run python scripts/data_validation.py --quiet

# 상세 로그 출력
uv run python scripts/data_validation.py --verbose
```

**검증 항목:**
- 기본 데이터 무결성 (NULL 값, 데이터 타입)
- 법령 데이터 일관성 (중복 ID, 법령명 일치성)
- 조항 데이터 일관성 (조항 번호, 내용 길이)
- 관계 무결성 (고아 레코드, 참조 일관성)
- 중복 데이터 검증
- 날짜 데이터 검증
- 통계 데이터 일관성

### 4. 배치 작업 모니터링 (`batch_monitor.py`)

배치 작업의 수동 실행 및 모니터링을 위한 통합 도구입니다.

#### 배치 작업 실행

```bash
# 전체 데이터 적재 실행
uv run python scripts/batch_monitor.py run full_load

# 증분 업데이트 실행
uv run python scripts/batch_monitor.py run incremental_update

# 데이터 검증 실행
uv run python scripts/batch_monitor.py run validation

# 실제 API 사용
uv run python scripts/batch_monitor.py run incremental_update --use-api

# 문제 자동 수정 포함 검증
uv run python scripts/batch_monitor.py run validation --fix
```

#### 작업 모니터링

```bash
# 실행 중인 작업 실시간 모니터링
uv run python scripts/batch_monitor.py monitor

# 새로고침 간격 설정 (기본값: 5초)
uv run python scripts/batch_monitor.py monitor --interval 10
```

#### 작업 이력 조회

```bash
# 최근 7일간 작업 이력 조회
uv run python scripts/batch_monitor.py history

# 최근 30일간 작업 이력 조회
uv run python scripts/batch_monitor.py history --days 30

# 최대 50개 작업 조회
uv run python scripts/batch_monitor.py history --limit 50
```

#### 실패한 작업 조회

```bash
# 최근 7일간 실패한 작업 조회
uv run python scripts/batch_monitor.py failed

# 최근 30일간 실패한 작업 조회
uv run python scripts/batch_monitor.py failed --days 30
```

#### 시스템 상태 조회

```bash
# 전체 시스템 상태 조회
uv run python scripts/batch_monitor.py status
```

### 5. 스키마 업데이트 (`update_schema.py`)

데이터베이스 스키마를 업데이트하는 스크립트입니다.

```bash
# 스키마 업데이트 실행
uv run python scripts/update_schema.py
```

## 사용 시나리오

### 초기 설정 및 데이터 적재

1. **데이터베이스 스키마 생성**
   ```bash
   uv run python scripts/update_schema.py
   ```

2. **전체 데이터 적재**
   ```bash
   uv run python scripts/full_data_load.py --verbose
   ```

3. **데이터 검증**
   ```bash
   uv run python scripts/data_validation.py
   ```

### 일상적인 데이터 관리

1. **증분 업데이트 실행**
   ```bash
   uv run python scripts/batch_monitor.py run incremental_update
   ```

2. **시스템 상태 확인**
   ```bash
   uv run python scripts/batch_monitor.py status
   ```

3. **작업 이력 확인**
   ```bash
   uv run python scripts/batch_monitor.py history
   ```

### 문제 해결

1. **실패한 작업 확인**
   ```bash
   uv run python scripts/batch_monitor.py failed
   ```

2. **데이터 검증 및 수정**
   ```bash
   uv run python scripts/data_validation.py --fix
   ```

3. **실행 중인 작업 모니터링**
   ```bash
   uv run python scripts/batch_monitor.py monitor
   ```

## 로그 및 모니터링

모든 스크립트는 구조화된 로깅을 사용하며, 다음과 같은 정보를 제공합니다:

- **실행 시간**: 각 작업의 시작/종료 시간 및 소요 시간
- **처리 통계**: 처리된 법령 수, 조항 수, 오류 수
- **진행률**: 대용량 데이터 처리 시 진행률 표시
- **오류 상세**: 발생한 오류의 상세 정보 및 스택 트레이스

## 주의사항

1. **데이터베이스 연결**: 모든 스크립트 실행 전에 데이터베이스 연결 설정이 올바른지 확인하세요.

2. **권한**: 스크립트 실행을 위해 적절한 데이터베이스 권한이 필요합니다.

3. **동시 실행**: 동일한 유형의 배치 작업을 동시에 실행하지 마세요.

4. **백업**: 전체 데이터 적재나 대량 업데이트 전에 데이터베이스 백업을 권장합니다.

5. **모니터링**: 장시간 실행되는 작업의 경우 모니터링 도구를 사용하여 진행 상황을 확인하세요.

## 문제 해결

### 일반적인 문제

1. **연결 오류**: 데이터베이스 연결 설정 확인
2. **권한 오류**: 데이터베이스 사용자 권한 확인
3. **메모리 부족**: 배치 크기 조정 (`--batch-size` 옵션)
4. **타임아웃**: 네트워크 설정 및 API 응답 시간 확인

### 로그 확인

상세한 오류 정보는 로그 파일에서 확인할 수 있습니다:
- 애플리케이션 로그: 구조화된 JSON 형식
- 배치 작업 로그: 데이터베이스의 `batch_jobs` 테이블

### 지원

추가 지원이 필요한 경우 다음을 확인하세요:
- 로그 파일의 오류 메시지
- 데이터베이스 연결 상태
- 시스템 리소스 사용량
- API 서비스 상태 (실제 API 사용 시)