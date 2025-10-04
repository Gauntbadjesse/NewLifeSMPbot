import discord
from discord.ext import commands
from discord import ui
import json
import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import Optional, cast
from config import WHITELIST_PANEL_CHANNEL_ID, WHITELIST_CATEGORY_ID, WHITELIST_STAFF_ROLE_ID, WHITELIST_ROLE_ID, STAFF_LOG_CHANNEL_ID
from bot import bot_log

class WhitelistCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_whitelist_tickets = {}
        self.whitelist_panel_message_id = None
        self.pending_whitelist = {}
        self.panel_channel_id = WHITELIST_PANEL_CHANNEL_ID
        self.category_id = WHITELIST_CATEGORY_ID
        self.staff_role_id = WHITELIST_STAFF_ROLE_ID
        self.whitelist_role_id = WHITELIST_ROLE_ID
        self.staff_log_channel_id = STAFF_LOG_CHANNEL_ID
        self.load_whitelist_data()

    def load_whitelist_data(self):
        """Load whitelist data from files"""
        try:
            with open("data/whitelist_tickets.json", "r") as f:
                data = json.load(f)
                self.active_whitelist_tickets = {}
                for user_id, ticket_data in data.items():
                    if isinstance(ticket_data, dict):
                        self.active_whitelist_tickets[user_id] = ticket_data
                    else:
                        self.active_whitelist_tickets[user_id] = {
                            "channel_id": ticket_data,
                            "owner_id": int(user_id)
                        }
        except (FileNotFoundError, json.JSONDecodeError):
            self.active_whitelist_tickets = {}

        try:
            with open("data/whitelist_panel.json", "r") as f:
                data = json.load(f)
                self.whitelist_panel_message_id = data.get("message_id")
        except (FileNotFoundError, json.JSONDecodeError):
            self.whitelist_panel_message_id = None

    def save_whitelist_data(self):
        """Save whitelist data to files"""
        os.makedirs("data", exist_ok=True)
        with open("data/whitelist_tickets.json", "w") as f:
            json.dump(self.active_whitelist_tickets, f, indent=2)
        with open("data/whitelist_panel.json", "w") as f:
            json.dump({"message_id": self.whitelist_panel_message_id}, f, indent=2)

    async def cog_load(self):
        """Add persistent views when cog loads"""
        self.bot.add_view(WhitelistView())
        self.bot.add_view(WhitelistCloseRequestView())
        self.bot.add_view(StaffWhitelistView())

        await self.ensure_whitelist_panel()

        print("Whitelist cog loaded and persistent views added")

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready event"""
        print("Whitelist cog ready")

    async def ensure_whitelist_panel(self):
        """Ensure the whitelist panel exists"""
        whitelist_channel = self.bot.get_channel(1376427874978103418)
        if not whitelist_channel:
            print("Whitelist channel not found!")
            return

        panel_exists = False
        if self.whitelist_panel_message_id:
            try:
                message = await whitelist_channel.fetch_message(self.whitelist_panel_message_id)
                if message.components:
                    panel_exists = True
                    view = WhitelistView()
                    try:
                        await message.edit(view=view)
                        print("Successfully updated whitelist panel with working view")
                    except Exception as e:
                        print(f"Could not update whitelist message view: {e}")
                        panel_exists = False
            except discord.NotFound:
                print("Stored whitelist panel message not found, will recreate")
                self.whitelist_panel_message_id = None
                self.save_whitelist_data()
            except Exception as e:
                print(f"Error checking whitelist panel: {e}")

        if not panel_exists:
            await self.create_whitelist_panel()

    async def create_whitelist_panel(self):
        """Create the whitelist application panel"""
        whitelist_channel = self.bot.get_channel(1376427874978103418)
        if not whitelist_channel:
            print("Whitelist channel not found!")
            return

        embed = discord.Embed(
            title="🎮 Minecraft Server Whitelist Application",
            description="**Join our exclusive Minecraft SMP server!**\n\nOur community-driven server offers a safe, enjoyable experience for all players. Apply today to start your adventure!",
            color=0x00FF7F
        )

        embed.add_field(
            name="🌟 Why Join Us?",
            value="• **Community-focused** gameplay with friendly players\n• **Grief protection** and active moderation\n• **Custom features** and regular events\n• **Both Java & Bedrock** players welcome",
            inline=True
        )

        embed.add_field(
            name="Application Process",
            value="• Click **Apply** to start your application\n• Fill out the required information\n• Complete the rules quiz\n• Wait for staff approval\n• Get whitelisted and start playing!",
            inline=True
        )

        embed.add_field(
            name="Important Notes",
            value="• **One application per person**\n• **Be honest** in your responses\n• **Read the rules** before applying\n• **Be patient** - staff will review your application\n• Use **Re-apply** if your previous application was denied",
            inline=False
        )

        embed.set_footer(
            text="TheNewLife Minecraft SMP • Professional Whitelist System",
            icon_url="https://cdn.discordapp.com/attachments/123456789/123456789/minecraft_icon.png"
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/123456789/123456789/server_icon.png")

        view = WhitelistView()
        message = await whitelist_channel.send(embed=embed, view=view)

        self.whitelist_panel_message_id = message.id
        self.save_whitelist_data()
        print("✔ Whitelist panel created and saved!")

    async def create_whitelist_ticket(self, interaction: discord.Interaction, application_data: dict):
        """Create a whitelist ticket with application data"""
        user = interaction.user
        guild = interaction.guild

        if not guild:
            return

        if user.id in self.active_whitelist_tickets:
            ticket_data = self.active_whitelist_tickets[user.id]
            existing_channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
            if existing_channel_id:
                existing_channel = guild.get_channel(existing_channel_id)
                if existing_channel:
                    await interaction.response.send_message(
                        f"✖ You already have an open whitelist application: {existing_channel.mention}",
                        ephemeral=True
                    )
                    return
            del self.active_whitelist_tickets[user.id]
            self.save_whitelist_data()

        category = guild.get_channel(1387287352426106922)
        staff_role = guild.get_role(1376432927444963420)

        if not category or not isinstance(category, discord.CategoryChannel) or not staff_role:
            await interaction.response.send_message("✖ Whitelist system configuration error!", ephemeral=True)
            return

        channel_name = f"whitelist-{user.display_name}".lower().replace(" ", "-")[:50]

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        }

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Whitelist application by {user}"
            )

            self.active_whitelist_tickets[user.id] = {
                "channel_id": channel.id,
                "owner_id": user.id
            }
            self.save_whitelist_data()

            embed = discord.Embed(
                title="📝 Minecraft Whitelist Application",
                description=f"**Application submitted by {user.mention}**\n\nPlease review the information below and proceed with the approval process.",
                color=0x00FF7F
            )

            embed.add_field(name="Minecraft Username", value=application_data["minecraft_username"], inline=True)
            embed.add_field(name="🎂 Age", value=application_data["age"], inline=True)
            embed.add_field(name="🎮 Platform", value=application_data["platform"], inline=True)
            embed.add_field(name="📍 How they found us", value=application_data["found_us"], inline=False)
            embed.add_field(name="📅 Applied", value=datetime.now().strftime('%B %d, %Y at %I:%M %p'), inline=True)
            embed.add_field(name="🆔 Discord ID", value=str(user.id), inline=True)

            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)
            embed.set_footer(text="Staff: Use the buttons below to approve, deny, or send quiz")

            staff_view = StaffWhitelistView()

            await channel.send(f"{user.mention} {staff_role.mention}", embed=embed, view=staff_view)

            await interaction.response.send_message(
                f"✔ Your whitelist application has been submitted! Please check {channel.mention} for updates.",
                ephemeral=True
            )
            await bot_log(f"[Whitelist] Application submitted by {user} ({application_data.get('minecraft_username')})")

        except discord.Forbidden as e:
            await interaction.response.send_message("✖ I don't have permission to create channels!", ephemeral=True)
            await bot_log(f"[Whitelist] Forbidden error creating ticket for {user}: {e}", error=True, exc_info=e)
        except Exception as e:
            await interaction.response.send_message(f"✖ Error creating application: {str(e)}", ephemeral=True)
            await bot_log(f"[Whitelist] Exception creating ticket for {user}: {e}", error=True, exc_info=e)

    @commands.command(name='whitelist')
    @commands.has_any_role(1376432927444963420, 1374421915938324583, 1374421925790482483)
    async def whitelist_user(self, ctx, user: discord.Member):
        """Whitelist a user (staff only)"""
        channel = ctx.channel
        applicant_id = user.id
        app_data = None
        for uid, data in self.active_whitelist_tickets.items():
            if int(uid) == applicant_id and isinstance(data, dict):
                app_data = data
                break
        if not app_data or 'minecraft_username' not in app_data:
            await ctx.send("Could not find Minecraft username for this user.")
            return
        mc_username = app_data['minecraft_username']
        mc_cog = self.bot.get_cog('MinecraftIntegration')
        if not mc_cog or not hasattr(mc_cog, 'rcon') or not mc_cog.rcon:
            await ctx.send("Minecraft RCON is not available.")
            return
        rcon = mc_cog.rcon
        try:
            result = await rcon.send_command(f"whitelist add {mc_username}")
            await ctx.send(f"✔ {user.mention} ({mc_username}) has been added to the Minecraft whitelist.")
        except Exception as e:
            await ctx.send(f"Error adding to whitelist: {e}")
            return
        try:
            await user.send("hi")
        except Exception:
            pass

    async def process_whitelist_command(self, minecraft_channel, command, username_or_uuid, user, platform, staff_member, ticket_channel):
        """Process the whitelist command and wait for response"""
        try:
            await minecraft_channel.send(command)

            response_channel = self.bot.get_channel(1374421938381783061)
            if not response_channel:
                embed = discord.Embed(
                    title="Error",
                    description="Response monitoring channel not found.",
                    color=0xFF4444
                )
                await ticket_channel.send(embed=embed)
                return

            def check(message):
                return (message.channel.id == 1374421938381783061 and
                       message.author.id == 1381671096776003715 and
                       (username_or_uuid.lower() in message.content.lower() or
                        "added" in message.content.lower() or
                        "whitelist" in message.content.lower() or
                        "removed" in message.content.lower() or
                        "error" in message.content.lower()))

            try:
                response = await self.bot.wait_for('message', timeout=30.0, check=check)

                if ("added" in response.content.lower() and "whitelist" in response.content.lower()) or "successfully" in response.content.lower():
                    await self.handle_whitelist_success(user, platform, ticket_channel, username_or_uuid)
                elif "removed" in response.content.lower():
                    embed = discord.Embed(
                        title="Success",
                        description=f"User **{username_or_uuid}** has been removed from the whitelist.\n\nServer response: {response.content}",
                        color=0x00FF7F
                    )
                    await ticket_channel.send(embed=embed)
                elif "error" in response.content.lower() or "failed" in response.content.lower():
                    embed = discord.Embed(
                        title="Error",
                        description=f"Server returned an error: {response.content}",
                        color=0xFF4444
                    )
                    await ticket_channel.send(embed=embed)
                else:
                    embed = discord.Embed(
                        title="Server Response",
                        description=f"Server response: {response.content}",
                        color=0xFFCC00
                    )
                    await ticket_channel.send(embed=embed)

            except asyncio.TimeoutError:
                embed = discord.Embed(
                    title="Timeout",
                    description="No response from server within 30 seconds. Please try again later.",
                    color=0xFF4444
                )
                await ticket_channel.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(
                title="❌ Error",
                description=f"Error sending whitelist command: {str(e)}",
                color=0xFF4444
            )
            await ticket_channel.send(embed=embed)
            await bot_log(f"[Whitelist] Error sending whitelist command for {user}: {e}", error=True, exc_info=e)

    async def handle_whitelist_success(self, user, platform, ticket_channel, username_or_uuid):
        """Handle successful whitelist approval"""
        whitelist_role = user.guild.get_role(1374421917284565046)
        if whitelist_role:
            try:
                await user.add_roles(whitelist_role, reason="Whitelisted for Minecraft server")
            except Exception as e:
                print(f"Error adding whitelist role: {e}")

        embed = discord.Embed(
            title="Congratulations — Your Whitelist Request Has Been Approved!",
            description=(
                "You can now join our SMP and start your adventure.\n\n"
                "__Server Information:__\n"
                "IP Address: `newlife.nestcore.dev`\n\n"
                "__Before You Join:__\n"
                "• Make sure you've read and understand all server rules.\n"
                "• Respect other players and staff.\n"
                "• Have fun and enjoy your time on the SMP!\n\n"
                "Need more details? Check out <
            ),
            color=0x00FF7F
        )
        embed.set_footer(text="Welcome to TheNewLife SMP!")

        await ticket_channel.send(f"{user.mention}", embed=embed)
        await bot_log(f"[Whitelist] Approved: {user} ({username_or_uuid}) on {platform}")

        await self.log_whitelist(user, platform, username_or_uuid, "approved")

    async def log_whitelist(self, user, platform, username_or_uuid, action):
        """Log whitelist action"""
        log_channel = self.bot.get_channel(1401409232212852787)
        if not log_channel:
            return

        embed = discord.Embed(
            title=f"Whitelist {action.title()}",
            description=f"User {user.mention} has been {action}",
            color=0x00FF7F if action == "approved" else 0xFF4444
        )
        embed.add_field(name="User", value=user.mention, inline=True)
        embed.add_field(name="Platform", value=platform, inline=True)
        embed.add_field(name="Username/UUID", value=username_or_uuid, inline=True)
        embed.add_field(name="Date", value=datetime.now().strftime('%B %d, %Y at %I:%M %p'), inline=True)
        embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

        await log_channel.send(embed=embed)
        await bot_log(f"[Whitelist] {action.title()}: {user} ({username_or_uuid}) on {platform}")

    async def find_whitelist_ticket_owner(self, channel):
        """Find the whitelist ticket owner"""
        for user_id, ticket_data in self.active_whitelist_tickets.items():
            if isinstance(ticket_data, dict):
                if ticket_data.get("channel_id") == channel.id:
                    owner_id = ticket_data.get("owner_id", int(user_id))
                    return channel.guild.get_member(owner_id)
            else:
                if ticket_data == channel.id:
                    return channel.guild.get_member(int(user_id))

        staff_role = channel.guild.get_role(1376432927444963420)
        if not staff_role:
            return None

        for member in channel.members:
            if member.bot:
                continue
            if staff_role in member.roles:
                continue
            return member

        return None

    async def close_whitelist_ticket(self, channel, reason="Manual closure"):
        """Close a whitelist ticket channel"""
        try:
            ticket_owner = await self.find_whitelist_ticket_owner(channel)

            user_to_remove = None
            for user_id, ticket_data in self.active_whitelist_tickets.items():
                current_channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                if current_channel_id == channel.id:
                    user_to_remove = user_id
                    break

            if user_to_remove:
                del self.active_whitelist_tickets[user_to_remove]
                self.save_whitelist_data()

            await bot_log(f"[Whitelist] Ticket closed for {ticket_owner} in {channel} by {reason}")

            await asyncio.sleep(3)
            await channel.delete()
            await bot_log(f"[Whitelist] Ticket closed for channel {channel.id} (reason: {reason})")

        except Exception as e:
            print(f"Error closing whitelist ticket: {e}")
            await bot_log(f"[Whitelist] Error closing ticket for channel {channel.id}: {e}", error=True, exc_info=e)

class WhitelistView(ui.View):
    """Main whitelist panel view"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Apply', style=discord.ButtonStyle.success, custom_id='whitelist_apply')
    async def apply_button(self, interaction: discord.Interaction, button: ui.Button):
        """Open whitelist application form"""
        modal = WhitelistApplicationModal()
        await interaction.response.send_modal(modal)

    @ui.button(label='Re-apply', style=discord.ButtonStyle.secondary, custom_id='whitelist_reapply')
    async def reapply_button(self, interaction: discord.Interaction, button: ui.Button):
        """Re-apply for whitelist (placeholder)"""
        await interaction.response.send_message("Re-apply functionality coming soon!", ephemeral=True)

