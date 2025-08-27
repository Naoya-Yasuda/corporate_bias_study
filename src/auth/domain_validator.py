"""
ドメイン制限チェックモジュール

サイバー大学（@cyber-u.ac.jp）ドメインのメールアドレスのみを許可する
ドメイン制限機能を提供します。
"""

import re
from typing import List, Optional


class DomainValidator:
    """ドメイン制限チェッククラス"""

    def __init__(self, allowed_domains: List[str], allowed_emails: List[str] = None):
        """
        初期化

        Args:
            allowed_domains: 許可するドメインのリスト
            allowed_emails: 許可するメールアドレスのリスト（オプション）
        """
        self.allowed_domains = [domain.lower().strip() for domain in allowed_domains]
        self.allowed_emails = [email.lower().strip() for email in (allowed_emails or [])]

    def validate_email(self, email: str) -> bool:
        """
        メールアドレスの検証

        Args:
            email: 検証するメールアドレス

        Returns:
            bool: 許可されたドメインまたはメールアドレスの場合True、そうでなければFalse
        """
        if not email:
            return False

        # メールアドレスの形式チェック
        if not self._is_valid_email_format(email):
            return False

        email_lower = email.lower().strip()

        # 1. ドメイン一致チェック（優先）
        domain = self.get_user_domain(email)
        if domain and domain.lower() in self.allowed_domains:
            return True

        # 2. メールアドレス完全一致チェック
        if email_lower in self.allowed_emails:
            return True

        return False

    def get_user_domain(self, email: str) -> Optional[str]:
        """
        ユーザードメインの抽出

        Args:
            email: メールアドレス

        Returns:
            Optional[str]: ドメイン部分、無効な場合はNone
        """
        if not email:
            return None

        # @記号で分割してドメイン部分を取得
        parts = email.split('@')
        if len(parts) != 2:
            return None

        domain = parts[1].lower().strip()
        return domain if domain else None

    def _is_valid_email_format(self, email: str) -> bool:
        """
        メールアドレスの形式チェック

        Args:
            email: チェックするメールアドレス

        Returns:
            bool: 有効な形式の場合True
        """
        # 基本的なメールアドレス形式の正規表現
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))

    def get_allowed_domains(self) -> List[str]:
        """
        許可されているドメインのリストを取得

        Returns:
            List[str]: 許可ドメインのリスト
        """
        return self.allowed_domains.copy()

    def get_allowed_emails(self) -> List[str]:
        """
        許可されているメールアドレスのリストを取得

        Returns:
            List[str]: 許可メールアドレスのリスト
        """
        return self.allowed_emails.copy()

    def add_allowed_domain(self, domain: str) -> None:
        """
        許可ドメインを追加

        Args:
            domain: 追加するドメイン
        """
        domain = domain.lower().strip()
        if domain and domain not in self.allowed_domains:
            self.allowed_domains.append(domain)

    def add_allowed_email(self, email: str) -> None:
        """
        許可メールアドレスを追加

        Args:
            email: 追加するメールアドレス
        """
        email = email.lower().strip()
        if email and email not in self.allowed_emails:
            self.allowed_emails.append(email)

    def remove_allowed_domain(self, domain: str) -> bool:
        """
        許可ドメインを削除

        Args:
            domain: 削除するドメイン

        Returns:
            bool: 削除成功の場合True
        """
        domain = domain.lower().strip()
        if domain in self.allowed_domains:
            self.allowed_domains.remove(domain)
            return True
        return False

    def remove_allowed_email(self, email: str) -> bool:
        """
        許可メールアドレスを削除

        Args:
            email: 削除するメールアドレス

        Returns:
            bool: 削除成功の場合True
        """
        email = email.lower().strip()
        if email in self.allowed_emails:
            self.allowed_emails.remove(email)
            return True
        return False


def create_default_domain_validator() -> DomainValidator:
    """
    デフォルトのドメイン制限チェッカーを作成

    Returns:
        DomainValidator: サイバー大学ドメインを許可するバリデーター
    """
    return DomainValidator(["cyber-u.ac.jp"])