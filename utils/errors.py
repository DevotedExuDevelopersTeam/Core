from disnake.ext import commands


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
