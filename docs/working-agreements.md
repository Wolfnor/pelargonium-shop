# Правила работы

## Названия задач

Формат: `[TYPE] Краткое действие`.

Допустимые типы: `RESEARCH`, `FEATURE`, `TASK`, `BUG`, `TEST`, `DOCS`.

Примеры:

- `[RESEARCH] Уточнить процесс приема заказа`
- `[FEATURE] Добавить карточку сорта`
- `[BUG] Исправить сохранение статуса заказа`

## Названия веток

Формат: `type/issue-number-short-name`.

- `feature/2-catalog-card`
- `fix/8-order-status`
- `docs/5-update-adr`
- `test/11-order-flow`

## Коммиты

Используется короткий формат Conventional Commits:

- `feat: add variety catalog card`
- `fix: save order status`
- `docs: update delivery model ADR`
- `test: add order form checks`

## Pull request

Название: `#номер Краткий результат`.

В описании указываются связанная задача, выполненные изменения, способ проверки и известные ограничения.

## Готовность задачи

Задача переходит в Done, когда результат реализован, проверен, показан заказчику при необходимости и отражен в документации.

