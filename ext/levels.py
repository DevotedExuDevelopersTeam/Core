import random
from datetime import datetime, timedelta

import asyncpg
import disnake
from disnake.ext import commands, tasks
from tabulate import tabulate

from utils.bot import Bot
from utils.cog import Cog
from utils.constants import (
    PROMOCODE_CHANNEL_ID,
    PROMOCODE_NOTIFICATIONS,
    PROMOCODE_REQUIRED_SCORE,
    XP_BOUNDS,
    XP_COOLDOWN_SECONDS,
    XP_IGNORED_CHANNELS_IDS,
)
from utils.converters import DateConverter
from utils.embeds import SuccessEmbed
from utils.enums import FetchMode
from utils.errors import AdminOnly
from utils.image_generator import draw_leaderboard, draw_rank_card
from utils.utils import get_next_score, sep_num


class Levels(Cog):
    def __init__(self, bot: Bot):
        super().__init__(bot)
        self.cooldowns: dict[int, datetime] = {}

        # keys are channel IDs and values are ID of last member that sent the message
        self.last_messages: dict[int, int] = {}

        self.cooldowns_cleaner.start()

    def _is_member_on_cooldown(self, member_id: int) -> bool:
        return member_id in self.cooldowns and self.cooldowns[member_id] > datetime.now()

    async def _check_level_roles(self, member: disnake.Member, channel: disnake.TextChannel):
        score = await self.bot.db.get_users_score(member.id)
        levels = await self.bot.db.get_level_roles()
        all_roles = set(levels.values())
        required_roles = {v for k, v in levels.items() if k < score}
        unearned_roles = all_roles - required_roles
        current_roles = {r.id for r in member.roles}
        roles_to_add = required_roles - current_roles
        roles_to_remove = unearned_roles & current_roles
        if len(roles_to_add) > 0:
            await member.add_roles(*[disnake.Object(i) for i in roles_to_add])
            top_role = levels[max(filter(lambda x: score >= x, levels))]
            if top_role in roles_to_add:
                await channel.send(
                    f"GG {member.mention}, you just earned <@&{top_role}>!",
                    allowed_mentions=disnake.AllowedMentions.none(),
                )
        if len(roles_to_remove) > 0:
            await member.remove_roles(*[disnake.Object(i) for i in roles_to_remove])

    async def _check_promocodes(self, member: disnake.Member, channel: disnake.TextChannel):
        weekly_score = (
            await self.bot.db.execute(
                "SELECT score_weekly FROM scores WHERE id = $1",
                member.id,
                fetch_mode=FetchMode.VAL,
            )
            or 0
        )
        required_notifications = set(filter(lambda x: x <= weekly_score, PROMOCODE_NOTIFICATIONS))
        done_notifications = set(
            [
                r["score"]
                for r in await self.bot.db.execute(
                    "SELECT score FROM promo_notifications WHERE id = $1",
                    member.id,
                    fetch_mode=FetchMode.ALL,
                )
            ]
        )
        required_notifications -= done_notifications
        if len(required_notifications) > 0:
            for score in required_notifications:
                await self.bot.db.execute(
                    "INSERT INTO promo_notifications (id, score) VALUES ($1, $2) ON CONFLICT DO NOTHING",
                    member.id,
                    score,
                )
            if weekly_score < PROMOCODE_REQUIRED_SCORE:
                await channel.send(
                    f"{member.mention}, you just hit **{max(required_notifications)}** weekly score! "
                    f"Earn **{PROMOCODE_REQUIRED_SCORE - weekly_score:,}** more till the end of the week "
                    "to receive the promocode!"
                )
        if weekly_score > PROMOCODE_REQUIRED_SCORE:
            await channel.send(
                f"🥳 Congratulations, {member.mention}, you earned **{PROMOCODE_REQUIRED_SCORE:,}** weekly score "
                f"which means you can now **claim a promocode** in <#{PROMOCODE_CHANNEL_ID}>!"
            )

    def _is_last_member(self, msg: disnake.Message) -> bool:
        is_last = self.last_messages.get(msg.channel.id, None) == msg.author.id
        self.last_messages[msg.channel.id] = msg.author.id
        return is_last

    @tasks.loop(minutes=10)
    async def cooldowns_cleaner(self):
        now = datetime.now()
        for id, dt in self.cooldowns.copy().items():
            if dt < now:
                del self.cooldowns[id]

    @Cog.listener("on_message")
    async def xp_controller(self, message: disnake.Message):
        if (
            isinstance(message.author, disnake.User)
            or message.author.bot
            or message.channel.id in XP_IGNORED_CHANNELS_IDS
            or message.channel.category_id in XP_IGNORED_CHANNELS_IDS
            or self._is_last_member(message)
            or self._is_member_on_cooldown(message.author.id)
        ):
            return

        self.cooldowns[message.author.id] = datetime.now() + timedelta(seconds=XP_COOLDOWN_SECONDS)
        await self.bot.db.update_users_score(message.author.id, random.randint(*XP_BOUNDS))
        await self._check_level_roles(message.author, message.channel)
        await self._check_promocodes(message.author, message.channel)

    @commands.slash_command(name="rank", description="Shows activity info")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def rank(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member = None):
        await inter.response.defer()
        user = user or inter.user
        levels = await self.bot.db.get_level_roles()
        current_score = await self.bot.db.get_users_score(user.id)
        score_daily, score_weekly = await self.bot.db.execute(
            "SELECT score_daily, score_weekly FROM scores WHERE id = $1",
            inter.user.id,
            fetch_mode=FetchMode.ROW,
        )
        next_score = get_next_score(current_score, levels.keys())
        next_role = inter.guild.get_role(levels[next_score]) if next_score is not None else None

        await inter.send(
            f"Daily score: **{score_daily:,}**\nWeekly score: **{score_weekly:,}**",
            file=disnake.File(
                f := await draw_rank_card(
                    user,
                    await self.bot.db.get_lb_position(current_score),
                    next_role,
                    current_score,
                    next_score,
                ),
                filename="rank.png",
            ),
        )
        f.close()

    @commands.slash_command(name="leaderboard", description="Displays user's leaderboard")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def leaderboard(self, inter: disnake.ApplicationCommandInteraction, page: int = 1):
        await inter.response.defer()
        await inter.send(file=disnake.File(f := await draw_leaderboard(self.bot, page), filename="leaderboard.png"))
        f.close()

    @commands.slash_command(name="levels", description="Shows all leveled roles")
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def levels(self, inter: disnake.ApplicationCommandInteraction):
        lvls = await self.bot.db.get_level_roles()
        lvls_format: list[tuple[str, str]] = [(f"`{sep_num(k, ' ')}`", f"<@&{v}>") for k, v in lvls.items()]
        lvls_format.insert(0, ("Score", "Role"))
        await inter.send(
            embed=disnake.Embed(
                color=disnake.Color.random(),
                title="Levels",
                description=tabulate(lvls_format, headers="firstrow"),
            )
        )


