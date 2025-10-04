import discord
from discord.ext import commands
import time
import asyncio
from bot import bot_log

class BasicCommands(commands.Cog):

    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='ping')
    async def ping(self, ctx):
        start_time = time.time()
        message = await ctx.send("Pinging...")
        end_time = time.time()

        api_latency = round(self.bot.latency * 1000, 2)
        message_latency = round((end_time - start_time) * 1000, 2)

        embed = discord.Embed(
            title="Pong!",
            color=discord.Color.green()
        )
        embed.add_field(name="API Latency", value=f"{api_latency}ms", inline=True)
        embed.add_field(name="Message Latency", value=f"{message_latency}ms", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.name}")

        await message.edit(content="", embed=embed)

        await bot_log(f"[Basic] Ping command used by {ctx.author}")

    @commands.command(name='info')
    async def info_command(self, ctx):
        """Display bot information"""
        guild = ctx.guild

        embed = discord.Embed(
            title="Bot Information",
            description="Minimal Discord bot for single server use",
            color=discord.Color.blue()
        )
        embed.add_field(name="Server", value=guild.name, inline=True)
        embed.add_field(name="Members", value=guild.member_count, inline=True)
        embed.add_field(name="Channels", value=len(guild.channels), inline=True)
        embed.add_field(name="Roles", value=len(guild.roles), inline=True)
        embed.set_thumbnail(url=self.bot.user.avatar.url if self.bot.user.avatar else None)

        await ctx.send(embed=embed)

        await bot_log(f"[Basic] Info command used by {ctx.author}")

    @commands.command(name='wldelete')
    async def wl_delete(self, ctx):
        """Delete all channels in specified category (Owner only)"""
        authorized_users = [1374421925790482483, 1099560849250729994, 1254852198505119853]
        if ctx.author.id not in authorized_users:
            await ctx.send("✖ You don't have permission to use this command.")
            return

        category_id = 1387287352426106922
        category = self.bot.get_channel(category_id)

        if not category or not isinstance(category, discord.CategoryChannel):
            await ctx.send("✖ Category not found.")
            return

        channels_to_delete = category.channels.copy()

        if not channels_to_delete:
            await ctx.send(f"No channels found in category '{category.name}'.")
            return

        embed = discord.Embed(
            title="Channel Deletion Warning",
            description=f"This will delete **{len(channels_to_delete)}** channels from category '{category.name}':",
            color=discord.Color.red()
        )

        channel_list = "\n".join([f"• {ch.name}" for ch in channels_to_delete[:10]])
        if len(channels_to_delete) > 10:
            channel_list += f"\n... and {len(channels_to_delete) - 10} more"

        embed.add_field(name="Channels to delete:", value=channel_list, inline=False)
        embed.set_footer(text="React with ✔ to confirm or ✖ to cancel")

        message = await ctx.send(embed=embed)
        await message.add_reaction("✔")
        await message.add_reaction("✖")

        def check(reaction, user):
            return user == ctx.author and str(reaction.emoji) in ["✔", "✖"] and reaction.message.id == message.id

        try:
            reaction, user = await self.bot.wait_for('reaction_add', timeout=30.0, check=check)

            if str(reaction.emoji) == "✖":
                await ctx.send("✖ Channel deletion cancelled.")
                return

            deleted_count = 0
            failed_count = 0

            status_embed = discord.Embed(
                title="Deleting Channels...",
                description="Please wait while channels are being deleted.",
                color=discord.Color.orange()
            )
            status_message = await ctx.send(embed=status_embed)

            for channel in channels_to_delete:
                try:
                    await channel.delete(reason=f"Bulk delete by {ctx.author}")
                    deleted_count += 1
                except Exception as e:
                    print(f"Failed to delete channel {channel.name}: {e}")
                    failed_count += 1
                    await bot_log(f"[Basic] Error deleting channel {channel.name}: {e}")

            result_embed = discord.Embed(
                title="✔ Channel Deletion Complete",
                color=discord.Color.green()
            )
            result_embed.add_field(name="Successfully deleted", value=str(deleted_count), inline=True)
            if failed_count > 0:
                result_embed.add_field(name="Failed to delete", value=str(failed_count), inline=True)

            await status_message.edit(embed=result_embed)

            await bot_log(f"[Basic] {deleted_count} channels deleted from category '{category.name}' by {ctx.author}")

        except asyncio.TimeoutError:
            await ctx.send("Confirmation timeout. Channel deletion cancelled.")
            await bot_log(f"[Basic] Channel deletion confirmation timeout for {ctx.author}")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(BasicCommands(bot))
