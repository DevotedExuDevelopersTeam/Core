import os
from datetime import datetime, timezone

import disnake
from disnake.ext import commands
from strmath import evaluate

from utils.autocomplete import rules_autocomplete
from utils.checks import staff_only
from utils.cog import Cog
from utils.converters import RuleConverter
from utils.image_generator import resize_bg
from utils.utils import datetime_to_timestamp, timedelta_to_full_str
from utils.views import ConfirmationView


class Miscellaneous(Cog):
    @Cog.listener("on_message")
    async def afk_controller(self, message: disnake.Message):
        if message.author.bot:
            return
        afk, set_at = await self.bot.db.get_member_afk(message.author.id)
        if afk is not None and (datetime.now() - set_at).seconds > 10:
            await self.bot.db.reset_member_afk(message.author.id)
            await message.channel.send(
                f"{message.author.mention}, removed your AFK! \
You were AFK for **{timedelta_to_full_str(datetime.now() - set_at)}**"
            )
            return

        for member in message.mentions[
            :5
        ]:  # the amount is limited to 5 to prevent spam pings
            afk, set_at = await self.bot.db.get_member_afk(member.id)
            if afk is not None:
                await message.channel.send(
                    f"**{member}** is AFK: {afk} {datetime_to_timestamp(set_at, 'R')}"
                )
                return

    @commands.slash_command(name="whois", description="Shows info about a person")
    async def whois(
        self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member = None
    ):
        user = user or inter.author
        embed = (
            disnake.Embed(color=0x00FFFF, title=str(user))
            .add_field(
                name="Joined on",
                value=f"{user.joined_at.strftime('%d %b %Y  %H:%M:%S')} \
({(datetime.now(timezone.utc) - user.joined_at).days} days ago)",
            )
            .add_field(
                name="Account created",
                value=f"{user.created_at.strftime('%d %b %Y  %H:%M:%S')} \
({(datetime.now(timezone.utc) - user.created_at).days} days ago)",
            )
            .set_author(name=str(user), url=user.display_avatar.url)
        )
        await inter.send(embed=embed)

    @commands.slash_command(name="setbg", description="Sets your rank card background")
    async def setbg(
        self, inter: disnake.ApplicationCommandInteraction, bg: disnake.Attachment = None
    ):
        path = f"backgrounds/{inter.author.id}.png"
        if bg is None:
            os.remove(path)
            await inter.send("Successfully reset your background")
        await inter.response.defer()
        # noinspection PyTypeChecker
        await bg.save(path)
        await resize_bg(path)
        await inter.send("Successfully set your background")

    @commands.slash_command(name="afk", description="Sets an AFK")
    async def afk(self, inter: disnake.ApplicationCommandInteraction, text: str):
        await self.bot.db.set_member_afk(inter.author.id, text)
        await inter.send(f"You are now AFK: `{text}`")

    @commands.slash_command(name="rule", description="Shows rule")
    async def rule(
        self,
        inter: disnake.ApplicationCommandInteraction,
        rule: RuleConverter = commands.Param(autocomplete=rules_autocomplete),
    ):
        await inter.send(str(rule))

    @commands.slash_command(
        name="math", description="Evaluates a simple math expression"
    )
    async def math(self, inter: disnake.ApplicationCommandInteraction, expr: str):
        try:
            result = evaluate(expr)
        except Exception as e:
            await inter.send(f"Failed to evaluate this expression: `{e}`")
            return
        await inter.send(f"Result: `{result}`")

    @commands.slash_command(name="dm", description="DMs member a message")
    @staff_only()
    async def dm(
        self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member, text
    ):
        view = ConfirmationView(inter.author.id)
        await inter.send(
            f"Are you sure you want to DM {user.mention} this text?",
            embed=disnake.Embed(description=text),
            view=view,
        )
        r, inter = await view.get_result()
        if r:
            await inter.response.defer()
            try:
                await user.send(
                    embed=disnake.Embed(
                        title=f"You got a message from {self.bot.server.name} staff",
                        color=0x00FFFF,
                        description=text,
                    )
                )
                await inter.send(f"Successfully sent DM to {user.mention}")
            except disnake.HTTPException:
                await inter.send("Their DMs are closed for bot")