class WhitelistApplicationModal(ui.Modal):
    """Modal for whitelist application"""

    def __init__(self):
        super().__init__(title="Minecraft Whitelist Application")

        self.minecraft_username = ui.TextInput(
            label="Minecraft Username",
            placeholder="Enter your Minecraft username...",
            max_length=16,
            required=True
        )
        self.add_item(self.minecraft_username)

        self.age = ui.TextInput(
            label="Age",
            placeholder="Enter your age...",
            max_length=3,
            required=True
        )
        self.add_item(self.age)

        self.platform = ui.TextInput(
            label="Java or Bedrock",
            placeholder="Java or Bedrock",
            max_length=10,
            required=True
        )
        self.add_item(self.platform)

        self.found_us = ui.TextInput(
            label="Where did you find us?",
            placeholder="How did you discover our server?",
            style=discord.TextStyle.paragraph,
            max_length=500,
            required=True
        )
        self.add_item(self.found_us)

    async def on_submit(self, interaction: discord.Interaction):
        """Process the application"""
        application_data = {
            "minecraft_username": self.minecraft_username.value,
            "age": self.age.value,
            "platform": self.platform.value.title(),
            "found_us": self.found_us.value
        }

        if hasattr(interaction.client, 'get_cog'):
            bot = cast(commands.Bot, interaction.client)
            cog = cast(WhitelistCog, bot.get_cog('WhitelistCog'))
            if cog:
                await cog.create_whitelist_ticket(interaction, application_data)
            else:
                await interaction.response.send_message("✖ Whitelist system temporarily unavailable.", ephemeral=True)

