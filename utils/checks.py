import disnake
from disnake.ext.commands import Context, check

from utils.errors import StaffOnly


async def is_staff(bot, inter: disnake.Interaction) -> bool:
    if bot.staff_role in inter.user.roles:
        return True
    raise StaffOnly()


def staff_only():
    async def predicate(ctx: Context | disnake.ApplicationCommandInteraction):
        return await is_staff(ctx.bot, ctx)

    return check(predicate)
