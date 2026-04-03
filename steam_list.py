import time
import io
from .steam_list_render import render_steam_list_image

async def handle_steam_list(self, event, font_path=None):
    '''列出所有玩家当前状态（图片美化版，分群支持）'''
    # 获取分群ID
    group_id = None
    if hasattr(event, 'get_group_id'):
        group_id = str(event.get_group_id())
    elif hasattr(event, 'group_id'):
        group_id = str(event.group_id)
    else:
        group_id = 'default'
    steam_ids = self.group_steam_ids.get(group_id, [])
    start_play_times = self.group_start_play_times.get(group_id, {})
    user_list = []
    now = int(time.time())
    for idx, sid in enumerate(steam_ids):
        status = await self.fetch_player_status(sid, retry=1)
        if not status:
            user_list.append({
                'sid': sid,
                'name': sid,
                'status': 'error',
                'avatar_url': '',
                'game': '',
                'gameid': '',
                'play_str': '获取失败',
                'lastlogoff': None
            })
            continue
        name = status.get('name') or sid
        gameid = status.get('gameid')
        game = status.get('gameextrainfo')
        lastlogoff = status.get('lastlogoff')
        personastate = status.get('personastate', 0)
        avatar_url = status.get('avatarfull') or status.get('avatar') or ''
        zh_game_name = await self.get_chinese_game_name(gameid, game) if gameid else (game or "未知游戏")
        if gameid:
            if sid in start_play_times:
                play_seconds = now - start_play_times[sid]
                play_minutes = play_seconds / 60
                if play_minutes < 60:
                    play_str = f"{play_minutes:.1f}分钟"
                else:
                    play_str = f"{play_minutes/60:.1f}小时"
            else:
                play_str = "刚开始"
            user_list.append({
                'sid': sid,
                'name': name,
                'status': 'playing',
                'avatar_url': avatar_url,
                'game': zh_game_name,
                'gameid': gameid,
                'play_str': play_str,
                'lastlogoff': lastlogoff
            })
        elif personastate and int(personastate) > 0:
            user_list.append({
                'sid': sid,
                'name': name,
                'status': 'online',
                'avatar_url': avatar_url,
                'game': '',
                'gameid': '',
                'play_str': '',
                'lastlogoff': lastlogoff
            })
        elif lastlogoff:
            hours_ago = (now - int(lastlogoff)) / 3600
            user_list.append({
                'sid': sid,
                'name': name,
                'status': 'offline',
                'avatar_url': avatar_url,
                'game': '',
                'gameid': '',
                'play_str': f"上次在线 {hours_ago:.1f} 小时前",
                'lastlogoff': lastlogoff
            })
        else:
            user_list.append({
                'sid': sid,
                'name': name,
                'status': 'offline',
                'avatar_url': avatar_url,
                'game': '',
                'gameid': '',
                'play_str': '',
                'lastlogoff': lastlogoff
            })
    # 渲染图片
    if font_path is None:
        font_path = self.get_font_path('NotoSansHans-Regular.otf') if hasattr(self, 'get_font_path') else None
    img_bytes = await render_steam_list_image(self.data_dir, user_list, font_path=font_path)
    if img_bytes:
        with io.BytesIO(img_bytes) as buf:
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
                tmp.write(buf.read())
                tmp_path = tmp.name
            yield event.image_result(tmp_path)
    else:
        yield event.plain_result("渲染图片失败")
