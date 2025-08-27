#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
共通エラーハンドリングモジュール

統一されたエラー処理とログ出力を提供します。
"""

import logging
import traceback
from typing import Optional, Dict, Any, Callable
from functools import wraps
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorSeverity(Enum):
    """エラー重要度の定義"""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CorporateBiasError(Exception):
    """企業バイアス分析システムの基底エラークラス"""

    def __init__(self, message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM,
                 details: Optional[Dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.severity = severity
        self.details = details or {}
        self.timestamp = None  # 後で設定

    def __str__(self):
        return f"[{self.severity.value.upper()}] {self.message}"


class ConfigError(CorporateBiasError):
    """設定関連エラー"""
    def __init__(self, message: str, config_type: str = "unknown"):
        super().__init__(message, ErrorSeverity.HIGH, {"config_type": config_type})


class DataError(CorporateBiasError):
    """データ処理関連エラー"""
    def __init__(self, message: str, data_type: str = "unknown"):
        super().__init__(message, ErrorSeverity.MEDIUM, {"data_type": data_type})


class APIError(CorporateBiasError):
    """API呼び出し関連エラー"""
    def __init__(self, message: str, api_name: str = "unknown", status_code: Optional[int] = None):
        details = {"api_name": api_name}
        if status_code:
            details["status_code"] = status_code
        super().__init__(message, ErrorSeverity.MEDIUM, details)


class StorageError(CorporateBiasError):
    """ストレージ関連エラー"""
    def __init__(self, message: str, storage_type: str = "unknown"):
        super().__init__(message, ErrorSeverity.MEDIUM, {"storage_type": storage_type})


class AnalysisError(CorporateBiasError):
    """分析処理関連エラー"""
    def __init__(self, message: str, analysis_type: str = "unknown"):
        super().__init__(message, ErrorSeverity.MEDIUM, {"analysis_type": analysis_type})


def handle_errors(func: Callable) -> Callable:
    """エラーハンドリングデコレータ"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except CorporateBiasError as e:
            log_error(e)
            raise
        except Exception as e:
            # 予期しないエラーをCorporateBiasErrorに変換
            error = CorporateBiasError(
                f"予期しないエラーが発生しました: {str(e)}",
                ErrorSeverity.HIGH,
                {"original_error": str(e), "function": func.__name__}
            )
            log_error(error)
            raise error
    return wrapper


def log_error(error: CorporateBiasError) -> None:
    """エラーをログに記録"""
    if error.severity == ErrorSeverity.CRITICAL:
        logger.critical(f"CRITICAL ERROR: {error.message}", extra=error.details)
    elif error.severity == ErrorSeverity.HIGH:
        logger.error(f"HIGH ERROR: {error.message}", extra=error.details)
    elif error.severity == ErrorSeverity.MEDIUM:
        logger.warning(f"MEDIUM ERROR: {error.message}", extra=error.details)
    else:
        logger.info(f"LOW ERROR: {error.message}", extra=error.details)


def safe_execute(func: Callable, *args, default_return: Any = None,
                error_message: str = "処理中にエラーが発生しました", **kwargs) -> Any:
    """安全な関数実行"""
    try:
        return func(*args, **kwargs)
    except Exception as e:
        logger.error(f"{error_message}: {str(e)}")
        return default_return


def retry_on_error(max_retries: int = 3, delay: float = 1.0,
                  backoff_factor: float = 2.0) -> Callable:
    """リトライ機能デコレータ"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"試行 {attempt + 1}/{max_retries + 1} が失敗しました: {str(e)}. "
                            f"{current_delay}秒後にリトライします。"
                        )
                        import time
                        time.sleep(current_delay)
                        current_delay *= backoff_factor
                    else:
                        logger.error(f"最大試行回数に達しました: {str(e)}")

            # 全ての試行が失敗した場合
            raise last_exception
        return wrapper
    return decorator


def validate_required_fields(data: Dict[str, Any], required_fields: list,
                           context: str = "データ") -> None:
    """必須フィールドの検証"""
    missing_fields = [field for field in required_fields if field not in data or data[field] is None]
    if missing_fields:
        raise DataError(
            f"{context}に必須フィールドが不足しています: {missing_fields}",
            "validation"
        )


def validate_config(config: Dict[str, Any], required_keys: list,
                   config_name: str = "設定") -> None:
    """設定の検証"""
    missing_keys = [key for key in required_keys if key not in config or config[key] is None]
    if missing_keys:
        raise ConfigError(
            f"{config_name}に必須キーが不足しています: {missing_keys}",
            config_name
        )
