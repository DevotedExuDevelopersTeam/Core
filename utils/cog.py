from disnake.ext import commands

from utils.bot import Bot


class Cog(commands.Cog):
    def __init__(self, bot: Bot):
        self.bot = bot
