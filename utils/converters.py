from dataclasses import dataclass
from datetime import timedelta
from re import search

import disnake
from disnake.ext.commands import Converter, converter_method

from utils.autocomplete import get_rules
from utils.errors import RuleNotFound


class TimeConverter(Converter, timedelta):
    @converter_method
    async def convert(
        self, inter: disnake.ApplicationCommandInteraction, argument: str
    ) -> timedelta:
        arg = argument.lower().replace(" ", "")
        values = {"days": 0, "hours": 0, "minutes": 0, "seconds": 0}
        for k in values.copy():
            try:
                value = search(r"\d+" + k[0], arg).group()
                values[k] = int(value.replace(k[0], ""))
            except (AttributeError, ValueError):
                pass

        return timedelta(**values)


@dataclass
class Rule:
    id: str
    content: str

    def __str__(self):
        return f"{self.id} {self.content}"


class RuleConverter(Converter, Rule):
    @converter_method
    async def convert(
        self, inter: disnake.ApplicationCommandInteraction, argument: str
    ) -> Rule:
        argument = argument.strip().lower()
        rules = await get_rules(inter.bot)
        if argument not in rules:
            raise RuleNotFound(argument)

        return Rule(argument, rules[argument])
