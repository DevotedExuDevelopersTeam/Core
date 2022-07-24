from datetime import datetime, timedelta

import disnake
from disnake.ext import tasks

from utils.bot import Bot
from utils.cog import Cog
from utils.enums import FetchMode


class SystemLoops(Cog):
    def __init__(self, bot: Bot):
        super().__init__(bot)

        self.temproles_and_locked_channels_remover.start()
        self.bans_remover.start()

    @tasks.loop(minutes=5)
    async def temproles_and_locked_channels_remover(self):
        await self.bot.wait_until_ready()
        now = datetime.now()
        records = await self.bot.db.execute(
            "SELECT * FROM temproles WHERE remove_at < $1",
            now,
            fetch_mode=FetchMode.ALL,
        )
        for r in records:
            member = self.bot.server.get_member(r["id"])
            role = self.bot.server.get_role(r["role_id"])
            if member is None or role is None:
                continue

            try:
                await member.remove_roles(role)
            except disnake.HTTPException:
                self.bot.log.warning("Failed to remove temprole from %s", member)

        await self.bot.db.execute("DELETE FROM temproles WHERE remove_at < $1", now)

        records = await self.bot.db.execute(
            "SELECT id FROM locked_channels WHERE unlock_at < $1",
            now,
            fetch_mode=FetchMode.ALL,
        )
        for r in records:
            channel = self.bot.server.get_channel(r["id"])
            if channel is None:
                self.bot.log.warning("Failed to unlock channel %s", r["id"])
                continue
            await channel.set_permissions(
                self.bot.server.default_role, send_messages=None
            )

        await self.bot.db.execute(
            "DELETE FROM locked_channels WHERE unlock_at < $1", now
        )

    @tasks.loop(minutes=30)
    async def bans_remover(self):
        await self.bot.wait_until_ready()
        now = datetime.now()
        records = await self.bot.db.execute(
            "SELECT * FROM bans WHERE unban_at < $1", now, fetch_mode=FetchMode.ALL
        )
        for r in records:
            try:
                await self.bot.server.unban(disnake.Object(r["id"]))
            except disnake.HTTPException:
                await self.bot.log.warning("Failed to unban %s", r["id"])

        await self.bot.db.execute("DELETE FROM bans WHERE unban_at < $1", now)

    @tasks.loop(hours=12)
    async def warnings_remover(self):
        await self.bot.wait_until_ready()
        await self.bot.db.execute(
            "DELETE FROM warns WHERE issued_at < $1",
            datetime.now() - timedelta(days=30),
        )
