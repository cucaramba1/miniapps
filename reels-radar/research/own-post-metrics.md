# Ресерч: цифры своих постов Полины (05.11.2026)

Субагент-исследователь. Факты со ссылками на документацию Meta/TikTok; помеченное «не проверено» это вывод модели.

## Вывод
- **Instagram:** официальный бесплатный путь рабочий: Instagram API with Instagram Login, аккаунт Creator/Business, Standard Access (свой аккаунт, app review не нужен, Facebook Page не нужна).
- **TikTok:** Display API по докам отдаёт view/like/comment/share, но доступ (review, sandbox, регион, физлицо) не подтверждён. Рабочий запас: yt-dlp по публичному профилю без логина + ручной ввод saves.

## Instagram (факты)
- Аккаунт профессиональный (business или creator), Page не нужна, скоуп `instagram_business_basic`. Какой скоуп нужен для insights при Instagram Login, в доке не нашёл. https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/
- Standard Access достаточно для своих аккаунтов; Advanced (review + Business Verification) только для чужих. Работа через роль Instagram Tester. https://developers.facebook.com/docs/instagram-platform/overview
- Токены: короткий 1 ч, long-lived 60 дней, продлевается (эндпоинт refresh не проверен). Лимит 4800 × показы за 24 ч, для одного аккаунта не проблема.
- Метрики Reels: `views`, `reach`, `saved`, `shares`, `total_interactions`, `likes`, `comments`, `reposts`, `ig_reels_avg_watch_time`, `ig_reels_video_view_total_time`, `reels_skip_rate`. **Задержка до 48 ч**, нет данных = пустой ответ (не 0), история 2 года. Замер «через 1 ч» может быть пустым. https://developers.facebook.com/docs/instagram-platform/reference/instagram-media/insights
- `plays`, `video_views`, `impressions` устарели (2024-2025), вместо них `views` (с повторами).
- Порог 100 подписчиков для media insights в доке не нашёл.

## TikTok (факты)
- Display API: `/v2/user/info/`, `/v2/video/list/`, `/v2/video/query/`, скоупы `user.info.basic`, `video.list`, нужно одобрение Login Kit + Display API. https://developers.tiktok.com/doc/display-api-get-started/
- Поля: `view_count`, `like_count`, `comment_count`, `share_count`, `create_time`, `duration`. **Saves нет.** https://developers.tiktok.com/doc/tiktok-api-v2-video-object
- Сроки токенов в доках противоречат друг другу, брать `expires_in` из ответа.
- Sandbox и review для Display API, регистрация физлицом, регион: не нашёл.

## Россия (вывод, не факт)
Meta заблокирована в РФ. Запросы к API делает скрипт на ноуте Некита (Вьетнам). Приложение регистрирует Некит, Полина принимает роль Tester (через VPN). Ограничит ли Meta регистрацию, не нашёл.

## Без API
- instaloader: 429 = временный бан, логин рискует checkpoint. Просмотры и лайки видны, shares и saves нет. https://instaloader.github.io/troubleshooting.html
- yt-dlp для TikTok: публичные метрики без логина, риск низкий при опросе раз в час-день. Статус 2026 не проверен.
- Saves в TikTok и глубокая аналитика только вручную (TikTok Studio).

## Предложенные шаги
IG: перевести аккаунт в Creator → приложение на developers.facebook.com (Некит) → Полина Tester → long-lived токен, продление раз в ~50 дней → опрос `/{ig-id}/media` раз в 15-30 мин, insights на 24 ч, 3 д, 7 д (1 ч может быть пусто).
TikTok: сразу yt-dlp по профилю; параллельно попробовать Display API; saves руками.
Не проверено: скоуп insights, регистрация приложения, работа без review на живом аккаунте, yt-dlp в 2026.
