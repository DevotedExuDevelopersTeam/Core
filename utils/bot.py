import importlib.util
import inspect
import os
import sys
import traceback
from datetime import datetime, timedelta

import disnake
from disnake.ext import commands
from exencolorlogs import Logger

from utils.constants import GUILD_ID, LOG_CHANNEL_ID, STAFF_ROLE_ID
from utils.datamodels import Database
from utils.utils import timedelta_to_full_str, timedelta_to_timestamp
from utils.views import ApplicationControlsView, ApplicationsView, PromocodeView

REQUIRED_DIRS = ["logs", "backgrounds"]
PERSISTENT_VIEWS = [ApplicationsView, ApplicationControlsView]


class Bot(commands.Bot):
    server: disnake.Guild
    staff_role: disnake.Role

    def __init__(self):
        intents = disnake.Intents.default()
        intents.message_content = True
        intents.members = True
        intents.dm_messages = False
        super().__init__(
            intents=intents,
            activity=disnake.Activity(type=disnake.ActivityType.watching, name="the server"),
            status=disnake.Status.idle,
        )
        self.log = Logger()
        self.db = Database()
        self.dis_log = DisLogger(self)

    def check_required_dirs(self):
        self.log.info("Checking required directories...")
        for d in REQUIRED_DIRS:
            if not os.path.exists(d):
                os.mkdir(d)
                self.log.warning("Directory %s was autogenerated", d)
        self.log.ok("All required directories exist")

    def run(self):
        self.log.info("Running...")
        self.check_required_dirs()
        self.load_all_extensions("ext")

        token = os.getenv("TOKEN")
        assert token is not None, "No token was provided"
        super().run(token)

    async def start(self, *args, **kwargs):
        self.log.info("Starting...")
        self.setup_persistent_views()
        await self.db.connect()

        await super().start(*args, **kwargs)

    async def close(self):
        self.log.info("Shutting down...")
        await self.db.close()

        await super().close()

    async def on_ready(self):
        self.log.info("Bot is ready!")

        self.server = self.get_guild(GUILD_ID)
        assert self.server is not None
        self.staff_role = self.server.get_role(STAFF_ROLE_ID)
        self.dis_log.load()

    def auto_setup(self, module_name: str):
        module = importlib.import_module(module_name, None)
        sys.modules[module_name] = module
        members = inspect.getmembers(
            module,
            lambda x: inspect.isclass(x) and issubclass(x, commands.Cog) and x.__name__ != "Cog",
        )
        for member in members:
            self.add_cog(member[1](self))

        self.log.ok("%s loaded", module_name)

    def load_all_extensions(self, path: str):
        self.log.info("Loading extensions...")
        for file in os.listdir(path):
            full_path = os.path.join(path, file).replace("\\", "/")
            if os.path.isdir(full_path):
                self.load_all_extensions(full_path)

            elif full_path.endswith(".py"):
                self.auto_setup(full_path[:-3].replace("/", "."))

    def setup_persistent_views(self):
        for cls in PERSISTENT_VIEWS:
            self.add_view(cls())
        self.add_view(PromocodeView(self))

    async def on_error(self, event_method: str, *args, **kwargs):
        self.log.error("Unhandled exception occurred at %s", event_method)
        await self.log_error()

    async def log_error(self):
        now = datetime.now().date()
        month_path = f"logs/{now.month}"
        if not os.path.exists(month_path):
            os.mkdir(month_path)

        path = f"{month_path}/{now.day}.log.err"
        with open(path, "a") as f:
            f.write("\n" + "-" * 50)
            f.write(f"\n{datetime.now()}\n")
            tb = traceback.format_exc()
            f.write(tb)

        await self.dis_log.log_channel.send(
            self.owner.mention,
            embed=disnake.Embed(
                colour=0xFF0000,
                title="❗ Unexpected error occurred",
            ).add_field("Traceback (most recent call last):", tb[-1000:], inline=False),
            file=disnake.File(path),
        )


class DisLogger:
    log_channel: disnake.TextChannel

    def __init__(self, bot: Bot):
        self.bot = bot

    def load(self):
        self.log_channel = self.bot.server.get_channel(LOG_CHANNEL_ID)
        assert self.log_channel is not None, "Failed to load log channel"

    async def log_target_action(
        self,
        action_name: str,
        target: disnake.Member | disnake.TextChannel,
        issuer: disnake.Member,
        duration: timedelta = None,
        violated_rule: str = None,
        color: int = 0xFF0000,
    ):
        embed = (
            disnake.Embed(color=color, title=action_name.capitalize(), timestamp=datetime.now())
            .add_field("Target", f"**{target}** ({target.mention})\nID: {target.id}")
            .add_field(
                "Issued By",
                f"{issuer.top_role.mention} **{issuer}** ({issuer.mention})\nID: {issuer.id}",
            )
        )

        if duration is not None:
            embed.add_field(
                "Duration",
                f"**{timedelta_to_full_str(duration)}** (ends at {timedelta_to_timestamp(duration)})",
            )

        if violated_rule is not None:
            embed.add_field("Violated Rule", violated_rule)

        await self.log_channel.send(embed=embed)
