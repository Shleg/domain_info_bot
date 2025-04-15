uptime_monitor/
├── bot/                    # Telegram-бот
│   ├── main.py             # Запуск бота
│   └── handlers.py         # Команды /start, /add, /list и т.д.
├── monitor/                # Модули мониторинга
│   ├── checker.py          # Проверка HTTP, HTTPS, SSL, WHOIS
│   ├── scheduler.py        # Планировщик (APScheduler)
│   └── notifier.py         # Отправка сообщений в Telegram
├── db/
│   ├── models.py           # SQLAlchemy модели
│   └── db.py               # Подключение к базе и сессии
├── config.py               # Настройки (бот токен, БД и т.п.)
├── .env                    # Переменные окружения
├── Dockerfile
└── docker-compose.yml