class StaffWhitelistView(ui.View):
    """Staff view for approving/denying whitelist applications - now properly persistent"""

    def __init__(self):
        super().__init__(timeout=None)

    async def find_whitelist_ticket_owner(self, channel):
        """Find the whitelist ticket owner from the channel"""
        cog = None
        if hasattr(channel, 'guild') and hasattr(channel.guild, '_state'):
            bot = channel.guild._state._get_client()
            cog = bot.get_cog('WhitelistCog')

        if cog:
            for user_id, ticket_data in cog.active_whitelist_tickets.items():
                if isinstance(ticket_data, dict):
                    if ticket_data.get("channel_id") == channel.id:
                        owner_id = ticket_data.get("owner_id", int(user_id))
                        return channel.guild.get_member(owner_id)
                else:
                    if ticket_data == channel.id:
                        return channel.guild.get_member(int(user_id))

        staff_role = channel.guild.get_role(1376432927444963420)
        if not staff_role:
            return None

        for member in channel.members:
            if member.bot:
                continue
            if staff_role in member.roles:
                continue
            return member

        return None

    async def check_staff_permissions(self, interaction):
        """Check if user has staff permissions"""
        staff_roles = [1376432927444963420, 1374421915938324583, 1374421925790482483]
        user_role_ids = [role.id for role in interaction.user.roles]

        if any(role_id in staff_roles for role_id in user_role_ids):
            return True

        if interaction.user.guild_permissions.manage_guild:
            return True

        return False

    async def check_staff_permissions(self, interaction):
        """Check if user has staff permissions"""
        staff_roles = [1376432927444963420, 1374421915938324583, 1374421925790482483]
        user_role_ids = [role.id for role in interaction.user.roles]

        if any(role_id in staff_roles for role_id in user_role_ids):
            return True

        if interaction.user.guild_permissions.manage_guild:
            return True

        return False

