import logging

import aiosqlite
from aiogram import Bot
from aiogram.exceptions import TelegramAPIError, TelegramBadRequest
from aiogram.types import CallbackQuery, Message


logger = logging.getLogger(__name__)


class MessageManager:
    def __init__(self, db_path: str, max_messages_per_user: int = 3):
        self.db_path = db_path
        self.max_messages_per_user = max_messages_per_user

    async def send_message(
        self,
        bot: Bot,
        chat_id: int,
        text: str,
        *,
        user_id: int | None = None,
        persistent: bool = False,
        **kwargs,
    ) -> Message:
        sent = await bot.send_message(chat_id, text, **kwargs)
        await self._remember_message(
            bot,
            chat_id=chat_id,
            user_id=user_id or chat_id,
            message_id=sent.message_id,
            persistent=persistent,
        )
        return sent

    async def answer(
        self,
        message: Message,
        text: str,
        *,
        persistent: bool = False,
        user_id: int | None = None,
        **kwargs,
    ) -> Message:
        return await self.send_message(
            message.bot,
            message.chat.id,
            text,
            user_id=user_id or message.from_user.id,
            persistent=persistent,
            **kwargs,
        )

    async def send_location(
        self,
        bot: Bot,
        chat_id: int,
        latitude: float,
        longitude: float,
        *,
        user_id: int | None = None,
        persistent: bool = False,
        **kwargs,
    ) -> Message:
        sent = await bot.send_location(chat_id, latitude, longitude, **kwargs)
        await self._remember_message(
            bot,
            chat_id=chat_id,
            user_id=user_id or chat_id,
            message_id=sent.message_id,
            persistent=persistent,
        )
        return sent

    async def edit_or_send(
        self,
        callback: CallbackQuery,
        text: str,
        *,
        reply_markup=None,
        parse_mode: str = "HTML",
        persistent: bool = False,
        **kwargs,
    ) -> Message | None:
        if callback.message:
            try:
                await callback.message.edit_text(
                    text,
                    parse_mode=parse_mode,
                    reply_markup=reply_markup,
                    **kwargs,
                )
                return callback.message
            except TelegramBadRequest as exc:
                if "message is not modified" in str(exc).lower():
                    try:
                        await callback.message.edit_reply_markup(reply_markup=reply_markup)
                    except TelegramBadRequest:
                        pass
                    return callback.message
                logger.info("Edit failed, sending a new message instead: %s", exc)
            except TelegramAPIError as exc:
                logger.warning("Edit failed, sending a new message instead: %s", exc)

        return await self.send_message(
            callback.bot,
            callback.from_user.id,
            text,
            user_id=callback.from_user.id,
            persistent=persistent,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )

    async def edit_message(
        self,
        bot: Bot,
        chat_id: int,
        message_id: int,
        text: str,
        *,
        reply_markup=None,
        parse_mode: str = "HTML",
        persistent: bool = False,
        user_id: int | None = None,
        **kwargs,
    ) -> Message | None:
        try:
            return await bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode=parse_mode,
                reply_markup=reply_markup,
                **kwargs,
            )
        except TelegramBadRequest as exc:
            if "message is not modified" in str(exc).lower():
                try:
                    await bot.edit_message_reply_markup(
                        chat_id=chat_id,
                        message_id=message_id,
                        reply_markup=reply_markup,
                    )
                except TelegramBadRequest:
                    pass
                return None
            logger.info("Stored message edit failed, sending replacement: %s", exc)
        except TelegramAPIError as exc:
            logger.warning("Stored message edit failed, sending replacement: %s", exc)

        return await self.send_message(
            bot,
            chat_id,
            text,
            user_id=user_id or chat_id,
            persistent=persistent,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
            **kwargs,
        )

    async def _remember_message(
        self,
        bot: Bot,
        *,
        chat_id: int,
        user_id: int,
        message_id: int,
        persistent: bool,
    ) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO bot_message_history (chat_id, user_id, message_id, persistent)
                   VALUES (?, ?, ?, ?)""",
                (chat_id, user_id, message_id, 1 if persistent else 0),
            )
            await db.commit()
        await self._prune_messages(bot, chat_id=chat_id, user_id=user_id)

    async def _prune_messages(self, bot: Bot, *, chat_id: int, user_id: int) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                """SELECT id, message_id
                   FROM bot_message_history
                   WHERE chat_id = ? AND user_id = ? AND persistent = 0
                   ORDER BY created_at, id""",
                (chat_id, user_id),
            ) as cur:
                rows = await cur.fetchall()

        overflow = len(rows) - self.max_messages_per_user
        if overflow <= 0:
            return

        for row in rows[:overflow]:
            try:
                await bot.delete_message(chat_id=chat_id, message_id=row["message_id"])
            except TelegramBadRequest as exc:
                logger.info(
                    "Message %s in chat %s is already gone or can't be deleted: %s",
                    row["message_id"],
                    chat_id,
                    exc,
                )
            except TelegramAPIError as exc:
                logger.warning(
                    "Failed to delete old bot message %s in chat %s: %s",
                    row["message_id"],
                    chat_id,
                    exc,
                )
            finally:
                async with aiosqlite.connect(self.db_path) as db:
                    await db.execute("DELETE FROM bot_message_history WHERE id = ?", (row["id"],))
                    await db.commit()


async def safe_answer_callback(
    callback: CallbackQuery,
    text: str | None = None,
    *,
    show_alert: bool = False,
) -> None:
    try:
        await callback.answer(text=text, show_alert=show_alert)
    except TelegramAPIError as exc:
        logger.warning("Failed to answer callback %s: %s", callback.id, exc)
