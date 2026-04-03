import asyncio
import io
import logging
import os

import httpx
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

STEAM_BG_TOP = (44, 62, 80)
STEAM_BG_BOTTOM = (24, 32, 44)
CARD_BG = (38, 44, 56, 230)
CARD_RADIUS = 12
AVATAR_SIZE = 72
AVATAR_RADIUS = 12
CARD_HEIGHT = 110
CARD_MARGIN = 18
CARD_GAP = 12
FONT_PATH_BOLD = "msyhbd.ttc"
FONT_PATH = "msyh.ttc"


async def fetch_avatar(avatar_url, data_dir, sid):
    if not avatar_url:
        return None
    avatar_dir = os.path.join(data_dir, "avatars")
    os.makedirs(avatar_dir, exist_ok=True)
    path = os.path.join(avatar_dir, f"{sid}.jpg")
    if os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            pass
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(avatar_url)
            if resp.status_code == 200:
                with open(path, "wb") as f:
                    f.write(resp.content)
                return Image.open(io.BytesIO(resp.content)).convert("RGBA")
    except Exception:
        pass
    return None


def get_status_color(status):
    if status == "playing":
        return (80, 220, 120)  # 绿色
    elif status == "online":
        return (80, 180, 255)  # 蓝色
    elif status == "away":
        return (255, 200, 80)  # 橙色
    elif status == "snooze":
        return (180, 180, 180)  # 灰色
    elif status == "busy":
        return (255, 100, 100)  # 红色
    elif status == "offline":
        return (255, 255, 255)  # 白色
    else:
        return (180, 80, 80)


def get_name_color(status):
    if status == "playing":
        return (227, 255, 194)
    elif status == "online":
        return (80, 180, 255)
    elif status == "away":
        return (255, 200, 80)
    elif status == "snooze":
        return (180, 180, 180)
    elif status == "busy":
        return (255, 100, 100)
    elif status == "offline":
        return (220, 220, 220)
    else:
        return (255, 120, 120)


def get_status_text(status):
    if status == "playing":
        return "正在游戏"
    elif status == "online":
        return "在线"
    elif status == "away":
        return "离开"
    elif status == "snooze":
        return "打盹"
    elif status == "busy":
        return "忙碌"
    elif status == "offline":
        return "离线"
    else:
        return "异常"


def get_font_path(font_name):
    fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
    font_path = os.path.join(fonts_dir, font_name)
    if os.path.exists(font_path):
        return font_path
    font_path2 = os.path.join(os.path.dirname(__file__), font_name)
    if os.path.exists(font_path2):
        return font_path2
    return font_name


