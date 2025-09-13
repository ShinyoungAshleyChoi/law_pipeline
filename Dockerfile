FROM apache/airflow:2.8.4-python3.11

# root 사용자로 전환하여 시스템 패키지 설치
USER root

# 시스템 의존성 설치 (필요한 경우)
RUN apt-get update \
  && apt-get install -y --no-install-recommends \
         vim \
         git \
         build-essential \
         curl \
  && apt-get autoremove -yqq --purge \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/*

# airflow 사용자로 전환
USER airflow

# uv 설치 (root 권한으로)
RUN pip install uv

# uv 프로젝트 파일들 복사
COPY pyproject.toml /opt/airflow/pyproject.toml
COPY uv.lock /opt/airflow/uv.lock

# 작업 디렉토리 설정
WORKDIR /opt/airflow

USER root
# uv.lock에서 requirements.txt 형식으로 export한 후 시스템 파이썬 환경에 직접 설치
RUN uv pip install -r pyproject.toml --system
