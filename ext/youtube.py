import disnake
from disnake.ext import commands, tasks

from utils.checks import is_staff
from utils.cog import Cog
from utils.constants import APPLICATIONS_CHANNEL_ID, NEW_VIDEOS_ROLE_ID, YOUTUBE_CHANNEL_ID
from utils.embeds import SuccessEmbed
from utils.errors import YoutubeFetchFailure
from utils.youtube import fetch_last_video


class YoutubeFetchers(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self.queue: list[tuple[int, str]] = []  # list[tuple[discord_id, youtube_id]]
        self.youtube_fetcher.start()
        self.youtube_poster.start()

    @Cog.listener("on_member_remove")
    async def youtuber_remover(self, member: disnake.Member):
        is_youtuber = await self.bot.db.remove_youtuber(member.id)
        if is_youtuber:
            self.bot.log.warning("Youtuber %s left so was removed from content creators program", member)
            await self.bot.dis_log.log_target_action("Youtuber Autoremove", member, member.guild.me)
            for t in self.queue.copy():
                if t[0] == member.id:
                    self.queue.remove(t)

    @tasks.loop(minutes=5)
    async def youtube_fetcher(self):
        await self.bot.wait_until_ready()
        youtubers = await self.bot.db.get_youtubers()
        for youtuber in youtubers:
            try:
                last_video = await fetch_last_video(youtuber.youtube_id)
            except YoutubeFetchFailure:
                self.bot.log.error(
                    "Failed to fetch video for youtuber %s (%s)",
                    youtuber.youtube_id,
                    await self.bot.server.get_or_fetch_member(youtuber.id),
                )
                continue
            if last_video != youtuber.last_video:
                member = await self.bot.server.get_or_fetch_member(youtuber.id)
                if member is None:
                    await self.bot.db.remove_youtuber(youtuber.id)
                    self.bot.log.warning(
                        "Youtuber %s left so was removed from content creators program",
                        youtuber.id,
                    )
                    continue
                self.queue.append((youtuber.id, last_video))
                await self.bot.db.set_youtuber_last_video(youtuber.id, last_video)

    @tasks.loop(minutes=10)
    async def youtube_poster(self):
        await self.bot.wait_until_ready()
        if len(self.queue) == 0:
            return

        id, last_video = self.queue.pop(0)
        youtube_channel = self.bot.server.get_channel(YOUTUBE_CHANNEL_ID)
        m = await youtube_channel.send(
            f"<@&{NEW_VIDEOS_ROLE_ID}>\nOur content creator <@{id}> "
            f"just posted a new video!\n\nhttps://youtube.com/watch?v={last_video}\n\n"
            f"Want to be advertised like this as well? Check out <#{APPLICATIONS_CHANNEL_ID}>"
        )
        await m.publish()


class YoutubeManagement(Cog):
    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        return await is_staff(self.bot, inter)

    @commands.slash_command(name="addyt", description="Adds a new youtuber")
    async def addyt(
        self,
        inter: disnake.ApplicationCommandInteraction,
        user: disnake.Member,
        youtube_id: str,
        premium: bool,
    ):
        await self.bot.db.add_youtuber(user.id, youtube_id, premium)
        await inter.send(
            embed=SuccessEmbed(
                inter.user,
                f"Successfully added {user.mention} to content creators program",
            )
        )

    @commands.slash_command(name="removeyt", description="Removes a youtuber")
    async def removeyt(self, inter: disnake.ApplicationCommandInteraction, user: disnake.Member):
        is_youtuber = await self.bot.db.remove_youtuber(user.id)
        if is_youtuber:
            await inter.send(
                embed=SuccessEmbed(
                    inter.user,
                    f"Successfully removed {user.mention} from content creators program",
                )
            )
        else:
            await inter.send("This user is not a youtuber", ephemeral=True)
