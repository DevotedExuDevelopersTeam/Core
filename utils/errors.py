import inspect
import sys

import disnake
from disnake.ext import commands

UNKNOWN = object()


class CustomError(commands.CommandError):
    pass


class StaffOnly(CustomError):
    def __init__(self):
        super().__init__("This command is **staff only**")


class AdminOnly(CustomError):
    def __init__(self):
        super().__init__("This command is **admin only**")


class TimeConversionFailure(CustomError):
    def __init__(self, arg: str):
        super().__init__(f"Could not convert `{arg}` to time")


class HierarchyError(CustomError):
    def __init__(self):
        super().__init__(
            "You cannot use this command on someone with equal or higher top role than you"
        )


class RuleNotFound(CustomError):
    def __init__(self, rule: str):
        super().__init__(f"Rule {rule} does not exist.")


class YoutubeFetchFailure(CustomError):
    def __init__(self, youtuber_id: str):
        super().__init__(f"Failed to fetch latest video for youtuber {youtuber_id}")


known_exceptions = [
    i[1]
    for i in inspect.getmembers(
        sys.modules[__name__],
        lambda x: inspect.isclass(x) and issubclass(x, CustomError),
    )
]
known_exceptions.extend(
    [
        commands.MissingRequiredArgument,
        commands.ArgumentParsingError,
        commands.BadArgument,
        commands.CheckFailure,
        commands.CommandNotFound,
        commands.DisabledCommand,
        commands.CommandOnCooldown,
        commands.NotOwner,
        commands.MemberNotFound,
        commands.UserNotFound,
        commands.ChannelNotFound,
        commands.RoleNotFound,
        commands.MissingPermissions,
        commands.BotMissingPermissions,
        commands.MissingRole,
        commands.MissingAnyRole,
        disnake.Forbidden,
    ]
)


def get_error_msg(error: commands.CommandError) -> object | str:
    if type(error) not in known_exceptions:
        return UNKNOWN
    else:
        return str(error)