class LevelsManagement(Cog):
    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if inter.user.guild_permissions.manage_guild:
            return True
        raise AdminOnly()

    @commands.slash_command(name="addlevel", description="Adds a level")
    async def addlevel(
        self,
        inter: disnake.ApplicationCommandInteraction,
        role: disnake.Role,
        required_score: int,
    ):
        await self.bot.db.add_level(role.id, required_score)
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully added level with role {role.mention} and score `{sep_num(required_score, '.')}`",
            )
        )

    @commands.slash_command(name="removelevel", description="Removes a level")
    async def removelevel(self, _):
        pass

    @removelevel.sub_command(name="role", description="Removes a level by role")
    async def removelevel_role(self, inter: disnake.ApplicationCommandInteraction, role: disnake.Role):
        role_id, required_score = await self.bot.db.remove_level(role)
        if role_id is None:
            await inter.send("This role is not assigned as level role", ephemeral=True)
            return
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully removed level with role {role.mention} and score `{sep_num(required_score, '.')}`",
            )
        )

    @removelevel.sub_command(name="score", description="Removes a level by score")
    async def removelevel_score(self, inter: disnake.ApplicationCommandInteraction, score: int):
        role_id, required_score = await self.bot.db.remove_level(score)
        if role_id is None:
            await inter.send("There's no role assigned to this score", ephemeral=True)
            return
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully removed level with role <@&{role_id}> and score `{sep_num(required_score, '.')}`",
            )
        )

    @commands.slash_command(name="addscore", description="Adds score to a member")
    async def addscore(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        score: int = commands.Param(ge=1, le=1_000_000),
    ):
        await self.bot.db.update_users_score(user.id, score, admin=True)
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully added `{sep_num(score, ' ')}` score to {user.mention}",
            )
        )

    @commands.slash_command(name="removescore", description="Removes score from a member")
    async def removescore(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        score: int = commands.Param(ge=1, le=1_000_000),
    ):
        await self.bot.db.update_users_score(user.id, -score, admin=True)
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully removed `{sep_num(score, ' ')}` score from {user.mention}",
            )
        )

    @commands.slash_command(name="addpromo", description="Add a new promocode")
    @commands.has_permissions(manage_guild=True)
    async def addpromo(
        self,
        inter: disnake.ApplicationCommandInteraction,
        promocode: str = commands.Param(min_length=8, max_length=8),
        expires_at: DateConverter = commands.Param(),
    ):
        promocode = promocode.upper()
        if expires_at.is_past():
            await inter.send("Promocode is already expired", ephemeral=True)
            return
        if expires_at.weekday() != 6:
            await inter.send("Promocode must expire on Sunday", ephemeral=True)
            return
        try:
            await self.bot.db.execute(
                "INSERT INTO promocodes (code, expires_at) VALUES ($1, $2)",
                promocode,
                expires_at,
            )
        except asyncpg.UniqueViolationError:
            await inter.send("This promocode is already added!")
            return
        await inter.send("Successfully added new promocode!")
