import re
from typing import Awaitable, Callable, Generic, TypeVar

import disnake

from utils.checks import is_staff
from utils.constants import (
    APPLICATIONS_LINKS,
    JOB_APPLICATIONS_CATEGORY_ID,
    STAFF_APPL_MIN_ROLE_ID,
    STAFF_ROLE_ID,
)

T = TypeVar("T")


MENTION_PATTERN = re.compile(r"<@!?\d{18,19}>")


class Button(disnake.ui.Button, Generic[T]):
    def __init__(self, return_value: T = None, **kwargs):
        super().__init__(**kwargs)
        self.return_value = return_value

    async def callback(self, interaction: disnake.MessageInteraction):
        self.view.set_value(self.return_value, interaction)


class BaseView(disnake.ui.View, Generic[T]):
    def __init__(
        self,
        user_id: int,
        buttons: list[Button[T]],
        disable_after_interaction: bool = True,
    ):
        self.value: T = None
        self.inter: disnake.MessageInteraction | None = None
        self.user_id = user_id
        self.disable_after_interaction = disable_after_interaction
        super().__init__()
        for button in buttons:
            self.add_item(button)

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        if inter.author.id != self.user_id:
            await inter.send("This button is not for you :wink:", ephemeral=True)
            return False

        return True

    def set_value(self, value, inter: disnake.MessageInteraction):
        self.value = value
        self.inter = inter
        self.stop()

    async def get_result(self) -> tuple[T, disnake.MessageInteraction]:
        await self.wait()
        if self.disable_after_interaction:
            for child in self.children:
                child.disabled = True

            await self.inter.message.edit(view=self)

        return self.value, self.inter


class ConfirmationView(BaseView):
    def __init__(self, user_id: int, disable_after_interaction: bool = True):
        super().__init__(
            user_id,
            [
                Button(True, label="Yes", style=disnake.ButtonStyle.green),
                Button(False, label="No", style=disnake.ButtonStyle.red),
            ],
            disable_after_interaction,
        )


class ApplicationsView(disnake.ui.View):
    applicants: list[int] = []

    def __init__(self):
        super().__init__(timeout=None)

        async def staff_check(inter: disnake.Interaction):
            role = inter.guild.get_role(STAFF_APPL_MIN_ROLE_ID)
            if role not in inter.user.roles:
                await inter.send(
                    f"You need {role.mention} to apply for staff", ephemeral=True
                )
                return False
            return True

        buttons = [
            ApplicationButton(
                staff_check,
                label="Server Staff",
                emoji="🛠️",
                custom_id="appl_server_staff",
                style=disnake.ButtonStyle.blurple,
            ),
            ApplicationButton(
                label="Game Manager",
                emoji="🎮",
                custom_id="appl_game_manager",
                style=disnake.ButtonStyle.green,
            ),
            ApplicationButton(
                label="Content Creator",
                emoji="🎥",
                custom_id="appl_content_creator",
                style=disnake.ButtonStyle.red,
            ),
        ]

        for button in buttons:
            self.add_item(button)


class ApplicationControlsView(disnake.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @disnake.ui.button(
        label="Close", style=disnake.ButtonStyle.red, custom_id="appl_close"
    )
    async def close(self, _, inter: disnake.MessageInteraction):
        await inter.send("Closing...", ephemeral=True)
        await inter.channel.delete()
        try:
            ApplicationsView.applicants.remove(inter.author.id)
        except ValueError:
            pass

    @disnake.ui.button(
        label="Done", style=disnake.ButtonStyle.green, custom_id="appl_done"
    )
    async def done(self, _, inter: disnake.MessageInteraction):
        await inter.response.defer(with_message=True)
        await inter.channel.set_permissions(
            inter.user, send_messages=False, read_messages=True
        )
        for button in self.children:
            if isinstance(button, disnake.ui.Button):
                match button.custom_id:
                    case "appl_done":
                        button.disabled = True
                    case "appl_unlock":
                        button.disabled = False
        await inter.bot.owner.send(
            f"New application by {inter.author} please check {inter.channel.mention}"
        )
        await inter.message.edit(view=self)
        await inter.send(
            "We have notified staff that you have sent the form, now please wait for them to review it. "
            "Usually it doesn't take more than a day"
        )

    @disnake.ui.button(
        label="Unlock",
        style=disnake.ButtonStyle.blurple,
        custom_id="appl_unlock",
        disabled=True,
    )
    async def unlock(
        self, button: disnake.ui.Button, inter: disnake.MessageInteraction
    ):
        if not await is_staff(inter.bot, inter):
            await inter.send("Only staff can use this", ephemeral=True)
            return
        await inter.response.defer(with_message=True, ephemeral=True)
        self.remove_item(button)
        await inter.message.edit(view=self)
        member = inter.message.mentions[0]
        if member is None or isinstance(member, disnake.User):
            await inter.send("Seems like this member has left the server")
            return
        await inter.channel.set_permissions(
            member, send_messages=True, read_messages=True
        )
        await inter.send("Unlocked the channel", ephemeral=True)
        await inter.channel.send(
            f"{member.mention}, {inter.author.mention} has come to review your application!"
        )


class ApplicationButton(disnake.ui.Button):
    def __init__(
        self,
        pred: Callable[[disnake.Interaction], Awaitable[bool]] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.pred = pred

    async def callback(self, interaction: disnake.MessageInteraction, /):
        if interaction.author.id in ApplicationsView.applicants:
            await interaction.send(
                "You already have an application opened, please close your current one first.",
                ephemeral=True,
            )
            return
        if self.pred is not None and not await self.pred(interaction):
            return
        link = APPLICATIONS_LINKS[self.custom_id]
        category: disnake.CategoryChannel = interaction.guild.get_channel(
            JOB_APPLICATIONS_CATEGORY_ID
        )
        if category is None:
            await interaction.send(
                "Sorry, I was unable to find the system category. "
                "Please contact administrators about this.",
                ephemeral=True,
            )
            return
        await interaction.response.defer(with_message=True, ephemeral=True)
        channel = await category.create_text_channel(
            name=f"ja-{interaction.user}",
            overwrites={
                interaction.guild.default_role: disnake.PermissionOverwrite(
                    read_messages=False
                ),
                interaction.user: disnake.PermissionOverwrite(
                    read_messages=True, send_messages=False
                ),
                interaction.guild.get_role(STAFF_ROLE_ID): disnake.PermissionOverwrite(
                    read_messages=True, send_messages=True
                ),
            },
        )
        await channel.send(
            f"__**{self.label} Application**__\n"
            f"{interaction.user.mention} please fill out this form and press "
            f"the green button below when you are done: {link}.\n\n"
            "If you didn't intend to open an application, press close button.",
            view=ApplicationControlsView(),
        )
        await interaction.send(f"Please head to {channel.mention}", ephemeral=True)
