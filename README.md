# NonRoot

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-%3E%3D3.8-brightgreen.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-macOS%20%7C%20Linux%20%7C%20Windows-lightgrey.svg)]()
[![DeepSeek API](https://img.shields.io/badge/DeepSeek-V3%20%2F%20R1-blueviolet.svg)](https://github.com/nadaroot/freedeepseek)
[![Architecture](https://img.shields.io/badge/arch-ReAct%20Agent-orange.svg)]()

**NonRoot** — автономный ИИ-агент для разработки, системного администрирования и автоматизации задач на базе моделей DeepSeek (V3 и R1 Reasoning). Приложение работает локально на машине пользователя, предоставляет встроенный веб-интерфейс и выполняет полный спектр операций с терминалом, файловой системой, поиском по коду и параллельными субагентами.

---

## О проекте

NonRoot спроектирован как легковесный автономный агент без тяжелых внешних серверных фреймворков. Приложение построено на стандартной библиотеке Python и включает в себя:
- Автономный исполнительный цикл ReAct (Reasoning + Acting) с динамическим вызовом инструментов (Tool Calling).
- Потоковую передачу данных через Server-Sent Events (SSE) в реальном времени.
- Встроенный веб-сервер с автоматическим разрешением конфликтов портов и управлением жизненным циклом процесса.
- Темный минималистичный пользовательский интерфейс с правой панелью сессий чатов и визуализацией цепочки рассуждений (Reasoning Chain).
- Поддержку мультимодальных запросов (загрузка скриншотов, диаграмм и фотографий кода).

---

## Интеграция с DeepSeek API

NonRoot полностью совместим со стандартом OpenAI Chat Completions API и оптимизирован для работы с локальным или удаленным прокси-сервером **[FreeDeepseekAPI](https://github.com/nadaroot/freedeepseek)**.

### Поддерживаемые модели:
- `deepseek-chat` — флагманская модель DeepSeek-V3 для написания кода, рефакторинга и общих задач.
- `deepseek-reasoner` — модель DeepSeek-R1 с извлечением и пошаговым отображением хода мыслей (`<think>`).
- `deepseek-coder` (33B / 6.7B) — специализированные модели для анализа и генерации программного кода.
- `deepseek-ai/DeepSeek-V3` и `deepseek-ai/DeepSeek-R1` — маршрутизируемые эндпоинты через роутеры и сторонние API-провайдеры.
- Динамическое обнаружение моделей через эндпоинт `/v1/models`.

Для локального запуска прокси-сервера DeepSeek API обратитесь к репозиторию **[nadaroot/freedeepseek](https://github.com/nadaroot/freedeepseek)**.

---

## Технологический стек

### Backend & Движок агента
- **Python 3 Standard Library**: `http.server`, `socketserver.ThreadingMixIn`, `threading`, `urllib.request`, `urllib.parse`, `queue`, `mimetypes`, `subprocess`.
- **Zero Heavy Runtime Dependencies**: сервер не требует Flask, FastAPI, Uvicorn или Node.js.
- **Двунаправленный ReAct Loop**: многошаговый цикл принятия решений с лимитом шагов, обработкой отказов и автоматической коррекцией ошибок.
- **Подсистема субагентов**: параллельное исполнение изолированных фоновых потоков с отдельными контекстами и трансляцией событий в UI.

### Frontend & Интерфейс
- **HTML5 & CSS3 Variables**: адаптивная 3-колоночная архитектура с темной палитрой (`#09090b`, `#121215`, `#27272a`).
- **Vanilla JavaScript**: легковесный клиент без сборщиков (Webpack/Vite), прямое подключение по SSE (`/api/events`).
- **Мультисессионное хранилище**: локальное сохранение и переключение истории чатов через `localStorage`.
- **Векторная графика**: строгие SVG-иконки без использования сторонних шрифтов и эмодзи.

---

## Архитектура системы

```
nonroot/
├── nonroot/
│   ├── __init__.py
│   ├── cli.py                  # CLI-лаунчер, аргументы командной строки и открытие браузера
│   ├── config.py               # Менеджер конфигурации (~/.nonroot/config.json)
│   ├── server.py               # Многопоточный HTTP & SSE веб-сервер
│   ├── engine/
│   │   ├── agent.py            # Master ReAct агент и координатор цикла
│   │   ├── deepseek_client.py  # SSE-клиент DeepSeek API, парсер <think> и Vision
│   │   ├── prompts.py          # Системные инструкции и спецификации инструментов
│   │   ├── subagents.py        # Менеджер параллельных субагентов
│   │   └── tools.py            # Исполнители инструментов (shell, fs, web)
│   └── ui/
│       ├── index.html          # Главная разметка интерфейса
│       ├── style.css           # Стили темной темы
│       ├── app.js              # Клиентская логика, сессии и SSE-обработчики
│       └── favicon.png         # Иконка приложения
├── assets/                     # Ассеты иконки (.icns, .ico, .png, .svg)
├── scripts/                    # Скрипты установки под macOS, Linux, Windows
├── nonroot.py                  # Главная точка входа
├── build_standalone.py         # Сборщик в единый бинарный файл (PyInstaller)
└── requirements.txt
```

---

## Доступные инструменты (Tools)

Агент имеет доступ к следующим системным операциям:

| Инструмент | Параметры | Описание |
| :--- | :--- | :--- |
| `run_command` | `command`, `cwd`, `timeout` | Выполнение shell-команд в рабочей директории |
| `read_file` | `path`, `start_line`, `end_line` | Построчное чтение файлов проекта |
| `write_file` | `path`, `content` | Создание или полная перезапись файлов |
| `edit_file` | `path`, `search_target`, `replacement` | Точечная замена блоков кода в существующих файлах |
| `list_dir` | `path` | Инспекция структуры каталогов |
| `grep_search` | `query`, `path`, `is_regex` | Поиск текста или регулярных выражений по файлам |
| `web_fetch` | `url` | Загрузка и конвертация веб-страниц в Markdown |
| `spawn_subagent` | `role`, `prompt`, `model` | Запуск параллельного субагента для подзадач |
| `finish_task` | `summary` | Сигнал об успешном завершении задачи |

---

## Быстрый старт

### Вариант 1: Запуск через Python

```bash
# Клонирование репозитория
git clone https://github.com/nadaroot/deepsekagent.git nonroot
cd nonroot

# Запуск приложения
python3 nonroot.py
```

После запуска сервер автоматически подберет свободный порт и откроет веб-интерфейс в браузере: `http://127.0.0.1:8765`.

### Вариант 2: Запуск через глобальную команду `nonroot`

#### macOS
```bash
bash scripts/setup_macos.sh
```
Скрипт установит команду `nonroot` в `/usr/local/bin` и создаст автономное приложение `NonRoot.app` в `~/Applications`.

#### Linux
```bash
bash scripts/setup_linux.sh
```
Скрипт добавит исполняемый файл в `~/.local/bin/nonroot` и создаст `.desktop` файл.

#### Windows
Запустите `scripts\setup_windows.bat` от имени администратора. Скрипт создаст ярлык на рабочем столе и добавит `nonroot` в системный `PATH`.

---

## Параметры командной строки

```bash
nonroot [опции]

Опции:
  --port PORT           Порт веб-сервера (по умолчанию: 8765)
  --host HOST           Хост для привязки (по умолчанию: 127.0.0.1)
  --workspace DIR       Корневая рабочая директория
  --model MODEL         Модель DeepSeek по умолчанию (deepseek-chat, deepseek-reasoner)
  --api-url URL         Базовый адрес DeepSeek API (по умолчанию: http://127.0.0.1:3000/v1)
  --api-key KEY         Ключ API (по умолчанию: sk-nonroot-free)
  --auto-accept         Включить автоматическое выполнение инструментов без подтверждения
  --no-browser          Не открывать браузер автоматически при запуске
```

Все настройки также сохраняются в файле `~/.nonroot/config.json` и доступны для редактирования через графическое окно настроек в веб-интерфейсе.

---

## Сборка standalone-бинарника

Для компиляции приложения в единый исполняемый файл без необходимости установки Python:

```bash
python3 build_standalone.py
```

Готовый бинарный файл будет помещен в директорию `dist/` (`NonRoot` на macOS/Linux или `NonRoot.exe` на Windows).

---

## Связанные проекты

* **[FreeDeepseekAPI](https://github.com/nadaroot/freedeepseek)** — локальный прокси-сервер DeepSeek API с поддержкой OpenAI и Anthropic протоколов, Function Calling и Vision.

---

## Лицензия

Проект распространяется под лицензией MIT. Подробности в файле [LICENSE](LICENSE).

