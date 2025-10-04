from typing import Optional

import discord
from discord.ext import commands
from discord import ui
import json
import os
from datetime import datetime, timedelta
import asyncio
from bot import bot_log
from config import STAFF_LOG_CHANNEL_ID

class ModerationCog(commands.Cog):
    """Moderation system with logging and case management"""

    def __init__(self, bot):
        self.bot = bot
        self.staff_log_channel_id = STAFF_LOG_CHANNEL_ID
        self.appeals_channel_id = 1419528947561005138
        self.data_file = "data/moderation_cases.json"
        self.appeals_file = "data/appeals.json"
        self.notify_users_file = "data/notify_users.json"
        self.ensure_data_file()

        self.life_team_role_name = "Life Team"
        self.administration_role_name = "Administration"
        self.owner_role_name = "Owner"
        self.owner_id = 1374421925790482483

    def ensure_data_file(self):
        """Create moderation data file if it doesn't exist"""
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(self.data_file):
            with open(self.data_file, "w") as f:
                json.dump({"cases": [], "next_case_number": 1}, f)
        if not os.path.exists(self.appeals_file):
            with open(self.appeals_file, "w") as f:
                json.dump({"appeals": [], "next_appeal_number": 1}, f)
        if not os.path.exists(self.notify_users_file):
            with open(self.notify_users_file, "w") as f:
                json.dump({"notify_users": []}, f)

    def load_cases(self):
        """Load moderation cases from file"""
        with open(self.data_file, "r") as f:
            return json.load(f)

    def save_cases(self, data):
        """Save moderation cases to file"""
        with open(self.data_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_next_case_number(self):
        """Get the next case number and increment it"""
        data = self.load_cases()
        case_number = data["next_case_number"]
        data["next_case_number"] += 1
        self.save_cases(data)
        return case_number

    def load_appeals(self):
        """Load appeals from file"""
        with open(self.appeals_file, "r") as f:
            return json.load(f)

    def save_appeals(self, data):
        """Save appeals to file"""
        with open(self.appeals_file, "w") as f:
            json.dump(data, f, indent=2)

    def get_next_appeal_number(self):
        """Get the next appeal number and increment it"""
        data = self.load_appeals()
        appeal_number = data["next_appeal_number"]
        data["next_appeal_number"] += 1
        self.save_appeals(data)
        return appeal_number

    def load_notify_users(self):
        """Load notify users list"""
        with open(self.notify_users_file, "r") as f:
            return json.load(f)

    def save_notify_users(self, data):
        """Save notify users list"""
        with open(self.notify_users_file, "w") as f:
            json.dump(data, f, indent=2)

    def has_life_team_permissions(self, member):
        """Check if member has Life Team permissions or higher"""
        if member.id == self.owner_id:
            return True

        role_names = [role.name for role in member.roles]
        return (self.life_team_role_name in role_names or
                self.administration_role_name in role_names or
                self.owner_role_name in role_names)

    def has_ban_permissions(self, member):
        """Check if member can use ban command"""
        if member.id == self.owner_id:
            return True

        role_names = [role.name for role in member.roles]
        return (self.administration_role_name in role_names or
                self.owner_role_name in role_names)

    async def send_staff_log(self, moderator, target_user, infraction_type, reason, case_number):
        """Send log to staff channel and bot log channel"""
        channel = self.bot.get_channel(self.staff_log_channel_id)
        if channel:
            embed = discord.Embed(
                title=f"Moderation Action - Case
                color=discord.Color.orange()
            )
            embed.add_field(name="Moderator", value=f"{moderator.mention} ({moderator.id})", inline=True)
            embed.add_field(name="Target", value=f"{target_user.mention} ({target_user.id})", inline=True)
            embed.add_field(name="Type", value=infraction_type, inline=True)
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.timestamp = datetime.now()
            await channel.send(embed=embed)
        await bot_log(f"[Moderation] {moderator} -> {target_user} | {infraction_type} | {reason}")

    async def dm_user_infraction(self, user, infraction_type, reason, case_number):
        """DM user about their infraction"""
        try:
            embed = discord.Embed(
                title="Moderation Notice",
                description=f"You have received a moderation action in NewLifeSMP",
                color=discord.Color.red()
            )
            embed.add_field(name="Type", value=infraction_type, inline=True)
            embed.add_field(name="Case
            embed.add_field(name="Reason", value=reason, inline=False)
            embed.add_field(name="Date", value=datetime.now().strftime("%m/%d/%Y %I:%M %p"), inline=False)
            embed.set_footer(text="If you believe this is in error, contact staff")

            await user.send(embed=embed)
        except discord.Forbidden:
            pass

    @commands.command(name='log')
    async def log_infraction(self, ctx, target: discord.Member):
        """Log an infraction against a user (Life Team+)"""
        if not self.has_life_team_permissions(ctx.author):
            await ctx.send("✖ You don't have permission to use this command.")
            return
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        embed = discord.Embed(
            title="Log Infraction",
            description=f"Select the type of infraction for {target.mention}:",
            color=discord.Color.orange()
        )
        view = LogView(ctx.author, target, self, ctx.channel)
        msg = await ctx.send(embed=embed, view=view, ephemeral=True)
        await asyncio.sleep(5)
        try:
            await msg.delete()
        except Exception:
            pass

    @commands.command(name='ban')
    async def ban_user(self, ctx, target: discord.Member, *, reason="No reason provided"):
        """Ban a user from the server (Administration+)"""
        if not self.has_ban_permissions(ctx.author):
            await ctx.send("✖ You don't have permission to use this command.")
            return
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        try:
            await target.ban(reason=f"Banned by {ctx.author}: {reason}")
            case_number = self.get_next_case_number()
            data = self.load_cases()
            case_data = {
                "case_number": case_number,
                "moderator_id": ctx.author.id,
                "moderator_name": str(ctx.author),
                "target_id": target.id,
                "target_name": str(target),
                "type": "Discord Ban",
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "date": datetime.now().strftime("%m/%d/%Y"),
                "time": datetime.now().strftime("%I:%M %p")
            }
            data["cases"].append(case_data)
            self.save_cases(data)
            await self.send_staff_log(ctx.author, target, "Discord Ban", reason, case_number)
            msg = await ctx.send(f"✔ {target.mention} was banned.")
            await asyncio.sleep(5)
            try:
                await msg.delete()
            except Exception:
                pass
        except discord.Forbidden:
            await ctx.send("✖ I don't have permission to ban this user.")
        except Exception as e:
            await ctx.send(f"✖ Error banning user: {str(e)}")

    @commands.command(name='mute')
    async def mute_user(self, ctx, target: discord.Member, duration: str = "60m", *, reason="No reason provided"):
        """Timeout a user with duration format: 5m, 2h, 1d (Life Team+)"""
        if not self.has_life_team_permissions(ctx.author):
            await ctx.send("✖ You don't have permission to use this command.")
            return
        try:
            await ctx.message.delete()
        except discord.NotFound:
            pass
        try:
            if duration.endswith('m') or duration.endswith('min'):
                minutes = int(duration.replace('m', '').replace('in', ''))
                duration_text = f"{minutes} minute(s)"
            elif duration.endswith('h') or duration.endswith('hour'):
                hours = int(duration.replace('h', '').replace('our', ''))
                minutes = hours * 60
                duration_text = f"{hours} hour(s)"
            elif duration.endswith('d') or duration.endswith('day'):
                days = int(duration.replace('d', '').replace('ay', ''))
                minutes = days * 24 * 60
                duration_text = f"{days} day(s)"
            else:
                minutes = int(duration)
                duration_text = f"{minutes} minute(s)"
        except ValueError:
            await ctx.send("✖ Invalid duration format. Use: 5m, 2h, 1d, or just a number for minutes.")
            return
        if minutes > 40320:
            await ctx.send("✖ Maximum timeout duration is 28 days.")
            return
        try:
            timeout_until = datetime.now() + timedelta(minutes=minutes)
            await target.timeout(timeout_until, reason=f"Muted by {ctx.author}: {reason}")
            case_number = self.get_next_case_number()
            data = self.load_cases()
            case_data = {
                "case_number": case_number,
                "moderator_id": ctx.author.id,
                "moderator_name": str(ctx.author),
                "target_id": target.id,
                "target_name": str(target),
                "type": f"Timeout ({duration_text})",
                "reason": reason,
                "timestamp": datetime.now().isoformat(),
                "date": datetime.now().strftime("%m/%d/%Y"),
                "time": datetime.now().strftime("%I:%M %p")
            }
            data["cases"].append(case_data)
            self.save_cases(data)
            await self.send_staff_log(ctx.author, target, f"Timeout ({duration_text})", reason, case_number)
            msg = await ctx.send(f"✔ {target.mention} was muted for {duration_text}.")
            await asyncio.sleep(5)
            try:
                await msg.delete()
            except Exception:
                pass
        except discord.Forbidden:
            await ctx.send("✖ I don't have permission to timeout this user.")
        except Exception as e:
            await ctx.send(f"✖ Error muting user: {str(e)}")

    @commands.command(name='lock')
    async def lock_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Lock a channel (Life Team+)"""
        if not self.has_life_team_permissions(ctx.author):
            await ctx.send("✖ You don't have permission to use this command.")
            return

        target_channel = channel if channel is not None else ctx.channel

        try:
            everyone = ctx.guild.default_role

            await target_channel.set_permissions(everyone, send_messages=False, reason=f"Channel locked by {ctx.author}")

            embed = discord.Embed(
                title="✔ Channel Locked",
                description=f"{target_channel.mention} has been locked.",
                color=discord.Color.red()
            )
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)

            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("✖ I don't have permission to lock this channel.")
        except Exception as e:
            await ctx.send(f"✖ Error locking channel: {str(e)}")

    @commands.command(name='unlock')
    async def unlock_channel(self, ctx, channel: Optional[discord.TextChannel] = None):
        """Unlock a channel (Life Team+)"""
        if not self.has_life_team_permissions(ctx.author):
            await ctx.send("✖ You don't have permission to use this command.")
            return

        target_channel = channel if channel is not None else ctx.channel

        try:
            everyone = ctx.guild.default_role

            await target_channel.set_permissions(everyone, send_messages=None, reason=f"Channel unlocked by {ctx.author}")

            embed = discord.Embed(
                title="✔ Channel Unlocked",
                description=f"{target_channel.mention} has been unlocked.",
                color=discord.Color.green()
            )
            embed.add_field(name="Moderator", value=ctx.author.mention, inline=True)

            await ctx.send(embed=embed)

        except discord.Forbidden:
            await ctx.send("✖ I don't have permission to unlock this channel.")
        except Exception as e:
            await ctx.send(f"✖ Error unlocking channel: {str(e)}")

    @commands.command(name='lookup')
    async def lookup_infractions(self, ctx, *, search_term):
        """Search for infractions, tickets, and whitelist data by username or ID (Life Team+)"""
        if not self.has_life_team_permissions(ctx.author):
            await ctx.send("✖ You don't have permission to use this command.")
            return

        user = None
        if search_term.startswith('<@') and search_term.endswith('>'):
            user_id = int(search_term[2:-1].replace('!', ''))
            user = self.bot.get_user(user_id)
        elif search_term.isdigit():
            user = self.bot.get_user(int(search_term))
        else:
            for member in ctx.guild.members:
                if search_term.lower() in member.display_name.lower() or search_term.lower() in member.name.lower():
                    user = member
                    break

        embed = discord.Embed(
            title=f"Lookup Results for '{search_term}'",
            color=discord.Color.blue()
        )

        if user:
            embed.add_field(name="User", value=f"{user.mention} ({user.display_name})", inline=False)
            embed.add_field(name="User ID", value=str(user.id), inline=True)
            embed.add_field(name="Account Created", value=user.created_at.strftime('%B %d, %Y'), inline=True)

            if hasattr(user, 'roles'):
                whitelisted_role = discord.utils.get(user.roles, id=1419540080081633310)
                staff_role = discord.utils.get(user.roles, id=1374421915938324583)
                whitelist_staff_role = discord.utils.get(user.roles, id=1376432927444963420)

                status_parts = []
                if whitelisted_role:
                    status_parts.append("Whitelisted")
                if staff_role:
                    status_parts.append("Staff Member")
                if whitelist_staff_role:
                    status_parts.append("Whitelist Staff")

                if status_parts:
                    embed.add_field(name="Status", value=" | ".join(status_parts), inline=False)
                else:
                    embed.add_field(name="Status", value="Regular Member", inline=False)

            embed.set_thumbnail(url=user.avatar.url if user.avatar else user.default_avatar.url)

        try:
            support_cog = self.bot.get_cog('SupportCog')
            if support_cog and user and user.id in support_cog.active_tickets:
                ticket_data = support_cog.active_tickets[user.id]
                channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                channel = self.bot.get_channel(channel_id)
                if channel:
                    embed.add_field(name="Active Support Ticket", value=f"{channel.mention}", inline=True)

            whitelist_cog = self.bot.get_cog('WhitelistCog')
            if whitelist_cog and user:
                if hasattr(whitelist_cog, 'active_whitelist_tickets') and user.id in whitelist_cog.active_whitelist_tickets:
                    ticket_data = whitelist_cog.active_whitelist_tickets[user.id]
                    channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                    channel = self.bot.get_channel(channel_id)
                    if channel:
                        embed.add_field(name="Active Whitelist Ticket", value=f"{channel.mention}", inline=True)

                if hasattr(whitelist_cog, 'pending_whitelist') and user and user.id in whitelist_cog.pending_whitelist:
                    pending_data = whitelist_cog.pending_whitelist[user.id]
                    embed.add_field(
                        name="Pending Application",
                        value=f"Username: {pending_data.get('username', 'Unknown')}\nType: {pending_data.get('type', 'Unknown')}",
                        inline=False
                    )
        except Exception as e:
            print(f"Error accessing ticket data: {e}")

        data = self.load_cases()
        cases = data.get("cases", [])

        if cases:
            matching_cases = []
            search_lower = search_term.lower()

            for case in cases:
                if search_term.isdigit() and case["case_number"] == int(search_term):
                    matching_cases.append(case)
                    continue

                if (search_lower in case["target_name"].lower() or
                    search_lower in case["moderator_name"].lower()):
                    matching_cases.append(case)
                    continue

                if search_lower in case["type"].lower():
                    matching_cases.append(case)
                    continue

                if (search_term.isdigit() and
                    (case["target_id"] == int(search_term) or case["moderator_id"] == int(search_term))):
                    matching_cases.append(case)
                    continue

            if matching_cases:
                matching_cases.sort(key=lambda x: x["case_number"], reverse=True)

                embed.add_field(name="Recent Infractions", value=f"Found {len(matching_cases)} case(s)", inline=False)

                for i, case in enumerate(matching_cases[:5]):
                    case_info = f"**{case['type']}** | {case['target_name']} | {case['date']}"
                    if len(case['reason']) > 50:
                        case_info += f"\n*{case['reason'][:50]}...*"
                    else:
                        case_info += f"\n*{case['reason']}*"

                    embed.add_field(
                        name=f"Case
                        value=case_info,
                        inline=True
                    )

                if len(matching_cases) > 5:
                    embed.set_footer(text=f"Showing 5 of {len(matching_cases)} infractions. Use case number for details.")

        if user:
            view = LookupView(user, matching_cases if 'matching_cases' in locals() else [], self.bot)
            await ctx.send(embed=embed, view=view)
        else:
            await ctx.send(embed=embed)

class LookupView(ui.View):
    """Interactive view for lookup results"""

    def __init__(self, user: discord.User, cases: list, bot):
        super().__init__(timeout=300)
        self.user = user
        self.cases = cases
        self.bot = bot

    @ui.button(label='View Logs', style=discord.ButtonStyle.primary, emoji='📋')
    async def view_logs(self, interaction: discord.Interaction, button: ui.Button):
        """Show detailed moderation logs"""
        if not self.cases:
            await interaction.response.send_message("No moderation logs found for this user.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"Moderation Logs - {self.user.display_name}",
            color=discord.Color.red()
        )

        for case in self.cases[:10]:
            case_info = f"**Moderator**: {case['moderator_name']}\n"
            case_info += f"**Date**: {case['date']} at {case['time']}\n"
            case_info += f"**Reason**: {case['reason']}"

            embed.add_field(
                name=f"Case
                value=case_info,
                inline=False
            )

        if len(self.cases) > 10:
            embed.set_footer(text=f"Showing 10 of {len(self.cases)} total cases")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label='Whitelist Info', style=discord.ButtonStyle.success, emoji='✅')
    async def whitelist_info(self, interaction: discord.Interaction, button: ui.Button):
        """Show whitelist information"""
        try:
            whitelist_cog = self.bot.get_cog('WhitelistCog')
            if not whitelist_cog:
                await interaction.response.send_message("Whitelist system not available.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"Whitelist Info - {self.user.display_name}",
                color=discord.Color.green()
            )

            guild_member = interaction.guild.get_member(self.user.id) if interaction.guild else None
            if guild_member and hasattr(guild_member, 'roles'):
                whitelisted_role = discord.utils.get(guild_member.roles, id=1419540080081633310)
                if whitelisted_role:
                    embed.add_field(name="Status", value="✔ Whitelisted", inline=False)
                else:
                    embed.add_field(name="Status", value="✖ Not Whitelisted", inline=False)

            if hasattr(whitelist_cog, 'active_whitelist_tickets') and self.user.id in whitelist_cog.active_whitelist_tickets:
                ticket_data = whitelist_cog.active_whitelist_tickets[self.user.id]
                channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                if channel_id:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel and hasattr(channel, 'mention'):
                        embed.add_field(name="Active Ticket", value=channel.mention, inline=False)

            if hasattr(whitelist_cog, 'pending_whitelist') and self.user.id in whitelist_cog.pending_whitelist:
                pending_data = whitelist_cog.pending_whitelist[self.user.id]
                embed.add_field(
                    name="Pending Application",
                    value=f"Username: {pending_data.get('username', 'Unknown')}\nType: {pending_data.get('type', 'Unknown')}",
                    inline=False
                )

            if not embed.fields:
                embed.add_field(name="No Data", value="No whitelist information found.", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error retrieving whitelist info: {str(e)}", ephemeral=True)

    @ui.button(label='Ticket History', style=discord.ButtonStyle.secondary, emoji='🎫')
    async def ticket_history(self, interaction: discord.Interaction, button: ui.Button):
        """Show ticket history and transcripts"""
        try:
            embed = discord.Embed(
                title=f"Ticket History - {self.user.display_name}",
                color=discord.Color.blue()
            )

            support_cog = self.bot.get_cog('SupportCog')
            if support_cog and hasattr(support_cog, 'active_tickets') and self.user.id in support_cog.active_tickets:
                ticket_data = support_cog.active_tickets[self.user.id]
                channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                if channel_id:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel and hasattr(channel, 'mention'):
                        embed.add_field(name="Active Support Ticket", value=channel.mention, inline=False)

            whitelist_cog = self.bot.get_cog('WhitelistCog')
            if whitelist_cog and hasattr(whitelist_cog, 'active_whitelist_tickets') and self.user.id in whitelist_cog.active_whitelist_tickets:
                ticket_data = whitelist_cog.active_whitelist_tickets[self.user.id]
                channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                if channel_id:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel and hasattr(channel, 'mention'):
                        embed.add_field(name="Active Whitelist Ticket", value=channel.mention, inline=False)

            embed.add_field(
                name="Transcripts",
                value="Transcripts are available through the !transcribe command in active tickets or can be found in the transcript logs channel.",
                inline=False
            )

            if len(embed.fields) == 1:
                embed.add_field(name="No Active Tickets", value="User has no active tickets currently.", inline=False)

            await interaction.response.send_message(embed=embed, ephemeral=True)

        except Exception as e:
            await interaction.response.send_message(f"Error retrieving ticket history: {str(e)}", ephemeral=True)

class LogView(ui.View):
    """Interactive view for logging infractions"""

    def __init__(self, moderator, target_user, moderation_cog, channel):
        super().__init__(timeout=300)
        self.moderator = moderator
        self.target_user = target_user
        self.moderation_cog = moderation_cog
        self.channel = channel
        self.infraction_type = None
        self.reason = None

    @ui.button(label='Warning', style=discord.ButtonStyle.secondary)
    async def warning_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_infraction_type(interaction, "Warning")

    @ui.button(label='Ingame Kick', style=discord.ButtonStyle.primary)
    async def kick_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_infraction_type(interaction, "Ingame Kick")

    @ui.button(label='Ingame Ban', style=discord.ButtonStyle.danger)
    async def ban_button(self, interaction: discord.Interaction, button: ui.Button):
        await self.handle_infraction_type(interaction, "Ingame Ban")

    async def handle_infraction_type(self, interaction, infraction_type):
        """Handle infraction type selection and show reason modal"""
        self.infraction_type = infraction_type

        modal = ReasonModal(self.moderator, self.target_user, self.infraction_type, self.moderation_cog, self.channel)
        await interaction.response.send_modal(modal)

class ReasonModal(ui.Modal):
    """Modal for entering infraction reason"""

    def __init__(self, moderator, target_user, infraction_type, moderation_cog, channel):
        super().__init__(title=f"Reason for {infraction_type}")
        self.moderator = moderator
        self.target_user = target_user
        self.infraction_type = infraction_type
        self.moderation_cog = moderation_cog
        self.channel = channel

        self.reason_input = ui.TextInput(
            label="Reason",
            placeholder="Enter the reason for this infraction...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        """Process the infraction when modal is submitted"""
        reason = self.reason_input.value

        case_number = self.moderation_cog.get_next_case_number()

        data = self.moderation_cog.load_cases()
        case_data = {
            "case_number": case_number,
            "moderator_id": self.moderator.id,
            "moderator_name": str(self.moderator),
            "target_id": self.target_user.id,
            "target_name": str(self.target_user),
            "type": self.infraction_type,
            "reason": reason,
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%m/%d/%Y"),
            "time": datetime.now().strftime("%I:%M %p")
        }
        data["cases"].append(case_data)
        self.moderation_cog.save_cases(data)

        await self.moderation_cog.send_staff_log(self.moderator, self.target_user, self.infraction_type, reason, case_number)
        await self.moderation_cog.dm_user_infraction(self.target_user, self.infraction_type, reason, case_number)

        embed = discord.Embed(
            title="✔ Infraction Logged",
            description=f"Case
            color=discord.Color.green()
        )
        embed.add_field(name="Type", value=self.infraction_type, inline=True)
        embed.add_field(name="Reason", value=reason, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        public_message = f"✔ {self.target_user.mention} has been {self.infraction_type.lower()}."
        await self.channel.send(public_message)

async def setup(bot):
    """Setup function for the cog"""
    await bot.add_cog(ModerationCog(bot))
