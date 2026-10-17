# UK: решения Ярослава

**Работаем с 8 фирмами тира A из Greater Manchester. Цена: £350–500 разово плюс £20 в месяц. Оплата через зарубежную карту Ярослава.**

## Фирмы (17.10.2026)

- В работе (8): Tailored joinery solutions, Barron Bespoke, handley bespoke joinery, Inspired Living, Altered Images, 307 Builders, M.D kitchen Fitters, Jamie Shaw Kitchens.
- Убраны: Greater Manchester Handyman (домен куплен 24.08.2026, сайт в работе), Kwix4 (сайт умер, Ltd ликвидирована).
- Inspired Living оставлен, хотя есть похожий сайт-заготовка inspiredlivinguk.co.uk без контактов.
- Тир B пока не берём: по 1-2 отзыва, фото почти нет. Сначала смотрим отклик на 8 фирмах.

## Данные

- `data/drafts/<id>.json` собраны `landing-brief/build/tools/gmaps_collect.js` из Google Maps.
- Google без входа в аккаунт показывает только часть карточки: 4–21 фото и 3 отзыва на фирму, автор фото неизвестен.
- Фото мало (по 4) у 307 Builders, M.D и Jamie Shaw: там будут заглушки.
- Имена: Mark Barron (Checkatrade через выдачу поиска), Lewis Handley (Instagram), Jamie Shaw (название). В Tailored клиент хвалит «Jaque» [оценка: владелец].

## Цена

- Рынок UK: фрилансер £1,000–3,000 разово, подписки для мастеров £39–99 в месяц, Checkatrade от £59 в месяц (источники: блоги студий и прайсы продавцов, см. переписку 17.10).
- Решение: £350–500 разово плюс £20 в месяц (хостинг и правки). Ниже рынка, потому что нет британских отзывов.

## Подача (17.10)

- Канал: WhatsApp, на всех 8 номерах мобильные.
- Первое сообщение как в России: скрин первого экрана, видео-демо и короткий текст.
- Английский: Ярослав пишет через переводчик, поэтому сделку ведём в переписке. Нужны готовые ответы на типовые вопросы.
- Дизайн: тот же шаблон, что у Симметрии, тексты на английском.
- Подпись: Yar, web designer. Пишет с зарубежного номера. Страну в первом сообщении не называет, если спросят, отвечает честно.
- Цену в первом сообщении не называет, только после ответа.
- Темп: 2 новых чата в день. Напоминаний нет: не ответили, значит больше не пишем.
- Правила ICO (PECR): мастерам без Ltd рекламные сообщения формально требуют согласия. Ярослав решил писать всем 8, но аккуратно: одно личное сообщение, честная подпись, в конце фраза-отказ «If not, no worries, I won't message again».

## Первое сообщение (шаблон)

> Hi {Name}, I'm Yar, a web designer. {Firm} has {rating} from {n} Google reviews but no website, so I mocked one up with your photos (below). Want to see the full thing? If not, no worries, I won't message again.

- Рейтинг 5.0 писать «5 stars». Имя владельца ставить только подтверждённое (у Barron это Mark: его называют в отзывах), иначе «Hi there».

## Сборка макетов

- `cd landing-brief/build && python3 build.py --uk <id>`: берёт `uk-brief/companies.json` и `uk-brief/data/<id>.json`, пишет в `uk-brief/out/<id>/`.
- Скрины и видео: `OUT_DIR=../../uk-brief/out node shoot.js <id>` и `node video.js <id>` (с тем же `OUT_DIR` и `PLAYWRIGHT_MODULE`).
- Карта берётся из OpenStreetMap, фото из Google без обрезки водяного знака.
- Пробный макет: Barron Bespoke (`uk-brief/out/barron-bespoke/`).
