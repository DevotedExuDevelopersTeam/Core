from datetime import datetime, time, timedelta

import disnake
from disnake.ext import commands, tasks

from utils.bot import Bot
from utils.cog import Cog
from utils.constants import ADMIN_ROLE_ID, ADMINISTRATION_CHANNEL_ID, DAILY_SCORE_TRACKER_ID, MEMBERS_TRACKER_ID
from utils.enums import FetchMode
from utils.errors import UNKNOWN, get_error_msg


class SystemLoops(Cog):
    def __init__(self, bot: Bot):
        super().__init__(bot)

        self.temproles_and_locked_channels_remover.start()
        self.bans_remover.start()
        self.warnings_remover.start()
        self.stats_updater.start()
        self.daily_reset.start()

    @tasks.loop(minutes=30)
    async def stats_updater(self):
        await self.bot.wait_until_ready()
        if not hasattr(self.bot, "server"):
            return
        try:
            members_tracker = self.bot.server.get_channel(MEMBERS_TRACKER_ID)
            await members_tracker.edit(name=f"Members: {self.bot.server.member_count}")
            daily_score_tracker = self.bot.server.get_channel(DAILY_SCORE_TRACKER_ID)
            await daily_score_tracker.edit(name=f"Daily Score: {await self.bot.db.get_total_daily_score()}")
        except Exception as e:
            self.bot.log.error("Failed to update trackers", exc_info=e)

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
            await channel.set_permissions(self.bot.server.default_role, send_messages=None)

        await self.bot.db.execute("DELETE FROM locked_channels WHERE unlock_at < $1", now)

    @tasks.loop(minutes=30)
    async def bans_remover(self):
        await self.bot.wait_until_ready()
        now = datetime.now()
        records = await self.bot.db.execute("SELECT * FROM bans WHERE unban_at < $1", now, fetch_mode=FetchMode.ALL)
        for r in records:
            try:
                await self.bot.server.unban(disnake.Object(r["id"]))
            except disnake.HTTPException:
                self.bot.log.warning("Failed to unban %s", r["id"])

        await self.bot.db.execute("DELETE FROM bans WHERE unban_at < $1", now)

    @tasks.loop(hours=12)
    async def warnings_remover(self):
        await self.bot.wait_until_ready()
        await self.bot.db.execute(
            "DELETE FROM warns WHERE issued_at < $1",
            datetime.now() - timedelta(days=30),
        )

    @tasks.loop(time=time(0))
    async def daily_reset(self):
        await self.bot.wait_until_ready()
        await self.bot.db.reset_daily_score()
        if await self.bot.db.execute("SELECT COUNT(*) FROM promocodes", fetch_mode=FetchMode.VAL) == 0:
            try:
                await self.bot.get_channel(ADMINISTRATION_CHANNEL_ID).send(
                    f"<@&{ADMIN_ROLE_ID}> there are no promocodes left, please add more"
                )
            except Exception as e:
                self.bot.log.error("Failed to notify admins on promocodes run out", exc_info=e)


class SystemListeners(Cog):
    @Cog.listener()
    async def on_slash_command_error(self, inter: disnake.ApplicationCommandInteraction, error: commands.CommandError):
        text = get_error_msg(error)
        if text is UNKNOWN:
            raise error
        await inter.send(text, ephemeral=True)
