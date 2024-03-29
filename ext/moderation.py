from datetime import datetime

import disnake
from disnake.ext import commands

from utils.autocomplete import invalidate as invalidate_rules
from utils.autocomplete import rules_autocomplete
from utils.checks import is_staff
from utils.cog import Cog
from utils.constants import FILEMUTED_ROLE_ID
from utils.converters import RuleConverter, TimeConverter
from utils.embeds import BaseEmbed, ErrorEmbed, SuccessEmbed
from utils.enums import FetchMode
from utils.errors import HierarchyError
from utils.utils import datetime_to_timestamp, s_, timedelta_to_full_str

RulesAutocomplete = commands.Param(autocomplete=rules_autocomplete)


class ModerationCommands(Cog):
    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        return await is_staff(self.bot, inter)

    @commands.slash_command(name="mute", description="Timeouts the member")
    async def mute(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        time: TimeConverter,
        rule: RuleConverter = RulesAutocomplete,
    ):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        await user.timeout(duration=time, reason=f"Mod: {inter.user} | Rule: {rule.id}")

        await inter.send(
            embed=BaseEmbed(
                user,
                color=0xFFFF00,
                title="⏰ Timeout",
                description=f"{user.mention} was timed out for `{timedelta_to_full_str(time)}`.",
                timestamp=datetime.now(),
            ).add_field("Violated rule", str(rule), inline=False)
        )
        await self.bot.dis_log.log_target_action("Mute", user, inter.user, time, str(rule))

    @commands.slash_command(name="unmute", description="Removes timeout from the member")
    async def unmute(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        await user.timeout(duration=None, reason=f"Mod: {inter.user}")

        await inter.send(embed=SuccessEmbed(inter.user, f"Successfully removed timeout from {user.mention}"))
        await self.bot.dis_log.log_target_action("Unmute", user, inter.user, color=0x00FF00)

    @commands.slash_command(name="filemute", description="Blocks user from attaching files")
    async def filemute(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        time: TimeConverter,
    ):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        filemuted_role = self.bot.server.get_role(FILEMUTED_ROLE_ID)
        if filemuted_role is None:
            raise commands.RoleNotFound("Filemuted")

        if filemuted_role in user.roles:
            await inter.send("That user is already filemuted", ephemeral=True)
            return

        await user.add_roles(filemuted_role)
        await self.bot.db.add_temprole(user.id, filemuted_role.id, time)

        await inter.send(
            embed=BaseEmbed(
                user,
                color=0xFFFF00,
                title="📁 Filemuted",
                description=f"{user.mention} was filemuted for `{timedelta_to_full_str(time)}`.",
                timestamp=datetime.now(),
            )
        )
        await self.bot.dis_log.log_target_action("Filemute", user, inter.user)

    @commands.slash_command(name="unfilemute", description="Takes off the filemute from user")
    async def unfilemute(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        filemuted_role = self.bot.server.get_role(FILEMUTED_ROLE_ID)
        if filemuted_role is None:
            raise commands.RoleNotFound("Filemuted")

        if filemuted_role not in user.roles:
            await inter.send("That user is not filemuted", ephemeral=True)
            return

        await user.remove_roles(filemuted_role)

        await inter.send(embed=SuccessEmbed(inter.user, f"Took off the filemute from {user.mention}"))
        await self.bot.dis_log.log_target_action("Unfilemute", user, inter.user)

    @commands.slash_command(name="ban", description="Bans a user")
    @commands.has_permissions(ban_members=True)
    async def ban(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        rule: RuleConverter = RulesAutocomplete,
        time: TimeConverter = None,
        clean_history_duration: TimeConverter = 86400,
    ):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        await inter.response.defer()
        time_str = ("for " + timedelta_to_full_str(time)) if time is not None else "permanently"
        try:
            await user.send(f"You were banned from **{inter.guild.name}** *{time_str}* for breaking rule `{rule}`")
        except disnake.HTTPException:
            pass

        await user.ban(
            reason=f"Mod: {inter.user} | Duration: {time} | Rule: {rule.id}",
            clean_history_duration=clean_history_duration,
        )
        if time is not None:
            await self.bot.db.add_tempban(user.id, datetime.now() + time)
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"**{user}** was banned {time_str} for breaking rule `{rule.id}`",
            )
        )
        await self.bot.dis_log.log_target_action("Ban", user, inter.user, time, str(rule), color=0xFF0000)

    @commands.slash_command(name="unban", description="Unbans a user")
    @commands.has_permissions(ban_members=True)
    async def unban(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user_id: int = commands.Param(large=True),
    ):
        try:
            await inter.guild.unban(disnake.Object(user_id), reason=f"Mod: {inter.user}")
            await inter.send(embed=SuccessEmbed(inter.user, f"Successfully unbanned `{user_id}`"))
        except disnake.HTTPException:
            await inter.send("Failed to unban that user", ephemeral=True)

    @commands.slash_command(name="kick", description="Kicks a user")
    @commands.has_permissions(kick_members=True)
    async def kick(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        rule: RuleConverter = RulesAutocomplete,
    ):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        try:
            await user.send(f"You were kicked from **{inter.guild.name}** for breaking rule `{rule}`")
        except disnake.HTTPException:
            pass

        await user.kick(reason=f"Mod: {inter.user}")
        await inter.send(embed=SuccessEmbed(inter.user, f"**{user}** was kicked for breaking rule `{rule.id}`"))
        await self.bot.dis_log.log_target_action("Kick", user, inter.user, violated_rule=str(rule))

    @commands.slash_command(name="temprole", description="Temporarily assigns a role to a user")
    async def temprole(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        role: disnake.Role,
        time: TimeConverter,
    ):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        await inter.response.defer()
        await user.add_roles(role)
        await self.bot.db.add_temprole(user.id, role.id, time)
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully assigned {role.mention} to {user.mention} for **{timedelta_to_full_str(time)}**",
            )
        )


