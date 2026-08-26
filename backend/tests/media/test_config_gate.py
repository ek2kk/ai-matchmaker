import pytest
from pydantic import ValidationError

from ai_dating.config import Settings


def test_media_auto_approve_rejected_outside_local():
    with pytest.raises(ValidationError, match="media_auto_approve"):
        Settings(_env_file=None, app_env="production", media_auto_approve=True)


def test_message_auto_approve_rejected_outside_local():
    with pytest.raises(ValidationError, match="message_auto_approve"):
        Settings(
            _env_file=None,
            app_env="production",
            media_auto_approve=False,
            message_auto_approve=True,
        )
