import json
import aiosqlite
from typing import Optional, Dict, Any
from aiogram.fsm.storage.base import BaseStorage, StorageKey, StateType


class SQLiteStorage(BaseStorage):
    """Persistent FSM storage backed by SQLite — survives bot restarts."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    async def _get(self, key: StorageKey) -> dict:
        destiny = getattr(key, "destiny", "fsm")
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT state, data FROM fsm_data "
                "WHERE bot_id=? AND chat_id=? AND user_id=? AND destiny=?",
                (key.bot_id, key.chat_id, key.user_id, destiny),
            ) as cur:
                row = await cur.fetchone()
        if row:
            return {"state": row[0], "data": json.loads(row[1] or "{}")}
        return {"state": None, "data": {}}

    async def _put(self, key: StorageKey, state: Optional[str], data: dict):
        destiny = getattr(key, "destiny", "fsm")
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """INSERT INTO fsm_data (bot_id, chat_id, user_id, destiny, state, data)
                   VALUES (?, ?, ?, ?, ?, ?)
                   ON CONFLICT(bot_id, chat_id, user_id, destiny)
                   DO UPDATE SET state=excluded.state, data=excluded.data""",
                (key.bot_id, key.chat_id, key.user_id, destiny, state, json.dumps(data)),
            )
            await db.commit()

    async def set_state(self, key: StorageKey, state: StateType = None) -> None:
        record = await self._get(key)
        if state is None:
            state_str = None
        elif isinstance(state, str):
            state_str = state
        else:
            state_str = state.state  # "ClassName:attr_name", not str() → "<State '...'>"
        await self._put(key, state_str, record["data"])

    async def get_state(self, key: StorageKey) -> Optional[str]:
        return (await self._get(key))["state"]

    async def set_data(self, key: StorageKey, data: Dict[str, Any]) -> None:
        record = await self._get(key)
        await self._put(key, record["state"], data)

    async def get_data(self, key: StorageKey) -> Dict[str, Any]:
        return (await self._get(key))["data"]

    async def close(self) -> None:
        pass
