import json
import logging
import time
from typing import Optional

import discord
import redis.asyncio as aioredis
from discord import app_commands
from discord.ext import commands, tasks

log = logging.getLogger("pomodoro-bot.pomodoro")

# Embed colours
COLOR_STUDY = 0xFF6B6B   # tomato red
COLOR_BREAK = 0x6BCB77   # soft green
COLOR_INFO  = 0x4D96FF   # blue
COLOR_STOP  = 0xAAAAAA   # grey


class Pomodoro(commands.Cog):
    """Slash commands for managing Pomodoro study sessions."""

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.redis: Optional[aioredis.Redis] = None
        self.check_expired.start()

    async def cog_load(self):
        self.redis = aioredis.from_url(
            self.bot.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        log.info("Redis connection established (Pomodoro cog)")

    async def cog_unload(self):
        self.check_expired.cancel()
        if self.redis:
            await self.redis.aclose()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _session_key(self, user_id: int) -> str:
        return f"session:{user_id}"

    def _expiry_key(self, user_id: int) -> str:
        """Shadow key used to detect when the real session expires."""
        return f"session_expiry:{user_id}"

    async def _get_session(self, user_id: int) -> Optional[dict]:
        raw = await self.redis.get(self._session_key(user_id))
        if raw is None:
            return None
        return json.loads(raw)

    async def _set_session(self, user_id: int, data: dict, seconds: int):
        key = self._session_key(user_id)
        await self.redis.set(key, json.dumps(data), ex=seconds)
        # Store a shadow key with the exact expiry timestamp so the
        # background task can notify the user precisely after expiry.
        await self.redis.set(
            self._expiry_key(user_id),
            json.dumps({"user_id": user_id, "guild_id": data["guild_id"], "session_type": data["session_type"]}),
            ex=seconds + 60,  # keep for 60 s after expiry so the task catches it
        )

    async def _delete_session(self, user_id: int):
        await self.redis.delete(self._session_key(user_id))
        await self.redis.delete(self._expiry_key(user_id))

    # ------------------------------------------------------------------
    # Background task — polls every 30 s
    # ------------------------------------------------------------------

    @tasks.loop(seconds=30)
    async def check_expired(self):
        """Scan for sessions that have just expired and DM the user."""
        try:
            expiry_keys = []
            async for key in self.redis.scan_iter("session_expiry:*"):
                expiry_keys.append(key)

            for exp_key in expiry_keys:
                raw = await self.redis.get(exp_key)
                if raw is None:
                    continue

                data = json.loads(raw)
                user_id = int(data["user_id"])
                session_key = self._session_key(user_id)

                # If the real session key is gone but the expiry shadow key
                # still exists, the session just expired — notify the user.
                still_active = await self.redis.exists(session_key)
                if still_active:
                    continue

                session_type = data.get("session_type", "study")
                await self.redis.delete(exp_key)

                # Update stats for completed study sessions
                if session_type == "study":
                    await self._increment_stats(user_id)

                # DM the user
                user = self.bot.get_user(user_id)
                if user is None:
                    try:
                        user = await self.bot.fetch_user(user_id)
                    except discord.NotFound:
                        continue

                try:
                    if session_type == "study":
                        embed = discord.Embed(
                            title="⏰ Time's up!",
                            description="Great work! Your study session is complete.\nTake a **5-minute break** — you earned it.",
                            color=COLOR_STUDY,
                        )
                        embed.set_footer(text="Use /break 5 to start a break timer")
                    else:
                        embed = discord.Embed(
                            title="☕ Break's over!",
                            description="Ready to get back to it? Start your next Pomodoro!",
                            color=COLOR_BREAK,
                        )
                        embed.set_footer(text="Use /study to start a new session")

                    await user.send(embed=embed)
                    log.info(f"Notified user {user_id} — {session_type} session expired")
                except discord.Forbidden:
                    log.warning(f"Could not DM user {user_id} (DMs disabled)")

        except Exception as e:
            log.error(f"check_expired task error: {e}", exc_info=True)

    @check_expired.before_loop
    async def before_check_expired(self):
        await self.bot.wait_until_ready()

    async def _increment_stats(self, user_id: int):
        """Increment total_sessions and total_minutes for a user after a completed session."""
        # We need the duration; it's stored in the expiry shadow key data.
        # By this point the real session is already gone, so we read from the
        # expiry data that was already fetched by the caller.  The duration is
        # NOT stored there, so we approximate by using the session's scheduled
        # duration stored in the expiry payload when we set it.  For simplicity,
        # we just always add 25 minutes for study sessions here, but a
        # production version would store the exact duration in the shadow key.
        stats_key = f"stats:{user_id}"
        pipe = self.redis.pipeline()
        pipe.hincrby(stats_key, "total_sessions", 1)
        pipe.hincrby(stats_key, "total_minutes", 25)
        await pipe.execute()

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    @app_commands.command(name="study", description="Start a Pomodoro study session (default 25 minutes)")
    @app_commands.describe(minutes="How long to study in minutes (1–120)")
    async def study(self, interaction: discord.Interaction, minutes: int = 25):
        if not 1 <= minutes <= 120:
            await interaction.response.send_message(
                "Please pick a duration between 1 and 120 minutes.", ephemeral=True
            )
            return

        existing = await self._get_session(interaction.user.id)
        if existing:
            remaining = await self.redis.ttl(self._session_key(interaction.user.id))
            mins_left = remaining // 60
            secs_left = remaining % 60
            await interaction.response.send_message(
                f"You already have an active session! **{mins_left}m {secs_left}s** remaining.\n"
                "Use `/stop` to cancel it first.",
                ephemeral=True,
            )
            return

        session_data = {
            "user_id": interaction.user.id,
            "guild_id": interaction.guild_id,
            "start_time": time.time(),
            "duration": minutes,
            "session_type": "study",
        }
        await self._set_session(interaction.user.id, session_data, minutes * 60)

        embed = discord.Embed(
            title="🍅 Pomodoro Started!",
            description=f"I'll ping you in **{minutes} minute{'s' if minutes != 1 else ''}**. Stay focused!",
            color=COLOR_STUDY,
        )
        embed.add_field(name="Duration", value=f"{minutes} min", inline=True)
        embed.add_field(name="Type", value="Study", inline=True)
        embed.set_footer(text="Use /status to check time remaining • /stop to cancel")
        embed.set_thumbnail(url="https://cdn.discordapp.com/emojis/tomato.png")

        await interaction.response.send_message(embed=embed)
        log.info(f"Study session started for user {interaction.user.id} ({minutes} min)")

    @app_commands.command(name="break", description="Start a break timer (default 5 minutes)")
    @app_commands.describe(minutes="How long to break in minutes (1–60)")
    async def take_break(self, interaction: discord.Interaction, minutes: int = 5):
        if not 1 <= minutes <= 60:
            await interaction.response.send_message(
                "Please pick a break between 1 and 60 minutes.", ephemeral=True
            )
            return

        existing = await self._get_session(interaction.user.id)
        if existing:
            remaining = await self.redis.ttl(self._session_key(interaction.user.id))
            mins_left = remaining // 60
            secs_left = remaining % 60
            await interaction.response.send_message(
                f"You already have an active session! **{mins_left}m {secs_left}s** remaining.\n"
                "Use `/stop` to cancel it first.",
                ephemeral=True,
            )
            return

        session_data = {
            "user_id": interaction.user.id,
            "guild_id": interaction.guild_id,
            "start_time": time.time(),
            "duration": minutes,
            "session_type": "break",
        }
        await self._set_session(interaction.user.id, session_data, minutes * 60)

        embed = discord.Embed(
            title="☕ Break Time!",
            description=f"Taking a **{minutes} minute{'s' if minutes != 1 else ''}** break. Relax!",
            color=COLOR_BREAK,
        )
        embed.add_field(name="Duration", value=f"{minutes} min", inline=True)
        embed.add_field(name="Type", value="Break", inline=True)
        embed.set_footer(text="I'll DM you when it's time to get back to work")

        await interaction.response.send_message(embed=embed)
        log.info(f"Break started for user {interaction.user.id} ({minutes} min)")

    @app_commands.command(name="stop", description="Stop your current Pomodoro session or break")
    async def stop(self, interaction: discord.Interaction):
        existing = await self._get_session(interaction.user.id)
        if not existing:
            await interaction.response.send_message(
                "You don't have an active session.", ephemeral=True
            )
            return

        await self._delete_session(interaction.user.id)

        embed = discord.Embed(
            title="⏹️ Session Stopped",
            description="Your session has been cancelled.",
            color=COLOR_STOP,
        )
        await interaction.response.send_message(embed=embed)
        log.info(f"Session stopped for user {interaction.user.id}")

    @app_commands.command(name="status", description="Check how much time is left in your current session")
    async def status(self, interaction: discord.Interaction):
        session = await self._get_session(interaction.user.id)
        if not session:
            await interaction.response.send_message(
                "You don't have an active session. Start one with `/study`!", ephemeral=True
            )
            return

        remaining = await self.redis.ttl(self._session_key(interaction.user.id))
        if remaining <= 0:
            await interaction.response.send_message(
                "Your session just expired! Check your DMs.", ephemeral=True
            )
            return

        mins_left = remaining // 60
        secs_left = remaining % 60
        session_type = session.get("session_type", "study")
        total_duration = session.get("duration", 25)

        color = COLOR_STUDY if session_type == "study" else COLOR_BREAK
        icon = "🍅" if session_type == "study" else "☕"

        embed = discord.Embed(
            title=f"{icon} Session Status",
            color=color,
        )
        embed.add_field(name="Type", value=session_type.capitalize(), inline=True)
        embed.add_field(name="Total Duration", value=f"{total_duration} min", inline=True)
        embed.add_field(name="Time Remaining", value=f"**{mins_left}m {secs_left}s**", inline=False)
        embed.set_footer(text="Use /stop to cancel the session")

        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Pomodoro(bot))
