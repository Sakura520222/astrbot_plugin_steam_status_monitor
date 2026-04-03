import asyncio
import io
import logging
import os

import httpx
from PIL import Image, ImageDraw, ImageFont

from .steam_list_render import (
    fetch_avatar,
    get_font_path,
    get_name_color,
    get_status_color,
    get_status_text,
)

logger = logging.getLogger(__name__)

# 渲染精度倍率（2x = 高清输出）
SCALE = 2

# Steam 客户端配色
BG_COLOR = (27, 40, 56)  # #1b2838
HEADER_BG = (31, 46, 63)  # #1f2e3f
SECTION_LINE = (46, 63, 82)  # #2e3f52 分组标题下方分割线
ROW_LINE = (36, 50, 66)  # #243242 行间分割线

# 分组标题颜色
HEADER_COLOR_PLAYING = (76, 255, 176)  # #4CFFB0
HEADER_COLOR_ONLINE = (102, 192, 244)  # #66C0F4
HEADER_COLOR_OFFLINE = (143, 152, 160)  # #8F98A0

# 布局常量（逻辑像素，实际渲染时乘以 SCALE）
_IMG_WIDTH = 480
_PADDING_LEFT = 16
_PADDING_RIGHT = 16
_AVATAR_SIZE = 36
_AVATAR_RADIUS = 6
_ENTRY_MIN_HEIGHT = 54
_NAME_LINE_H = 20
_STATUS_LINE_H = 18
_TEXT_LEFT_OFFSET = _AVATAR_SIZE + 10

# 横版封面
_COVER_W = 120
_COVER_H = 45
_COVER_RADIUS = 6
_COVER_GAP = 10

# 有封面时文字最大宽度
_TEXT_MAX_WIDTH_COVER = (
    _IMG_WIDTH
    - _PADDING_LEFT
    - _TEXT_LEFT_OFFSET
    - _COVER_GAP
    - _COVER_W
    - _PADDING_RIGHT
)
# 无封面时文字最大宽度
_TEXT_MAX_WIDTH_FULL = _IMG_WIDTH - _PADDING_LEFT - _TEXT_LEFT_OFFSET - _PADDING_RIGHT

_HEADER_HEIGHT = 32
_TITLE_HEIGHT = 44
_FOOTER_HEIGHT = 32
_SECTION_GAP = 6
_ENTRY_PAD_Y = 6

# 缩放后的常量
S = SCALE
IMG_WIDTH = _IMG_WIDTH * S
PADDING_LEFT = _PADDING_LEFT * S
PADDING_RIGHT = _PADDING_RIGHT * S
AVATAR_SIZE = _AVATAR_SIZE * S
AVATAR_RADIUS = _AVATAR_RADIUS * S
ENTRY_MIN_HEIGHT = _ENTRY_MIN_HEIGHT * S
NAME_LINE_H = _NAME_LINE_H * S
STATUS_LINE_H = _STATUS_LINE_H * S
TEXT_LEFT_OFFSET = _TEXT_LEFT_OFFSET * S
TEXT_MAX_WIDTH_COVER = _TEXT_MAX_WIDTH_COVER * S
TEXT_MAX_WIDTH_FULL = _TEXT_MAX_WIDTH_FULL * S
COVER_W = _COVER_W * S
COVER_H = _COVER_H * S
COVER_RADIUS = _COVER_RADIUS * S
COVER_GAP = _COVER_GAP * S
HEADER_HEIGHT = _HEADER_HEIGHT * S
TITLE_HEIGHT = _TITLE_HEIGHT * S
FOOTER_HEIGHT = _FOOTER_HEIGHT * S
SECTION_GAP = _SECTION_GAP * S
ENTRY_PAD_Y = _ENTRY_PAD_Y * S


async def fetch_capsule_cover(data_dir, gameid):
    """获取游戏横版封面图（capsule），带重试和备选URL，返回PIL Image或None"""
    if not gameid:
        return None
    capsule_dir = os.path.join(data_dir, "capsules")
    os.makedirs(capsule_dir, exist_ok=True)
    path = os.path.join(capsule_dir, f"{gameid}.jpg")
    # 缓存读取
    if os.path.exists(path):
        try:
            return Image.open(path).convert("RGBA")
        except Exception:
            # 缓存文件损坏，删除后重新下载
            try:
                os.remove(path)
            except Exception:
                pass
    # 多个备选URL（按优先级尝试）
    urls = [
        f"https://cdn.akamai.steamstatic.com/steam/apps/{gameid}/capsule_231x87.jpg",
        f"https://cdn.akamai.steamstatic.com/steam/apps/{gameid}/header.jpg",
        f"https://cdn.akamai.steamstatic.com/steam/apps/{gameid}/capsule_184x69.jpg",
    ]
    for url in urls:
        for attempt in range(3):
            try:
                async with httpx.AsyncClient(
                    timeout=15, follow_redirects=True
                ) as client:
                    resp = await client.get(url)
                    if resp.status_code == 200 and len(resp.content) > 500:
                        with open(path, "wb") as f:
                            f.write(resp.content)
                        logger.info(
                            f"[capsule] 下载成功 {gameid} (attempt {attempt + 1}): {url}"
                        )
                        return Image.open(io.BytesIO(resp.content)).convert("RGBA")
            except Exception as e:
                logger.debug(
                    f"[capsule] 下载异常 {gameid} (attempt {attempt + 1}): {e}"
                )
            if attempt < 2:
                await asyncio.sleep(0.5 * (attempt + 1))
    logger.warning(f"[capsule] 所有URL尝试均失败: {gameid}")
    return None


