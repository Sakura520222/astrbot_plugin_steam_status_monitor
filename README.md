# Steam 状态监控插件V2

## 访问统计
![访问统计](https://count.getloli.com/get/@astrbot_ssm?theme=rule34)

本插件是专为AstrBot设计的插件，用于定时轮询 Steam Web API，监控指定玩家的在线/离线/游戏状态变更，并在状态变化时推送通知。支持多 SteamID 监控，自动记录游玩日志，支持群聊分组，数据持久化，支持丰富指令。

## 功能特性
- 支持定时轮询多个 SteamID 的状态，分群管理，每个群聊可独立配置监控玩家
- 检测玩家上线、下线、开始/切换/退出游戏等状态变更，自动推送游戏启动/关闭提醒
- 成就变动自动推送提醒
- 已配置自动轮询频率，默认为1-30分钟查询一次状态，取决于steam的上次在线时间
- 持久化记录玩家游玩日志，重启bot后状态不会丢失

## 默认轮询间隔说明
| 玩家最近在线时间      | 轮询间隔 |
|----------------------|---------|
| 12分钟内             | 1分钟   |
| 12分钟~3小时         | 5分钟   |
| 3小时~24小时         | 10分钟  |
| 24~48小时            | 20分钟  |
| 超过48小时           | 30分钟  |

## 快速上手
1. 在AstrBot网页后台的配置中配置 Steam_Web_API_Key：[点击获取](https://steamcommunity.com/dev/apikey)
2. 在AstrBot网页后台的配置中配置 SGDB_API_KEY（用于获取封面图，可选）：[点击获取](https://www.steamgriddb.com/profile/preferences/api)
3. 在需要进行提醒的群聊输入指令：
   `/steam addid [Steam64位ID]`  （如：/steam addid 7656119xxxxxxxxxx）
4. 启动轮询：
   `/steam on`  启动本群 Steam 状态监控，后续状态变更会自动推送。



## 注意事项
- 获取速度与是否成功获取 Steam 数据取决于网络环境。建议通过加速或魔法手段来保证稳定的查询状态。

如果出现未知的轮询错误可以使用 /steam clear_allids 来清除所有群聊的轮询id

## 演示截图
![开始游戏示例](https://raw.githubusercontent.com/Maoer233/astrbot_plugin_steam_status_monitor/main/str.png)
![结束游戏示例](https://raw.githubusercontent.com/Maoer233/astrbot_plugin_steam_status_monitor/main/stop.png)
![成就推送示例](https://raw.githubusercontent.com/Maoer233/astrbot_plugin_steam_status_monitor/main/achievement.png)


## 指令列表
- `/steam on` 启动本群Steam状态监控
- `/steam off` 停止本群Steam状态监控
- `/steam list` 列出本群所有玩家当前状态
- `/steam alllist` 列出所有群聊分组及玩家状态
- `/steam config` 查看当前插件配置
- `/steam set [参数] [值]` 设置配置参数（如 `/steam set poll_interval_sec 30`）
- `/steam addid [SteamID]` 添加SteamID到本群监控列表
- `/steam delid [SteamID]` 从本群监控列表删除SteamID
- `/steam openbox [SteamID]` 查看指定SteamID的全部详细信息
- `/steam rs` 清除所有状态并初始化
- `/steam achievement_on` 开启本群Steam成就推送
- `/steam achievement_off` 关闭本群Steam成就推送
- `/steam test_achievement_render [steamid] [gameid] [数量]` 测试成就图片渲染
- `/steam test_game_start_render [steamid] [gameid]` 测试开始游戏图片渲染
- `/steam清除缓存` 清除所有头像、封面图等图片缓存
- `/steam help` 显示所有指令帮助

## 依赖
- Python 3.7+
- httpx
- Pillow
- AstrBot 框架

### 依赖安装方法
如果显示缺少依赖，你可以尝试下载以下工具来进行修复
pip install httpx pillow

可以添加QQ：1912584909 来反馈功能和建议 闲聊也欢迎喵~

## ⭐ Stars

> 如果本项目对您的生活 / 工作产生了帮助，或者您关注本项目的未来发展，请给项目 Star，这是我维护这个开源项目的动力 ❤️。
