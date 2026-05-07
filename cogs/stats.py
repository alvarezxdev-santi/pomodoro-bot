import logging
from typing import Optional

import discord
import redis.asyncio as aioredis
from discord import app_commands
from discord.ext import commands

log = logging.getLogger("pomodoro-bot.stats")

COLOR_STATS = 0xF8C630   # warm yellow
COLOR_LEADERBOARD = 0xA259FF  # purple

MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


class Stats(commands.Cog):
    """Slash commands for viewing study statistics and the leaderboard."""

    def __init__(self, bot: commands.Bot):
        super().__init__()
        self.bot = bot
        self.redis: Optional[aioredis.Redis] = None

    async def cog_load(self):
        self.redis = aioredis.from_url(
            self.bot.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        log.info("Redis connection established (Stats cog)")

    async def cog_unload(self):
        if self.redis:
            await self.redis.aclose()

    # ------------------------------------------------------------------
    # Slash commands
    # ------------------------------------------------------------------

    @app_commands.command(name="mystats", description="View your personal study statistics")
    async def mystats(self, interaction: discord.Interaction):
        stats_key = f"stats:{interaction.user.id}"
        raw = await self.redis.hgetall(stats_key)

        total_sessions = int(raw.get("total_sessions", 0))
        total_minutes = int(raw.get("total_minutes", 0))
        total_hours = total_minutes // 60
        leftover_mins = total_minutes % 60

        embed = discord.Embed(
            title=f"📊 Study Stats — {interaction.user.display_name}",
            color=COLOR_STATS,
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if total_sessions == 0:
            embed.description = (
                "No sessions completed yet. Start your first one with `/study`!"
            )
        else:
            embed.add_field(
                name="🍅 Total Sessions",
                value=str(total_sessions),
                inline=True,
            )
            embed.add_field(
                name="⏱️ Total Time",
                value=f"{total_hours}h {leftover_mins}m" if total_hours > 0 else f"{total_minutes}m",
                inline=True,
            )

            # Simple motivational tier
            if total_sessions >= 50:
                tier = "🔥 Pomodoro Master"
            elif total_sessions >= 20:
                tier = "⭐ Dedicated Studier"
            elif total_sessions >= 5:
                tier = "📚 Getting into the groove"
            else:
                tier = "🌱 Just getting started"

            embed.add_field(name="Rank", value=tier, inline=False)

        embed.set_footer(text="Complete a /study session to earn stats")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="See the top 5 studiers on the server")
    async def leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()  # fetching users can take a moment

        # Collect all stats keys
        all_stats = []
        async for key in self.redis.scan_iter("stats:*"):
            try:
                user_id = int(key.split(":")[1])
            except (IndexError, ValueError):
                continue

            raw = await self.redis.hgetall(key)
            total_sessions = int(raw.get("total_sessions", 0))
            total_minutes = int(raw.get("total_minutes", 0))

            if total_sessions > 0:
                all_stats.append(
                    {
                        "user_id": user_id,
                        "total_sessions": total_sessions,
                        "total_minutes": total_minutes,
                    }
                )

        # Sort by total_minutes desc, then sessions as tiebreaker
        all_stats.sort(key=lambda x: (x["total_minutes"], x["total_sessions"]), reverse=True)
        top5 = all_stats[:5]

        embed = discord.Embed(
            title="🏆 Study Leaderboard",
            description="Top 5 studiers this server",
            color=COLOR_LEADERBOARD,
        )

        if not top5:
            embed.description = "No sessions logged yet. Be the first with `/study`!"
        else:
            lines = []
            for i, entry in enumerate(top5):
                medal = MEDALS[i]
                user_id = entry["user_id"]
                total_minutes = entry["total_minutes"]
                total_sessions = entry["total_sessions"]
                hours = total_minutes // 60
                mins = total_minutes % 60
                time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"

                # Try to resolve the display name
                user = self.bot.get_user(user_id)
                if user is None:
                    try:
                        user = await self.bot.fetch_user(user_id)
                        name = user.display_name
                    except discord.NotFound:
                        name = f"Unknown ({user_id})"
                else:
                    name = user.display_name

                lines.append(
                    f"{medal} **{name}** — {time_str} ({total_sessions} session{'s' if total_sessions != 1 else ''})"
                )

            embed.description = "\n".join(lines)

        embed.set_footer(text="Stats update after each completed session")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Stats(bot))
