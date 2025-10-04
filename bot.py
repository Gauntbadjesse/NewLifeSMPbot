import discord
from discord.ext import commands
import asyncio
import json
import os
import sys
from datetime import datetime
import traceback
from config import GUILD_ID, OWNER_ID, LOG_CHANNEL_ID, validate_config

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True

_log_throttle = {}
_log_throttle_window = 10
_log_last_message = None

bot = commands.Bot(command_prefix='!', intents=intents)

try:
    validate_config()
except Exception as e:
    print(f"Config validation failed: {e}")
    sys.exit(1)

async def bot_log(message, *, error=False, force=False, exc_info=None):
    """Send a log message to the logging channel, with throttling."""
    global _log_last_message
    now = datetime.now().timestamp()
    key = (message[:40], error)
    if not force and key in _log_throttle and now - _log_throttle[key] < _log_throttle_window:
        return
    _log_throttle[key] = now
    channel = bot.get_channel(LOG_CHANNEL_ID)
    if channel:
        try:
            content = f"[{'ERROR' if error else 'LOG'}] {message}"
            if exc_info:
                tb = ''.join(traceback.format_exception(None, exc_info, exc_info.__traceback__))
                content += f"\n```{tb[-1500:]}```"
            _log_last_message = await channel.send(content)
        except Exception as e:
            print(f"[BOT-LOG] Could not send log: {e}")
    else:
        print(f"[BOT-LOG] {message}")

@bot.event
async def on_ready():
    await bot_log(f'{bot.user} has connected to Discord!')
    await bot_log(f'Bot is in {len(bot.guilds)} guild(s)')
    await bot_log(f"[Bot] Bot started successfully.")
    await update_server_data()
    await load_cogs()
    try:
        guild = bot.get_guild(GUILD_ID)
        if guild is not None:
            synced = await bot.tree.sync(guild=guild)
            await bot_log(f"Slash commands synced to guild {guild.id}: {len(synced)} command(s)")
        else:
            synced = await bot.tree.sync()
            await bot_log(f"Global slash commands synced: {len(synced)} command(s)")
    except Exception as e:
        await bot_log(f"Failed to sync application commands: {e}", error=True, exc_info=e)

async def update_server_data():
    """Update server channels and roles data"""
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print(f"Error: Could not find guild with ID {GUILD_ID}")
        return

    server_data = {
        "guild_name": guild.name,
        "guild_id": guild.id,
        "last_updated": datetime.now().isoformat(),
        "channels": {},
        "roles": {},
        "member_count": guild.member_count
    }

    for category in guild.categories:
        server_data["channels"][category.name] = {
            "category_id": category.id,
            "channels": []
        }
        for channel in category.channels:
            channel_info = {
                "name": channel.name,
                "id": channel.id,
                "type": str(channel.type)
            }
            server_data["channels"][category.name]["channels"].append(channel_info)

    uncategorized_channels = [ch for ch in guild.channels if not ch.category]
    if uncategorized_channels:
        server_data["channels"]["Uncategorized"] = {
            "category_id": None,
            "channels": []
        }
        for channel in uncategorized_channels:
            channel_info = {
                "name": channel.name,
                "id": channel.id,
                "type": str(channel.type)
            }
            server_data["channels"]["Uncategorized"]["channels"].append(channel_info)

    for role in guild.roles:
        server_data["roles"][role.name] = {
            "id": role.id,
            "position": role.position,
            "permissions": role.permissions.value,
            "color": str(role.color),
            "mentionable": role.mentionable,
            "hoisted": role.hoist
        }

    data_dir = os.path.join(os.path.dirname(__file__), "data")
    try:
        os.makedirs(data_dir, exist_ok=True)
        with open(os.path.join(data_dir, "server_data.json"), "w", encoding="utf-8") as f:
            json.dump(server_data, f, indent=2, ensure_ascii=False)
        print(f"Server data updated for {guild.name}")
    except Exception as e:
        print(f"Could not save server data to data folder: {e}")
        try:
            with open("server_data.json", "w", encoding="utf-8") as f:
                json.dump(server_data, f, indent=2, ensure_ascii=False)
            print(f"Server data saved as server_data.json in current directory")
        except Exception as e2:
            print(f"Could not save server data anywhere: {e2}")

async def load_cogs():
    """Load all cogs from the cogs folder"""
    cogs_path = os.path.join(os.path.dirname(__file__), "cogs")
    if not os.path.exists(cogs_path):
        print("Cogs folder not found")
        return

    for filename in os.listdir(cogs_path):
        if filename.endswith(".py") and not filename.startswith("__"):
            try:
                await bot.load_extension(f"cogs.{filename[:-3]}")
                print(f"Loaded cog: {filename[:-3]}")
            except Exception as e:
                print(f"Failed to load cog {filename}: {e}")

    try:
        await bot.load_extension("minecraft_integration")
        print("Loaded: minecraft_integration")
    except Exception as e:
        print(f"Minecraft integration not loaded: {e}")
        print("Create minecraft_config.txt to enable Minecraft integration")

    try:
        await bot.load_extension("minecraft_linking")
        print("Loaded: minecraft_linking")
    except Exception as e:
        print(f"Minecraft linking not loaded: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler with logging"""
    if isinstance(error, commands.CommandNotFound):
        return
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("You don't have permission to use this command.")
        await bot_log(f"MissingPermissions: {ctx.author} tried {ctx.command}", error=True)
    else:
        await bot_log(f"Error in command {getattr(ctx, 'command', None)}: {error}", error=True, exc_info=error)
        await ctx.send("An error occurred while processing the command.")

@bot.command(name='botstatus')
@commands.is_owner()
async def bot_status(ctx):
    """Show bot health and integration status."""
    status = [f"Bot is online as {bot.user}"]
    loaded = list(bot.cogs.keys())
    status.append(f"Loaded cogs: {', '.join(loaded) if loaded else 'None'}")
    mc_cog = bot.get_cog('MinecraftIntegration')
    if mc_cog and hasattr(mc_cog, 'rcon') and mc_cog.rcon:
        try:
            resp = await mc_cog.rcon.send_command('list')
            status.append(f"RCON: Connected (list: {resp[:50] if resp else 'no response'})")
        except Exception as e:
            status.append(f"RCON: Error - {e}")
    else:
        status.append("RCON: Not connected")
    await ctx.send("\n".join(status))

def is_owner():
    """Check if user is the bot owner"""
    def predicate(ctx):
        return ctx.author.id == OWNER_ID
    return commands.check(predicate)

if __name__ == "__main__":
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    try:
        os.makedirs(data_dir, exist_ok=True)
        print("Data directory created successfully")
    except Exception as e:
        print(f"Could not create data directory: {e}")
        print("Will use current directory for data files")

    try:
        with open("token.txt", "r") as f:
            content = f.read().strip()
            if "=" in content:
                token = content.split("=", 1)[1].strip()
            else:
                token = content

        if not token:
            print("Error: No token found in token.txt")
            exit(1)

    except FileNotFoundError:
        print("Error: token.txt file not found")
        exit(1)
    except Exception as e:
        print(f"Error reading token.txt: {e}")
        exit(1)

    bot.run(token)
