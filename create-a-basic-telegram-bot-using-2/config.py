import logging
import os

logger = logging.getLogger(__name__)


def parse_int_env(name: str) -> int | None:
    raw_value = os.getenv(name)
    if not raw_value:
        return None

    try:
        return int(raw_value)
    except ValueError:
        logger.warning("%s is set but is not a valid integer", name)
        return None


def get_admin_id() -> int | None:
    return parse_int_env("ADMIN_ID")


def get_admin_chat_id() -> int | None:
    return parse_int_env("ADMIN_CHAT_ID") or get_admin_id()


def is_admin(user_id: int) -> bool:
    admin_id = get_admin_id()
    return admin_id is not None and user_id == admin_id
