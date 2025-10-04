import discord
from discord.ext import commands
import json
import os
import re
from datetime import datetime, timedelta
import asyncio
from config import LINKED_ROLE_ID
from bot import bot_log

class MinecraftLinking(commands.Cog):
    """Discord-Minecraft account linking system"""

    def __init__(self, bot):
        self.bot = bot
        self.pending_verifications = {}
        self.linked_accounts = {}
        self.load_linked_accounts()
        self.link_requests_channel_id = None
        self.debug_link_webhook = False
        self.linked_role_id = LINKED_ROLE_ID
        self.success_message_delete_after = 5

    def load_linked_accounts(self):
        """Load linked accounts from file"""
        try:
            if os.path.exists("data/minecraft_links.json"):
                with open("data/minecraft_links.json", "r") as f:
                    data = json.load(f)
                    self.linked_accounts = data.get("linked_accounts", {})
                    for discord_id, mc_data in self.linked_accounts.items():
                        if isinstance(mc_data, str):
                            self.linked_accounts[discord_id] = [mc_data]
        except (FileNotFoundError, json.JSONDecodeError):
            self.linked_accounts = {}

    def save_linked_accounts(self):
        """Save linked accounts to file"""
        os.makedirs("data", exist_ok=True)
        data = {
            "linked_accounts": self.linked_accounts,
            "last_updated": datetime.now().isoformat()
        }
        with open("data/minecraft_links.json", "w") as f:
            json.dump(data, f, indent=2)

    async def _delete_message_after_delay(self, message, delay_seconds):
        try:
            await asyncio.sleep(delay_seconds)
            await message.delete()
        except Exception as e:
            print(f"[LINK-DEBUG] Could not delete message after delay: {e}")
            await bot_log(f"[Linking] Error deleting message after delay: {e}", error=True, exc_info=e)

    @commands.command(name='verify')
    async def verify_minecraft(self, ctx, code: str = None):
        """Verify your Minecraft account with the code from /link"""

        if not code:
            embed = discord.Embed(
                title="❌ Missing Verification Code",
                description="Please provide the 6-digit code you received in Minecraft.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Usage",
                value="`!verify 123456`",
                inline=False
            )
            embed.add_field(
                name="How to get a code",
                value="1. Join the Minecraft server\n2. Type `/link YourDiscordUsername`\n3. Use the code here with `!verify`",
                inline=False
            )
            await ctx.send(embed=embed)
            await bot_log(f"[Linking] Missing verification code from {ctx.author}", error=True)
            return

        code = re.sub(r'[^0-9]', '', code)

        if len(code) != 6:
            embed = discord.Embed(
                title="❌ Invalid Code Format",
                description="Verification codes are exactly 6 digits.",
                color=discord.Color.red()
            )
            embed.add_field(name="Example", value="`!verify 123456`", inline=False)
            await ctx.send(embed=embed)
            await bot_log(f"[Linking] Invalid code format from {ctx.author}: {code}", error=True)
            return

        if str(ctx.author.id) in self.linked_accounts:
            current_accounts = self.linked_accounts[str(ctx.author.id)]
            if mc_username in current_accounts:
                embed = discord.Embed(
                    title="❌ Already Linked",
                    description=f"Your Discord account is already linked to **{mc_username}**",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                await bot_log(f"[Linking] Already linked: {ctx.author} -> {mc_username}", error=True)
                return

        verification = None
        mc_username = None

        for pending_code, data in self.pending_verifications.items():
            if pending_code == code:
                if datetime.now() > data["expires"]:
                    del self.pending_verifications[pending_code]
                    embed = discord.Embed(
                        title="❌ Code Expired",
                        description="This verification code has expired. Please generate a new one in Minecraft.",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="Generate New Code", value="Type `/link YourDiscordUsername` in Minecraft", inline=False)
                    await ctx.send(embed=embed)
                    await bot_log(f"[Linking] Code expired for {ctx.author}: {code}", error=True)
                    return

                verification = data
                mc_username = data["mc_username"]
                break

        if not verification:
            embed = discord.Embed(
                title="❌ Invalid Code",
                description="Verification code not found or expired.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Make sure you:",
                value="1. Generated the code in Minecraft with `/link`\n2. Used the correct 6-digit code\n3. Verified within 5 minutes",
                inline=False
            )
            await ctx.send(embed=embed)
            await bot_log(f"[Linking] Invalid code for {ctx.author}: {code}", error=True)
            return

        if str(ctx.author.id) not in self.linked_accounts:
            self.linked_accounts[str(ctx.author.id)] = []

        self.linked_accounts[str(ctx.author.id)].append(mc_username)
        del self.pending_verifications[code]
        self.save_linked_accounts()

        try:
            mc_cog = self.bot.get_cog("MinecraftIntegration")
            if mc_cog and getattr(mc_cog, "rcon", None):
                rcon = mc_cog.rcon
                verify_cmd = f"dilinkverify {mc_username} {ctx.author.id} {code}"
                verify_resp = await rcon.send_command(verify_cmd)

                reload_cmd = "dilinkreload"
                reload_resp = await rcon.send_command(reload_cmd)

            else:
                print("[LINK-DEBUG] MinecraftIntegration cog or RCON not available; skipping MC notify")
                await bot_log(f"[Linking] RCON not available for linking {ctx.author} -> {mc_username}", error=True)
        except Exception as e:
            print(f"[LINK-DEBUG] Error notifying MC server via RCON: {e}")
            await bot_log(f"[Linking] Error notifying MC server for {ctx.author} -> {mc_username}: {e}", error=True, exc_info=e)

        embed = discord.Embed(
            title="🎉 Account Successfully Linked!",
            description=f"Your Discord account has been linked to **{mc_username}**",
            color=discord.Color.green()
        )
        embed.add_field(name="🎮 Minecraft", value=mc_username, inline=True)
        embed.add_field(name="💬 Discord", value=ctx.author.mention, inline=True)
        embed.add_field(name="✅ Status", value="Linked & Verified", inline=True)
        embed.set_footer(text="You can now play on the server without restrictions!")

        try:
            success_msg = await ctx.send(embed=embed, delete_after=self.success_message_delete_after)
        except TypeError:
            success_msg = await ctx.send(embed=embed)
            try:
                await asyncio.sleep(self.success_message_delete_after)
                await success_msg.delete()
            except Exception as e:
                await bot_log(f"[Linking] Error deleting success message: {e}", error=True, exc_info=e)
        try:
            await ctx.message.delete()
            print(f"[LINK-DEBUG] Deleted user's command message id={ctx.message.id}")
        except Exception as e:
            print(f"[LINK-DEBUG] Could not delete user's command message: {e}")
            await bot_log(f"[Linking] Error deleting command message for {ctx.author}: {e}", error=True, exc_info=e)

        try:
            if ctx.guild is not None and self.linked_role_id:
                role = ctx.guild.get_role(self.linked_role_id)
                if role is not None:
                    await ctx.author.add_roles(role, reason="Minecraft account linked")
                    print(f"[LINK-DEBUG] Granted role {role.id} to user {ctx.author.id}")
                else:
                    print(f"[LINK-DEBUG] Linked role id {self.linked_role_id} not found in guild {ctx.guild.id}")
                    await bot_log(f"[Linking] Linked role not found in guild for {ctx.author}", error=True)
            else:
                print("[LINK-DEBUG] Guild context or linked_role_id missing; cannot assign role")
                await bot_log(f"[Linking] Guild context or linked_role_id missing for {ctx.author}", error=True)
        except Exception as e:
            print(f"[LINK-DEBUG] Failed to assign linked role: {e}")
            await bot_log(f"[Linking] Failed to assign linked role for {ctx.author}: {e}", error=True, exc_info=e)

        await bot_log(f"[Linking] Linked: {ctx.author} -> {mc_username}")

        log_channel = self.bot.get_channel(1401761548300582952)
        if log_channel:
            log_embed = discord.Embed(
                title="🔗 New Account Link",
                color=discord.Color.blue()
            )
            log_embed.add_field(name="Discord", value=f"{ctx.author.mention} ({ctx.author.name}
            log_embed.add_field(name="Minecraft", value=mc_username, inline=True)
            log_embed.add_field(name="Linked At", value=datetime.now().strftime('%B %d, %Y at %I:%M %p'), inline=True)
            try:
                log_msg = await log_channel.send(embed=log_embed)
                asyncio.create_task(self._delete_message_after_delay(log_msg, 10))
                await bot_log(f"[Linking] Log sent for {ctx.author} -> {mc_username}")
            except Exception as e:
                print(f"[LINK-DEBUG] Could not send/schedule deletion of log message: {e}")
                await bot_log(f"[Linking] Could not send/schedule deletion of log message for {ctx.author}: {e}", error=True, exc_info=e)

    @commands.command(name='unlink')
    async def unlink_minecraft(self, ctx, minecraft_name: str = None):
        """Unlink a Minecraft account from Discord"""

        if str(ctx.author.id) not in self.linked_accounts:
            embed = discord.Embed(
                title="❌ Not Linked",
                description="Your Discord account is not linked to any Minecraft account.",
                color=discord.Color.red()
            )
            embed.add_field(name="Want to link?", value="Use `!verify` with a code from Minecraft", inline=False)
            await ctx.send(embed=embed)
            return

        mc_usernames = self.linked_accounts[str(ctx.author.id)]

        if not minecraft_name:
            if len(mc_usernames) == 1:
                minecraft_name = mc_usernames[0]
            else:
                embed = discord.Embed(
                    title="🔗 Multiple Linked Accounts",
                    description="You have multiple linked accounts. Specify which to unlink:",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="Your Linked Accounts",
                    value="\n".join([f"• {username}" for username in mc_usernames]),
                    inline=False
                )
                embed.add_field(name="Usage", value="`!unlink <minecraft_name>`", inline=False)
                await ctx.send(embed=embed)
                return

        if minecraft_name not in mc_usernames:
            embed = discord.Embed(
                title="❌ Not Linked",
                description=f"**{minecraft_name}** is not linked to your account.",
                color=discord.Color.red()
            )
            if mc_usernames:
                embed.add_field(
                    name="Your Linked Accounts",
                    value="\n".join([f"• {username}" for username in mc_usernames]),
                    inline=False
                )
            await ctx.send(embed=embed)
            return

        mc_usernames.remove(minecraft_name)

        if not mc_usernames:
            del self.linked_accounts[str(ctx.author.id)]

        self.save_linked_accounts()

        embed = discord.Embed(
            title="🔓 Account Unlinked",
            description=f"Unlinked **{minecraft_name}** from your Discord account",
            color=discord.Color.orange()
        )

        remaining = self.linked_accounts.get(str(ctx.author.id), [])
        if remaining:
            embed.add_field(
                name="Remaining Linked Accounts",
                value="\n".join([f"• {username}" for username in remaining]),
                inline=False
            )
        else:
            embed.add_field(name="Note", value="You can link to Minecraft accounts anytime with `!verify`", inline=False)

        await ctx.send(embed=embed)

        print(f"🔓 Unlinked: {ctx.author.name}

    @commands.command(name='linked')
    async def check_linked(self, ctx, user: discord.Member = None):
        """Check if your account (or someone else's) is linked"""

        target_user = user or ctx.author

        if str(target_user.id) in self.linked_accounts:
            mc_usernames = self.linked_accounts[str(target_user.id)]
            embed = discord.Embed(
                title="✅ Account Linked",
                color=discord.Color.green()
            )
            embed.add_field(name="Discord", value=target_user.mention, inline=True)
            embed.add_field(name="Status", value="✅ Verified", inline=True)
            embed.add_field(name="Total Accounts", value=str(len(mc_usernames)), inline=True)
            embed.add_field(
                name="Minecraft Accounts",
                value="\n".join([f"• {username}" for username in mc_usernames]),
                inline=False
            )
        else:
            name_possessive = "Your" if target_user == ctx.author else f"{target_user.name}'s"
            embed = discord.Embed(
                title="❌ Account Not Linked",
                description=f"{name_possessive} account is not linked to any Minecraft account.",
                color=discord.Color.red()
            )
            if target_user == ctx.author:
                embed.add_field(
                    name="How to Link",
                    value="1. Join the Minecraft server\n2. Use `/link YourDiscordUsername`\n3. Use `!verify <code>` here",
                    inline=False
                )

        await ctx.send(embed=embed)

    @commands.command(name='linkinfo')
    @commands.has_permissions(manage_guild=True)
    async def link_info(self, ctx):
        """Show linking system statistics (Staff only)"""

        total_linked = len(self.linked_accounts)
        pending_count = len(self.pending_verifications)

        expired = []
        for code, data in self.pending_verifications.items():
            if datetime.now() > data["expires"]:
                expired.append(code)

        for code in expired:
            del self.pending_verifications[code]

        embed = discord.Embed(
            title="🔗 Minecraft Linking Statistics",
            color=discord.Color.blue()
        )
        embed.add_field(name="📊 Total Linked Accounts", value=str(total_linked), inline=True)
        embed.add_field(name="⏳ Pending Verifications", value=str(pending_count), inline=True)
        embed.add_field(name="🗑️ Expired Codes Cleaned", value=str(len(expired)), inline=True)

        embed.add_field(
            name="📋 Recent Links (Last 5)",
            value="\n".join([f"• {mc_name}" for mc_name in list(self.linked_accounts.values())[-5:]]) or "None",
            inline=False
        )

        await ctx.send(embed=embed)

    def handle_minecraft_link_request(self, mc_username: str, discord_username: str, code: str):
        """Handle link request from Minecraft plugin (via webhook)"""

        expires_at = datetime.now() + timedelta(minutes=5)

        self.pending_verifications[code] = {
            "mc_username": mc_username,
            "discord_username": discord_username,
            "expires": expires_at
        }

        print(f"🔗 Link request: {mc_username} -> {discord_username} (Code: {code})")
        return True

    def get_minecraft_usernames(self, discord_id: str) -> list:
        """Get list of Minecraft usernames from Discord ID"""
        return self.linked_accounts.get(str(discord_id), [])

    def get_minecraft_username(self, discord_id: str) -> str:
        """Get first/primary Minecraft username from Discord ID (for backwards compatibility)"""
        usernames = self.get_minecraft_usernames(discord_id)
        return usernames[0] if usernames else None

    def get_discord_id(self, mc_username: str) -> str:
        """Get Discord ID from Minecraft username"""
        for discord_id, usernames in self.linked_accounts.items():
            if mc_username.lower() in [u.lower() for u in usernames]:
                return discord_id
        return None

    def is_linked(self, discord_id: str) -> bool:
        """Check if Discord user is linked"""
        return str(discord_id) in self.linked_accounts and len(self.linked_accounts[str(discord_id)]) > 0

    def add_link(self, discord_id: str, mc_username: str) -> bool:
        """Add a link between Discord and Minecraft account"""
        discord_id = str(discord_id)
        if discord_id not in self.linked_accounts:
            self.linked_accounts[discord_id] = []

        if mc_username not in self.linked_accounts[discord_id]:
            self.linked_accounts[discord_id].append(mc_username)
            self.save_linked_accounts()
            return True
        return False

    def remove_link(self, discord_id: str, mc_username: str) -> bool:
        """Remove a specific link between Discord and Minecraft account"""
        discord_id = str(discord_id)
        if discord_id in self.linked_accounts:
            if mc_username in self.linked_accounts[discord_id]:
                self.linked_accounts[discord_id].remove(mc_username)
                if not self.linked_accounts[discord_id]:
                    del self.linked_accounts[discord_id]
                self.save_linked_accounts()
                return True
        return False

    def get_all_links(self) -> dict:
        """Get all linked accounts"""
        return self.linked_accounts.copy()

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Capture verification codes from the Minecraft plugin webhook embed.

        The plugin posts an embed with title "🔗 New Link Request" and a description like:
            🎮 Minecraft: `Steve`
            💬 Discord: `JohnDoe
            🔢 Verification Code: `847291`
        We'll parse it and store a pending verification so !verify can find the code.
        """
        try:
            if message.author.id == self.bot.user.id:
                return

            if self.link_requests_channel_id and message.channel.id != self.link_requests_channel_id:
                if self.debug_link_webhook and getattr(message, "webhook_id", None):
                    print(f"[LINK-DEBUG] Webhook msg in other channel ignored: msg_id={message.id} channel_id={message.channel.id} expected_channel_id={self.link_requests_channel_id}")
                return

            if not getattr(message, "webhook_id", None):
                return

            if self.debug_link_webhook:
                author = message.author
                print("[LINK-DEBUG] Saw webhook message:")
                print(f"  msg_id={message.id} channel_id={message.channel.id} channel_name=
                print(f"  webhook_id={message.webhook_id} author={author} embeds={len(message.embeds)}")

            if not message.embeds:
                if self.debug_link_webhook:
                    print("[LINK-DEBUG] Webhook message has no embeds; skipping")
                return

            embed = message.embeds[0]
            title = (embed.title or "").strip()
            if self.debug_link_webhook:
                print(f"[LINK-DEBUG] Embed title: {title!r}")
            if "New Link Request" not in title:
                if self.debug_link_webhook:
                    print("[LINK-DEBUG] Title does not contain 'New Link Request'; skipping")
                return

            description = (embed.description or "")
            if self.debug_link_webhook:
                sample = description.replace('\n', '\\n')
                if len(sample) > 240:
                    sample = sample[:240] + "..."
                print(f"[LINK-DEBUG] Embed description (truncated): {sample}")

            mc_match = re.search(r"(?i)Minecraft:\**\s*`([^`]+)`", description)
            dc_match = re.search(r"(?i)Discord:\**\s*`([^`]+)`", description)
            code_match = re.search(r"(?i)Verification Code:\**\s*`(\d{6})`", description)

            if not (mc_match and dc_match and code_match):
                if self.debug_link_webhook:
                    print(f"[LINK-DEBUG] Parse results -> mc:{bool(mc_match)} dc:{bool(dc_match)} code:{bool(code_match)}; skipping")
                return

            mc_username = mc_match.group(1).strip()
            discord_username = dc_match.group(1).strip()
            code = code_match.group(1).strip()

            if self.debug_link_webhook:
                print(f"[LINK-DEBUG] Parsed values -> mc='{mc_username}' dc='{discord_username}' code={code}")

            expires_at = datetime.now() + timedelta(minutes=5)
            self.pending_verifications[code] = {
                "mc_username": mc_username,
                "discord_username": discord_username,
                "expires": expires_at,
            }

            print(f"📥 Captured link code from webhook: {mc_username} -> {discord_username} (Code: {code}) exp={expires_at.strftime('%H:%M:%S')}")

        except Exception as e:
            print(f"[LINK-DEBUG] on_message parsing error for link webhook: {e}")
            await bot_log(f"[MinecraftLinking] Error parsing link webhook: {e}", error=True, exc_info=e)

async def setup(bot):
    await bot.add_cog(MinecraftLinking(bot))
