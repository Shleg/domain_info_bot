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

# 🛰️ DomainInfoBot  

A Telegram bot that monitors website availability and provides essential domain information, including HTTP/HTTPS status, SSL certificate validity, and domain registration expiry dates.

---

## 🚀 Features

- **Website Monitoring**: Checks HTTP/HTTPS availability periodically.
- **SSL Certificate Monitoring**: Notifies about upcoming SSL certificate expirations.
- **Domain Expiration Check**: Alerts users about approaching domain registration expiry.
- **Telegram Integration**: Instant notifications and management through a Telegram bot.
- **Individual Domain Lists**: Each user manages their own list of monitored domains (coming soon).

---

## 🛠️ Technology Stack

- **Python 3.11**
- **Aiogram** for Telegram bot interactions
- **SQLAlchemy (Async)** for database interactions
- **PostgreSQL** as the primary database
- **APScheduler** for scheduling regular domain checks
- **Docker & Docker Compose** for easy deployment
- **HTTPX** for asynchronous HTTP requests
- **python-whois** for retrieving WHOIS domain data

---

## ⚙️ Installation and Usage

### Prerequisites

- Docker and Docker Compose installed on your machine.
- Telegram bot token from [BotFather](https://t.me/BotFather).

### Steps:

1. **Clone the repository**:

```bash
git clone https://github.com/Shleg/DomainInfoBot.git
cd DomainInfoBot
```
2. **Set up environment variables:**

```bash
cp .env.example .env
```

3. **Run the bot using Docker Compose:**

```bash
docker compose build
docker compose up
```

## 🤖 Telegram Bot Commands
- **/start – Start interacting with the bot**
- **/help – Show available commands**
- **/add <domain> – Add a domain to your monitoring list**
- **/remove <domain> – Remove a domain from your monitoring list**
- **/list – List all monitored domains**
- **/check <domain> – Manually check a domain’s status**
