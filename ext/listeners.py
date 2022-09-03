from datetime import datetime

import disnake

from utils.bot import Bot
from utils.cog import Cog
from utils.constants import (
    COUNTING_CHANNEL_ID,
    DELETED_MESSAGES_LOG_CHANNEL_ID,
    FILEMUTED_ROLE_ID,
    GOODBYE_CHANNEL_ID,
    HU_CHANNEL_ID,
    WELCOME_CHANNEL_ID,
)
from utils.embeds import ErrorEmbed
from utils.utils import ordinal_num


class MessageListeners(Cog):
    def __init__(self, bot: Bot):
        super().__init__(bot)
        self._filemuted_role = None

    @property
    def filemuted_role(self):
        if self._filemuted_role is None:
            self._filemuted_role = self.bot.server.get_role(FILEMUTED_ROLE_ID)
        return self._filemuted_role

    @Cog.listener("on_message")
    async def filemuted_controller(self, message: disnake.Message):
        if isinstance(message.author, disnake.User):
            return
        if self.filemuted_role in message.author.roles and len(message.attachments) > 0:
            await message.delete()
            await message.channel.send(
                embed=ErrorEmbed(
                    message.author,
                    f"{message.author.mention}, you cannot send attachments when filemuted!",
                ),
                delete_after=3,
            )

    @Cog.listener("on_message_delete")
    async def deleted_messages_log(self, message: disnake.Message):
        if message.author.bot:
            return
        channel = self.bot.server.get_channel(DELETED_MESSAGES_LOG_CHANNEL_ID)
        if channel is None:
            self.bot.log.warning("Failed to get deleted messages log channel")
            return

        await channel.send(
            embed=disnake.Embed(
                color=0xFFFF00,
                title=f"Message deleted from #{message.channel.name}",
                description=message.content,
                timestamp=datetime.now(),
            ).set_author(
                name=message.author, icon_url=message.author.display_avatar.url
            ),
            files=[await a.to_file() for a in message.attachments],
        )

    @Cog.listener("on_message")
    async def content_checker(self, message: disnake.Message):
        if message.author.bot or message.author.guild_permissions.manage_guild:
            return

        if message.channel.id == HU_CHANNEL_ID and message.content.lower() != "hu":
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} hu only!", delete_after=3
            )

        elif (
            message.channel.id == COUNTING_CHANNEL_ID
            and not disnake.utils.remove_markdown(message.content).isnumeric()
        ):
            await message.delete()
            await message.channel.send(
                f"{message.author.mention} numbers only!", delete_after=3
            )


class MembersListeners(Cog):
    @Cog.listener("on_member_join")
    async def member_welcomer(self, member: disnake.Member):
        channel = self.bot.server.get_channel(WELCOME_CHANNEL_ID)
        if channel is None:
            self.bot.log.warning("Failed to get welcome channel")
            return

        await channel.send(
            f"{member.mention} has joined! \
They are our **{ordinal_num(member.guild.member_count)}** member!"
        )

    @Cog.listener("on_member_remove")
    async def member_goodbyer(self, member: disnake.Member):
        channel = self.bot.server.get_channel(GOODBYE_CHANNEL_ID)
        if channel is None:
            self.bot.log.warning("Failed to get goodbye channel")
            return

        await channel.send(f"{member} just left.")
