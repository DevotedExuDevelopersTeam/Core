import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, overload

import asyncpg
import disnake
from exencolorlogs import Logger

from utils.enums import FetchMode
from utils.youtube import fetch_last_video

DATABASE = os.getenv("DATABASE")
HOST = os.getenv("HOST")
USER = os.getenv("USER")
PASSWORD = os.getenv("PASSWORD")


@dataclass
class Warn:
    id: int
    target_id: int
    issuer_id: int
    issued_at: datetime
    rule_violated: str


@dataclass
class Youtuber:
    id: int
    youtube_id: str
    last_video: str


class Database:
    log: Logger
    _pool: asyncpg.Pool
    _connection_config: dict[str, Any]
    _cache: "Cache"

    def __init__(self, **connection_config):
        self.log = Logger("DB")
        self._connection_config = {
            "database": DATABASE,
            "host": HOST or "127.0.0.1",
            "user": USER,
        }
        if PASSWORD is not None:
            self._connection_config["password"] = PASSWORD

        self._connection_config.update(connection_config)
        self._cache = Cache()

    async def connect(self):
        self.log.info("Creating connection pool...")
        self._pool = await asyncpg.create_pool(**self._connection_config)
        self.log.ok("Connection pool created successfully!")

    async def close(self):
        self.log.info("Closing connection pool...")
        await self._pool.close()
        self.log.ok("Connection pool closed successfully")

    @property
    def pool(self):
        return self._pool

    async def execute(
        self, query: str, *args, fetch_mode: FetchMode = FetchMode.NONE
    ) -> None | list[dict] | dict | Any:
        if query.upper().startswith("SELECT") and fetch_mode == FetchMode.NONE:
            self.log.warning("Selection with no output. Query: %s", query)
        async with self._pool.acquire() as con:
            con: asyncpg.Connection
            match fetch_mode:
                case FetchMode.NONE:
                    return await con.execute(query, *args)
                case FetchMode.VAL:
                    return await con.fetchval(query, *args)
                case FetchMode.ROW:
                    return await con.fetchrow(query, *args)
                case FetchMode.ALL:
                    return await con.fetch(query, *args)

    async def setup(self, filename: str = "base_config.sql"):
        self.log.info("Executing setup statements...")
        with open(filename, "r") as f:
            async with self._pool.acquire() as con:
                con: asyncpg.Connection
                for sql in f.read().split(";\n"):
                    if len(sql) <= 1:
                        continue
                    await con.execute(sql)

    async def get_member_afk(self, id: int) -> tuple[str, datetime] | tuple[None, None]:
        r = await self.execute(
            "SELECT afk, set_at FROM afks WHERE id = $1", id, fetch_mode=FetchMode.ROW
        )
        if r is None:
            return None, None
        return r["afk"], r["set_at"]

    async def reset_member_afk(self, id: int):
        await self.execute("DELETE FROM afks WHERE id = $1", id)

    async def set_member_afk(self, id: int, afk: str):
        await self.execute(
            "INSERT INTO afks (id, afk) VALUES ($1, $2) ON CONFLICT (id) DO UPDATE SET afk = $2",
            id,
            afk,
        )

    async def add_temprole(self, user_id: int, role_id: int, duration: timedelta):
        await self.execute(
            "INSERT INTO temproles (id, role_id, remove_at) VALUES ($1, $2, $3)",
            user_id,
            role_id,
            datetime.now() + duration,
        )

    async def add_warn(self, target_id: int, issuer_id: int, rule_violated: str):
        await self.execute(
            "INSERT INTO warns (target_id, issuer_id, rule_violated) VALUES ($1, $2, $3)",
            target_id,
            issuer_id,
            rule_violated,
        )

    async def delete_warn(self, id: int) -> bool:
        """Returns True if warning existed, False if it didn't"""
        return await self.execute(
            "WITH deleted AS (DELETE FROM warns WHERE id = $1 RETURNING *) SELECT COUNT(*) > 0 FROM deleted",
            id,
            fetch_mode=FetchMode.VAL,
        )

    async def clear_warns(self, user_id: int) -> int:
        """Returns amount of warnings cleared"""
        return await self.execute(
            "WITH deleted AS (DELETE FROM warns WHERE target_id = $1 RETURNING *) SELECT COUNT(*) FROM deleted",
            user_id,
            fetch_mode=FetchMode.VAL,
        )

    async def get_warns(self, user_id: int) -> list[Warn]:
        return [
            Warn(*r.values())
            for r in await self.execute(
                "SELECT id, target_id, issuer_id, issued_at, rule_violated \
FROM warns WHERE target_id = $1",
                user_id,
                fetch_mode=FetchMode.ALL,
            )
        ]

    async def add_locked_channel(self, channel_id: int, duration: timedelta):
        await self.execute(
            "INSERT INTO locked_channels (id, unlock_at) VALUES ($1, $2)",
            channel_id,
            datetime.now() + duration,
        )

    async def remove_locked_channel(self, channel_id: int):
        await self.execute("DELETE FROM locked_channels WHERE id = $1", channel_id)

    async def get_level_roles(self) -> dict[int, int]:
        """Returns a dict where keys are required scores and values are role ids"""
        if len(self._cache.level_roles) == 0:
            self._cache.level_roles = {
                r["required_score"]: r["role_id"]
                for r in await self.execute(
                    "SELECT required_score, role_id FROM levels ORDER BY required_score",
                    fetch_mode=FetchMode.ALL,
                )
            }
        return self._cache.level_roles

    async def get_users_score(self, user_id: int) -> int:
        return (
            await self.execute(
                "SELECT score_total FROM scores WHERE id = $1",
                user_id,
                fetch_mode=FetchMode.VAL,
            )
            or 0
        )

    async def reset_daily_score(self):
        # noinspection SqlWithoutWhere
        await self.execute("UPDATE scores SET score_daily = 0")

    async def get_total_daily_score(self) -> int:
        return await self.execute(
            "SELECT SUM(score_daily) FROM scores", fetch_mode=FetchMode.VAL
        )

    async def update_users_score(self, user_id: int, delta: int, admin: bool = False):
        await self.execute(
            "INSERT INTO scores (id, score_total) VALUES ($1, $2) "
            "ON CONFLICT (id) DO UPDATE SET score_total = scores.score_total + $2, left_server = false",
            user_id,
            delta,
        )
        if not admin and delta > 0:
            await self.execute(
                "UPDATE scores SET score_daily = score_daily + $1 WHERE id = $2",
                delta,
                user_id,
            )

    async def get_lb_position(self, score: int) -> int:
        return await self.execute(
            "SELECT COUNT(*) + 1 FROM scores WHERE score_total > $1 AND NOT left_server",
            score,
            fetch_mode=FetchMode.VAL,
        )

    async def get_top_data(self, page: int):
        return await self.execute(
            "SELECT id, score_total FROM scores WHERE NOT left_server ORDER BY score_total DESC LIMIT 10 OFFSET $1",
            (page - 1) * 10,
            fetch_mode=FetchMode.ALL,
        )

    async def add_level(self, role_id: int, required_score: int):
        await self.execute(
            "INSERT INTO levels (required_score, role_id) VALUES ($1, $2)",
            required_score,
            role_id,
        )
        self._cache.level_roles.clear()

    @overload
    async def remove_level(self, role: disnake.Role):
        ...

    @overload
    async def remove_level(self, score: int):
        ...

    async def remove_level(
        self, value: disnake.Role | int
    ) -> tuple[int, int] | tuple[None, None]:
        """role_id, required_score = await remove_level(...)"""
        if isinstance(value, disnake.Role):
            r = await self.execute(
                "DELETE FROM levels WHERE role_id = $1 RETURNING *",
                value.id,
                fetch_mode=FetchMode.ROW,
            )
        elif isinstance(value, int):
            r = await self.execute(
                "DELETE FROM levels WHERE required_score = $1 RETURNING *",
                value,
                fetch_mode=FetchMode.ROW,
            )
        else:
            raise TypeError("Expected `disnake.Role` or `int`, got `%s`", type(value))

        if r is None:
            return None, None
        self._cache.level_roles.clear()
        return r["role_id"], r["required_score"]

    async def get_youtubers(self) -> list[Youtuber]:
        return [
            Youtuber(*d.values())
            for d in await self.execute(
                "SELECT id, youtube_id, last_video FROM youtubers",
                fetch_mode=FetchMode.ALL,
            )
        ]

    async def set_youtuber_last_video(self, id: int, last_video: str):
        await self.execute(
            "UPDATE youtubers SET last_video = $1 WHERE id = $2", last_video, id
        )

    async def add_youtuber(self, id: int, youtube_id: str, premium: bool):
        last_video = await fetch_last_video(youtube_id)
        await self.execute(
            "INSERT INTO youtubers (id, youtube_id, last_video, is_premium) VALUES ($1, $2, $3, $4)",
            id,
            youtube_id,
            last_video,
            premium,
        )

    async def remove_youtuber(self, id: int) -> bool:
        return await self.execute(
            "WITH deleted AS (DELETE FROM youtubers WHERE id = $1 RETURNING *) SELECT COUNT(*) > 0 FROM deleted",
            id,
            fetch_mode=FetchMode.VAL,
        )

    async def get_button_roles(self) -> dict[str, int]:
        return {
            r["id"]: r["role_id"]
            for r in await self.execute(
                "SELECT id, role_id FROM button_roles", fetch_mode=FetchMode.ALL
            )
        }

    async def add_button_role(self, id: str, role_id: int, message_id: int):
        await self.execute(
            "INSERT INTO button_roles (id, role_id, message_id) VALUES ($1, $2, $3)",
            id,
            role_id,
            message_id,
        )

    async def remove_button_role(self, id: str):
        await self.execute("DELETE FROM button_roles WHERE id = $1", id)

    async def clear_button_roles(self, message_id: int):
        await self.execute("DELETE FROM button_roles WHERE message_id = $1", message_id)

    async def add_rule(self, id: str, content: str):
        await self.execute(
            "INSERT INTO rules (id, content) VALUES ($1, $2)", id, content
        )

    async def remove_rule(self, id: str):
        await self.execute("DELETE FROM rules WHERE id = $1", id)


class Cache:
    level_roles: dict[int, int]

    def __init__(self):
        self.level_roles = {}