def _text_wrap(draw, text, font, max_width):
    """逐字符自动换行，返回行列表"""
    if not text:
        return [""]
    lines = []
    line = ""
    for char in text:
        bbox = draw.textbbox((0, 0), line + char, font=font)
        width = bbox[2] - bbox[0]
        if width <= max_width:
            line += char
        else:
            if line:
                lines.append(line)
            line = char
    if line:
        lines.append(line)
    return lines


def _get_status_line(user):
    """获取用户状态行文字"""
    if user["status"] == "playing":
        return f"正在玩 {user['game']}"
    elif user["status"] == "error":
        return "获取失败"
    elif user["status"] == "offline":
        if user.get("play_str"):
            return user["play_str"]
        return "离线"
    else:
        return get_status_text(user["status"])


def _get_status_line_color(user):
    """获取状态行颜色"""
    if user["status"] == "playing":
        return (131, 175, 80)
    elif user["status"] == "error":
        return (255, 120, 120)
    elif user["status"] == "offline":
        return (140, 145, 155)
    else:
        return get_status_color(user["status"])


def _has_cover(user):
    """该用户是否有游戏封面"""
    return user["status"] == "playing" and user.get("gameid")


def _calc_entry_height(draw, user, font_name, font_status):
    """计算单行高度（考虑自动换行和封面）"""
    has_cv = _has_cover(user)
    max_w = TEXT_MAX_WIDTH_COVER if has_cv else TEXT_MAX_WIDTH_FULL
    name_lines = _text_wrap(draw, user["name"], font_name, max_w)
    status_text = _get_status_line(user)
    status_lines = _text_wrap(draw, status_text, font_status, max_w)
    h = ENTRY_PAD_Y
    h += len(name_lines) * NAME_LINE_H
    h += len(status_lines) * STATUS_LINE_H
    h += ENTRY_PAD_Y
    return max(h, ENTRY_MIN_HEIGHT), name_lines, status_lines


def _draw_rounded_cover(img, cover, x, y, w, h, radius):
    """在img上绘制圆角封面"""
    cover_resized = cover.resize((w, h), Image.LANCZOS)
    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, w, h), radius=radius, fill=255)
    img.paste(cover_resized, (x, y), mask)


