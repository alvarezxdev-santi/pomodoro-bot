import os
import logging

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger("pomodoro-bot")


class PomodoroBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        intents.voice_states = True

        super().__init__(command_prefix="!", intents=intents)
        self.redis_url = REDIS_URL

    async def setup_hook(self):
        await self.load_extension("cogs.pomodoro")
        await self.load_extension("cogs.stats")
        log.info("Cogs loaded successfully")

        # Sync slash commands globally (takes up to an hour to propagate)
        # For testing, sync to a specific guild instead:
        # await self.tree.sync(guild=discord.Object(id=YOUR_GUILD_ID))
        await self.tree.sync()
        log.info("Application commands synced")

    async def on_ready(self):
        log.info(f"Logged in as {self.user} (ID: {self.user.id})")
        log.info(f"Connected to {len(self.guilds)} guild(s)")
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="you study 🍅 | /study",
            )
        )


def main():
    if not TOKEN:
        raise ValueError("DISCORD_TOKEN is not set. Check your .env file.")

    bot = PomodoroBot()
    bot.run(TOKEN, log_handler=None)


if __name__ == "__main__":
    main()
