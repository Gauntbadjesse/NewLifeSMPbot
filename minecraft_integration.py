import asyncio
import struct
import socket
import json
import os
from typing import Optional
import discord
from discord.ext import commands
from aiohttp import web
import threading
from config import RCON_CONSOLE_CHANNEL_ID, RCON_MSG_CHANNEL_ID, RCON_VOTE_CHANNEL_ID, RCON_RESPONSE_CHANNEL_ID
from bot import bot_log

class MinecraftRCON:
    """RCON client for Minecraft server communication"""

    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self.socket = None
        self.request_id = 0
        self.debug = False
        self.retry_interval = 300

    async def connect(self):
        """Connect to the Minecraft server via RCON with retry mechanism"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                if not self.debug:
                    print(f"🔄 Attempting RCON connection ({attempt + 1}/{max_retries})...")

                self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.socket.settimeout(10)
                self.socket.connect((self.host, self.port))

                auth_response = await self._send_packet(3, self.password)
                if auth_response is None:
                    raise Exception("RCON authentication failed - invalid password or RCON disabled")

                if not self.debug:
                    print(f"✅ RCON connected to {self.host}:{self.port}")
                return True

            except (ConnectionRefusedError, socket.timeout, Exception) as e:
                if attempt < max_retries - 1:
                    print(f"❌ Connection attempt {attempt + 1} failed, retrying in 30s...")
                    await asyncio.sleep(30)
                    continue
                else:
                    print(f"❌ All RCON connection attempts failed: {e}")
                    return False
        return False

    async def disconnect(self):
        """Disconnect from RCON"""
        if self.socket:
            self.socket.close()
            self.socket = None

    async def send_command(self, command: str) -> Optional[str]:
        """Send a command to the Minecraft server"""
        if not self.socket:
            if not await self.connect():
                return None

        for attempt in (1, 2):
            try:
                response = await self._send_packet(2, command)
                await bot_log(f"[RCON] Command sent: {command} | Response: {str(response)[:100]}")
                return response
            except Exception as e:
                await bot_log(f"[RCON] Error sending command '{command}': {e}", error=True, exc_info=e)
                try:
                    await self.disconnect()
                except Exception:
                    pass
                if attempt == 1:
                    if not await self.connect():
                        return None
                else:
                    return None

    async def _send_packet(self, packet_type: int, data: str) -> Optional[str]:
        """Send RCON packet and return response"""
        self.request_id += 1

        try:
            packet_data = struct.pack('<ii', self.request_id, packet_type) + data.encode('utf-8') + b'\x00\x00'
            packet = struct.pack('<i', len(packet_data)) + packet_data

            self.socket.send(packet)

            length_data = b''
            while len(length_data) < 4:
                chunk = self.socket.recv(4 - len(length_data))
                if not chunk:
                    raise Exception("Connection closed while reading response length")
                length_data += chunk

            response_length = struct.unpack('<i', length_data)[0]

            response_data = b''
            while len(response_data) < response_length:
                chunk = self.socket.recv(response_length - len(response_data))
                if not chunk:
                    raise Exception("Connection closed while reading response data")
                response_data += chunk

            if len(response_data) < 8:
                raise Exception(f"Response too short: {len(response_data)} bytes, expected at least 8")

            response_id, response_type = struct.unpack('<ii', response_data[:8])
            response_body = response_data[8:-2].decode('utf-8') if len(response_data) > 10 else ""

            return response_body if response_body else "Command executed successfully"

        except struct.error as e:
            raise Exception(f"RCON protocol error: {e}")
        except socket.error as e:
            raise Exception(f"Socket error: {e}")
        except Exception as e:
            raise Exception(f"Packet error: {e}")

class MinecraftIntegration(commands.Cog):
    """Discord-Minecraft integration commands"""

    def __init__(self, bot):
        self.bot = bot
        self.rcon = None
        self.guild_id = None
        self.console_channel_id = RCON_CONSOLE_CHANNEL_ID
        self.msg_channel_id = RCON_MSG_CHANNEL_ID
        self.vote_channel_id = RCON_VOTE_CHANNEL_ID
        self.response_channel_id = RCON_RESPONSE_CHANNEL_ID
        self.console_channel = None
        self.msg_channel = None
        self.status_channel = None
        self.vote_state_path = os.path.join("data", "vote_state.json")
        self.vote_state = {}
        self.rcon_key = None
        self._vote_poll_initialized = False

        self.retry_task = None
        self.monitoring_task = None
        self.vote_server = None
        self.vote_channel_id = 1417983368057978961
        self.rcon_poll_seq = 0
        self.debug_votes = False

        self.load_minecraft_config()

    def load_minecraft_config(self):
        """Load Minecraft server configuration"""
        try:
            if os.path.exists("minecraft_config.txt"):
                with open("minecraft_config.txt", "r") as f:
                    lines = f.read().strip().split('\n')
                    config = {}
                    for line in lines:
                        if '=' in line:
                            key, value = line.split('=', 1)
                            config[key.strip()] = value.strip()
                    self.rcon = MinecraftRCON(
                        host=config.get('MC_HOST', 'localhost'),
                        port=int(config.get('MC_RCON_PORT', 25575)),
                        password=config.get('MC_RCON_PASSWORD', '')
                    )
                    self.rcon_key = f"{self.rcon.host}:{self.rcon.port}"
                    self._load_vote_state()
                    saved_seq = self._get_saved_last_seq()
                    if saved_seq:
                        self.rcon_poll_seq = saved_seq
                        if self.debug_votes:
                            print(f"\U0001F4BE [VOTE-DEBUG] Loaded persisted last_seq={saved_seq} for {self.rcon_key}")
            else:
                print("\u26A0\ufe0f minecraft_config.txt not found. RCON integration disabled.")
                print("Create minecraft_config.txt with:")
                print("MC_HOST=your_server_ip")
                print("MC_RCON_PORT=25575")
                print("MC_RCON_PASSWORD=your_rcon_password")
        except Exception as e:
            print(f"Error loading Minecraft config: {e}")

    async def log_rcon_config_status(self, success=True, error=None):
        if success and self.rcon:
            await bot_log(f"[RCON] Loaded config and initialized RCON for {self.rcon.host}:{self.rcon.port}")
        elif error:
            await bot_log(f"[RCON] Failed to load config or initialize RCON: {error}", error=True, exc_info=error)

    async def cog_load(self):
        """Initialize RCON connection and create channels when cog loads"""
        await self.setup_channels()
        try:
            if self.rcon:
                await self.log_rcon_config_status(success=True)
            else:
                await self.log_rcon_config_status(success=False, error="Config missing or invalid")
        except Exception as e:
            await self.log_rcon_config_status(success=False, error=e)
        if self.rcon:
            connected = await self.rcon.connect()
            if not connected:
                self.retry_task = asyncio.create_task(self.retry_connection())
            else:
                self.monitoring_task = asyncio.create_task(self.poll_vote_logs())
        await self.start_vote_server()

    def _load_vote_state(self):
        try:
            if os.path.exists(self.vote_state_path):
                with open(self.vote_state_path, 'r') as f:
                    self.vote_state = json.load(f)
            else:
                self.vote_state = {}
        except Exception as e:
            print(f"⚠️ Failed to load vote state: {e}")
            self.vote_state = {}

    def _save_vote_state(self):
        try:
            os.makedirs(os.path.dirname(self.vote_state_path), exist_ok=True)
            with open(self.vote_state_path, 'w') as f:
                json.dump(self.vote_state, f, indent=2)
        except Exception as e:
            print(f"⚠️ Failed to save vote state: {e}")

    def _get_saved_last_seq(self) -> int:
        try:
            if self.rcon_key and self.vote_state.get(self.rcon_key):
                return int(self.vote_state[self.rcon_key].get('last_seq', 0))
        except Exception:
            pass
        return 0

    def _update_last_seq(self, seq: int):
        if not self.rcon_key:
            return
        try:
            entry = self.vote_state.get(self.rcon_key, {})
            if 'last_seq' not in entry or int(entry['last_seq']) < seq:
                self.vote_state[self.rcon_key] = {
                    'last_seq': int(seq),
                    'updated_at': discord.utils.utcnow().isoformat()
                }
                self._save_vote_state()
                if self.debug_votes:
                    print(f"💾 [VOTE-DEBUG] Persisted last_seq={seq} for {self.rcon_key}")
        except Exception as e:
            print(f"⚠️ Failed to update last_seq persistence: {e}")

    async def setup_channels(self):
        """Setup channels using specific channel IDs"""
        guild = self.bot.get_guild(self.guild_id)
        if not guild:
            print(f"❌ Guild {self.guild_id} not found!")
            return

        console_channel = self.bot.get_channel(self.console_channel_id)
        msg_channel = self.bot.get_channel(self.msg_channel_id)

        if not console_channel:
            print(f"❌ Console channel {self.console_channel_id} not found!")
        else:
            print(f"✅ Using console channel: #{getattr(console_channel, 'name', 'unknown')} (ID: {getattr(console_channel, 'id', 'n/a')})")

        if not msg_channel:
            print(f"❌ Messages channel {self.msg_channel_id} not found!")
        else:
            print(f"✅ Using messages channel: #{getattr(msg_channel, 'name', 'unknown')} (ID: {getattr(msg_channel, 'id', 'n/a')})")

        status_channel = discord.utils.get(guild.channels, name="minecraft-status")
        if not status_channel:
            try:
                status_channel = await guild.create_text_channel(
                    "minecraft-status",
                    topic="Minecraft server start/stop notifications"
                )
                print(f"✅ Created status channel: #{getattr(status_channel, 'name', 'minecraft-status')} (ID: {getattr(status_channel, 'id', 'n/a')})")
            except Exception as e:
                print(f"❌ Failed to create status channel: {e}")
        else:
            print(f"✅ Using status channel: #{getattr(status_channel, 'name', 'minecraft-status')} (ID: {getattr(status_channel, 'id', 'n/a')})")

        self.console_channel = console_channel
        self.msg_channel = msg_channel
        self.status_channel = status_channel

    async def start_vote_server(self):
        """Start HTTP server to receive vote notifications from Minecraft plugin"""
        try:
            app = web.Application()
            app.router.add_post('/vote-notification', self.handle_vote_notification)

            runner = web.AppRunner(app)
            await runner.setup()

            site = web.TCPSite(runner, 'localhost', 8080)
            await site.start()

            self.vote_server = runner
            print("✅ Vote notification server started on http://localhost:8080")

        except Exception as e:
            print(f"❌ Failed to start vote server: {e}")
            print("Vote notifications will not work until this is resolved")

    async def handle_vote_notification(self, request):
        """Handle incoming vote notifications from Minecraft plugin"""
        try:
            data = await request.json()
            channel_id = int(data.get('channel_id', self.vote_channel_id))
            embed_data = data.get('embed', {})

            vote_channel = self.bot.get_channel(channel_id)
            if not vote_channel:
                print(f"❌ Vote channel {channel_id} not found!")
                return web.Response(text="Channel not found", status=404)

            embed = discord.Embed(
                title=embed_data.get('title', 'Vote Received'),
                description=embed_data.get('description', 'Thank you for voting!'),
                color=embed_data.get('color', 0x00D4AA)
            )

            if 'timestamp' in embed_data:
                embed.timestamp = discord.utils.utcnow()

            if 'footer' in embed_data and embed_data['footer'].get('text'):
                embed.set_footer(text=embed_data['footer']['text'])

            await vote_channel.send(embed=embed)
            print(f"✅ Vote notification sent to #{getattr(vote_channel, 'name', 'unknown')} (ID: {getattr(vote_channel, 'id', 'n/a')})")

            return web.Response(text="Vote notification sent", status=200)

        except Exception as e:
            print(f"❌ Error handling vote notification: {e}")
            return web.Response(text="Internal server error", status=500)

    async def process_vote_from_console(self, console_message):
        """Process vote notifications from console messages (fallback method)"""
        try:
            if self.debug_votes:
                print(f"🔍 [VOTE-DEBUG] Processing console message: {console_message}")
            lower = console_message.lower()
            if self.debug_votes:
                print(f"🔎 [VOTE-DEBUG] Lowercase check: '{lower[:120]}...' ")

            if ("[votifier]" in lower) or ("protocol v1 vote record" in lower and "vote (from:" in lower):
                if self.debug_votes:
                    print(f"🎯 [VOTE-DEBUG] Detected Votifier-style message (tagged: {'[votifier]' in lower})")
                import re

                pattern = r"Vote \(from:([^\s]+) username:([^\s]+) address:"
                if self.debug_votes:
                    print(f"🧩 [VOTE-DEBUG] Using regex: {pattern}")
                vote_match = re.search(pattern, console_message, re.IGNORECASE)
                if vote_match:
                    service_name = vote_match.group(1)
                    player_name = vote_match.group(2)
                    if self.debug_votes:
                        print(f"✅ [VOTE-DEBUG] Parsed Votifier vote - Service: '{service_name}', Player: '{player_name}'")

                    vote_channel = self.bot.get_channel(self.vote_channel_id)
                    if not vote_channel:
                        if self.debug_votes:
                            print(f"❌ [VOTE-DEBUG] Vote channel {self.vote_channel_id} not found!")
                        return

                    if "planetminecraft" in service_name.lower() or "pmc" in service_name.lower():
                        if self.debug_votes:
                            print(f"🌟 [VOTE-DEBUG] Processing PMC vote for {player_name}")
                        description = (f"**🗳️ Thank you {player_name} for voting for us on PMC!**\n\n"
                                     f"🌟 **Your vote helps our server grow!**\n"
                                     f"🎮 **Player:** `{player_name}`\n"
                                     f"📊 **Vote Site:** PlanetMinecraft.com\n\n"
                                     f"**[🔗 Vote for us on PMC!](https://www.planetminecraft.com/server/the-new-life/)**\n\n"
                                     f"💰 *Vote rewards have been automatically given!*")

                        embed = discord.Embed(
                            title="🗳️ New Vote Received!",
                            description=description,
                            color=0x00D4AA,
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_footer(text="Vote System • Minecraft Server")

                        await vote_channel.send(embed=embed)
                        if self.debug_votes:
                            print(f"✅ [VOTE-DEBUG] PMC vote notification sent for {player_name}")
                    else:
                        if self.debug_votes:
                            print(f"🎮 [VOTE-DEBUG] Processing generic vote for {player_name} from {service_name}")
                        description = (f"**🗳️ Thank you {player_name} for voting!**\n\n"
                                     f"🎮 **Player:** `{player_name}`\n"
                                     f"📊 **Vote Site:** {service_name}\n\n"
                                     f"💰 *Vote rewards have been automatically given!*")

                        embed = discord.Embed(
                            title="🗳️ New Vote Received!",
                            description=description,
                            color=0x00D4AA,
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_footer(text="Vote System • Minecraft Server")

                        await vote_channel.send(embed=embed)
                        if self.debug_votes:
                            print(f"✅ [VOTE-DEBUG] Generic vote notification sent for {player_name} from {service_name}")
                else:
                    if self.debug_votes:
                        print(f"⚠️ [VOTE-DEBUG] Could not parse Votifier message format with pattern: {pattern}")
                        print(f"   Raw message: {console_message}")
                return

            if "[votingplugin]" in lower or ("received a vote from service site" in lower and "by player" in lower):
                if self.debug_votes:
                    print(f"🎯 [VOTE-DEBUG] Detected VotingPlugin-style message")
                import re
                match = re.search(r"service site '([^']+)' by player '([^']+)'", console_message, re.IGNORECASE)
                if match:
                    service_name = match.group(1)
                    player_name = match.group(2)

                    vote_channel = self.bot.get_channel(self.vote_channel_id)
                    if not vote_channel:
                        if self.debug_votes:
                            print(f"❌ Vote channel {self.vote_channel_id} not found!")
                        return

                    if "planetminecraft" in service_name.lower() or "pmc" in service_name.lower():
                        description = f"**🗳️ Thank you {player_name} for voting for us on PMC!**\n\n" \
                                    f"🌟 **Your vote helps our server grow!**\n" \
                                    f"🎮 **Player:** `{player_name}`\n" \
                                    f"📊 **Vote Site:** PlanetMinecraft.com\n\n" \
                                    f"**[🔗 Vote for us on PMC!](https://www.planetminecraft.com/server/the-new-life/)**\n\n" \
                                    f"💰 *Vote rewards have been automatically given!*"

                        embed = discord.Embed(
                            title="🗳️ New Vote Received!",
                            description=description,
                            color=0x00D4AA,
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_footer(text="Vote System • Minecraft Server")

                        await vote_channel.send(embed=embed)
                        if self.debug_votes:
                            print(f"✅ PMC vote notification sent for {player_name}")
                    else:
                        description = f"**🗳️ Thank you {player_name} for voting!**\n\n" \
                                    f"🎮 **Player:** `{player_name}`\n" \
                                    f"📊 **Vote Site:** {service_name}\n\n" \
                                    f"💰 *Vote rewards have been automatically given!*"

                        embed = discord.Embed(
                            title="🗳️ New Vote Received!",
                            description=description,
                            color=0x00D4AA,
                            timestamp=discord.utils.utcnow()
                        )
                        embed.set_footer(text="Vote System • Minecraft Server")

                        await vote_channel.send(embed=embed)
                        if self.debug_votes:
                            print(f"✅ Vote notification sent for {player_name} from {service_name}")
                else:
                    if self.debug_votes:
                        print("⚠️ [VOTE-DEBUG] Could not parse VotingPlugin message with expected pattern")
                        print(f"   Raw message: {console_message}")
            else:
                if self.debug_votes:
                    print("ℹ️ [VOTE-DEBUG] Message did not match any known vote patterns.")

        except Exception as e:
            print(f"❌ Error processing vote from console: {e}")

    async def retry_connection(self):
        """Retry RCON connection every 5 minutes"""
        while True:
            await asyncio.sleep(300)
            if self.rcon and not self.rcon.socket:
                print("🔄 Retrying RCON connection...")
                if await self.rcon.connect():
                    print("✅ RCON reconnected successfully!")
                    if not self.monitoring_task or self.monitoring_task.done():
                        self.monitoring_task = asyncio.create_task(self.poll_vote_logs())
                    break

    async def cog_unload(self):
        """Cleanup RCON connection when cog unloads"""
        if self.retry_task:
            self.retry_task.cancel()
        if self.monitoring_task:
            self.monitoring_task.cancel()
        if self.rcon:
            await self.rcon.disconnect()
        if self.vote_server:
            await self.vote_server.cleanup()

    @commands.command(name='testchannels')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def test_channels(self, ctx):
        """Test all logging channels"""
        embed = discord.Embed(
            title="🧪 Channel Test Results",
            color=discord.Color.blue(),
            timestamp=discord.utils.utcnow()
        )

        if self.console_channel:
            embed.add_field(
                name="⚡ Console Channel",
                value=f"✅ {self.console_channel.mention} (ID: {self.console_channel.id})",
                inline=False
            )
            await self.log_operator_command("TestUser", "test command")
        else:
            embed.add_field(
                name="⚡ Console Channel",
                value=f"❌ Not found (ID: {self.console_channel_id})",
                inline=False
            )

        if self.msg_channel:
            embed.add_field(
                name="💬 Messages Channel",
                value=f"✅ {self.msg_channel.mention} (ID: {self.msg_channel.id})",
                inline=False
            )
            await self.log_msg_command("TestSender", "TestRecipient", "Test message")
        else:
            embed.add_field(
                name="💬 Messages Channel",
                value=f"❌ Not found (ID: {self.msg_channel_id})",
                inline=False
            )

        if self.status_channel:
            embed.add_field(
                name="🟢 Status Channel",
                value=f"✅ {self.status_channel.mention} (ID: {self.status_channel.id})",
                inline=False
            )
            await self.log_server_status("start", "Test server start message")
        else:
            embed.add_field(
                name="🟢 Status Channel",
                value="❌ Not found",
                inline=False
            )

        await ctx.send(embed=embed)

    @commands.command(name='testmsg')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def test_msg_log(self, ctx, sender: str, recipient: str, *, message: str):
        """Test the /msg logging system"""
        await self.log_msg_command(sender, recipient, message)
        await ctx.send(f"✅ Test message logged: {sender} -> {recipient}")

    @commands.command(name='teststatus')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def test_status_log(self, ctx, status: str, *, message: str = "Test status message"):
        """Test the server status logging system"""
        if status.lower() not in ['start', 'stop']:
            await ctx.send("❌ Status must be 'start' or 'stop'")
            return

        await self.log_server_status(status.lower(), message)
        await ctx.send(f"✅ Test {status} status logged")

    @commands.command(name='update')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def update_nickname(self, ctx, user: discord.Member = None):
        """Update a user's nickname to their Minecraft name"""
        target_user = user or ctx.author

        linking_cog = self.bot.get_cog("MinecraftLinking")
        if not linking_cog:
            await ctx.send("❌ Linking system not available!")
            return

        mc_usernames = linking_cog.get_minecraft_usernames(str(target_user.id))
        if not mc_usernames:
            await ctx.send(f"❌ {target_user.mention} is not linked to any Minecraft accounts!")
            return

        try:
            primary_mc = mc_usernames[0]
            await target_user.edit(nick=primary_mc, reason=f"Updated by {ctx.author}")

            embed = discord.Embed(
                title="✅ Nickname Updated",
                description=f"Updated {target_user.mention}'s nickname to **{primary_mc}**",
                color=discord.Color.green()
            )
            if len(mc_usernames) > 1:
                embed.add_field(
                    name="Other Linked Accounts",
                    value=", ".join(mc_usernames[1:]),
                    inline=False
                )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("❌ I don't have permission to change that user's nickname!")
        except Exception as e:
            await ctx.send(f"❌ Failed to update nickname: {e}")

    @commands.command(name='linkcheck')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def check_linked_accounts(self, ctx, user: discord.Member):
        """Show all linked Minecraft accounts for a user"""
        linking_cog = self.bot.get_cog("MinecraftLinking")
        if not linking_cog:
            await ctx.send("❌ Linking system not available!")
            return

        mc_usernames = linking_cog.get_minecraft_usernames(str(user.id))

        if not mc_usernames:
            embed = discord.Embed(
                title="❌ No Linked Accounts",
                description=f"{user.mention} is not linked to any Minecraft accounts",
                color=discord.Color.red()
            )
        else:
            embed = discord.Embed(
                title="🔗 Linked Accounts",
                description=f"{user.mention} is linked to:",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="Minecraft Accounts",
                value="\n".join([f"• {username}" for username in mc_usernames]),
                inline=False
            )
            embed.add_field(name="Total", value=str(len(mc_usernames)), inline=True)

        await ctx.send(embed=embed)

    @commands.command(name='adminunlink')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def admin_unlink(self, ctx, user: discord.Member, minecraft_name: str):
        """Unlink a specific Minecraft account from a Discord user"""
        linking_cog = self.bot.get_cog("MinecraftLinking")
        if not linking_cog:
            await ctx.send("❌ Linking system not available!")
            return

        success = linking_cog.remove_link(str(user.id), minecraft_name)

        if success:
            embed = discord.Embed(
                title="🔓 Account Unlinked",
                description=f"Unlinked **{minecraft_name}** from {user.mention}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Staff Member", value=ctx.author.mention, inline=True)
            await ctx.send(embed=embed)

            if self.console_channel:
                log_embed = discord.Embed(
                    title="🔓 Admin Unlink",
                    description=f"{ctx.author.mention} unlinked **{minecraft_name}** from {user.mention}",
                    color=discord.Color.orange()
                )
                await self.console_channel.send(embed=log_embed)
        else:
            await ctx.send(f"❌ {minecraft_name} is not linked to {user.mention}!")

    @commands.command(name='mlink')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def manual_link(self, ctx, user: discord.Member, minecraft_name: str):
        """Manually link a Discord user to a Minecraft account"""
        linking_cog = self.bot.get_cog("MinecraftLinking")
        if not linking_cog:
            await ctx.send("❌ Linking system not available!")
            return

        linking_cog.add_link(str(user.id), minecraft_name)

        embed = discord.Embed(
            title="🔗 Manual Link Created",
            description=f"Manually linked {user.mention} to **{minecraft_name}**",
            color=discord.Color.green()
        )
        embed.add_field(name="Staff Member", value=ctx.author.mention, inline=True)
        await ctx.send(embed=embed)

        try:
            linked_role_id = 1422016465804202098
            role = ctx.guild.get_role(linked_role_id)
            if role:
                await user.add_roles(role, reason=f"Manually linked by {ctx.author}")
        except Exception as e:
            print(f"Failed to assign linked role: {e}")

        if self.console_channel:
            log_embed = discord.Embed(
                title="🔗 Manual Link",
                description=f"{ctx.author.mention} manually linked {user.mention} to **{minecraft_name}**",
                color=discord.Color.green()
            )
            await self.console_channel.send(embed=log_embed)

    @commands.command(name='mctest')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def test_connection(self, ctx):
        """Test the RCON connection to Minecraft server"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured! Check minecraft_config.txt")
            return

        embed = discord.Embed(title="🔧 RCON Connection Test", color=discord.Color.blue())
        embed.add_field(name="Host", value=self.rcon.host, inline=True)
        embed.add_field(name="Port", value=self.rcon.port, inline=True)
        embed.add_field(name="Password", value="*" * len(self.rcon.password), inline=True)

        try:
            success = await self.rcon.connect()
            if success:
                response = await self.rcon.send_command("list")
                embed.color = discord.Color.green()
                embed.add_field(name="Status", value="✅ Connected", inline=False)
                embed.add_field(name="Test Command", value="list", inline=True)
                embed.add_field(name="Response", value=response or "No response", inline=False)
            else:
                embed.color = discord.Color.red()
                embed.add_field(name="Status", value="❌ Connection Failed", inline=False)
                embed.add_field(name="Troubleshooting", value="• Check server is online\n• Verify RCON is enabled\n• Check host:port is correct\n• Verify password", inline=False)

        except Exception as e:
            embed.color = discord.Color.red()
            embed.add_field(name="Status", value="❌ Error", inline=False)
            embed.add_field(name="Error", value=str(e), inline=False)

        await ctx.send(embed=embed)

    async def log_operator_command(self, user, command):
        """Log operator commands to console channel"""
        if self.console_channel:
            embed = discord.Embed(
                title="⚡ Operator Command Used",
                description=f"**User:** {user}\n**Command:** `/{command}`",
                color=discord.Color.red(),
                timestamp=discord.utils.utcnow()
            )
            await self.console_channel.send(embed=embed)
        else:
            print(f"⚠️ Console channel not available for logging: {user} -> /{command}")

    async def log_msg_command(self, sender, recipient, message):
        """Log /msg commands to messages channel"""
        if self.msg_channel:
            embed = discord.Embed(
                title="💬 Private Message",
                description=f"**From:** {sender}\n**To:** {recipient}\n**Message:** {message}",
                color=discord.Color.blue(),
                timestamp=discord.utils.utcnow()
            )
            await self.msg_channel.send(embed=embed)
        else:
            print(f"⚠️ Messages channel not available for logging: {sender} -> {recipient}")

    async def log_server_status(self, status, message):
        """Log server start/stop events to status channel"""
        if self.status_channel:
            color = discord.Color.green() if status == "start" else discord.Color.red()
            emoji = "🟢" if status == "start" else "🔴"
            embed = discord.Embed(
                title=f"{emoji} Server {status.title()}",
                description=message,
                color=color,
                timestamp=discord.utils.utcnow()
            )
            await self.status_channel.send(embed=embed)
        else:
            print(f"⚠️ Status channel not available for logging: {status} -> {message}")

    @commands.Cog.listener()
    async def on_message(self, message):
        """Listen for server status messages from webhooks (reduced noise)"""
        if not getattr(message, 'webhook_id', None):
            return

        if message.embeds:
            embed = message.embeds[0]
            title = embed.title or ""
            description = embed.description or ""

            if "Server Started" in title:
                await self.log_server_status("start", "The Minecraft server has come online!")
            elif "Server Stopped" in title:
                await self.log_server_status("stop", "The Minecraft server has gone offline!")

            elif "/msg Command" in title or "Private Message" in title:
                if self.msg_channel:
                    clean_embed = discord.Embed(
                        title="💬 Private Message",
                        description=description,
                        color=discord.Color.blue(),
                        timestamp=discord.utils.utcnow()
                    )
                    await self.msg_channel.send(embed=clean_embed)

            elif "Admin Command" in title:
                if self.console_channel:
                    clean_embed = discord.Embed(
                        title="⚡ Admin Command Executed",
                        description=description,
                        color=discord.Color.red(),
                        timestamp=discord.utils.utcnow()
                    )
                    await self.console_channel.send(embed=clean_embed)

    async def poll_vote_logs(self):
        """Continuously poll Minecraft via RCON for recent vote-related console lines."""
        await asyncio.sleep(2)
        if self.debug_votes:
            print("📡 Starting RCON vote log polling...")
        while True:
            try:
                if not self.rcon:
                    await asyncio.sleep(10)
                    continue
                cmd = f"divotelog {self.rcon_poll_seq} 50"
                resp = await self.rcon.send_command(cmd)
                if not resp:
                    await asyncio.sleep(2)
                    continue
                json_start = resp.find('[')
                json_end = resp.rfind(']')
                if json_start == -1 or json_end == -1 or json_end < json_start:
                    if self.debug_votes:
                        print(f"⚠️ [POLL-DEBUG] Unexpected /divotelog response (no JSON array): {resp[:200]}...")
                    await asyncio.sleep(2)
                    continue
                data = json.loads(resp[json_start:json_end+1])
                if not isinstance(data, list):
                    if self.debug_votes:
                        print(f"⚠️ [POLL-DEBUG] Parsed JSON is not a list: {type(data)}")
                    await asyncio.sleep(2)
                    continue
                if not self._vote_poll_initialized:
                    self._vote_poll_initialized = True
                    if self.rcon_poll_seq == 0 and data:
                        max_seq = max((entry.get('seq', 0) or 0) for entry in data)
                        if max_seq:
                            if self.debug_votes:
                                print(f"⏭️  [POLL-DEBUG] Skipping initial backlog up to seq={max_seq}")
                            self.rcon_poll_seq = max_seq
                            self._update_last_seq(max_seq)
                            await asyncio.sleep(2)
                            continue
                if self.debug_votes:
                    print(f"📥 [POLL-DEBUG] Received {len(data)} vote log entr{'y' if len(data)==1 else 'ies'} (afterSeq={self.rcon_poll_seq})")
                for entry in data:
                    seq = entry.get('seq', 0)
                    line = entry.get('line', '')
                    if seq <= self.rcon_poll_seq:
                        continue
                    self.rcon_poll_seq = seq
                    self._update_last_seq(self.rcon_poll_seq)
                    if line:
                        if self.debug_votes:
                            print(f"➡️  [POLL-DEBUG] Processing seq={seq}: {line}")
                        await self.process_vote_from_console(line)
                await asyncio.sleep(2)
            except Exception as e:
                print(f"❌ RCON vote log polling error: {e}")
                await asyncio.sleep(5)

    @commands.command(name='mcgive')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def give_item(self, ctx, player: str, item: str, amount: int = 1):
        """Give items to a player in Minecraft"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        command = f"give {player} {item} {amount}"
        response = await self.rcon.send_command(command)

        await self.log_operator_command(ctx.author.mention, command)

        if response:
            embed = discord.Embed(
                title="🎁 Item Given",
                description=f"Gave **{amount}x {item}** to **{player}**",
                color=discord.Color.green()
            )
            embed.add_field(name="Command", value=f"`/{command}`", inline=False)
            embed.add_field(name="Response", value=response[:500], inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to execute command!")

    @commands.command(name='mctp')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def teleport_player(self, ctx, player1: str, player2: str = None):
        """Teleport player(s) in Minecraft"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        if player2:
            command = f"tp {player1} {player2}"
            description = f"Teleported **{player1}** to **{player2}**"
        else:
            command = f"tp {player1} spawn"
            description = f"Teleported **{player1}** to spawn"

        response = await self.rcon.send_command(command)

        await self.log_operator_command(ctx.author.mention, command)

        if response:
            embed = discord.Embed(
                title="🚀 Player Teleported",
                description=description,
                color=discord.Color.blue()
            )
            embed.add_field(name="Command", value=f"`/{command}`", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to teleport player!")

    @commands.command(name='mckick')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def kick_player(self, ctx, player: str, *, reason: str = "No reason provided"):
        """Kick a player from Minecraft"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        command = f"kick {player} {reason}"
        response = await self.rcon.send_command(command)

        await self.log_operator_command(ctx.author.mention, command)

        if response:
            embed = discord.Embed(
                title="👢 Player Kicked",
                description=f"Kicked **{player}** from the server",
                color=discord.Color.orange()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Staff Member", value=ctx.author.mention, inline=True)
            await ctx.send(embed=embed)

            log_channel = self.bot.get_channel(1401761548300582952)
            if log_channel:
                await log_channel.send(embed=embed)
        else:
            await ctx.send("❌ Failed to kick player!")

    @commands.command(name='mcban')
    @commands.has_any_role(1374421925790482483)
    async def ban_player(self, ctx, player: str, *, reason: str = "No reason provided"):
        """Ban a player from Minecraft"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        command = f"ban {player} {reason}"
        response = await self.rcon.send_command(command)

        await self.log_operator_command(ctx.author.mention, command)

        if response:
            embed = discord.Embed(
                title="🔨 Player Banned",
                description=f"Banned **{player}** from the server",
                color=discord.Color.red()
            )
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Staff Member", value=ctx.author.mention, inline=True)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to ban player!")

    @commands.command(name='mclist')
    async def list_players(self, ctx):
        """List online players"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        response = await self.rcon.send_command("list")

        if response:
            embed = discord.Embed(
                title="👥 Online Players",
                description=response,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to get player list!")

    @commands.command(name='mcwhitelist')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def whitelist_player(self, ctx, action: str, player: str):
        """Add/remove player from whitelist"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        if action.lower() not in ['add', 'remove']:
            await ctx.send("❌ Use `add` or `remove` as the action!")
            return

        command = f"whitelist {action.lower()} {player}"
        response = await self.rcon.send_command(command)

        await self.log_operator_command(ctx.author.mention, command)

        if response:
            embed = discord.Embed(
                title="📋 Whitelist Updated",
                description=f"**{action.title()}ed** {player} {'to' if action.lower() == 'add' else 'from'} whitelist",
                color=discord.Color.green() if action.lower() == 'add' else discord.Color.orange()
            )
            embed.add_field(name="Response", value=response, inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to update whitelist!")

    @commands.command(name='mcsay')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def server_say(self, ctx, *, message: str):
        """Send a message to all players"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        formatted_message = f"[Discord] {ctx.author.display_name}: {message}"
        command = f"say {formatted_message}"

        response = await self.rcon.send_command(command)

        await self.log_operator_command(ctx.author.mention, command)

        if response:
            embed = discord.Embed(
                title="💬 Message Sent to Server",
                description=formatted_message,
                color=discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to send message!")

    @commands.command(name='mccmd')
    @commands.has_any_role(1374421925790482483)
    async def raw_command(self, ctx, *, command: str):
        """Execute raw Minecraft command (Owner only)"""
        if not self.rcon:
            await ctx.send("❌ RCON not configured!")
            return

        response = await self.rcon.send_command(command)

        await self.log_operator_command(ctx.author.mention, command)

        if response:
            embed = discord.Embed(
                title="🔧 Raw Command Executed",
                color=discord.Color.blue()
            )
            embed.add_field(name="Command", value=f"`/{command}`", inline=False)
            embed.add_field(name="Response", value=f"```{response[:1000]}```", inline=False)
            await ctx.send(embed=embed)
        else:
            await ctx.send("❌ Failed to execute command!")

    @commands.command(name='testvote')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def test_vote(self, ctx, player_name: str = "TestPlayer", vote_type: str = "votingplugin"):
        """Test the vote notification system - Usage: !testvote PlayerName [votifier|votingplugin]"""
        if vote_type.lower() == "votifier":
            fake_console_message = f"[03:47:47 INFO]: [Votifier] Got a protocol v1 vote record from /34.239.107.144:48166 -> Vote (from:PlanetMinecraft.com username:{player_name} address:34.239.107.144 timeStamp:1759290467 additionalData:null)"
            await ctx.send(f"🧪 Testing EXACT Votifier format for **{player_name}**...")
        else:
            fake_console_message = f"[VotingPlugin] Received a vote from service site 'PlanetMinecraft.com' by player '{player_name}'!"
            await ctx.send(f"🧪 Testing VotingPlugin format for **{player_name}**...")

        print(f"🧪 [TEST-DEBUG] Simulating vote message: {fake_console_message}")
        await self.process_vote_from_console(fake_console_message)
        await ctx.send(f"✅ Test complete! Check console for debug output.")

    @commands.command(name='testrealvote')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def test_real_vote(self, ctx):
        """Test with the exact message from your console"""
        real_message = "[03:47:47 INFO]: [Votifier] Got a protocol v1 vote record from /34.239.107.144:48166 -> Vote (from:PlanetMinecraft.com username:PMC address:34.239.107.144 timeStamp:1759290467 additionalData:null)"

        await ctx.send("🧪 Testing with your exact console message...")
        print(f"🧪 [REAL-TEST-DEBUG] Processing real message: {real_message}")
        await self.process_vote_from_console(real_message)
        await ctx.send("✅ Real test complete! Check console for debug output.")

    @commands.command(name='votesetup')
    @commands.has_any_role(1376432927444963420, 1374421915938324583)
    async def vote_setup_info(self, ctx):
        """Show information about setting up vote detection"""
        embed = discord.Embed(
            title="🗳️ Vote Detection Setup Guide",
            description="To detect votes, we need Minecraft console messages sent to Discord",
            color=0x00D4AA
        )

        vote_channel = self.bot.get_channel(self.vote_channel_id)
        vote_status = f"<#{vote_channel.id}>" if vote_channel else f"Not found (ID: {self.vote_channel_id})"
        embed.add_field(
            name="📋 Current Status",
            value=f"• **Vote Channel:** {vote_status}",
            inline=False,
        )

        embed.add_field(
            name="🔧 Setup Options",
            value=(
                "**Option 1: Console Webhook**\n"
                "Use a plugin like DiscordSRV or ConsoleBot to send console messages to Discord\n\n"
                "**Option 2: Log Parsing**\n"
                "Set up log file monitoring to detect votes\n\n"
                "**Option 3: Plugin Integration**\n"
                "Use a vote listener plugin that sends webhooks directly"
            ),
            inline=False
        )

        embed.add_field(
            name="🧪 Testing",
            value=(
                "`!testrealvote` - Test with your exact console message\n"
                "`!testvote PMC votifier` - Test Votifier format\n"
                "`!testvote PlayerName` - Test VotingPlugin format"
            ),
            inline=False
        )

        embed.add_field(
            name="🎯 What We're Looking For",
            value="`[Votifier] Got a protocol v1 vote record from... -> Vote (from:PlanetMinecraft.com username:PMC ...)`",
            inline=False
        )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(MinecraftIntegration(bot))
