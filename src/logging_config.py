"""로깅 설정 모듈"""
import logging
import logging.handlers
import structlog
import colorlog
from pathlib import Path
from typing import Optional
from .config import config

def setup_logging(
    level: str = None,
    log_file: Optional[str] = None,
    format_type: str = None
) -> None:
    """로깅 시스템 초기화"""
    
    # 설정에서 기본값 가져오기
    logging_config = config.logging
    level = level or logging_config.level
    log_file = log_file or logging_config.file_path
    format_type = format_type or logging_config.format
    
    # 로그 레벨 설정
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # 기본 로거 설정
    logging.basicConfig(level=log_level)
    
    # structlog 설정
    if format_type.lower() == "json":
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(ensure_ascii=False)
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    else:
        # 컬러 로깅 설정 (개발 환경용)
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.dev.ConsoleRenderer(colors=True)
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )
    
    # 파일 로깅 설정
    if log_file:
        setup_file_logging(log_file, log_level, logging_config)
    
    # 콘솔 로깅 설정
    setup_console_logging(log_level, format_type)

def setup_file_logging(log_file: str, log_level: int, logging_config) -> None:
    """파일 로깅 설정"""
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    
    # 로테이팅 파일 핸들러 설정
    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=_parse_file_size(logging_config.max_file_size),
        backupCount=logging_config.backup_count,
        encoding='utf-8'
    )
    file_handler.setLevel(log_level)
    
    # JSON 포맷터 설정
    formatter = logging.Formatter(
        '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
        '"logger": "%(name)s", "message": "%(message)s", '
        '"module": "%(module)s", "function": "%(funcName)s", "line": %(lineno)d}'
    )
    file_handler.setFormatter(formatter)
    
    # 루트 로거에 핸들러 추가
    logging.getLogger().addHandler(file_handler)

def setup_console_logging(log_level: int, format_type: str) -> None:
    """콘솔 로깅 설정"""
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    
    if format_type.lower() == "json":
        formatter = logging.Formatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
    else:
        # 컬러 포맷터 설정
        formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            }
        )
    
    console_handler.setFormatter(formatter)
    logging.getLogger().addHandler(console_handler)

def _parse_file_size(size_str: str) -> int:
    """파일 크기 문자열을 바이트로 변환"""
    size_str = size_str.upper()
    if size_str.endswith('KB'):
        return int(size_str[:-2]) * 1024
    elif size_str.endswith('MB'):
        return int(size_str[:-2]) * 1024 * 1024
    elif size_str.endswith('GB'):
        return int(size_str[:-2]) * 1024 * 1024 * 1024
    else:
        return int(size_str)

def get_logger(name: str) -> structlog.BoundLogger:
    """구조화된 로거 인스턴스 반환"""
    return structlog.get_logger(name)

# 기본 로깅 설정 초기화
setup_logging()