class DenyWhitelistModal(ui.Modal, title="Deny Whitelist Application"):
    def __init__(self, user_id, view):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.view = view

    reason = ui.TextInput(
        label="Denial Reason",
        placeholder="Please provide a reason for denial...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        user = interaction.guild.get_member(self.user_id)
        if not user:
            await interaction.response.send_message("User not found in server.", ephemeral=True)
            return

        embed = discord.Embed(
            title="❌ Whitelist Application Denied",
            description=f"{user.mention}'s whitelist application has been denied by {interaction.user.mention}",
            color=discord.Color.red()
        )
        embed.add_field(name="Reason", value=self.reason.value, inline=False)

        await interaction.response.send_message(embed=embed)

        try:
            dm_embed = discord.Embed(
                title="Whitelist Application Denied",
                description="Unfortunately, your whitelist application has been denied.",
                color=discord.Color.red()
            )
            dm_embed.add_field(name="Reason", value=self.reason.value, inline=False)
            dm_embed.add_field(name="What's Next?", value="You can apply again after addressing the concerns mentioned above.", inline=False)
            await user.send(embed=dm_embed)
        except:
            pass

        if interaction.channel.name.startswith('whitelist-'):
            cog = interaction.client.get_cog('WhitelistCog')
            if cog:
                await cog.close_whitelist_ticket(interaction.channel, reason=f"Application denied: {self.reason.value}")

        await bot_log(f"[Whitelist] Application denied for {user} by {interaction.user} - Reason: {self.reason.value}")

class WhitelistTypeView(ui.View):
    """View for selecting whitelist type (Java/Bedrock)"""

    def __init__(self, moderator, target_user, whitelist_cog, channel):
        super().__init__(timeout=300)
        self.moderator = moderator
        self.target_user = target_user
        self.whitelist_cog = whitelist_cog
        self.channel = channel

    @ui.button(label='Java', style=discord.ButtonStyle.success)
    async def java_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle Java whitelist"""
        modal = UsernameModal(self.moderator, self.target_user, "Java", self.whitelist_cog, self.channel)
        await interaction.response.send_modal(modal)

    @ui.button(label='Bedrock', style=discord.ButtonStyle.primary)
    async def bedrock_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle Bedrock whitelist"""
        modal = UUIDModal(self.moderator, self.target_user, "Bedrock", self.whitelist_cog, self.channel)
        await interaction.response.send_modal(modal)

class UnwhitelistTypeView(ui.View):
    """View for selecting unwhitelist type (Java/Bedrock)"""

    def __init__(self, moderator, target_user, whitelist_cog, channel):
        super().__init__(timeout=300)
        self.moderator = moderator
        self.target_user = target_user
        self.whitelist_cog = whitelist_cog
        self.channel = channel

    @ui.button(label='Java', style=discord.ButtonStyle.danger)
    async def java_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle Java unwhitelist"""
        modal = UnwhitelistUsernameModal(self.moderator, self.target_user, "Java", self.whitelist_cog, self.channel)
        await interaction.response.send_modal(modal)

    @ui.button(label='Bedrock', style=discord.ButtonStyle.danger)
    async def bedrock_button(self, interaction: discord.Interaction, button: ui.Button):
        """Handle Bedrock unwhitelist"""
        modal = UnwhitelistUUIDModal(self.moderator, self.target_user, "Bedrock", self.whitelist_cog, self.channel)
        await interaction.response.send_modal(modal)

class UsernameModal(ui.Modal):
    """Modal for entering Java username"""

    def __init__(self, moderator, target_user, platform, whitelist_cog, channel):
        super().__init__(title=f"Java Whitelist - {target_user.display_name}")
        self.moderator = moderator
        self.target_user = target_user
        self.platform = platform
        self.whitelist_cog = whitelist_cog
        self.channel = channel

        self.username_input = ui.TextInput(
            label="Minecraft Username",
            placeholder="Enter the Java username...",
            max_length=16,
            required=True
        )
        self.add_item(self.username_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Process Java whitelist"""
        username = self.username_input.value
        command = f"whitelist add {username}"

        await interaction.response.send_message(f"Processing Java whitelist for {username}...", ephemeral=True)

        minecraft_channel = self.whitelist_cog.bot.get_channel(1374421938381783061)
        if minecraft_channel:
            await self.whitelist_cog.process_whitelist_command(
                minecraft_channel, command, username, self.target_user,
                self.platform, self.moderator, self.channel
            )

class UUIDModal(ui.Modal):
    """Modal for entering Bedrock UUID"""

    def __init__(self, moderator, target_user, platform, whitelist_cog, channel):
        super().__init__(title=f"Bedrock Whitelist - {target_user.display_name}")
        self.moderator = moderator
        self.target_user = target_user
        self.platform = platform
        self.whitelist_cog = whitelist_cog
        self.channel = channel

        self.uuid_input = ui.TextInput(
            label="Floodgate UUID",
            placeholder="Enter the Bedrock UUID...",
            max_length=100,
            required=True
        )
        self.add_item(self.uuid_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Process Bedrock whitelist"""
        fuuid = self.uuid_input.value
        command = f"fwhitelist add {fuuid}"

        await interaction.response.send_message(f"Processing Bedrock whitelist for {fuuid}...", ephemeral=True)

        minecraft_channel = self.whitelist_cog.bot.get_channel(1374421938381783061)
        if minecraft_channel:
            await self.whitelist_cog.process_whitelist_command(
                minecraft_channel, command, fuuid, self.target_user,
                self.platform, self.moderator, self.channel
            )

class UnwhitelistUsernameModal(ui.Modal):
    """Modal for entering Java username to remove"""

    def __init__(self, moderator, target_user, platform, whitelist_cog, channel):
        super().__init__(title=f"Java Unwhitelist - {target_user.display_name}")
        self.moderator = moderator
        self.target_user = target_user
        self.platform = platform
        self.whitelist_cog = whitelist_cog
        self.channel = channel

        self.username_input = ui.TextInput(
            label="Minecraft Username",
            placeholder="Enter the Java username to remove...",
            max_length=16,
            required=True
        )
        self.add_item(self.username_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Process Java unwhitelist"""
        username = self.username_input.value
        command = f"whitelist remove {username}"

        await interaction.response.send_message(f"Processing Java unwhitelist for {username}...", ephemeral=True)

        minecraft_channel = self.whitelist_cog.bot.get_channel(1374421938381783061)
        if minecraft_channel:
            await minecraft_channel.send(command)

            whitelist_role = self.target_user.guild.get_role(1374421917284565046)
            if whitelist_role and whitelist_role in self.target_user.roles:
                try:
                    await self.target_user.remove_roles(whitelist_role, reason="Unwhitelisted from Minecraft server")
                except Exception as e:
                    print(f"Error removing whitelist role: {e}")

            await self.whitelist_cog.log_whitelist(self.target_user, self.platform, username, "removed")

            embed = discord.Embed(
                title="✔ User Unwhitelisted",
                description=f"{self.target_user.mention} has been removed from the Java whitelist.",
                color=0xFF4444
            )
            await self.channel.send(embed=embed)

class UnwhitelistUUIDModal(ui.Modal):
    """Modal for entering Bedrock UUID to remove"""

    def __init__(self, moderator, target_user, platform, whitelist_cog, channel):
        super().__init__(title=f"Bedrock Unwhitelist - {target_user.display_name}")
        self.moderator = moderator
        self.target_user = target_user
        self.platform = platform
        self.whitelist_cog = whitelist_cog
        self.channel = channel

        self.uuid_input = ui.TextInput(
            label="Floodgate UUID",
            placeholder="Enter the Bedrock UUID to remove...",
            max_length=100,
            required=True
        )
        self.add_item(self.uuid_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Process Bedrock unwhitelist"""
        fuuid = self.uuid_input.value
        command = f"fwhitelist remove {fuuid}"

        await interaction.response.send_message(f"Processing Bedrock unwhitelist for {fuuid}...", ephemeral=True)

        minecraft_channel = self.whitelist_cog.bot.get_channel(1374421938381783061)
        if minecraft_channel:
            await minecraft_channel.send(command)

            whitelist_role = self.target_user.guild.get_role(1374421917284565046)
            if whitelist_role and whitelist_role in self.target_user.roles:
                try:
                    await self.target_user.remove_roles(whitelist_role, reason="Unwhitelisted from Minecraft server")
                except Exception as e:
                    print(f"Error removing whitelist role: {e}")

            await self.whitelist_cog.log_whitelist(self.target_user, self.platform, fuuid, "removed")

            embed = discord.Embed(
                title="✔ User Unwhitelisted",
                description=f"{self.target_user.mention} has been removed from the Bedrock whitelist.",
                color=0xFF4444
            )
            await self.channel.send(embed=embed)

class WhitelistCloseRequestView(ui.View):
    """View for whitelist ticket close confirmation"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, custom_id='whitelist_close_confirm')
    async def close_confirm(self, interaction: discord.Interaction, button: ui.Button):
        """Confirm ticket closure"""
        embed = discord.Embed(
            title="Whitelist Ticket Closed",
            description="This whitelist application has been closed by staff.",
            color=0xFF4444
        )

        await interaction.response.send_message(embed=embed)

        if hasattr(interaction.client, 'get_cog'):
            bot = cast(commands.Bot, interaction.client)
            cog = cast(WhitelistCog, bot.get_cog('WhitelistCog'))
            if cog and interaction.channel:
                ticket_owner = await cog.find_whitelist_ticket_owner(interaction.channel)
                await bot_log(f"[Whitelist] Ticket closed by {interaction.user} for {ticket_owner} in {interaction.channel}")

        await asyncio.sleep(3)
        if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.channel.delete(reason="Whitelist ticket closed by staff")

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(WhitelistCog(bot))
