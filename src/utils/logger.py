#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
標準化ログ出力モジュール

統一されたログフォーマットと出力機能を提供します。
"""

import logging
import json
import sys
from datetime import datetime
from typing import Dict, Any, Optional
from pathlib import Path
from .config_manager import get_config_manager

# ログレベル定義
LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL
}


class StructuredFormatter(logging.Formatter):
    """構造化ログフォーマッター"""

    def __init__(self, include_timestamp: bool = True, include_module: bool = True):
        super().__init__()
        self.include_timestamp = include_timestamp
        self.include_module = include_module

    def format(self, record: logging.LogRecord) -> str:
        """ログレコードを構造化フォーマットで整形"""
        log_data = {
            'level': record.levelname,
            'message': record.getMessage(),
        }

        if self.include_timestamp:
            log_data['timestamp'] = datetime.fromtimestamp(record.created).isoformat()

        if self.include_module:
            log_data['module'] = record.name

        # 追加フィールドがある場合は追加
        if hasattr(record, 'extra_fields'):
            log_data.update(record.extra_fields)

        # 例外情報がある場合は追加
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False, default=str)


class SimpleFormatter(logging.Formatter):
    """シンプルなログフォーマッター"""

    def __init__(self):
        super().__init__(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )


def setup_logger(name: str = None, level: str = 'INFO',
                log_file: Optional[str] = None,
                use_structured: bool = False,
                include_timestamp: bool = True,
                include_module: bool = True) -> logging.Logger:
    """ロガーの設定"""

    # ロガーの取得
    logger = logging.getLogger(name or __name__)

    # 既存のハンドラーをクリア
    logger.handlers.clear()

    # ログレベルの設定
    log_level = LOG_LEVELS.get(level.upper(), logging.INFO)
    logger.setLevel(log_level)

    # フォーマッターの選択
    if use_structured:
        formatter = StructuredFormatter(include_timestamp, include_module)
    else:
        formatter = SimpleFormatter()

    # コンソールハンドラー
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # ファイルハンドラー（指定された場合）
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str = None) -> logging.Logger:
    """設定済みロガーを取得"""
    return logging.getLogger(name or __name__)


def log_function_call(func_name: str, args: tuple = None, kwargs: dict = None,
                     logger: logging.Logger = None) -> None:
    """関数呼び出しをログに記録"""
    if logger is None:
        logger = get_logger()

    call_info = {
        'function': func_name,
        'args_count': len(args) if args else 0,
        'kwargs_count': len(kwargs) if kwargs else 0
    }

    logger.debug(f"関数呼び出し: {json.dumps(call_info, ensure_ascii=False)}")


def log_function_result(func_name: str, result: Any = None,
                      execution_time: float = None,
                      logger: logging.Logger = None) -> None:
    """関数実行結果をログに記録"""
    if logger is None:
        logger = get_logger()

    result_info = {
        'function': func_name,
        'result_type': type(result).__name__,
        'execution_time': execution_time
    }

    logger.debug(f"関数実行完了: {json.dumps(result_info, ensure_ascii=False)}")


def log_data_operation(operation: str, data_type: str, data_size: int = None,
                      success: bool = True, error_message: str = None,
                      logger: logging.Logger = None) -> None:
    """データ操作をログに記録"""
    if logger is None:
        logger = get_logger()

    operation_info = {
        'operation': operation,
        'data_type': data_type,
        'data_size': data_size,
        'success': success
    }

    if error_message:
        operation_info['error'] = error_message

    if success:
        logger.info(f"データ操作成功: {json.dumps(operation_info, ensure_ascii=False)}")
    else:
        logger.error(f"データ操作失敗: {json.dumps(operation_info, ensure_ascii=False)}")


def log_api_call(api_name: str, endpoint: str = None, status_code: int = None,
                response_time: float = None, success: bool = True,
                error_message: str = None, logger: logging.Logger = None) -> None:
    """API呼び出しをログに記録"""
    if logger is None:
        logger = get_logger()

    api_info = {
        'api_name': api_name,
        'endpoint': endpoint,
        'status_code': status_code,
        'response_time': response_time,
        'success': success
    }

    if error_message:
        api_info['error'] = error_message

    if success:
        logger.info(f"API呼び出し成功: {json.dumps(api_info, ensure_ascii=False)}")
    else:
        logger.error(f"API呼び出し失敗: {json.dumps(api_info, ensure_ascii=False)}")


def log_analysis_step(step_name: str, analysis_type: str,
                     input_size: int = None, output_size: int = None,
                     execution_time: float = None, success: bool = True,
                     error_message: str = None, logger: logging.Logger = None) -> None:
    """分析ステップをログに記録"""
    if logger is None:
        logger = get_logger()

    analysis_info = {
        'step_name': step_name,
        'analysis_type': analysis_type,
        'input_size': input_size,
        'output_size': output_size,
        'execution_time': execution_time,
        'success': success
    }

    if error_message:
        analysis_info['error'] = error_message

    if success:
        logger.info(f"分析ステップ完了: {json.dumps(analysis_info, ensure_ascii=False)}")
    else:
        logger.error(f"分析ステップ失敗: {json.dumps(analysis_info, ensure_ascii=False)}")


def setup_default_logging(verbose: bool = False, log_file: str = None) -> None:
    """デフォルトログ設定"""
    level = 'DEBUG' if verbose else 'INFO'

    # プロジェクト全体のログ設定
    setup_logger(
        name='corporate_bias_study',
        level=level,
        log_file=log_file,
        use_structured=False  # デフォルトはシンプルフォーマット
    )

    # 外部ライブラリのログレベルを調整
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('boto3').setLevel(logging.WARNING)
    logging.getLogger('botocore').setLevel(logging.WARNING)
