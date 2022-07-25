import disnake

from utils.bot import Bot
from utils.enums import FetchMode

_cache: dict[str, str] = {}


def invalidate():
    _cache.clear()


async def get_rules(bot: Bot) -> dict[str, str]:
    global _cache
    if len(_cache) == 0:
        _cache = {
            r["id"]: r["content"]
            for r in await bot.db.execute(
                "SELECT id, content FROM rules ORDER BY id", fetch_mode=FetchMode.ALL
            )
        }
    return _cache


async def rules_autocomplete(inter: disnake.ApplicationCommandInteraction, arg: str):
    arg = arg.lower()
    return [r for r in await get_rules(inter.bot) if arg in r.lower()][:25]
