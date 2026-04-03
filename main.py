import asyncio
import io
import json
import os
import random
import shutil
import tempfile
import time
import traceback

import httpx
import requests  # 新增导入
from PIL import Image as PILImage

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, MessageChain, filter
from astrbot.api.message_components import Image, Plain  # 确保已导入 Image
from astrbot.api.star import Context, Star, register

from .achievement_monitor import AchievementMonitor
from .game_end_render import render_game_end  # 新增导入
from .game_start_render import render_game_start  # 新增导入
from .openbox import handle_openbox  # 新增导入
from .steam_list import handle_steam_list  # 新增导入
from .superpower_util import get_daily_superpower, load_abilities  # 新增导入


@register(
    "steam_status_monitor_V2",
    "Maoer",
    "Steam状态监控插件V2版",
    "2.1.6",
    "https://github.com/Maoer233/astrbot_plugin_steam_status_monitor",
)
class SteamStatusMonitorV2(Star):
    def _get_group_data_path(self, group_id, key):
        """获取分群数据文件路径"""
        return os.path.join(self.data_dir, f"group_{group_id}_{key}.json")

    def _load_persistent_data(self):
        # 分群加载各群的状态数据
        for group_id in self.group_steam_ids:
            try:
                path = self._get_group_data_path(group_id, "states")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self.group_last_states[group_id] = json.load(f)
            except Exception as e:
                logger.warning(
                    f"加载 group_last_states 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "start_play_times")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self.group_start_play_times[group_id] = json.load(f)
            except Exception as e:
                logger.warning(
                    f"加载 group_start_play_times 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "last_quit_times")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self.group_last_quit_times[group_id] = json.load(f)
            except Exception as e:
                logger.warning(
                    f"加载 group_last_quit_times 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "pending_logs")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self.group_pending_logs[group_id] = json.load(f)
            except Exception as e:
                logger.warning(
                    f"加载 group_pending_logs 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "pending_quit")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self.group_pending_quit[group_id] = json.load(f)
            except Exception as e:
                logger.warning(
                    f"加载 group_pending_quit 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "recent_games")
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        self.group_recent_games[group_id] = json.load(f)
            except Exception as e:
                logger.warning(
                    f"加载 group_recent_games 失败: {e} (group_id={group_id})"
                )

    def _save_persistent_data(self):
        # 分群保存各群的状态数据
        for group_id in self.group_steam_ids:
            try:
                path = self._get_group_data_path(group_id, "states")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        self.group_last_states.get(group_id, {}), f, ensure_ascii=False
                    )
            except Exception as e:
                logger.warning(
                    f"保存 group_last_states 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "start_play_times")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        self.group_start_play_times.get(group_id, {}),
                        f,
                        ensure_ascii=False,
                    )
            except Exception as e:
                logger.warning(
                    f"保存 group_start_play_times 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "last_quit_times")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        self.group_last_quit_times.get(group_id, {}),
                        f,
                        ensure_ascii=False,
                    )
            except Exception as e:
                logger.warning(
                    f"保存 group_last_quit_times 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "pending_logs")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        self.group_pending_logs.get(group_id, {}), f, ensure_ascii=False
                    )
            except Exception as e:
                logger.warning(
                    f"保存 group_pending_logs 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "pending_quit")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        self.group_pending_quit.get(group_id, {}), f, ensure_ascii=False
                    )
            except Exception as e:
                logger.warning(
                    f"保存 group_pending_quit 失败: {e} (group_id={group_id})"
                )
            try:
                path = self._get_group_data_path(group_id, "recent_games")
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(
                        self.group_recent_games.get(group_id, []), f, ensure_ascii=False
                    )
            except Exception as e:
                logger.warning(
                    f"保存 group_recent_games 失败: {e} (group_id={group_id})"
                )

    def _load_notify_session(self):
        path = os.path.join(self.data_dir, "notify_sessions.json")
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.notify_sessions = json.load(f)
                logger.info(
                    f"[SteamStatusMonitor] 已加载 notify_sessions: {self.notify_sessions}"
                )
            except Exception as e:
                logger.warning(f"加载 notify_sessions 失败: {e}")
        else:
            self.notify_sessions = {}

    def _save_notify_session(self):
        if hasattr(self, "notify_sessions"):
            path = os.path.join(self.data_dir, "notify_sessions.json")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(self.notify_sessions, f, ensure_ascii=False)
                logger.info(
                    f"[SteamStatusMonitor] 已保存 notify_sessions: {self.notify_sessions}"
                )
            except Exception as e:
                logger.warning(f"保存 notify_sessions 失败: {e}")

    def _ensure_fonts(self):
        """检测插件fonts目录是否有NotoSansHans系列字体，有则复制到缓存目录并缓存路径"""
        plugin_fonts_dir = os.path.join(os.path.dirname(__file__), "fonts")
        cache_fonts_dir = os.path.join("data", "steam_status_monitor", "fonts")
        os.makedirs(plugin_fonts_dir, exist_ok=True)
        os.makedirs(cache_fonts_dir, exist_ok=True)
        font_candidates = ["NotoSansHans-Regular.otf", "NotoSansHans-Medium.otf"]
        self.font_paths = {}
        for font_name in font_candidates:
            plugin_font_path = os.path.join(plugin_fonts_dir, font_name)
            cache_font_path = os.path.join(cache_fonts_dir, font_name)
            if os.path.exists(plugin_font_path):
                shutil.copy(plugin_font_path, cache_font_path)
                self.font_paths[font_name] = cache_font_path
            elif os.path.exists(cache_font_path):
                self.font_paths[font_name] = cache_font_path
            else:
                self.font_paths[font_name] = None
        # 详细日志
        for font_name in font_candidates:
            logger.info(f"[Font] {font_name} 路径: {self.font_paths.get(font_name)}")
        if not all(self.font_paths.values()):
            logger.warning("[Font] 未检测到全部NotoSansHans字体，渲染可能会出现乱码！")

    def get_font_path(self, font_name=None, bold=False):
        """优先返回缓存fonts目录下NotoSansHans字体路径"""
        if not font_name:
            font_name = "NotoSansHans-Regular.otf"
        if bold:
            font_name = "NotoSansHans-Medium.otf"
        return self.font_paths.get(font_name) or font_name

    def _get_groups_file_path(self):
        """获取 steam_groups.json 文件路径"""
        return os.path.join(self.data_dir, "steam_groups.json")

    def _load_group_steam_ids(self):
        """从 steam_groups.json 加载所有群的 SteamID 列表"""
        path = self._get_groups_file_path()
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    self.group_steam_ids = json.load(f)
                logger.info(
                    f"[SteamStatusMonitor] 已加载 steam_groups.json: {self.group_steam_ids}"
                )
            except Exception as e:
                logger.warning(f"加载 steam_groups.json 失败: {e}")
        else:
            self.group_steam_ids = {}

    def _save_group_steam_ids(self):
        """保存所有群的 SteamID 列表到 steam_groups.json"""
        path = self._get_groups_file_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(self.group_steam_ids, f, ensure_ascii=False, indent=2)
            logger.info(
                f"[SteamStatusMonitor] 已保存 steam_groups.json: {self.group_steam_ids}"
            )
        except Exception as e:
            logger.warning(f"保存 steam_groups.json 失败: {e}")

    def __init__(self, context: Context, config=None):
        super().__init__(context)
        self._ensure_fonts()  # 插件启动时自动检测/下载字体
        self.context = context
        # 分群管理：所有状态数据均以 group_id 为 key
        self.group_steam_ids = {}  # {group_id: [steamid, ...]}
        self.group_last_states = {}  # {group_id: {steamid: status}}
        self.group_start_play_times = {}  # {group_id: {steamid: start_time}}
        self.group_last_quit_times = {}  # {group_id: {steamid: {gameid: quit_time}}}
        self.group_pending_logs = {}  # {group_id: {steamid: {gameid: log_dict}}}
        self.group_recent_games = {}  # {group_id: [gameid, ...]}
        self.group_pending_quit = {}  # {group_id: {steamid: {gameid: {quit_time, name, game_name, duration_min, start_time, notified}}}}
        # 超能力缓存和能力列表
        self._superpower_cache = {}  # {(steamid, date): superpower}
        self._abilities = None
        self._abilities_path = os.path.join(os.path.dirname(__file__), "abilities.txt")
        self._game_name_cache = {}  # 修复: 游戏名缓存，防止 AttributeError
        # 统一使用 AstrBot 配置系统
        self.config = config or {}
        # 兼容旧逻辑，若 config 为空则尝试读取 config.json（可选，建议后续移除）
        if not self.config:
            try:
                config_path = os.path.join(os.path.dirname(__file__), "config.json")
                with open(config_path, encoding="utf-8") as f:
                    self.config = json.load(f)
            except Exception as e:
                logger.error(f"steam_status_monitor 配置读取失败: {e}")
                self.config = {}
        # 旧配置迁移：如存在 steam_ids（未分群），迁移到 group_steam_ids['default']
        if "steam_ids" in self.config and "group_steam_ids" not in self.config:
            steam_ids = self.config.get("steam_ids", [])
            if isinstance(steam_ids, str):
                steam_ids = [x.strip() for x in steam_ids.split(",") if x.strip()]
            self.config["group_steam_ids"] = {"default": steam_ids}
            self.config.pop("steam_ids", None)
            logger.info("已自动迁移旧 steam_ids 配置到 group_steam_ids['default']")
        # 读取配置项，提供默认值
        self.API_KEY = self.config.get("steam_api_key", "")
        self.group_steam_ids = self.config.get("group_steam_ids", {})
        self.POLL_INTERVAL = self.config.get("poll_interval_sec", 10)
        self.RETRY_TIMES = self.config.get("retry_times", 3)
        self.max_group_size = 20
        self.GROUP_ID = None  # 当前操作群号，指令时动态赋值
        self.poll_interval_sec = self.config.get(
            "poll_interval_sec", 60
        )  # 在线/24小时内
        self.poll_interval_mid_sec = self.config.get(
            "poll_interval_mid_sec", 600
        )  # 10分钟
        self.poll_interval_long_sec = self.config.get(
            "poll_interval_long_sec", 1800
        )  # 30分钟
        self.next_poll_time = {}  # {group_id: {steamid: next_time}}
        self.detailed_poll_log = self.config.get("detailed_poll_log", True)
        # 数据持久化目录
        self.data_dir = os.path.join("data", "steam_status_monitor")
        os.makedirs(self.data_dir, exist_ok=True)
        self._load_group_steam_ids()  # 新增：优先从 steam_groups.json 加载
        self._load_persistent_data()
        self._load_notify_session()
        # 成就监控
        self.achievement_monitor = AchievementMonitor(self.data_dir)
        self.max_achievement_notifications = self.config.get(
            "max_achievement_notifications", 5
        )
        self.achievement_poll_tasks = {}  # {(group_id, sid, gameid): asyncio.Task}
        self.achievement_snapshots = {}  # {(group_id, sid, gameid): [成就列表]}
        self.achievement_blacklist = set()  # 新增：成就查询黑名单
        self.achievement_fail_count = {}  # 新增：成就查询失败计数
        # --- 新增：重启后自动推送 ---
        self.running_groups = set()  # 正在运行的群号集合
        self.group_monitor_enabled = {}  # {group_id: bool} 监控开关
        self.group_achievement_enabled = {}  # {group_id: bool} 成就推送开关
        # --- 新增：重启后自动恢复所有群的轮询 ---
        if (
            hasattr(self, "notify_sessions")
            and self.notify_sessions
            and self.API_KEY
            and self.group_steam_ids
        ):
            logger.info(
                f"[SteamStatusMonitor] 检测到 notify_sessions={self.notify_sessions}，自动启动监控轮询"
            )
            for group_id in self.notify_sessions:
                if group_id in self.group_steam_ids:
                    self.running_groups.add(group_id)
        # --- 新增：全局日志收集与统一输出 ---
        self._last_round_logs = []  # [(group_id, logstr)]
        asyncio.create_task(self.global_poll_and_log_loop())
        asyncio.create_task(self.init_poll_time_once())
        # SGDB API Key 可在 https://www.steamgriddb.com/profile/preferences/api 获取
        self.SGDB_API_KEY = self.config.get("sgdb_api_key", "")

    async def init_poll_time_once(self):
        """插件启动后10秒内进行一次全员初始化轮询，设置每个SteamID的next_poll_time，并输出一次初始日志"""
        await asyncio.sleep(10)
        all_logs = []
        for group_id in self.group_steam_ids:
            steam_ids = self.group_steam_ids[group_id]
            group_lines = []
            for sid in steam_ids:
                msg = await self.check_status_change(group_id, single_sid=sid)
                if msg:
                    group_lines.append(msg)
            if group_lines:
                all_logs.append(f"群{group_id}：\n" + "\n".join(group_lines))
        if all_logs:
            logger.info(
                "====== Steam状态监控初始化日志 ======\n"
                + "\n".join(all_logs)
                + "\n====================================================="
            )

    async def global_poll_and_log_loop(self):
        """全局定时并发查询所有群Steam状态，按动态间隔判断是否需要查询，40秒统一输出日志"""
        while True:
            # 计算距离下一个整分钟0秒的秒数
            now = time.time()
            next_minute = (int(now) // 60 + 1) * 60
            await asyncio.sleep(max(0, next_minute - now))
            # 0秒：遍历所有群和SteamID，按动态间隔判断是否需要查询
            group_ids = list(self.group_steam_ids.keys())
            poll_tasks = []
            for group_id in group_ids:
                if not self.group_monitor_enabled.get(group_id, True):
                    continue
                steam_ids = self.group_steam_ids.get(group_id, [])
                next_poll = self.next_poll_time.setdefault(group_id, {})
                now2 = time.time()
                # 只查询到点的SteamID
                sids_to_query = [
                    sid for sid in steam_ids if now2 >= next_poll.get(sid, 0)
                ]
                if not sids_to_query:
                    continue

                async def query_one_group(gid, sids):
                    round_msg_lines = []
                    tasks = [
                        self.check_status_change(gid, single_sid=sid) for sid in sids
                    ]
                    if tasks:
                        results = await asyncio.gather(*tasks)
                        for msg in results:
                            if msg:
                                round_msg_lines.append(msg)
                    if round_msg_lines:
                        self._last_round_logs.append((gid, "\n".join(round_msg_lines)))

                poll_tasks.append(query_one_group(group_id, sids_to_query))
            if poll_tasks:
                await asyncio.gather(*poll_tasks)
            # 40秒统一输出日志
            await asyncio.sleep(40)
            if self._last_round_logs:
                if self.detailed_poll_log:
                    all_logs = []
                    for group_id, logstr in self._last_round_logs:
                        all_logs.append(f"群{group_id}：\n" + logstr)
                    logger.info(
                        "====== Steam状态监控轮询日志 ======\n"
                        + "\n".join(all_logs)
                        + "\n====================================================="
                    )
                else:
                    logger.info("周期轮询成功")
                self._last_round_logs.clear()

    async def terminate(self):
        """插件被卸载/停用时自动保存持久化数据"""
        self._save_persistent_data()
        # 停止所有成就定时任务
        for task in self.achievement_poll_tasks.values():
            task.cancel()
        self.achievement_poll_tasks.clear()
        self.achievement_snapshots.clear()

    def crop_image_auto(self, img_path_or_bytes, bg_color=(20, 26, 33), threshold=25):
        """
        自动裁剪图片内容区域，去除边缘与 bg_color 相近的空白。
        支持本地路径、bytes、URL、PIL.Image。
        """
        import numpy as np

        # 新增：如果已经是PIL.Image对象，直接用
        if isinstance(img_path_or_bytes, PILImage.Image):
            img = img_path_or_bytes.convert("RGB")
        elif isinstance(img_path_or_bytes, str) and (
            img_path_or_bytes.startswith("http://")
            or img_path_or_bytes.startswith("https://")
        ):
            resp = requests.get(img_path_or_bytes)
            img = PILImage.open(io.BytesIO(resp.content)).convert("RGB")
        elif isinstance(img_path_or_bytes, bytes):
            img = PILImage.open(io.BytesIO(img_path_or_bytes)).convert("RGB")
        else:
            img = PILImage.open(img_path_or_bytes).convert("RGB")
        arr = np.array(img)
        # 自动检测背景色（取四角平均色）
        h, w, _ = arr.shape
        corners = [arr[0, 0], arr[0, -1], arr[-1, 0], arr[-1, -1]]
        avg_bg = np.mean(corners, axis=0)
        # 计算每个像素与背景色的距离
        diff = np.abs(arr - avg_bg).sum(axis=2)
        mask = diff > threshold
        coords = np.argwhere(mask)
        if coords.size == 0:
            return img
        y0, x0 = coords.min(axis=0)
        y1, x1 = coords.max(axis=0) + 1
        # 防止裁剪过度，留出2px边距
        y0 = max(y0 - 0, 0)
        x0 = max(x0 - 0, 0)
        y1 = min(y1 - 0, arr.shape[0])
        x1 = min(x1 - 0, arr.shape[1])
        cropped = img.crop((x0, y0, x1, y1))
        return cropped

    async def fetch_player_status(self, steam_id, retry=None):
        """拉取单个玩家的 Steam 状态，失败自动重试多次并指数退避"""
        url = (
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
            f"?key={self.API_KEY}&steamids={steam_id}"
        )
        delay = 1
        retry = retry if retry is not None else self.RETRY_TIMES
        for attempt in range(retry):
            async with httpx.AsyncClient(timeout=15) as client:
                try:
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        raise Exception(f"HTTP {resp.status_code}")
                    try:
                        data = resp.json()
                    except Exception as je:
                        raise Exception(f"JSON解析失败: {je}")
                    if (
                        not data.get("response")
                        or not data["response"].get("players")
                        or not data["response"]["players"]
                    ):
                        raise Exception("响应中无玩家数据")
                    player = data["response"].get("players")[0]
                    # 返回更多字段，包括头像
                    return {
                        "name": player.get("personaname"),
                        "gameid": player.get("gameid"),
                        "lastlogoff": player.get("lastlogoff"),
                        "gameextrainfo": player.get("gameextrainfo"),
                        "personastate": player.get("personastate", 0),
                        "avatarfull": player.get("avatarfull"),
                        "avatar": player.get("avatar"),
                    }
                except Exception as e:
                    logger.warning(
                        f"拉取 Steam 状态失败: {e} (SteamID: {steam_id}, 第{attempt + 1}次重试)"
                    )
                    if attempt < retry - 1:
                        await asyncio.sleep(delay)
                        delay *= 2
        logger.error(f"SteamID {steam_id} 状态获取失败，已重试{retry}次")
        return None

    async def get_chinese_game_name(self, gameid, fallback_name=None):
        """
        优先通过 Steam 商店API获取游戏中文名（l=schinese），若无则返回英文名（l=en），最后才返回 fallback_name 或“未知游戏”
        """
        if not gameid:
            return fallback_name or "未知游戏"
        gid = str(gameid)
        if gid in self._game_name_cache:
            return self._game_name_cache[gid]
        # 优先查中文名（l=schinese），再查英文名（l=en）
        url_zh = (
            f"https://store.steampowered.com/api/appdetails?appids={gid}&l=schinese"
        )
        url_en = f"https://store.steampowered.com/api/appdetails?appids={gid}&l=en"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # 查中文名
                resp_zh = await client.get(url_zh)
                data_zh = resp_zh.json()
                info_zh = data_zh.get(gid, {}).get("data", {})
                name_zh = info_zh.get("name")
                if name_zh:
                    self._game_name_cache[gid] = name_zh
                    return name_zh
                # 查英文名
                resp_en = await client.get(url_en)
                data_en = resp_en.json()
                info_en = data_en.get(gid, {}).get("data", {})
                name_en = info_en.get("name")
                if name_en:
                    self._game_name_cache[gid] = name_en
                    return name_en
        except Exception as e:
            logger.warning(f"获取游戏名失败: {e} (gameid={gid})")
        # 不缓存 fallback，让下次还能重试
        return fallback_name or "未知游戏"

    async def get_game_cover_url(self, gameid, force_update=False):
        """
        获取游戏封面图本地路径（优先小图，失败自动尝试日文/英文区域），自动缓存到本地，定期刷新
        force_update: True 时强制重新下载覆盖本地
        """
        if not gameid:
            return None
        gid = str(gameid)
        cover_dir = os.path.join(self.data_dir, "covers")
        os.makedirs(cover_dir, exist_ok=True)
        cover_path = os.path.join(cover_dir, f"{gid}.jpg")
        # 定期刷新周期（秒），如30天
        refresh_interval = 30 * 24 * 3600
        need_refresh = force_update
        # 判断本地缓存是否需要刷新
        if os.path.exists(cover_path) and not force_update:
            last_mtime = os.path.getmtime(cover_path)
            if time.time() - last_mtime > refresh_interval:
                need_refresh = True
            else:
                return cover_path
        # 先查缓存
        if (
            not need_refresh
            and hasattr(self, "_game_cover_cache")
            and gid in self._game_cover_cache
        ):
            return self._game_cover_cache[gid]
        # 多区域尝试
        lang_list = ["schinese", "japanese", "en"]
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for lang in lang_list:
                    url = f"https://store.steampowered.com/api/appdetails?appids={gid}&l={lang}"
                    resp = await client.get(url)
                    if resp.status_code != 200:
                        logger.warning(
                            f"获取游戏封面API失败: HTTP {resp.status_code} (gameid={gid}, lang={lang})"
                        )
                        continue
                    data = resp.json()
                    info = data.get(gid, {}).get("data", {})
                    header_img = info.get("header_image")
                    if not header_img:
                        logger.info(
                            f"未找到游戏封面字段 header_image (gameid={gid}, lang={lang})，API返回data: {repr(info)[:200]}"
                        )
                        continue
                    small_img = header_img.replace("_header.jpg", "_capsule_184x69.jpg")
                    img_resp = await client.get(small_img)
                    if img_resp.status_code == 200:
                        with open(cover_path, "wb") as f:
                            f.write(img_resp.content)
                        return cover_path
                    else:
                        logger.warning(
                            f"封面图片下载失败: HTTP {img_resp.status_code} url={small_img} (gameid={gid}, lang={lang})"
                        )
        except Exception as e:
            logger.warning(f"获取/缓存游戏封面异常: {e} (gameid={gid})")
        # 如果下载失败且本地有旧图，兜底返回旧图
        if os.path.exists(cover_path):
            return cover_path
        return None

    async def achievement_periodic_check(
        self, group_id, sid, gameid, player_name, game_name
    ):
        """每20分钟对比一次成就列表，直到游戏结束，失败多次自动加入黑名单"""
        key = (group_id, sid, gameid)
        try:
            while True:
                await asyncio.sleep(1200)  # 20分钟
                # 黑名单跳过
                if gameid in self.achievement_blacklist:
                    logger.info(f"[成就定时对比] 游戏 {gameid} 已在黑名单，跳过轮询")
                    break
                achievements_a = self.achievement_snapshots.get(key)
                achievements_b = await self.achievement_monitor.get_player_achievements(
                    self.API_KEY, group_id, sid, gameid
                )
                # 新增：当天失败次数统计
                today = time.strftime("%Y-%m-%d")
                fail_key = (gameid, today)
                if achievements_b is None:
                    cnt = self.achievement_fail_count.get(fail_key, 0) + 1
                    self.achievement_fail_count[fail_key] = cnt
                    if cnt >= 10:
                        self.achievement_blacklist.add(gameid)
                        logger.info(
                            f"[成就黑名单] 游戏 {gameid} 当天累计获取失败10次，已加入黑名单"
                        )
                        break
                    continue
                # 修正：补充新成就检测逻辑
                if achievements_a is not None and achievements_b is not None:
                    new_achievements = set(achievements_b) - set(achievements_a)
                    if new_achievements:
                        logger.info(
                            f"[成就定时对比] {player_name} 在 {game_name} 解锁新成就：{', '.join(new_achievements)}"
                        )
                        await self.notify_new_achievements(
                            group_id,
                            sid,
                            player_name,
                            gameid,
                            game_name,
                            new_achievements,
                        )
                        self.achievement_snapshots[key] = list(achievements_b)
                    else:
                        logger.info(
                            f"[成就定时对比] {player_name} 在 {game_name} 未发现新成就"
                        )
        except asyncio.CancelledError:
            logger.info(
                f"[成就定时对比] 任务已取消 group_id={group_id} sid={sid} gameid={gameid}"
            )
        except Exception as e:
            logger.error(
                f"[成就定时对比] group_id={group_id} sid={sid} gameid={gameid} 异常: {e}"
            )

    async def achievement_delayed_final_check(
        self, group_id, sid, gameid, player_name, game_name
    ):
        """游戏结束后延迟5分钟再做一次成就对比，失败多次自动加入黑名单"""
        key = (group_id, sid, gameid)
        await asyncio.sleep(300)  # 5分钟
        # 黑名单跳过
        if gameid in self.achievement_blacklist:
            logger.info(f"[成就结束冗余对比] 游戏 {gameid} 已在黑名单，跳过轮询")
            return
        achievements_a = self.achievement_snapshots.get(key)
        achievements_b = await self.achievement_monitor.get_player_achievements(
            self.API_KEY, group_id, sid, gameid
        )
        today = time.strftime("%Y-%m-%d")
        fail_key = (gameid, today)
        if achievements_b is None:
            cnt = self.achievement_fail_count.get(fail_key, 0) + 1
            self.achievement_fail_count[fail_key] = cnt
            if cnt >= 10:
                self.achievement_blacklist.add(gameid)
                logger.info(
                    f"[成就黑名单] 游戏 {gameid} 当天累计获取失败10次，已加入黑名单"
                )
                return
        if achievements_a is not None and achievements_b is not None:
            new_achievements = set(achievements_b) - set(achievements_a)
            if new_achievements:
                logger.info(
                    f"[成就结束冗余对比] {player_name} 在 {game_name} 解锁新成就：{', '.join(new_achievements)}"
                )
                await self.notify_new_achievements(
                    group_id, sid, player_name, gameid, game_name, new_achievements
                )
            else:
                logger.info(
                    f"[成就结束冗余对比] {player_name} 在 {game_name} 未发现新成就"
                )
        # 清理快照和定时任务
        self.achievement_snapshots.pop(key, None)
        self.achievement_poll_tasks.pop(key, None)
        self.achievement_monitor.clear_game_achievements(group_id, sid, gameid)

    async def notify_new_achievements(
        self, group_id, steamid, player_name, gameid, game_name, new_achievements
    ):
        if not self.group_achievement_enabled.get(group_id, True):
            return
        if not new_achievements or not self.notify_sessions:
            return
        achievements_to_notify = list(new_achievements)[
            : self.max_achievement_notifications
        ]
        extra_count = len(new_achievements) - len(achievements_to_notify)
        # 优先用缓存
        details = self.achievement_monitor.details_cache.get((group_id, gameid))
        if not details:
            try:
                details = await self.achievement_monitor.get_achievement_details(
                    group_id,
                    gameid,
                    lang="schinese",
                    api_key=self.API_KEY,
                    steamid=steamid,
                )
            except Exception as e:
                details = None
                logger.warning(f"获取成就详情失败: {e}")
        # 在渲染前补充 game_name 字段，确保图片顶部能显示游戏名
        if details and game_name:
            for d in details.values():
                d["game_name"] = game_name
        font_path = self.get_font_path("NotoSansHans-Regular.otf")
        if details:
            # 获取已解锁成就集合，API 失败时用快照兜底
            unlocked_set = await self.achievement_monitor.get_player_achievements(
                self.API_KEY, group_id, steamid, gameid
            )
            if not unlocked_set:
                key = (group_id, steamid, gameid)
                unlocked_set = set(self.achievement_snapshots.get(key, []))
            if unlocked_set is None:
                unlocked_set = set()
            try:
                img_bytes = await self.achievement_monitor.render_achievement_image(
                    details,
                    set(achievements_to_notify),
                    player_name=player_name,
                    steamid=steamid,
                    appid=gameid,
                    unlocked_set=unlocked_set,
                    font_path=font_path,
                )
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(img_bytes)
                    tmp_path = tmp.name
                await self.context.send_message(
                    self.notify_sessions[group_id],
                    MessageChain([Image.fromFileSystem(tmp_path)]),
                )
                return
            except Exception as e:
                import traceback

                logger.error(f"成就图片渲染失败: {e}\n{traceback.format_exc()}")
        # 回退文本
        message = f"🎉 {player_name} 在 {game_name} 中解锁了新成就!\n"
        for achievement in achievements_to_notify:
            message += f"• {achievement}\n"
        if extra_count > 0:
            message += f"...以及另外 {extra_count} 个成就"
        try:
            await self.context.send_message(
                self.notify_sessions[group_id], MessageChain([Plain(message)])
            )
        except Exception as e:
            logger.error(f"发送成就通知失败: {e}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam on")
    async def steam_on(self, event: AstrMessageEvent):
        """手动启动Steam状态监控轮询（分群）"""
        group_id = (
            str(event.get_group_id()) if hasattr(event, "get_group_id") else "default"
        )
        self.group_monitor_enabled[group_id] = True
        if not self.API_KEY:
            yield event.plain_result(
                "未配置 Steam API Key，请先在插件配置中填写 steam_api_key。"
            )
            return
        steam_ids = self.group_steam_ids.get(group_id, [])
        if not steam_ids or not any(
            isinstance(x, str) and x.strip() for x in steam_ids
        ):
            yield event.plain_result(
                "未设置监控的 SteamID 列表，请先在插件配置中填写 steam_ids，"
                "或使用 /steam addid [SteamID] 添加要监控的玩家。"
            )
            return
        if group_id in self.running_groups:
            yield event.plain_result("本群Steam监控已在运行。")
            return
        self.running_groups.add(group_id)
        if not hasattr(self, "notify_sessions"):
            self.notify_sessions = {}
        self.notify_sessions[group_id] = event.unified_msg_origin
        self._save_notify_session()
        # 初始化状态
        now = int(time.time())
        if group_id not in self.group_last_states:
            self.group_last_states[group_id] = {}
        if group_id not in self.group_start_play_times:
            self.group_start_play_times[group_id] = {}
        for sid in steam_ids:
            status = await self.fetch_player_status(sid)
            if status:
                self.group_last_states[group_id][sid] = status
                if status.get("gameid"):
                    prev = self.group_last_states[group_id].get(sid)
                    prev_gameid = prev.get("gameid") if prev else None
                    if (
                        prev_gameid
                        and prev_gameid == status.get("gameid")
                        and sid in self.group_start_play_times[group_id]
                    ):
                        pass
                    else:
                        self.group_start_play_times[group_id][sid] = int(time.time())
        yield event.plain_result("本群Steam状态监控启动完成喔！ヾ(≧ω≦)ゞ")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam addid")
    async def steam_addid(self, event: AstrMessageEvent, steamid: str):
        """添加SteamID到本群监控列表（分群），支持多个ID用逗号分隔"""
        group_id = (
            str(event.get_group_id()) if hasattr(event, "get_group_id") else "default"
        )
        # 支持多个ID同时输入
        steamid_list = [x.strip() for x in steamid.split(".") if x.strip()]
        invalid_ids = [
            sid for sid in steamid_list if not sid.isdigit() or len(sid) != 17
        ]
        if invalid_ids:
            yield event.plain_result(
                f"以下SteamID无效（需为64位数字串，17位）：{'.'.join(invalid_ids)}"
            )
            return
        steam_ids = self.group_steam_ids.setdefault(group_id, [])
        added = []
        already = []
        limit = self.max_group_size
        for sid in steamid_list:
            if sid in steam_ids:
                already.append(sid)
            elif len(steam_ids) < limit:
                steam_ids.append(sid)
                added.append(sid)
            else:
                break
        self.group_steam_ids[group_id] = steam_ids
        self._save_group_steam_ids()  # 新增：保存到 steam_groups.json
        msg = ""
        if added:
            msg += f"已为本群添加SteamID: {'.'.join(added)}\n"
        if already:
            msg += f"以下SteamID已存在于本群监控组: {'.'.join(already)}\n"
        if len(steam_ids) >= limit and len(added) < len(steamid_list):
            msg += f"本群监控组人数已达上限（{limit}人），部分ID未添加。\n"
        yield event.plain_result(msg.strip() if msg else "未添加任何SteamID。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam delid")
    async def steam_delid(self, event: AstrMessageEvent, steamid: str):
        """从本群监控组删除SteamID（分群）"""
        group_id = (
            str(event.get_group_id()) if hasattr(event, "get_group_id") else "default"
        )
        steam_ids = self.group_steam_ids.get(group_id, [])
        if steamid not in steam_ids:
            yield event.plain_result("该SteamID不存在于本群监控组")
            return
        steam_ids.remove(steamid)
        self.group_steam_ids[group_id] = steam_ids
        self._save_group_steam_ids()  # 新增：保存到 steam_groups.json
        yield event.plain_result(f"已为本群删除SteamID: {steamid}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam list")
    async def steam_list(self, event: AstrMessageEvent):
        """列出本群所有玩家当前状态（分群）"""
        group_id = (
            str(event.get_group_id()) if hasattr(event, "get_group_id") else "default"
        )
        steam_ids = self.group_steam_ids.get(group_id, [])
        if not self.API_KEY:
            yield event.plain_result(
                "未配置 Steam API Key，请先在插件配置中填写 steam_api_key。"
            )
            return
        if not steam_ids:
            yield event.plain_result("本群未设置监控的 SteamID 列表，请先添加。")
            return
        event.group_steam_ids = steam_ids
        font_path = self.get_font_path("NotoSansHans-Regular.otf")
        logger.info(f"[Font] steam_list 渲染传入字体路径: {font_path}")
        async for result in handle_steam_list(self, event, font_path=font_path):
            yield result

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam config")
    async def steam_config(self, event: AstrMessageEvent):
        """显示当前插件配置"""
        lines = []
        for k, v in self.config.items():
            lines.append(f"{k}: {v}")
        yield event.plain_result("当前配置：\n" + "\n".join(lines))

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam set")
    async def steam_set(self, event: AstrMessageEvent, key: str, value: str):
        """设置配置参数，立即生效（如 steam set poll_interval_sec 30）"""
        if key not in self.config:
            yield event.plain_result(f"无效参数: {key}")
            return
        # 类型转换
        old = self.config[key]
        if isinstance(old, int):
            try:
                value = int(value)
            except Exception:
                yield event.plain_result("类型错误，应为整数")
                return
        elif isinstance(old, float):
            try:
                value = float(value)
            except Exception:
                yield event.plain_result("类型错误，应为浮点数")
                return
        elif isinstance(old, list):
            value = [x.strip() for x in value.split(",") if x.strip()]
        self.config[key] = value
        # 同步到属性
        self.API_KEY = self.config.get("steam_api_key", "")
        self.STEAM_IDS = self.config.get("steam_ids", [])
        self.POLL_INTERVAL = self.config.get("poll_interval_sec", 10)
        self.RETRY_TIMES = self.config.get("retry_times", 3)
        self.GROUP_ID = self.config.get("notify_group_id", None)
        # 保存配置（如支持）
        if hasattr(self.config, "save_config"):
            self.config.save_config()
        yield event.plain_result(f"已设置 {key} = {value}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam rs")
    async def steam_rs(self, event: AstrMessageEvent):
        """清除所有状态并初始化（重启插件用）"""
        self.group_last_states.clear()
        self.group_start_play_times.clear()
        self.group_last_quit_times.clear()
        self.group_pending_logs.clear()
        self.group_pending_quit.clear()
        self.group_recent_games.clear()
        self._superpower_cache.clear()
        self._game_name_cache.clear()
        self.achievement_poll_tasks.clear()
        self.achievement_snapshots.clear()
        self.running_groups.clear()
        self.group_monitor_enabled.clear()
        self.group_achievement_enabled.clear()
        self.notify_sessions = {}
        self._save_persistent_data()  # 清空后保存
        yield event.plain_result("Steam状态监控插件已重置，所有状态已清空。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam help")
    async def steam_help(self, event: AstrMessageEvent):
        """显示所有指令帮助"""
        help_text = (
            "Steam状态监控插件指令：\n"
            "/steam on - 启动监控\n"
            "/steam off - 停止监控\n"
            "/steam list - 列出所有玩家状态\n"
            "/steam config - 查看当前配置\n"
            "/steam set [参数] [值] - 设置配置参数\n"
            "/steam addid [SteamID] - 添加SteamID\n"
            "/steam delid [SteamID] - 删除SteamID\n"
            "/steam openbox [SteamID] - 查看指定SteamID的全部信息\n"
            "/steam rs - 清除状态并初始化\n"
            "/steam help - 显示本帮助"
        )
        yield event.plain_result(help_text)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam openbox")
    async def steam_openbox(self, event: AstrMessageEvent, steamid: str):
        """查询并格式化展示指定SteamID的全部API返回信息（中文字段名，头像图片附加，位置ID合并，状态字段直观显示）"""
        if not self.API_KEY:
            yield event.plain_result(
                "未配置 Steam API Key，请先在插件配置中填写 steam_api_key。"
            )
            return
        async for result in handle_openbox(self, event, steamid):
            yield result

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam off")
    async def steam_off(self, event: AstrMessageEvent):
        """停止Steam状态监控轮询"""
        group_id = (
            str(event.get_group_id()) if hasattr(event, "get_group_id") else "default"
        )
        self.group_monitor_enabled[group_id] = False
        if group_id in self.running_groups:
            self.running_groups.remove(group_id)
        yield event.plain_result("已为本群关闭Steam监控和推送。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam achievement_on")
    async def steam_achievement_on(self, event: AstrMessageEvent):
        group_id = (
            str(event.get_group_id()) if hasattr(event, "get_group_id") else "default"
        )
        self.group_achievement_enabled[group_id] = True
        yield event.plain_result("已为本群开启Steam成就推送。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam achievement_off")
    async def steam_achievement_off(self, event: AstrMessageEvent):
        group_id = (
            str(event.get_group_id()) if hasattr(event, "get_group_id") else "default"
        )
        self.group_achievement_enabled[group_id] = False
        yield event.plain_result("已为本群关闭Steam成就推送。")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam test_achievement_render")
    async def steam_test_achievement_render(
        self, event: AstrMessageEvent, steamid: str, gameid: int, count: int = 3
    ):
        """测试成就消息渲染效果（steam test_achievement_render [steamid] [gameid] [数量]）"""
        player_name = steamid
        game_name = await self.get_chinese_game_name(gameid)
        group_id = self.GROUP_ID or "default"
        achievements = await self.achievement_monitor.get_player_achievements(
            self.API_KEY, group_id, steamid, gameid
        )
        if not achievements:
            yield event.plain_result("未获取到任何成就，可能为隐私或无成就。")
            return
        details = await self.achievement_monitor.get_achievement_details(
            group_id, gameid, lang="schinese", api_key=self.API_KEY, steamid=steamid
        )
        import random

        count = max(1, min(count, len(achievements)))
        unlocked = set(random.sample(list(achievements), count))
        font_path = self.get_font_path("NotoSansHans-Regular.otf")
        # 直接测试 Pillow 渲染
        try:
            img_bytes = await self.achievement_monitor.render_achievement_image(
                details, unlocked, player_name=player_name, font_path=font_path
            )
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            yield event.image_result(tmp_path)
        except Exception as e:
            import traceback

            logger.error(f"成就图片渲染失败: {e}\n{traceback.format_exc()}")
            # 回退文本
            msg = self.achievement_monitor.render_achievement_message(
                details, unlocked, player_name=player_name
            )
            yield event.plain_result(msg)

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam test_game_start_render")
    async def test_game_start_render(
        self, event: AstrMessageEvent, steamid: str, gameid: int
    ):
        """测试开始游戏图片渲染效果（steam test_game_start_render [steamid] [gameid]）"""
        try:
            # 获取玩家名
            status = await self.fetch_player_status(steamid)
            player_name = status.get("name") if status else steamid
            avatar_url = (
                status.get("avatarfull") or status.get("avatar") or "" if status else ""
            )
            # 获取游戏名（中文和英文）
            zh_game_name = await self.get_chinese_game_name(gameid)
            # 获取英文名
            url_en = (
                f"https://store.steampowered.com/api/appdetails?appids={gameid}&l=en"
            )
            en_game_name = None
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp_en = await client.get(url_en)
                    data_en = resp_en.json()
                    info_en = data_en.get(str(gameid), {}).get("data", {})
                    en_game_name = info_en.get("name")
            except Exception:
                en_game_name = None
            logger.info(
                f"[测试开始游戏渲染] steamid={steamid} gameid={gameid} player_name={player_name} avatar_url={avatar_url} game_name={zh_game_name} en_game_name={en_game_name}"
            )
            superpower = self.get_today_superpower(steamid)
            print(f"[superpower] test_game_start_render superpower={superpower}")
            font_path = self.get_font_path("NotoSansHans-Regular.otf")
            img_bytes = await render_game_start(
                self.data_dir,
                steamid,
                player_name,
                avatar_url,
                gameid,
                zh_game_name,
                api_key=self.API_KEY,
                superpower=superpower,
                sgdb_api_key=self.SGDB_API_KEY,
                font_path=font_path,
                sgdb_game_name=en_game_name,
            )
            logger.info(
                f"[测试开始游戏渲染] render_game_start 返回类型: {type(img_bytes)} 长度: {len(img_bytes) if img_bytes else 'None'}"
            )
            if img_bytes:
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                    tmp.write(img_bytes)
                    tmp_path = tmp.name
                img = PILImage.open(tmp_path).convert("RGB")
                cropped_img = self.crop_image_auto(
                    img, bg_color=(51, 81, 66), threshold=15
                )
                with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp2:
                    cropped_img.save(tmp2, format="PNG")
                    tmp_path2 = tmp2.name
                logger.info(f"[测试开始游戏渲染] 已保存裁剪图到 {tmp_path2}")
                yield event.image_result(tmp_path2)
            else:
                yield event.plain_result("渲染失败，未获取到图片数据。")
        except Exception as e:
            logger.error(f"测试开始游戏图片渲染失败: {e}\n{traceback.format_exc()}")
            yield event.plain_result(f"渲染异常: {e}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam test_game_end_render")
    async def steam_test_game_end_render(
        self,
        event: AstrMessageEvent,
        steamid: str,
        gameid: int,
        duration_min: float = 120,
        end_time: str = None,
        tip_text: str = None,
    ):
        """测试游戏结束图片渲染（steam test_game_end_render [steamid] [gameid] [时长分钟] [结束时间 可选] [提示 可选]）"""
        try:
            # 获取玩家名、头像
            status = await self.fetch_player_status(steamid)
            player_name = status.get("name") if status else steamid
            avatar_url = (
                status.get("avatarfull") or status.get("avatar") or "" if status else ""
            )
            # 获取游戏名（中文和英文）
            zh_game_name = await self.get_chinese_game_name(gameid)
            url_en = (
                f"https://store.steampowered.com/api/appdetails?appids={gameid}&l=en"
            )
            en_game_name = None
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    resp_en = await client.get(url_en)
                    data_en = resp_en.json()
                    info_en = data_en.get(str(gameid), {}).get("data", {})
                    en_game_name = info_en.get("name")
            except Exception:
                en_game_name = None
            from datetime import datetime

            if end_time:
                end_time_str = end_time
            else:
                end_time_str = datetime.now().strftime("%Y-%m-%d %H:%M")
            duration_h = float(duration_min) / 60 if duration_min else 0
            # 默认提示
            if not tip_text:
                tip_text = "欢迎下次再来玩~"
            font_path = self.get_font_path("NotoSansHans-Regular.otf")
            img_bytes = await render_game_end(
                self.data_dir,
                steamid,
                player_name,
                avatar_url,
                gameid,
                zh_game_name,
                end_time_str,
                tip_text,
                duration_h,
                sgdb_api_key=self.SGDB_API_KEY,
                font_path=font_path,
                sgdb_game_name=en_game_name,
            )
            msg = f"👋 {player_name} 不玩 {zh_game_name} 了"
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name
            yield event.plain_result(msg)
            yield event.image_result(tmp_path)
        except Exception as e:
            logger.error(f"测试游戏结束图片渲染失败: {e}\n{traceback.format_exc()}")
            yield event.plain_result(f"渲染异常: {e}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam清除缓存")
    async def steam_clear_cache(self, event: AstrMessageEvent):
        """清除所有头像、封面图等图片缓存（慎用）"""
        try:
            cache_dirs = [
                os.path.join(self.data_dir, "avatars"),
                os.path.join(self.data_dir, "covers"),
                os.path.join(self.data_dir, "covers_v"),
            ]
            cleared = []
            for d in cache_dirs:
                if os.path.exists(d):
                    shutil.rmtree(d)
                    cleared.append(d)
            msg = (
                "已清除以下缓存目录：\n" + "\n".join(cleared)
                if cleared
                else "未找到任何缓存目录，无需清理。"
            )
            yield event.plain_result(msg)
        except Exception as e:
            yield event.plain_result(f"清除缓存失败: {e}")

    @filter.permission_type(filter.PermissionType.ADMIN)
    @filter.command("steam clear_allids")
    async def steam_clear_allids(self, event: AstrMessageEvent):
        """删除所有群聊的所有已监控SteamID，并清空相关状态数据"""
        self.group_steam_ids.clear()
        self._save_group_steam_ids()  # 新增：保存到 steam_groups.json
        self.group_last_states.clear()
        self.group_start_play_times.clear()
        self.group_last_quit_times.clear()
        self.group_pending_logs.clear()
        self.group_pending_quit.clear()
        self.group_recent_games.clear()
        self._save_persistent_data()
        self.config["group_steam_ids"] = self.group_steam_ids
        if hasattr(self.config, "save_config"):
            self.config.save_config()
        yield event.plain_result("已删除所有群聊的所有SteamID，相关状态数据已清空。")

    async def check_status_change(
        self, group_id, single_sid=None, status_override=None, poll_level=None
    ):
        """轮询检测玩家状态变更并推送通知（分群，支持单个sid）
        返回精简日志字符串，不直接打印日志"""
        now = int(time.time())
        steam_ids = (
            [single_sid] if single_sid else self.group_steam_ids.get(group_id, [])
        )
        last_states = self.group_last_states.setdefault(group_id, {})
        start_play_times = self.group_start_play_times.setdefault(group_id, {})
        last_quit_times = self.group_last_quit_times.setdefault(group_id, {})
        pending_logs = self.group_pending_logs.setdefault(group_id, {})
        pending_quit = self.group_pending_quit.setdefault(group_id, {})
        recent_games = self.group_recent_games.setdefault(group_id, [])
        notify_session = getattr(self, "notify_sessions", {}).get(group_id, None)
        msg_lines = []
        for sid in steam_ids:
            status = (
                status_override
                if status_override and sid == single_sid
                else await self.fetch_player_status(sid)
            )
            if not status:
                continue
            prev = last_states.get(sid)
            name = status.get("name") or sid
            gameid = status.get("gameid")
            game = status.get("gameextrainfo")
            lastlogoff = status.get("lastlogoff")
            personastate = status.get("personastate", 0)
            zh_game_name = (
                await self.get_chinese_game_name(gameid, game)
                if gameid
                else (game or "未知游戏")
            )
            prev_gameid = prev.get("gameid") if prev else None
            current_gameid = gameid
            # --- 新增：初始化 last_quit_times/pending_logs/pending_quit ---
            if sid not in last_quit_times:
                last_quit_times[sid] = {}
            if sid not in pending_logs:
                pending_logs[sid] = {}
            if sid not in pending_quit:
                pending_quit[sid] = {}

            # --- 退出游戏（缓冲3分钟） ---
            if prev_gameid and current_gameid in [None, "", "0"]:
                logger.info(
                    f"[退出逻辑] {name} prev_gameid={prev_gameid} current_gameid={current_gameid}"
                )
                zh_prev_game_name = (
                    await self.get_chinese_game_name(
                        prev_gameid, prev.get("gameextrainfo") if prev else None
                    )
                    if prev_gameid
                    else (prev.get("gameextrainfo") if prev else "未知游戏")
                )
                duration_min = 0
                start_time = start_play_times.get(sid, now)
                if sid in start_play_times:
                    duration_min = (now - start_play_times[sid]) / 60
                # 成就结算：游戏结束时，延迟15分钟再做一次对比
                try:
                    player_name = name
                    game_name = zh_prev_game_name
                    key = (group_id, sid, prev_gameid)
                    poll_task = self.achievement_poll_tasks.pop(key, None)
                    if poll_task:
                        poll_task.cancel()
                    asyncio.create_task(
                        self.achievement_delayed_final_check(
                            group_id, sid, prev_gameid, player_name, game_name
                        )
                    )
                except Exception as e:
                    logger.error(f"结算成就时异常: {e}")
                self.achievement_monitor.clear_game_achievements(
                    group_id, sid, prev_gameid
                )
                pending_quit[sid][prev_gameid] = {
                    "quit_time": now,
                    "name": name,
                    "game_name": zh_prev_game_name,
                    "duration_min": duration_min,
                    "start_time": start_time,
                    "notified": False,
                }
                start_play_times.pop(sid, None)
                last_quit_times[sid][prev_gameid] = now
                last_states[sid] = status
                continue  # 防止重复推送

            # --- 开始游戏/继续游戏（仅当 gameid 变更时推送） ---
            if current_gameid not in [None, "", "0"] and current_gameid != prev_gameid:
                quit_info = pending_quit[sid].get(current_gameid)
                if (
                    quit_info
                    and now - quit_info["quit_time"] <= 180
                    and not quit_info.get("notified")
                ):
                    persona_state = status.get("personastate", 0)
                    persona_tail = ""
                    continue
                logger.info(
                    f"[开始逻辑] {name} prev_gameid={prev_gameid} current_gameid={current_gameid}"
                )
                last_quit = last_quit_times[sid].get(current_gameid)
                is_continue = last_quit and (now - last_quit) <= 300
                if is_continue:
                    if sid in start_play_times:
                        pass
                    else:
                        start_play_times[sid] = now
                    continue_tails = [
                        "是掉线了吗？继续肝！",
                        "游戏bug了吗？又回来了！",
                        "网络波动？咱一直在等你喵~",
                        "又是闪退？Steam真不省心喵~",
                        "欢迎回来，继续冲！",
                        "咱就知道你还会回来的喵~",
                        "继续刚才的进度吧！",
                        "咱以为你下线了，其实你还在游戏里喵~",
                    ]
                    msg = f"🔄 {name} 继续玩 {zh_game_name} 了！{random.choice(continue_tails)}"
                else:
                    start_play_times[sid] = now
                    msg = f"🟢 {name} 开始玩 {zh_game_name} 了！"
                try:
                    avatar_url = status.get("avatarfull") or status.get("avatar") or ""
                    if not avatar_url and prev:
                        avatar_url = prev.get("avatarfull") or prev.get("avatar") or ""
                    if not avatar_url:
                        status_full = await self.fetch_player_status(sid)
                        if status_full:
                            avatar_url = status_full.get(
                                "avatarfull"
                            ) or status_full.get("avatar")
                    logger.info(
                        f"[开始游戏渲染] avatar_url={avatar_url} sid={sid} name={name} gameid={current_gameid} game_name={zh_game_name}"
                    )
                    superpower = self.get_today_superpower(sid)
                    online_count = await self.get_game_online_count(current_gameid)
                    font_path = self.get_font_path("NotoSansHans-Regular.otf")
                    img_bytes = await render_game_start(
                        self.data_dir,
                        sid,
                        name,
                        avatar_url,
                        current_gameid,
                        zh_game_name,
                        api_key=self.API_KEY,
                        superpower=superpower,
                        online_count=online_count,
                        sgdb_api_key=self.SGDB_API_KEY,
                        font_path=font_path,
                    )
                    logger.info(
                        f"[开始游戏渲染] render_game_start 返回类型: {type(img_bytes)} 长度: {len(img_bytes) if img_bytes else 'None'}"
                    )
                    msg_chain = [Plain(msg)]
                    if img_bytes:
                        import tempfile

                        with tempfile.NamedTemporaryFile(
                            delete=False, suffix=".png"
                        ) as tmp:
                            tmp.write(img_bytes)
                            tmp_path = tmp.name
                        logger.info(f"[开始游戏渲染] 已保存原图到 {tmp_path}")
                        msg_chain.append(Image.fromFileSystem(tmp_path))
                    else:
                        logger.error("[开始游戏渲染] render_game_start 返回空")
                except Exception as e:
                    logger.error(f"开始游戏图片渲染失败: {e}\n{traceback.format_exc()}")
                    msg_chain = [Plain(msg)]
                try:
                    if notify_session:
                        logger.info(f"{name} 开始玩 {zh_game_name} 了，推送通知")
                        await self.context.send_message(
                            notify_session, MessageChain(msg_chain)
                        )
                        last_states[sid] = status
                    else:
                        logger.error("未设置推送会话，无法发送消息")
                except Exception as e:
                    logger.error(f"推送新开始游戏消息失败: {e}")
                last_quit_times[sid].pop(current_gameid, None)
                if current_gameid in pending_quit[sid]:
                    del pending_quit[sid][current_gameid]
                self.achievement_monitor.clear_game_achievements(
                    group_id, sid, current_gameid
                )
                # 启动成就轮询时跳过黑名单
                if current_gameid not in self.achievement_blacklist:
                    try:
                        logger.info(
                            f"[成就快照] 检测到用户 {name} 正在游玩游戏 {zh_game_name}({current_gameid})，正在获取成就列表"
                        )
                        achievements_start = (
                            await self.achievement_monitor.get_player_achievements(
                                self.API_KEY, group_id, sid, current_gameid
                            )
                        )
                        if achievements_start is not None:
                            logger.info(
                                f"[成就快照] 成功获取成就列表：{len(achievements_start)} / {current_gameid}"
                            )
                            key = (group_id, sid, current_gameid)
                            self.achievement_snapshots[key] = list(achievements_start)
                            player_name = name
                            game_name = zh_game_name
                            old_task = self.achievement_poll_tasks.pop(key, None)
                            if old_task:
                                old_task.cancel()
                            poll_task = asyncio.create_task(
                                self.achievement_periodic_check(
                                    group_id,
                                    sid,
                                    current_gameid,
                                    player_name,
                                    game_name,
                                )
                            )
                            self.achievement_poll_tasks[key] = poll_task
                        else:
                            # 失败计数
                            cnt = self.achievement_fail_count.get(current_gameid, 0) + 1
                            self.achievement_fail_count[current_gameid] = cnt
                            if cnt >= 10:
                                self.achievement_blacklist.add(current_gameid)
                                logger.info(
                                    f"[成就黑名单] 游戏 {current_gameid} 多次获取失败，已加入黑名单"
                                )
                    except Exception as e:
                        logger.error(f"保存开始游戏成就快照异常: {e}")
                last_states[sid] = status
                continue  # 防止重复推送

            # 智能轮询间隔设置
            next_poll = self.next_poll_time.setdefault(group_id, {})
            poll_interval = 1800  # 默认30分钟
            if gameid:
                poll_interval = 60
            elif personastate and int(personastate) > 0:
                poll_interval = 60
            elif lastlogoff:
                hours_ago = (now - int(lastlogoff)) / 3600
                if hours_ago <= 0.2:
                    poll_interval = 60
                elif hours_ago <= 3:
                    poll_interval = 300
                elif hours_ago <= 24:
                    poll_interval = 600
                elif hours_ago <= 48:
                    poll_interval = 1200
                else:
                    poll_interval = 1800
            else:
                poll_interval = 1800
            # 对齐到下一个整分钟/5分钟/10分钟等
            import math

            interval_min = poll_interval // 60
            next_time = ((now // 60) + math.ceil(interval_min)) * 60
            # 如果是5、10、20、30分钟轮询，进一步对齐到5、10、20、30的倍数
            if interval_min in [5, 10, 20, 30]:
                next_time = ((now // 60) // interval_min + 1) * interval_min * 60
            next_poll[sid] = next_time
            # 轮询间隔描述
            if poll_interval == 60:
                poll_level_str = "1分钟轮询"
            elif poll_interval == 300:
                poll_level_str = "5分钟轮询"
            elif poll_interval == 600:
                poll_level_str = "10分钟轮询"
            elif poll_interval == 1200:
                poll_level_str = "20分钟轮询"
            elif poll_interval == 1800:
                poll_level_str = "30分钟轮询"
            else:
                poll_level_str = f"{poll_interval // 60}分钟轮询"

            if gameid:
                msg_lines.append(
                    f"🟢【{name}】正在玩 {zh_game_name}（{poll_level_str}）"
                )
            elif personastate and int(personastate) > 0:
                msg_lines.append(f"🟡【{name}】在线（{poll_level_str}）")
            elif lastlogoff:
                hours_ago = (now - int(lastlogoff)) / 3600
                msg_lines.append(
                    f"⚪️【{name}】离线 上次在线 {hours_ago:.1f} 小时前（{poll_level_str}）"
                )
            else:
                msg_lines.append(f"⚪️【{name}】离线（{poll_level_str}）")
            last_states[sid] = status

        for sid in pending_quit:
            for gameid in list(pending_quit[sid].keys()):
                info = pending_quit[sid][gameid]
                if now - info["quit_time"] >= 180 and not info.get("notified"):
                    # 推送前先标记为已通知，防止并发重复推送
                    info["notified"] = True
                    duration_min = info["duration_min"]
                    msg = f"👋 {info['name']} 不玩 {info['game_name']} 了"
                    try:
                        if notify_session:
                            # 新增：渲染游戏结束图片
                            try:
                                from datetime import datetime

                                end_time_str = datetime.fromtimestamp(
                                    info["quit_time"]
                                ).strftime("%Y-%m-%d %H:%M")
                                duration_h = (
                                    info["duration_min"] / 60
                                    if info["duration_min"] > 0
                                    else 0
                                )
                                # 获取头像
                                avatar_url = None
                                last_state = last_states.get(sid)
                                if last_state:
                                    avatar_url = last_state.get(
                                        "avatarfull"
                                    ) or last_state.get("avatar")
                                if not avatar_url:
                                    status_full = await self.fetch_player_status(sid)
                                    if status_full:
                                        avatar_url = status_full.get(
                                            "avatarfull"
                                        ) or status_full.get("avatar")
                                # 获取友好提示词
                                if duration_min < 5:
                                    tip_text = "风扇都没转热，主人就结束了？"
                                elif duration_min < 10:
                                    tip_text = "杂鱼杂鱼~主人你就这水平？"
                                elif duration_min < 30:
                                    tip_text = "热身一下就结束了？"
                                elif duration_min < 60:
                                    tip_text = "歇会儿再来，别太累了喵！"
                                elif duration_min < 120:
                                    tip_text = "沉浸在游戏世界，时间过得飞快喵！"
                                elif duration_min < 300:
                                    tip_text = "肝到手软了喵！主人不如陪陪咱~"
                                elif duration_min < 600:
                                    tip_text = (
                                        "你吃饭了吗？还是说你已经忘了吃饭这件事？"
                                    )
                                elif duration_min < 1200:
                                    tip_text = "家里电费都要被你玩光了喵！"
                                elif duration_min < 1800:
                                    tip_text = "咱都要给你颁发‘不眠猫’勋章了！"
                                elif duration_min < 2400:
                                    tip_text = "主人你还活着喵？你是不是忘了关电脑呀~"
                                else:
                                    tip_text = "你已经和椅子合为一体，成为传说中的‘椅子精’了喵！"
                                font_path = self.get_font_path(
                                    "NotoSansHans-Regular.otf"
                                )
                                img_bytes = await render_game_end(
                                    self.data_dir,
                                    sid,
                                    info["name"],
                                    avatar_url,
                                    gameid,
                                    info["game_name"],
                                    end_time_str,
                                    tip_text,
                                    duration_h,
                                    sgdb_api_key=self.SGDB_API_KEY,
                                    font_path=font_path,
                                )
                                import tempfile

                                with tempfile.NamedTemporaryFile(
                                    delete=False, suffix=".png"
                                ) as tmp:
                                    tmp.write(img_bytes)
                                    tmp_path = tmp.name
                                await self.context.send_message(
                                    notify_session,
                                    MessageChain(
                                        [Plain(msg), Image.fromFileSystem(tmp_path)]
                                    ),
                                )
                            except Exception as e:
                                logger.error(f"推送游戏结束图片失败: {e}")
                                await self.context.send_message(
                                    notify_session, MessageChain([Plain(msg)])
                                )
                        else:
                            logger.error("未设置推送会话，无法发送消息")
                    except Exception as e:
                        logger.error(f"推送正常退出消息失败: {e}")
                    if gameid in pending_quit[sid]:
                        del pending_quit[sid][gameid]

        self._save_persistent_data()
        # 只返回日志字符串
        return "\n".join(msg_lines) if msg_lines else None

    async def get_game_online_count(self, gameid):
        """通过 Steam Web API 获取当前游戏在线人数"""
        if not gameid:
            return None
        url = f"https://api.steampowered.com/ISteamUserStats/GetNumberOfCurrentPlayers/v1/?appid={gameid}"
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("response", {}).get("player_count")
        except Exception as e:
            logger.warning(f"获取在线人数失败: {e} (gameid={gameid})")
        return None

    @filter.command("steam alllist")
    async def steam_alllist(self, event: AstrMessageEvent):
        """列出所有群聊绑定的steam情况，包含群聊分组，玩家名，在线情况，下次轮询时间"""
        lines = []
        now = int(time.time())
        for group_id, steam_ids in self.group_steam_ids.items():
            lines.append(f"群组: {group_id}")
            last_states = self.group_last_states.get(group_id, {})
            next_poll = self.next_poll_time.get(group_id, {})
            for sid in steam_ids:
                status = last_states.get(sid)
                name = status.get("name") if status else sid
                gameid = status.get("gameid") if status else None
                game = status.get("gameextrainfo") if status else None
                lastlogoff = status.get("lastlogoff") if status else None
                personastate = status.get("personastate", 0) if status else 0
                next_time = next_poll.get(sid, now)
                seconds_left = int(next_time - now)
                if seconds_left < 60:
                    poll_str = f"下次轮询{seconds_left}秒后"
                else:
                    poll_str = f"下次轮询{seconds_left // 60}分钟后"
                if gameid:
                    state_str = (
                        f"🟢正在玩 {await self.get_chinese_game_name(gameid, game)}"
                    )
                elif personastate and int(personastate) > 0:
                    state_str = "🟡在线"
                elif lastlogoff:
                    hours_ago = (now - int(lastlogoff)) / 3600
                    state_str = f"⚪️离线，上次在线 {hours_ago:.1f} 小时前"
                else:
                    state_str = "⚪️离线"
                lines.append(f"  {name}({sid}) - {state_str}（{poll_str}）")
            lines.append("")
        yield event.plain_result("\n".join(lines))

    def get_today_superpower(self, steamid):
        """获取指定SteamID当天的超能力描述（用于图片渲染）"""
        from datetime import date

        today = date.today().isoformat()
        cache_key = (steamid, today)
        if cache_key in self._superpower_cache:
            return self._superpower_cache[cache_key]
        if self._abilities is None:
            self._abilities = load_abilities(self._abilities_path)
        superpower = get_daily_superpower(steamid, self._abilities)
        self._superpower_cache[cache_key] = superpower
        return superpower
