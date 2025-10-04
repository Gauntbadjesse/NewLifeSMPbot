import asyncio
import discord
from discord.ext import commands
from bot import bot_log

class MassDM(commands.Cog):
    """Temporary cog that provides a !dm command to DM all guild members."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.command(name="dm")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def dm_all(self, ctx: commands.Context):
        """DM everyone in this guild with a predefined embed. Avoids rate limits and reports results."""
        guild = ctx.guild
        if guild is None:
            await ctx.reply("This command can only be used in a server.")
            return

        title = "Come join The New Life SMP"
        description = (
            "As you already know Honbar was shutdown in December 2024. I will be deleting the discord on October 11th.\n"
            "To continue the legacy, We have created a new server, The New Life SMP. It is what Honbar was but better.\n"
            "**I hope to see you there.**\n"
            "https://discord.gg/yx5YmEqez9\n\n"
            "-Testn"
        )
        embed = discord.Embed(title=title, description=description, color=discord.Color.green())

        ack = await ctx.reply(
            f"Starting to DM members of **{guild.name}**. This may take a while...\n"
            "I'll post a summary when finished."
        )

        sent = 0
        failed = 0
        skipped = 0

        delay_seconds = 1.25

        members = guild.members
        if not members or len(members) < guild.member_count:
            try:
                await guild.fetch_members(limit=None).flatten()
                members = guild.members
            except Exception:
                pass

        for member in members:
            if member.bot:
                skipped += 1
                continue
            try:
                await member.send(embed=embed)
                sent += 1
                await bot_log(f"[Temp] Mass DM sent to {member} by {ctx.author}")
            except (discord.Forbidden, discord.HTTPException) as e:
                failed += 1
                await bot_log(f"[Temp] Error sending DM to {member}: {e}")
            await asyncio.sleep(delay_seconds)

        try:
            await ack.edit(
                content=(
                    f"DM campaign finished for **{guild.name}**.\n"
                    f"Sent: **{sent}** | Failed (DMs closed or other): **{failed}** | Skipped (bots): **{skipped}**."
                )
            )
        except Exception:
            await ctx.send(
                f"DM campaign finished. Sent: **{sent}**, Failed: **{failed}**, Skipped: **{skipped}**."
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(MassDM(bot))
