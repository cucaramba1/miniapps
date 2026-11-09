# miniapps: прототипы и планы (сессия 03-04.11.2026)

Каждый проект разбирается в отдельной сессии по своему хендоффу.

| Проект | Хендофф | Статус |
|---|---|---|
| Нячанг Дом, платный mini-app по жилью (главный продукт) | `nhatrang/HANDOFF.md` | прототип, план, конкуренты, тесты |
| Радар рилсов (mini-app в духе Trendsee) | `reels-radar/HANDOFF.md` | прототип на демо-данных, тесты |
| YouTube без лица | `faceless/HANDOFF.md` | план (`docs/plan.html`), прототип отложен |
| ИИ-персонаж в Instagram и TikTok | `ai-model/HANDOFF.md` | только план (`docs/plan.html`) |

Общее: `shared/` дизайн-кит и обёртка Telegram, `tests/` (README внутри), `tools/build_bundle.py` сборка артефакта, `tools/tg/` чтение Telegram, `docs/` хаб, план каналов и скриншоты, `docs/e2e-report.json` последний отчёт тестов.
Артефакт (приватный): https://claude.ai/artifact/AGj2i1WjaDdgiycW2HwdEo, версия 5 от 04.11.2026 (safe-area, BackButton). Сборка: `python3 -I tools/build_bundle.py <папка>`, публикация страницей `hub.html` плюс изменившимися файлами `<app>/ds.css`, `<app>/tgx.js`.

Последний полный прогон 04.11.2026: 969 из 969 (жильё 506, радар 298, студия 165), после правки safe-area повторён с тем же результатом. Полный прогон перед релизом: `cd tests && node e2e.mjs && node summarize.mjs && node telegram-real.mjs` (около 2,5 минут; второй тест на ветку настоящего Telegram, 76 проверок).
