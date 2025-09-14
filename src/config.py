"""설정 관리 모듈"""
import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

@dataclass
class DatabaseConfig:
    """데이터베이스 설정"""
    host: str
    port: int
    name: str
    user: str
    password: str
    charset: str = "utf8mb4"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600

@dataclass
class APIConfig:
    """API 설정"""
    base_url: str
    timeout: int = 30
    max_retries: int = 3
    retry_delay: int = 5
    requests_per_minute: int = 60
    batch_size: int = 100
    use_mock_data: bool = False
    mock_data_path: Optional[str] = None
    mock_api_delay: bool = True
    mock_api_error_rate: float = 0.02
    mock_data_count: int = 50

@dataclass
class LoggingConfig:
    """로깅 설정"""
    level: str = "INFO"
    format: str = "json"
    file_path: Optional[str] = None
    max_file_size: str = "10MB"
    backup_count: int = 5

@dataclass
class SlackConfig:
    """슬랙 알림 설정"""
    bot_token: Optional[str]
    channel_id: Optional[str]
    webhook_url: Optional[str]
    enable_notifications: bool = False
    retry_attempts: int = 3
    retry_delay: int = 5
    timeout: int = 30

class ConfigManager:
    """설정 관리자"""
    
    def __init__(self, config_dir: str = "config"):
        # Airflow 실행 환경 감지
        if self._is_airflow_environment():
            # Airflow DAG 실행 환경에서는 dags 폴더 하위의 config 폴더 사용
            dags_folder = self._get_dags_folder()
            self.config_dir = Path(dags_folder) / config_dir
        else:
            # 일반 환경에서는 기본 config 폴더 사용
            self.config_dir = Path(config_dir)
            
        self._database_config: Optional[DatabaseConfig] = None
        self._api_config: Optional[APIConfig] = None
        self._logging_config: Optional[LoggingConfig] = None
        self._slack_config: Optional[SlackConfig] = None
    
    def _is_airflow_environment(self) -> bool:
        """Airflow 실행 환경인지 확인"""
        # Airflow 관련 환경 변수들을 확인
        airflow_indicators = [
            'AIRFLOW_HOME',
            'AIRFLOW__CORE__DAGS_FOLDER',
            '_AIRFLOW_WWW_USER_USERNAME',
            'AIRFLOW_CTX_DAG_ID',  # DAG 실행 컨텍스트
            'AIRFLOW_CTX_TASK_ID'  # Task 실행 컨텍스트
        ]
        
        # Airflow 모듈이 로드되어 있는지 확인
        airflow_module_loaded = False
        try:
            import sys
            airflow_module_loaded = any('airflow' in module for module in sys.modules.keys())
        except:
            pass
        
        # 환경 변수 또는 모듈 로드 상태로 판단
        return any(os.getenv(var) for var in airflow_indicators) or airflow_module_loaded
    
    def _get_dags_folder(self) -> str:
        """Airflow DAGs 폴더 경로 반환"""
        # 환경 변수에서 DAGs 폴더 경로 확인
        dags_folder = os.getenv('AIRFLOW__CORE__DAGS_FOLDER')
        
        if not dags_folder:
            # 기본 Airflow 홈 디렉토리에서 dags 폴더 사용
            airflow_home = os.getenv('AIRFLOW_HOME', os.path.expanduser('~/airflow'))
            dags_folder = os.path.join(airflow_home, 'dags')
        
        # 현재 실행 중인 스크립트의 위치에서 dags 폴더를 찾는 대안적 방법
        if not os.path.exists(dags_folder):
            current_file = Path(__file__).resolve()
            # config.py가 dags 폴더 내부에 있다고 가정하고 상위 폴더 탐색
            for parent in current_file.parents:
                if parent.name == 'dags' or (parent / 'dags').exists():
                    dags_folder = str(parent / 'dags' if parent.name != 'dags' else parent)
                    break
        
        return dags_folder
    
    def get_config_path(self) -> Path:
        """현재 설정 디렉토리 경로 반환"""
        return self.config_dir
    
    def get_environment_info(self) -> Dict[str, Any]:
        """현재 환경 정보 반환 (디버깅용)"""
        return {
            "is_airflow_environment": self._is_airflow_environment(),
            "config_directory": str(self.config_dir),
            "airflow_home": os.getenv('AIRFLOW_HOME'),
            "dags_folder": os.getenv('AIRFLOW__CORE__DAGS_FOLDER'),
            "dag_id": os.getenv('AIRFLOW_CTX_DAG_ID'),
            "task_id": os.getenv('AIRFLOW_CTX_TASK_ID'),
        }
    
    def _load_yaml_config(self, filename: str) -> Dict[str, Any]:
        """YAML 설정 파일 로드"""
        config_path = self.config_dir / filename
        
        # 디버그 정보 출력 (개발 중 확인용)
        print(f"[ConfigManager] Airflow 환경 감지: {self._is_airflow_environment()}")
        print(f"[ConfigManager] 설정 파일 로드 경로: {config_path}")
        
        if not config_path.exists():
            raise FileNotFoundError(f"설정 파일을 찾을 수 없습니다: {config_path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 환경 변수 치환
            content = self._substitute_env_vars(content)
            return yaml.safe_load(content)
    
    def _substitute_env_vars(self, content: str) -> str:
        """환경 변수 치환 (${VAR:default} 형식)"""
        import re
        
        def replace_env_var(match):
            var_expr = match.group(1)
            if ':' in var_expr:
                var_name, default_value = var_expr.split(':', 1)
            else:
                var_name, default_value = var_expr, ''
            
            return os.getenv(var_name, default_value)
        
        return re.sub(r'\$\{([^}]+)\}', replace_env_var, content)
    
    @property
    def database(self) -> DatabaseConfig:
        """데이터베이스 설정 반환"""
        if self._database_config is None:
            config = self._load_yaml_config("database_green.yaml")
            db_config = config["database"]
            
            self._database_config = DatabaseConfig(
                host=db_config["host"],
                port=int(db_config["port"]),
                name=db_config["name"],
                user=db_config["user"],
                password=db_config["password"],
                charset=db_config.get("charset", "utf8mb4"),
                pool_size=config.get("connection_pool", {}).get("pool_size", 10),
                max_overflow=config.get("connection_pool", {}).get("max_overflow", 20),
                pool_timeout=config.get("connection_pool", {}).get("pool_timeout", 30),
                pool_recycle=config.get("connection_pool", {}).get("pool_recycle", 3600)
            )
        
        return self._database_config
    
    @property
    def api(self) -> APIConfig:
        """API 설정 반환"""
        if self._api_config is None:
            config = self._load_yaml_config("api_config.yaml")
            api_config = config["legal_api"]
            
            self._api_config = APIConfig(
                base_url=api_config["base_url"],
                timeout=api_config.get("timeout", 30),
                max_retries=api_config.get("max_retries", 3),
                retry_delay=api_config.get("retry_delay", 5),
                requests_per_minute=api_config.get("requests_per_minute", 60),
                batch_size=api_config.get("batch_size", 100),
                use_mock_data=api_config.get("use_mock_data", False),
                mock_data_path=api_config.get("mock_data_path"),
                mock_api_delay=api_config.get("mock_api_delay", True),
                mock_api_error_rate=api_config.get("mock_api_error_rate", 0.02),
                mock_data_count=api_config.get("mock_data_count", 50)
            )
        
        return self._api_config
    
    @property
    def logging(self) -> LoggingConfig:
        """로깅 설정 반환"""
        if self._logging_config is None:
            self._logging_config = LoggingConfig(
                level=os.getenv("LOG_LEVEL", "INFO"),
                format=os.getenv("LOG_FORMAT", "json"),
                file_path=os.getenv("LOG_FILE_PATH"),
                max_file_size=os.getenv("LOG_MAX_FILE_SIZE", "10MB"),
                backup_count=int(os.getenv("LOG_BACKUP_COUNT", "5"))
            )
        
        return self._logging_config
    
    @property
    def slack(self) -> SlackConfig:
        """슬랙 알림 설정 반환 - config/notification.yaml에서만 로드"""
        if self._slack_config is None:
            config_data = self._load_yaml_config("notification.yaml")
            slack_config = config_data["slack"]
            
            self._slack_config = SlackConfig(
                bot_token=slack_config.get("bot_token"),
                channel_id=slack_config.get("channel_id"),
                webhook_url=slack_config.get("webhook_url"),
                enable_notifications=slack_config.get("enable_notifications", False),
                retry_attempts=slack_config.get("retry_attempts", 3),
                retry_delay=slack_config.get("retry_delay", 5),
                timeout=slack_config.get("timeout", 30)
            )
        
        return self._slack_config
    
    def is_mock_enabled(self) -> bool:
        """Mock 환경 사용 여부"""
        return self.mock.enabled
    
    def get_environment_type(self) -> str:
        """현재 환경 타입 반환"""
        return self.mock.environment_type
    
    def setup_mock_environment(self):
        """Mock 환경 설정"""
        if not self.is_mock_enabled():
            return None
            
        from .mock.mock_config import setup_mock_environment
        return setup_mock_environment(self.get_environment_type())

# 전역 설정 인스턴스
config = ConfigManager()