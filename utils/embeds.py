from datetime import datetime

import disnake

_Author = disnake.Member | disnake.User | None


class BaseEmbed(disnake.Embed):
    def __init__(self, author: _Author = None, **kwargs):
        super().__init__(**kwargs)
        if "timestamp" not in kwargs:
            self.timestamp = datetime.now()
        if author is not None:
            self.set_footer(text=str(author), icon_url=author.display_avatar.url)


class SuccessEmbed(BaseEmbed):
    def __init__(self, author: _Author, text: str, title: str | None = None):
        title = title or "Action Successful"
        title = "✅ " + title
        super().__init__(author, title=title, description=text, color=0x00FF00)


class ErrorEmbed(BaseEmbed):
    def __init__(self, author: _Author, text: str, title: str | None = None):
        title = title or "Error Occurred"
        title = "❌ " + title
        super().__init__(author, title=title, description=text, color=0xFF0000)
