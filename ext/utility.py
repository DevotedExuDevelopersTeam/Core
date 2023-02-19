from uuid import uuid4

import disnake
from disnake.ext import commands

from utils.checks import staff_only
from utils.cog import Cog
from utils.embeds import SuccessEmbed


class ButtonRoles(Cog):
    def __init__(self, bot):
        super().__init__(bot)

        self._button_roles: dict[str, int] = {}

    async def cog_slash_command_check(self, inter: disnake.ApplicationCommandInteraction) -> bool:
        if inter.user.guild_permissions.manage_guild:
            return True
        raise commands.MissingPermissions(["manage_guild"])

    async def get_button_roles(self):
        if len(self._button_roles) == 0:
            self._button_roles = await self.bot.db.get_button_roles()
        return self._button_roles

    @Cog.listener("on_raw_message_delete")
    async def clear_button_roles_data(self, payload: disnake.RawMessageDeleteEvent):
        await self.bot.db.clear_button_roles(payload.message_id)

    @Cog.listener("on_button_click")
    async def role_controller(self, inter: disnake.MessageInteraction):
        id = inter.component.custom_id
        roles = await self.get_button_roles()
        if id not in roles:
            return

        target_role = inter.guild.get_role(roles[id])
        if target_role is None:
            await inter.send(
                "Sorry, couldn't find the role associated with this button. It might have been deleted",
                ephemeral=True,
            )
        elif target_role in inter.user.roles:
            await inter.send(f"Removed {target_role.mention} from you", ephemeral=True)
            await inter.user.remove_roles(target_role)
        else:
            await inter.send(f"Added {target_role.mention} to you", ephemeral=True)
            await inter.user.add_roles(target_role)

    @commands.slash_command(name="addbuttonrole", description="Adds a button role")
    async def addbuttonrole(
        self,
        inter: disnake.ApplicationCommandInteraction,
        message_id: int = commands.Param(large=True),
        button_name: str = commands.Param(),
        role: disnake.Role = commands.Param(),
    ):
        try:
            message: disnake.Message = await inter.channel.fetch_message(message_id)
        except disnake.NotFound:
            await inter.send("Could not find message with this ID", ephemeral=True)
            return

        await inter.response.defer()
        view = disnake.ui.View.from_message(message)
        id = uuid4().hex
        view.add_item(disnake.ui.Button(custom_id=id, label=button_name))
        await message.edit(view=view)
        await self.bot.db.add_button_role(id, role.id, message_id)
        await inter.send(embed=SuccessEmbed(inter.user, "Added a new button role"))

    @commands.slash_command(name="removebuttonrole", description="Removes a button role")
    async def removebuttonrole(
        self,
        inter: disnake.ApplicationCommandInteraction,
        message_id: int = commands.Param(large=True),
        button_name: str = commands.Param(),
    ):
        try:
            message: disnake.Message = await inter.channel.fetch_message(message_id)
        except disnake.NotFound:
            await inter.send("Could not find message with this ID", ephemeral=True)
            return

        await inter.response.defer()
        view = disnake.ui.View.from_message(message)
        for component in view.children:
            if isinstance(component, disnake.ui.Button) and component.label == button_name:
                view.remove_item(component)
                await message.edit(view=view)
                await self.bot.db.remove_button_role(component.custom_id)
                await inter.send(embed=SuccessEmbed(inter.user, "Successfully removed button role from that message"))
                return

        await inter.send(
            f"Couldn't find any buttons named `{button_name}` in that message",
            ephemeral=True,
        )

    @commands.slash_command(name="say", description="Says stuff")
    @staff_only()
    async def say(self, inter: disnake.ApplicationCommandInteraction, stuff: str):
        await inter.send("Ok", ephemeral=True)
        await inter.channel.send(stuff)
