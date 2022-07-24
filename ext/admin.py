import asyncio
from contextlib import redirect_stdout
from io import StringIO

import disnake
from disnake.ext import commands

from utils.cog import Cog


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
            await inter.send(embed=disnake.Embed(color=0xFF0000, title="Exception Occurred").add_field("Exception", str(e)))
