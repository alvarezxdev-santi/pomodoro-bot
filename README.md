# pomodoro-bot

Discord bot for running Pomodoro study sessions. Start a timer, get a DM when it's done, and track your hours on a server leaderboard. Running in the StudyWithMe server.

## Commands

| Command | Description |
|---|---|
| `/study [minutes]` | Start a session (default 25 min) |
| `/break [minutes]` | Start a break (default 5 min) |
| `/stop` | Cancel your current session |
| `/status` | Check remaining time |
| `/mystats` | Your total sessions and hours |
| `/leaderboard` | Top 5 most studied members |

## Setup

```bash
git clone https://github.com/alvarezxdev-santi/pomodoro-bot
cd pomodoro-bot
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python bot.py
```

For Redis you can run it locally (`brew install redis && brew services start redis`) or use the free tier on [Redis Cloud](https://redis.io/try-free).

## How it works

Sessions are stored in Redis with a TTL equal to the session duration. A background task runs every 30 seconds and checks for expired sessions — when one expires, it DMs the user and updates their stats.

Stats live in Redis hashes (`stats:{user_id}`) so the leaderboard is just a scan + sort, no extra DB needed.

## Stack

- discord.py 2.3
- redis-py
- Python 3.11+