async def render_steam_list_image(data_dir, user_list, font_path=None):
    # 字体
    if font_path is None:
        font_path = os.path.join(
            os.path.dirname(__file__), "fonts", "NotoSansHans-Regular.otf"
        )
    logger.info(f"[Font] render_steam_list_image 使用字体路径: {font_path}")
    try:
        font_title = ImageFont.truetype(font_path, 28)
        font_name = ImageFont.truetype(font_path, 22)
        font_game = ImageFont.truetype(font_path, 18)
        # 加粗用 Medium
        font_bold_path = font_path.replace("Regular", "Medium")
        if os.path.exists(font_bold_path):
            font_status = ImageFont.truetype(font_bold_path, 16)
        else:
            font_status = ImageFont.truetype(font_path, 16)
        font_small = ImageFont.truetype(font_path, 14)
    except Exception as e:
        logger.warning(f"[Font] 加载字体失败: {e}")
        font_title = font_name = font_game = font_status = font_small = (
            ImageFont.load_default()
        )

    n = len(user_list)
    width = 600
    height = CARD_MARGIN + n * (CARD_HEIGHT + CARD_GAP) + CARD_MARGIN + 50
    img = Image.new("RGBA", (width, height), STEAM_BG_TOP)
    draw = ImageDraw.Draw(img)
    # 渐变背景
    for y in range(height):
        ratio = y / (height - 1)
        r = int(STEAM_BG_TOP[0] * (1 - ratio) + STEAM_BG_BOTTOM[0] * ratio)
        g = int(STEAM_BG_TOP[1] * (1 - ratio) + STEAM_BG_BOTTOM[1] * ratio)
        b = int(STEAM_BG_TOP[2] * (1 - ratio) + STEAM_BG_BOTTOM[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    # 标题
    title = "Steam 玩家状态列表"
    title_bbox = draw.textbbox((0, 0), title, font=font_title)
    draw.text(
        ((width - title_bbox[2] + title_bbox[0]) // 2, 12),
        title,
        font=font_title,
        fill=(255, 255, 255),
    )
    # 卡片
    tasks = [fetch_avatar(u["avatar_url"], data_dir, u["sid"]) for u in user_list]
    avatars = await asyncio.gather(*tasks)
    for idx, user in enumerate(user_list):
        top = CARD_MARGIN + idx * (CARD_HEIGHT + CARD_GAP) + 50
        left = CARD_MARGIN
        # 卡片底
        card = Image.new("RGBA", (width - 2 * CARD_MARGIN, CARD_HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card)
        card_draw.rounded_rectangle(
            (0, 0, width - 2 * CARD_MARGIN, CARD_HEIGHT),
            radius=CARD_RADIUS,
            fill=CARD_BG,
        )
        # 头像（正方形+小圆角）
        avatar = avatars[idx]
        if avatar:
            avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
            mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
            ImageDraw.Draw(mask).rounded_rectangle(
                (0, 0, AVATAR_SIZE, AVATAR_SIZE), radius=AVATAR_RADIUS, fill=255
            )
            card.paste(avatar, (18, (CARD_HEIGHT - AVATAR_SIZE) // 2), mask)
        # 顺序：玩家名（游戏时浅绿色），在线状态/游戏名（深绿色），上次在线/已游玩时间
        name_x = 18 + AVATAR_SIZE + 18
        name_y = 18
        # 玩家名颜色
        if user["status"] == "playing":
            name_color = (227, 255, 194)
        else:
            name_color = get_name_color(user["status"])
        card_draw.text((name_x, name_y), user["name"], font=font_name, fill=name_color)
        # 在线状态/游戏名
        status_y = name_y + 28
        if user["status"] == "playing":
            # 游戏名深绿色
            card_draw.text(
                (name_x, status_y),
                f"正在玩：{user['game']}",
                font=font_game,
                fill=(131, 175, 80),
            )
            # 已游玩时间
            info_y = status_y + 26
            card_draw.text(
                (name_x, info_y),
                f"时长：{user['play_str']}",
                font=font_small,
                fill=(180, 220, 180),
            )
        elif user["status"] in ("online", "away", "snooze", "busy"):
            # 其它在线状态
            card_draw.text(
                (name_x, status_y),
                get_status_text(user["status"]),
                font=font_game,
                fill=get_status_color(user["status"]),
            )
            # 不显示时长
        elif user["status"] == "offline" and user["play_str"]:
            # 离线状态白色
            card_draw.text(
                (name_x, status_y), "离线", font=font_game, fill=(255, 255, 255)
            )
            info_y = status_y + 26
            card_draw.text(
                (name_x, info_y),
                user["play_str"],
                font=font_small,
                fill=(180, 180, 180),
            )
        elif user["status"] == "error":
            card_draw.text(
                (name_x, status_y), "异常", font=font_game, fill=(255, 120, 120)
            )
            info_y = status_y + 26
            card_draw.text(
                (name_x, info_y),
                user["play_str"],
                font=font_small,
                fill=(255, 120, 120),
            )
        img.alpha_composite(card, (left, top))
    # 统计
    stat_str = f"在线: {sum(1 for u in user_list if u['status'] == 'online' or u['status'] == 'playing')} / 总数: {len(user_list)}"
    draw.text(
        (width - 220, height - 36), stat_str, font=font_small, fill=(180, 220, 255)
    )
    # 输出
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
