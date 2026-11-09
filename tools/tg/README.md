# Чтение Telegram без подключения MCP к сессии

`tgcall.py` ходит напрямую в локальный telegram-mcp (http://127.0.0.1:8765/mcp), только чтение.
Нужен запущенный сервис. Если не отвечает, поднять так же, как это делает стартёр (tools/boot-stagger):
`launchctl enable gui/$(id -u)/com.cucaramba.telegram-mcp-server && launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.cucaramba.telegram-mcp-server.plist; launchctl disable gui/$(id -u)/com.cucaramba.telegram-mcp-server`
(disable сразу после bootstrap, правило из ~/Claude Code/CLAUDE.md).

```
python3 -I tgcall.py search_global '{"query":"Нячанг бот","page_size":20}'
python3 -I tgcall.py get_full_user '{"username":"MotikBot"}'
python3 -I tgbots.py        # собирает упоминания ботов и startapp по нячангским чатам, ~2 мин
python3 -I tgdetail.py      # полные тексты анонсов выбранных ботов
```
Лимиты Telegram: паузы между вызовами уже есть в скриптах, не гонять параллельно.
