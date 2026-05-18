import logging
import aiosqlite
from aiogram import Bot

logger = logging.getLogger(__name__)

MAX_MESSAGES = 3
_DB_PATH = "booking.db"


class MessageManager:
    """
    Per-user ring buffer of bot message IDs backed by SQLite.
    Tracks the last MAX_MESSAGES bot messages for each user and
    auto-deletes the oldest from Telegram when the buffer overflows.

    Persists across restarts: message IDs survive bot reboots so that
    stale messages from a previous session can still be cleaned up.
    """

    async def register(
        self,
        bot: Bot,
        chat_id: int,
        user_id: int,
        message_id: int,
        persistent: bool = False,
    ) -> None:
        """
        Register a new bot message.
        If persistent=True the message is never tracked or auto-deleted.
        """
        if persistent:
            return

        async with aiosqlite.connect(_DB_PATH) as db:
            await db.execute(
                "INSERT INTO bot_messages (user_id, chat_id, message_id) VALUES (?,?,?)",
                (user_id, chat_id, message_id),
            )
            await db.commit()
            async with db.execute(
                "SELECT id, chat_id, message_id FROM bot_messages "
                "WHERE user_id=? ORDER BY id ASC",
                (user_id,),
            ) as cur:
                rows = list(await cur.fetchall())

        # Determine which rows exceed the buffer size
        overflow = rows[: max(0, len(rows) - MAX_MESSAGES)]
        if not overflow:
            return

        ids_to_remove = [r[0] for r in overflow]

        # Delete from Telegram (failures are logged but never raised)
        for _, del_chat, del_msg in overflow:
            try:
                await bot.delete_message(del_chat, del_msg)
            except Exception as e:
                logger.debug("Could not delete message %d: %s", del_msg, e)

        # Remove from DB
        async with aiosqlite.connect(_DB_PATH) as db:
            placeholders = ",".join("?" * len(ids_to_remove))
            await db.execute(
                f"DELETE FROM bot_messages WHERE id IN ({placeholders})",
                ids_to_remove,
            )
            await db.commit()

    async def clear(self, bot: Bot, user_id: int) -> None:
        """Delete all tracked messages for a user (e.g. on /start fresh flow)."""
        async with aiosqlite.connect(_DB_PATH) as db:
            async with db.execute(
                "SELECT id, chat_id, message_id FROM bot_messages WHERE user_id=?",
                (user_id,),
            ) as cur:
                rows = list(await cur.fetchall())
            if rows:
                ids = [r[0] for r in rows]
                for _, c, m in rows:
                    try:
                        await bot.delete_message(c, m)
                    except Exception as e:
                        logger.debug("clear: could not delete %d: %s", m, e)
                placeholders = ",".join("?" * len(ids))
                await db.execute(
                    f"DELETE FROM bot_messages WHERE id IN ({placeholders})", ids
                )
                await db.commit()


# Module-level singleton — import and use directly in handlers
manager = MessageManager()
