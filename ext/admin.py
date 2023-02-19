import asyncio
from contextlib import redirect_stdout
from io import StringIO

import asyncpg
import disnake
from disnake.ext import commands

from utils.cog import Cog
from utils.constants import APPLICATIONS_CHANNEL_ID, GUILD_ID
from utils.enums import FetchMode
from utils.views import ApplicationsView


class AdminCommands(Cog):
    @commands.slash_command(name="exec", description="Executes a code")
    @commands.is_owner()
    async def exec_code(self, inter: disnake.ApplicationCommandInteraction, code: str):
        indented_code = ""
        for line in code.split("\n"):
            indented_code += " " * 12 + line + "\n"
        code = f"""
async def asyncf():
    try:
        s = StringIO()
        with redirect_stdout(s):
{indented_code}
        res = s.getvalue()
        embed = disnake.Embed(color=0x00FF00, title="Code was executed successfully")
        if len(res) > 0:
            embed.add_field("Output", "```py\\n" + res + "```")
        await inter.send(embed=embed)
    except Exception as e:
        await inter.send(embed=disnake.Embed(color=0xFF0000, title="Exception Occurred").add_field("Exception", str(e)))

asyncio.run_coroutine_threadsafe(asyncf(), asyncio.get_running_loop())"""
        env = {
            "asyncio": asyncio,
            "self": self,
            "inter": inter,
            "disnake": disnake,
            "StringIO": StringIO,
            "redirect_stdout": redirect_stdout,
        }
        try:
            exec(code, env)
        except Exception as e:
            await inter.send(
                embed=disnake.Embed(color=0xFF0000, title="Exception Occurred").add_field("Exception", str(e))
            )

    @commands.Cog.listener("on_member_join")
    async def remove_left(self, member: disnake.Member):
        await self.bot.db.execute("UPDATE scores SET left_server = false WHERE id = $1", member.id)

    @commands.Cog.listener("on_member_remove")
    async def add_left(self, member: disnake.Member):
        await self.bot.db.execute("UPDATE scores SET left_server = true WHERE id = $1", member.id)

    @commands.slash_command(
        name="scanleftmembers",
        description="Scans left members and ignores them in lb",
        guild_ids=[GUILD_ID],
    )
    async def scanleftmembers(self, inter: disnake.ApplicationCommandInteraction):
        await inter.response.defer()
        all_actual_members = {m.id for m in inter.guild.members}
        db_members = {
            r["id"]
            for r in await self.bot.db.execute("SELECT id FROM scores WHERE NOT left_server", fetch_mode=FetchMode.ALL)
        }
        left_members = db_members - all_actual_members
        async with self.bot.db.pool.acquire() as con:
            con: asyncpg.Connection
            await con.executemany(
                "UPDATE scores SET left_server = TRUE WHERE id = $1",
                [(i,) for i in left_members],
            )
        await inter.send(f"Successfully marked **{len(left_members)} members** as left")

    @commands.slash_command(name="setupappl", description="Setups applications")
    async def setupappl(self, inter: disnake.ApplicationCommandInteraction):
        channel = inter.guild.get_channel(APPLICATIONS_CHANNEL_ID)
        await channel.send(
            "__**Job Application**__\nPress the corresponding button to apply for a job",
            view=ApplicationsView(),
        )
        await inter.send("Done", ephemeral=True)
