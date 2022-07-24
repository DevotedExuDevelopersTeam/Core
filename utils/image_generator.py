import asyncio
import os
from datetime import datetime
from random import randint
from urllib.request import build_opener, install_opener, urlretrieve

from PIL import Image, ImageDraw, ImageFont
from disnake import Role, User

from utils.bot import Bot

BASE_COLOR = (0, 255, 234)
PAGE_COLOR = (82, 206, 251)
WHITE = (255, 255, 255)

PLACE_X = 18
MEMBER_X = 138
SCORE_X = 597
FIRST_ROW_Y = 246
PAGE_TXT_POSITION = (24, 1161)

MEMBER_COLOR = (0, 251, 255)
PLACE_COLOR = (0, 221, 255)
SQUARE_COLOR = (50, 74, 255)

MEMBER_NAME_POSITION = (300, 192)
PLACE_POSITION = (1356.3, 144)
PFP_POSITION = (127, 294)
SCORE_POSITION = (905, 338)
NEXT_ROLE_POSITION = (905, 517.5)
SQUARE_LEFT_X = 529.5
SQUARE_TOP_Y = 297.5
SQUARE_BOTTOM_Y = 378.5
SQUARE_SIZE = 54.19
SQUARE_STEP = 77.41

request_opener = build_opener()
request_opener.addheaders = [("Authorization", f"Bot {os.getenv('TOKEN')}")]
install_opener(request_opener)


def get_font(size):
    return ImageFont.truetype("res/orbitron.ttf", size=size)


def generate_id():
    return f"{int(datetime.now().timestamp())}{str(randint(1000, 9999))}"


async def draw_leaderboard(bot: Bot, page: int) -> bytes:
    return await asyncio.get_event_loop().run_in_executor(
        None, _draw_leaderboard, bot, page
    )


def _draw_leaderboard(bot: Bot, page: int) -> bytes:
    img = Image.open("res/template.png")
    draw = ImageDraw.Draw(img)
    font = get_font(45)
    page_font = get_font(60)
    top_data = await bot.db.get_top_data(page)
    for pos, entry in enumerate(top_data):
        y_pos = FIRST_ROW_Y + 90 * pos
        if y_pos > 1070:
            break
        member = bot.get_user(entry["id"])
        if member is None:
            pos -= 1
            continue
        member_name = str(member)
        while draw.textsize(member_name, font=get_font(45))[0] > 430:
            if member_name.endswith("..."):
                member_name = member_name[:-4] + "..."
            else:
                member_name = member_name[:-1] + "..."
        draw.text(
            (PLACE_X, y_pos), text=str(pos), fill=BASE_COLOR, font=font, anchor="ls"
        )
        draw.text(
            (MEMBER_X, y_pos), text=member_name, fill=BASE_COLOR, font=font, anchor="ls"
        )
        draw.text(
            (SCORE_X, y_pos),
            text=number_to_numstring(entry["score_total"]),
            fill=BASE_COLOR,
            font=font,
            anchor="ls",
        )

    draw.text(
        PAGE_TXT_POSITION,
        text=f"Page#{page}",
        fill=PAGE_COLOR,
        font=page_font,
        anchor="ls",
    )
    return img.tobytes()


async def draw_rank_card(
    member: User,
    position: int,
    next_role: Role,
    current_score: int,
    score_to_next_role: int = None,
    custom_bg_path: str = None,
) -> bytes:
    return await asyncio.get_running_loop().run_in_executor(
        None,
        _draw_rank_card,
        member,
        position,
        next_role,
        current_score,
        score_to_next_role,
        custom_bg_path,
    )


def _draw_rank_card(
    member: User,
    position: int,
    next_role: Role | None,
    current_score: int,
    score_to_next_role: int | None = None
) -> bytes:
    if not next_role:
        next_role_name = "All roles obtained!"
        next_role_color = WHITE
    else:
        next_role_name = next_role.name
        next_role_color = next_role.color.to_rgb()
    urlretrieve(str(member.display_avatar.url)[:-3] + "png", "avatar.png")
    custom_bg_path = f"backgrounds/{member.id}.png"
    if not os.path.exists(custom_bg_path):
        template = Image.open("res/rank_template.png")
    else:
        template = Image.open(custom_bg_path)
        pasted_image = Image.open("res/rank_template_transparent.png")
        template.paste(pasted_image, mask=pasted_image)
    avatar = Image.open("avatar.png").resize((221, 221))
    draw = ImageDraw.Draw(template)

    member_font = get_font(40)
    place_font = get_font(95)
    score_role_font = get_font(55)

    template.paste(avatar, PFP_POSITION)
    draw.text(
        MEMBER_NAME_POSITION,
        str(member),
        fill=MEMBER_COLOR,
        font=member_font,
        anchor="ls",
    )
    draw.text(
        PLACE_POSITION,
        "#" + str(position),
        fill=PLACE_COLOR,
        font=place_font,
        anchor="rs",
    )
    draw.text(
        NEXT_ROLE_POSITION,
        next_role_name,
        fill=next_role_color,
        font=score_role_font,
        anchor="mm",
    )

    squares_amount = (
        10 if not score_to_next_role else int(current_score / score_to_next_role * 10)
    )
    for i in range(squares_amount):
        x_left = SQUARE_LEFT_X + SQUARE_STEP * i
        x_right = x_left + SQUARE_SIZE
        draw.rectangle(
            (x_left, SQUARE_TOP_Y, x_right, SQUARE_BOTTOM_Y),
            fill=SQUARE_COLOR,
        )

    if score_to_next_role:
        score_string = f"{number_to_numstring(current_score)} / {number_to_numstring(score_to_next_role)}"
    else:
        score_string = number_to_numstring(current_score)
    draw.text(
        SCORE_POSITION, f"{score_string}", fill=WHITE, font=score_role_font, anchor="mm"
    )

    return template.tobytes()


def number_to_numstring(num):
    if num < 10000:
        return str(num)
    elif 10000 <= num < 1000000:
        return (str(round(num / 1000, 1)) + "k").replace(".0k", "k")
    else:
        return (str(round(num / 1000000, 1)) + "m").replace(".0m", "m")
