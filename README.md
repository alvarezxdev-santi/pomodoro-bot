# 🍅 Pomodoro Bot

A Discord bot that helps your server study together using the Pomodoro technique. Track your sessions, compete on the leaderboard, and stay focused!

> Running in the **StudyWithMe** Discord server

---

## ✨ Features

- 🍅 Start a Pomodoro study session with one command
- ☕ Take timed breaks between sessions
- ⏰ Get a DM when your timer expires — no babysitting needed
- 📊 Track your total study sessions and minutes
- 🏆 Compete with your server on the weekly leaderboard
- 💾 Persistent stats backed by Redis

---

## 📋 Commands

| Command | Description |
|---|---|
| `/study [minutes]` | Start a Pomodoro session (default: 25 min) |
| `/break [minutes]` | Start a break timer (default: 5 min) |
| `/stop` | Cancel your current session |
| `/status` | Check how much time you have left |
| `/mystats` | View your study stats |
| `/leaderboard` | See the top 5 studiers on the server |

---

## 🚀 Setup

### 1. Clone the repo

```bash
git clone https://github.com/yourusername/pomodoro-bot.git
cd pomodoro-bot
```

### 2. Create a virtual environment

```bash
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Open `.env` and fill in your values:

```
DISCORD_TOKEN=your_bot_token_here
REDIS_URL=redis://localhost:6379
```

### 5. Run the bot

```bash
python bot.py
```

---

## 🔧 Redis Setup

The bot uses Redis to store active sessions and user stats.

**Option A — Local Redis (macOS):**
```bash
brew install redis
brew services start redis
```

**Option B — Redis Cloud (free tier):**
1. Sign up at [redis.io/try-free](https://redis.io/try-free)
2. Create a free database
3. Copy the connection URL into your `.env` as `REDIS_URL`

---

## 🤖 Creating a Discord Bot

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new Application
3. Go to **Bot** → **Add Bot**
4. Under **Privileged Gateway Intents**, enable:
   - Server Members Intent
   - Message Content Intent
5. Copy the token into your `.env`
6. Go to **OAuth2 → URL Generator**, select `bot` + `applications.commands`, then invite to your server

---

## 📁 Project Structure

```
pomodoro-bot/
├── bot.py          # Entry point
├── cogs/
│   ├── pomodoro.py # Timer commands
│   └── stats.py    # Stats and leaderboard
├── requirements.txt
├── .env.example
└── README.md
```