class WarningsManagement(Cog):
    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        return await is_staff(self.bot, inter)

    @commands.slash_command(name="warn", description="Warns a member")
    async def warn(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        rule: RuleConverter = RulesAutocomplete,
    ):
        if user.top_role >= inter.user.top_role:
            raise HierarchyError()

        await self.bot.db.add_warn(user.id, inter.user.id, rule.id)
        total_warns = await self.bot.db.execute(
            "SELECT COUNT(*) FROM warns WHERE target_id = $1",
            user.id,
            fetch_mode=FetchMode.VAL,
        )
        warns_for_rule = await self.bot.db.execute(
            "SELECT COUNT(*) FROM warns WHERE target_id = $1 AND rule_violated = $2",
            user.id,
            rule.id,
            fetch_mode=FetchMode.VAL,
        )

        await inter.send(
            embed=BaseEmbed(
                user,
                color=0xFFFF00,
                title="⚠️ Warning",
                description=f"{user.mention} was warned.",
            )
            .add_field("Violated rule", str(rule), inline=False)
            .add_field(
                "Warnings now",
                f"**Total:** `{total_warns}`\n**For rule `{rule.id}`:** `{warns_for_rule}`",
            )
        )
        await self.bot.dis_log.log_target_action("Warn", user, inter.user, violated_rule=str(rule))

        try:
            await user.send(
                f"You were warned in {inter.guild.name}. \
Violated rule: `{rule}`. This warning will automatically be removed from you in a month."
            )
        except disnake.HTTPException:
            pass

    @commands.slash_command(name="warns", description="Shows all warnings for member")
    async def warns(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member):
        warnings = await self.bot.db.get_warns(user.id)
        embed = disnake.Embed(
            color=0x00FFFF,
            title=f"{user}'s Warnings",
            description=f"This user has totally **{len(warnings)}** warning({s_(len(warnings))}",
        )

        for warning in warnings:
            embed.add_field(
                f"#{warning.id}",
                f"Issued by: <@{warning.issuer_id}> ({warning.issuer_id})\n\
Issued at: {datetime_to_timestamp(warning.issued_at)}\n\
Violated rule: `{warning.rule_violated}`",
            )

        await inter.send(embed=embed)

    @commands.slash_command(name="delwarn", description="Deletes a single warning")
    async def delwarn(self, inter: disnake.ApplicationCommandInteraction, id: int):
        if await self.bot.db.delete_warn(id):
            await inter.send(embed=SuccessEmbed(inter.user, f"Successfully deleted warning `#{id}`"))
        else:
            await inter.send(
                embed=ErrorEmbed(inter.user, f"Warning `#{id}` does not exist"),
                ephemeral=True,
            )

    @commands.slash_command(name="delwarns", description="Deletes all warnings from the user")
    async def delwarns(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member):
        count = await self.bot.db.clear_warns(user.id)
        if count > 0:
            await inter.send(
                embed=SuccessEmbed(
                    inter.user,
                    f"Successfully removed **{count}** warning{s_(count)} from {user.mention}",
                )
            )
        else:
            await inter.send("That user has no warnings to clear", ephemeral=True)


