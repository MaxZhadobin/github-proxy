# Реализация endpoint /schema

## Изменения

- Добавлен новый эндпоинт `GET /schema` в `main.py`.
- Созданы модели `ColumnInfo` и `TableSchema` для описания ответа.
- Эндпоинт возвращает список колонок таблицы из `information_schema.columns`.
- Обновлена версия API и README.

## Как работает

Эндпоинт `/schema` принимает параметры:

- `db` – алиас базы данных (обязательный);
- `table` – имя таблицы (обязательный).

Возвращается структура таблицы в формате:

```json
{
  "columns": [
    {"name": "id", "type": "uuid", "nullable": false, "default": null}
  ]
}
```

## Тестирование

- Проверена компиляция `main.py` через `python -m py_compile`.
