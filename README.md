# telegram-markup-bot

**Telegram-бот для рендеринга Markdown в формат, совместимый с Telegram (HTML).**

---

## Описание проекта

Монорепозиторий, содержащий:

| Пакет | Описание |
|-------|----------|
| **[md2tg](md2tg/)** | Независимая библиотека для преобразования Markdown → Telegram HTML. Может использоваться отдельно в любом Python-проекте. |
| **[bot](bot/)** | Telegram-бот на базе `aiogram`, использующий `md2tg` для рендеринга. |
| **[webapp](webapp/)** | Мини-приложение (Web App) для ввода текста через inline-режим Telegram. |

---

## Основные возможности

- Парсинг Markdown (через `markdown-it-py`) с поддержкой списков, таблиц, блоков кода, цитат, спойлеров и прочих стандартных конструкций.
- Преобразование во внутренний AST и рендер в Telegram-совместимый HTML.
- Обработка Telegram `MessageEntity` (UTF-16 offsets).
- Автоматическое разбиение длинных сообщений по ограничению Telegram (≤ 4096 символов).
- Поддержка загрузки `.md`/`.txt` файлов (до 2 MB).

---

## Быстрый старт

> Проект использует [uv](https://docs.astral.sh/uv/) для управления зависимостями.

### 1. Установите uv

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

### 2. Клонируйте репозиторий

```bash
git clone https://github.com/DmitryKolyadin/telegram-markup-bot.git
cd telegram-markup-bot
```

### 3. Установите зависимости

```bash
uv sync --all-packages
```

### 4. Запустите бота

```bash
export BOT_TOKEN="123:ABC..."
cd bot
uv run python main.py
```

---

## Использование md2tg как библиотеки

Библиотека `md2tg` может быть установлена и использована в любом проекте:

```bash
pip install md2tg          # после публикации на PyPI
# или для локальной разработки:
uv pip install ./md2tg
```

```python
from md2tg import convert

parts = convert("**Жирный** и *курсив*")
# ['<b>Жирный</b> и <i>курсив</i>']
```

Подробнее — см. [md2tg/README.md](md2tg/README.md).

---

## Запуск тестов

```bash
uv sync --all-packages
uv pip install pytest
uv run python -m pytest md2tg/tests/ -v
```

---

## Структура проекта

```
telegram-markup-bot/
├── pyproject.toml              # Корневой workspace (uv)
├── md2tg/                      # Библиотека md2tg
│   ├── pyproject.toml
│   ├── README.md
│   ├── src/md2tg/
│   │   ├── __init__.py         # Публичный API: convert(), классы
│   │   ├── ast_nodes.py        # Определения узлов AST
│   │   ├── parser.py           # Markdown → токены
│   │   ├── transformer.py      # Токены → AST
│   │   ├── renderer.py         # AST → Telegram HTML
│   │   └── splitter.py         # Разбиение на части ≤ 4096
│   └── tests/
│       └── test_md2tg.py
├── bot/
│   ├── pyproject.toml
│   ├── main.py
│   ├── cloud.py
│   ├── core/
│   │   └── entity_converter.py # Конвертер Telegram MessageEntity
│   └── yappa.yaml.example
└── webapp/
    └── index.html
```

---

## Ограничения

- Максимальный размер загружаемого файла ~2 MB.
- Telegram накладывает ограничение на длину сообщения ~4096 символов — бот автоматически разбивает слишком длинные рендеры.

---

## Конфигурация и переменные окружения

- `BOT_TOKEN` — **обязательно**: токен Telegram-бота.

---

## Лицензия

Проект распространяется под лицензией **GPL-3.0** — см. `LICENSE`.  
Библиотека `md2tg` распространяется под лицензией **MIT**.
