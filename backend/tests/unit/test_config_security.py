"""安全回归：弱 JWT 密钥必须被拒绝；计时均摊用的 dummy hash 可用。"""

import pytest
from pydantic import ValidationError

from app.access.auth import service
from app.core.config import Settings


def test_weak_or_short_jwt_secret_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(jwt_secret="dev-secret-change-me-please-32bytes")
    with pytest.raises(ValidationError):
        Settings(jwt_secret="short")


def test_dummy_password_hash_is_verifiable() -> None:
    assert service.verify_password("timing-equalizer-dummy", service.DUMMY_PASSWORD_HASH)
    assert not service.verify_password("wrong", service.DUMMY_PASSWORD_HASH)
