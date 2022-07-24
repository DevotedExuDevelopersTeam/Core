from typing import Generic, TypeVar

import disnake

T = TypeVar("T")


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
    def __init__(self, user_id: int):
        super().__init__(
            user_id,
            [
                Button(True, label="Yes", style=disnake.ButtonStyle.green),
                Button(False, label="No", style=disnake.ButtonStyle.red),
            ],
        )
