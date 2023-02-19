from dataclasses import dataclass
from datetime import timedelta
from re import search

import disnake
import pendulum
from disnake.ext.commands import Converter, converter_method

from utils.autocomplete import get_rules
from utils.errors import DateConversionFailure, RuleNotFound, TimeConversionFailure

utc = pendulum.timezone("UTC")


class TimeConverter(Converter, timedelta):
    @converter_method
    async def convert(self, inter: disnake.ApplicationCommandInteraction, argument: str) -> timedelta:
        arg = argument.lower().replace(" ", "")
        values = {"days": 0, "hours": 0, "minutes": 0, "seconds": 0}
        for k in values.copy():
            try:
                value = search(r"\d+" + k[0], arg).group()
                values[k] = int(value.replace(k[0], ""))
            except (AttributeError, ValueError):
                pass

        delta = timedelta(**values)
        if delta.total_seconds() == 0:
            raise TimeConversionFailure(argument)

        return delta


@dataclass
class Rule:
    id: str
    content: str

    def __str__(self):
        return f"{self.id}. {self.content}"


class RuleConverter(Converter, Rule):
    @converter_method
    async def convert(self, inter: disnake.ApplicationCommandInteraction, argument: str) -> Rule:
        argument = argument.strip().lower()
        rules = await get_rules(inter.bot)
        if argument not in rules:
            raise RuleNotFound(argument)

        return Rule(argument, rules[argument])


class DateConverter(Converter, pendulum.Date):
    @converter_method
    async def convert(self, inter: disnake.ApplicationCommandInteraction, argument: str) -> pendulum.Date:
        try:
            d = utc.convert(pendulum.parse(argument, strict=False))
            if isinstance(d, pendulum.DateTime):
                return pendulum.Date.fromtimestamp(d.timestamp())
            if isinstance(d, pendulum.Date):
                return d
        except Exception:
            raise DateConversionFailure(argument)
        raise DateConversionFailure(argument)