class ChannelsModeration(Cog):
    def __init__(self, bot):
        super().__init__(bot)
        self.locked_channels: list[disnake.TextChannel] = []

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        return await is_staff(self.bot, inter)

    @commands.slash_command(name="lock", description="Locks a channel")
    async def lock(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = None,
        time: TimeConverter = None,
    ):
        channel = channel or inter.channel
        user_perms = channel.permissions_for(inter.user)
        if not user_perms.send_messages or not user_perms.read_messages:
            await inter.send(
                embed=ErrorEmbed(inter.user, "You do not have right to lock that channel"),
                ephemeral=True,
            )
            return
        if channel.permissions_for(inter.guild.default_role).send_messages is False:
            await inter.send("This channel is already locked", ephemeral=True)
            return

        overwrite = channel.overwrites_for(inter.guild.default_role)
        overwrite.send_messages = False
        await channel.set_permissions(
            inter.guild.default_role,
            overwrite=overwrite,
            reason=f"Mod: {inter.user}",
        )
        if time is not None:
            await self.bot.db.add_locked_channel(channel.id, time)

        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Locked channel {channel.mention}{' for ' + timedelta_to_full_str(time) if time is not None else ''}",
            )
        )
        await self.bot.dis_log.log_target_action("Channel Lock", channel, inter.user, time, color=0xFF0000)

    @commands.slash_command(name="unlock", description="Unlocks a channel")
    async def unlock(
        self,
        inter: disnake.ApplicationCommandInteraction,
        channel: disnake.TextChannel = None,
    ):
        channel = channel or inter.channel
        user_perms = channel.permissions_for(inter.user)
        if not user_perms.send_messages or not user_perms.read_messages:
            await inter.send(
                embed=ErrorEmbed(inter.user, "You do not have right to lock that channel"),
                ephemeral=True,
            )
            return
        if channel.permissions_for(inter.guild.default_role).send_messages is not False:
            await inter.send("This channel is not locked", ephemeral=True)
            return

        overwrite = channel.overwrites_for(inter.guild.default_role)
        overwrite.send_messages = None
        await channel.set_permissions(
            inter.guild.default_role,
            overwrite=overwrite,
            reason=f"Mod: {inter.user}",
        )
        await self.bot.db.remove_locked_channel(channel.id)
        await inter.send(embed=SuccessEmbed(inter.user, f"Unlocked channel {channel.mention}"))
        await self.bot.dis_log.log_target_action("Channel Unlock", channel, inter.user, color=0x00FF00)

    @commands.slash_command(name="slowmode", description="Sets slowmode for a channel")
    async def slowmode(
        self,
        inter: disnake.ApplicationCommandInteraction,
        slowmode: TimeConverter = None,
        channel: disnake.TextChannel = None,
    ):
        channel = channel or inter.channel
        user_perms = channel.permissions_for(inter.user)
        if not user_perms.send_messages or not user_perms.read_messages:
            await inter.send(
                embed=ErrorEmbed(
                    inter.user,
                    "You do not have right to change slowmode in that channel",
                ),
                ephemeral=True,
            )
            return

        await channel.edit(slowmode_delay=slowmode.seconds if slowmode is not None else 0)
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully set the slowmode in {channel.mention} to **{timedelta_to_full_str(slowmode)}**",
            )
        )

    @commands.slash_command(name="purge", description="Purges messages in a channel")
    async def purge(
        self,
        inter: disnake.ApplicationCommandInteraction,
        amount: int,
        member: disnake.Member = None,
        channel: disnake.TextChannel = None,
    ):
        channel = channel or inter.channel
        user_perms = channel.permissions_for(inter.user)
        if not user_perms.send_messages or not user_perms.read_messages:
            await inter.send(
                embed=ErrorEmbed(inter.user, "You do not have right to purge that channel"),
                ephemeral=True,
            )
            return

        await inter.response.defer(ephemeral=True)
        if member is None:

            def check(m):
                return not m.pinned

        else:

            def check(m):
                return not m.pinned and m.author == member

        purged = len(await channel.purge(limit=amount, check=check))
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully purged **{purged}** messages in {channel.mention}",
            ),
            ephemeral=True,
        )

    @commands.slash_command(name="purgetill", description="Purges all messages below the given")
    async def purgetill(
        self,
        inter: disnake.ApplicationCommandInteraction,
        message_id: int = commands.Param(large=True),
    ):
        message = await inter.channel.fetch_message(message_id)
        if message is None:
            await inter.send("Could not find a message with that ID", ephemeral=True)
            return
        await inter.response.defer(ephemeral=True)
        purged = len(await inter.channel.purge(limit=500, check=lambda m: not m.pinned, after=message.created_at))
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully purged **{purged}** messages in {inter.channel.mention}",
            ),
            ephemeral=True,
        )

    @commands.slash_command(name="lockserver", description="Locks the entire server")
    @commands.has_permissions(manage_guild=True)
    async def lockserver(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        self.locked_channels = [
            c
            for c in inter.guild.text_channels
            if c.permissions_for(inter.guild.default_role).send_messages is not False
        ]
        for c in self.locked_channels:
            overwrite = c.overwrites_for(inter.guild.default_role)
            overwrite.send_messages = False
            await c.set_permissions(
                inter.guild.default_role,
                overwrite=overwrite,
                reason=f"Server lock done by {inter.user}",
            )
        await inter.send(embed=SuccessEmbed(inter.user, "Successfully locked the server"))

    @commands.slash_command(name="unlockserver", description="Unlocks the server")
    @commands.has_permissions(manage_guild=True)
    async def unlockserver(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        for c in self.locked_channels:
            overwrite = c.overwrites_for(inter.guild.default_role)
            overwrite.send_messages = None
            await c.set_permissions(
                inter.guild.default_role,
                overwrite=overwrite,
                reason=f"Server unlock done by {inter.user}",
            )
        await inter.send(embed=SuccessEmbed(inter.user, "Unlocked the server"))
        self.locked_channels.clear()


class RulesManagement(Cog):
    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if inter.user.guild_permissions.manage_guild:
            return True
        raise commands.MissingPermissions(["Manage Guild"])

    @commands.slash_command(name="addrule", description="Adds a rule")
    async def addrule(self, inter: disnake.ApplicationCommandInteraction, id: str, contents: str):
        id = id if not id.endswith(".") else id[:-1]
        if len(id) > 5:
            await inter.send("Rule id cannot be longer than 5 characters", ephemeral=True)
            return
        await self.bot.db.add_rule(id, contents)
        invalidate_rules()
        await inter.send(embed=SuccessEmbed(inter.user, f"Successfully added rule `{id}`"))

    @commands.slash_command(name="removerule", description="Removes a rule")
    async def removerule(
        self,
        inter: disnake.ApplicationCommandInteraction,
        rule: RuleConverter = RulesAutocomplete,
    ):
        await self.bot.db.remove_rule(rule.id)
        invalidate_rules()
        await inter.send(embed=SuccessEmbed(inter.user, f"Successfully removed rule `{rule.id}`"))