async def render_steam_friends_image(data_dir, user_list, font_path=None):
    """渲染Steam好友列表样式图片，返回PNG bytes（2x高清）"""
    # 字体加载（字号乘以SCALE）
    if font_path is None:
        font_path = get_font_path("NotoSansHans-Regular.otf")
    try:
        font_title = ImageFont.truetype(font_path, 18 * S)
        font_name = ImageFont.truetype(font_path, 16 * S)
        font_status = ImageFont.truetype(font_path, 13 * S)
        font_header = ImageFont.truetype(font_path, 15 * S)
        font_footer = ImageFont.truetype(font_path, 12 * S)
        # 尝试加载加粗字体用于标题
        font_bold_path = font_path.replace("Regular", "Medium")
        if os.path.exists(font_bold_path):
            font_header = ImageFont.truetype(font_bold_path, 15 * S)
    except Exception as e:
        logger.warning(f"[Font] 加载字体失败: {e}")
        font_title = font_name = font_status = font_header = font_footer = (
            ImageFont.load_default()
        )

    # 空状态
    if not user_list:
        h = 150 * S
        img = Image.new("RGB", (IMG_WIDTH, h), BG_COLOR)
        draw = ImageDraw.Draw(img)
        title = "Steam 好友列表"
        bbox = draw.textbbox((0, 0), title, font=font_title)
        draw.text(
            ((IMG_WIDTH - bbox[2] + bbox[0]) // 2, 12 * S),
            title,
            font=font_title,
            fill=(255, 255, 255),
        )
        empty_text = "暂无绑定的 Steam 用户"
        bbox2 = draw.textbbox((0, 0), empty_text, font=font_status)
        draw.text(
            ((IMG_WIDTH - bbox2[2] + bbox2[0]) // 2, 70 * S),
            empty_text,
            font=font_status,
            fill=(150, 155, 165),
        )
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    # 按状态分组
    groups = {
        "playing": [],
        "online": [],
        "offline": [],
    }
    for u in user_list:
        if u["status"] == "playing":
            groups["playing"].append(u)
        elif u["status"] in ("online", "away", "snooze", "busy"):
            groups["online"].append(u)
        else:
            groups["offline"].append(u)

    # 预计算每行高度（需要draw来测量文字）
    dummy = Image.new("RGB", (10, 10))
    dummy_draw = ImageDraw.Draw(dummy)

    sections = []
    group_meta = [
        ("playing", "游戏中", HEADER_COLOR_PLAYING),
        ("online", "在线", HEADER_COLOR_ONLINE),
        ("offline", "离线", HEADER_COLOR_OFFLINE),
    ]
    for key, label, color in group_meta:
        users = groups[key]
        if not users:
            continue
        entries = []
        for u in users:
            h, name_lines, status_lines = _calc_entry_height(
                dummy_draw, u, font_name, font_status
            )
            entries.append((u, h, name_lines, status_lines))
        sections.append((label, color, entries))

    # 计算总高度
    total_height = TITLE_HEIGHT
    for label, color, entries in sections:
        total_height += HEADER_HEIGHT + SECTION_GAP
        for u, h, nl, sl in entries:
            total_height += h
    total_height += FOOTER_HEIGHT

    # 创建画布
    img = Image.new("RGBA", (IMG_WIDTH, total_height), BG_COLOR + (255,))
    draw = ImageDraw.Draw(img)

    # 标题
    title_text = "Steam 好友列表"
    title_bbox = draw.textbbox((0, 0), title_text, font=font_title)
    draw.text(
        ((IMG_WIDTH - title_bbox[2] + title_bbox[0]) // 2, 12 * S),
        title_text,
        font=font_title,
        fill=(255, 255, 255),
    )

    # 并发获取头像和封面
    avatar_tasks = [
        fetch_avatar(u["avatar_url"], data_dir, u["sid"]) for u in user_list
    ]
    cover_tasks = [fetch_capsule_cover(data_dir, u.get("gameid")) for u in user_list]
    all_avatars, all_covers = await asyncio.gather(
        asyncio.gather(*avatar_tasks),
        asyncio.gather(*cover_tasks),
    )
    avatar_map = {u["sid"]: all_avatars[i] for i, u in enumerate(user_list)}
    cover_map = {u["sid"]: all_covers[i] for i, u in enumerate(user_list)}

    y = TITLE_HEIGHT

    for label, color, entries in sections:
        # 分组标题背景
        draw.rectangle(
            [(0, y), (IMG_WIDTH, y + HEADER_HEIGHT)],
            fill=HEADER_BG,
        )
        # 分组标题文字
        count = len(entries)
        draw.text(
            (PADDING_LEFT, y + (HEADER_HEIGHT - 15 * S) // 2),
            f"{label} ({count})",
            font=font_header,
            fill=color,
        )
        y += HEADER_HEIGHT
        # 分割线
        draw.line([(0, y), (IMG_WIDTH, y)], fill=SECTION_LINE, width=S)
        y += SECTION_GAP

        for user, entry_h, name_lines, status_lines in entries:
            has_cv = _has_cover(user)

            # 横版封面（右侧）
            if has_cv:
                cover_img = cover_map.get(user["sid"])
                if cover_img:
                    cover_x = IMG_WIDTH - PADDING_RIGHT - COVER_W
                    cover_y = y + (entry_h - COVER_H) // 2
                    _draw_rounded_cover(
                        img, cover_img, cover_x, cover_y, COVER_W, COVER_H, COVER_RADIUS
                    )
                    draw = ImageDraw.Draw(img)

            # 头像
            avatar = avatar_map.get(user["sid"])
            if avatar:
                avatar = avatar.resize((AVATAR_SIZE, AVATAR_SIZE), Image.LANCZOS)
                mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
                ImageDraw.Draw(mask).rounded_rectangle(
                    (0, 0, AVATAR_SIZE, AVATAR_SIZE),
                    radius=AVATAR_RADIUS,
                    fill=255,
                )
                avatar_rgba = avatar.convert("RGBA")
                avatar_y = y + (entry_h - AVATAR_SIZE) // 2
                img.paste(avatar_rgba, (PADDING_LEFT, avatar_y), mask)
                draw = ImageDraw.Draw(img)

            # 文字最大宽度
            max_w = TEXT_MAX_WIDTH_COVER if has_cv else TEXT_MAX_WIDTH_FULL
            text_x = PADDING_LEFT + TEXT_LEFT_OFFSET

            # 玩家名
            name_color = get_name_color(user["status"])
            ny = y + ENTRY_PAD_Y
            for line in name_lines:
                draw.text((text_x, ny), line, font=font_name, fill=name_color)
                ny += NAME_LINE_H

            # 状态行
            status_color = _get_status_line_color(user)
            for line in status_lines:
                draw.text((text_x, ny), line, font=font_status, fill=status_color)
                ny += STATUS_LINE_H

            # 行间分割线
            y += entry_h
            draw.line(
                [(PADDING_LEFT, y), (IMG_WIDTH - PADDING_RIGHT, y)],
                fill=ROW_LINE,
                width=S,
            )

    # 底部统计
    online_count = sum(
        1
        for u in user_list
        if u["status"] in ("playing", "online", "away", "snooze", "busy")
    )
    total_count = len(user_list)
    stat_text = f"在线 {online_count} / 总数 {total_count}"
    draw.text(
        (PADDING_LEFT, total_height - FOOTER_HEIGHT + 8 * S),
        stat_text,
        font=font_footer,
        fill=(150, 170, 190),
    )

    # 输出
    img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
