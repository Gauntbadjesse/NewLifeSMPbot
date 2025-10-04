import discord
from discord.ext import commands
from discord import ui
import json
import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, cast
import aiohttp
from config import LOG_CHANNEL_ID, STAFF_LOG_CHANNEL_ID
from bot import bot_log

class SupportCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_tickets = {}
        self.close_timers = {}
        self.support_panel_message_id = None
        self.load_active_tickets()
        self.load_support_panel_data()

    def load_active_tickets(self):
        """Load active tickets from data file"""
        try:
            with open("data/active_tickets.json", "r") as f:
                data = json.load(f)
                self.active_tickets = {}
                for user_id, ticket_data in data.items():
                    if isinstance(ticket_data, dict):
                        self.active_tickets[user_id] = ticket_data
                    else:
                        self.active_tickets[user_id] = {
                            "channel_id": ticket_data,
                            "owner_id": int(user_id)
                        }
        except (FileNotFoundError, json.JSONDecodeError):
            self.active_tickets = {}

    def save_active_tickets(self):
        """Save active tickets to data file"""
        os.makedirs("data", exist_ok=True)
        with open("data/active_tickets.json", "w") as f:
            json.dump(self.active_tickets, f, indent=2)

    def load_support_panel_data(self):
        """Load support panel message ID"""
        try:
            with open("data/support_panel.json", "r") as f:
                data = json.load(f)
                self.support_panel_message_id = data.get("message_id")
        except (FileNotFoundError, json.JSONDecodeError):
            self.support_panel_message_id = None

    def save_support_panel_data(self):
        """Save support panel message ID"""
        os.makedirs("data", exist_ok=True)
        with open("data/support_panel.json", "w") as f:
            json.dump({"message_id": self.support_panel_message_id}, f, indent=2)

    async def cog_load(self):
        """Add persistent views when cog loads and ensure support panel exists"""
        self.bot.add_view(SupportView())
        self.bot.add_view(CloseRequestView())
        self.bot.add_view(StaffSupportView())

        await self.ensure_support_panel()

        print("Support cog loaded and persistent views added")

    @commands.Cog.listener()
    async def on_ready(self):
        """Bot ready event"""
        print("Support cog ready")

    async def ensure_support_panel(self):
        """Ensure the support panel exists in the support channel"""
        support_channel = self.bot.get_channel(1386212545479708704)
        if not support_channel:
            print("Support channel not found!")
            return

        if not self.support_panel_message_id:
            self.support_panel_message_id = 1419543749872062474
            self.save_support_panel_data()
            print(f"Using provided message ID: {self.support_panel_message_id}")

        panel_exists = False
        if self.support_panel_message_id:
            try:
                message = await support_channel.fetch_message(self.support_panel_message_id)
                print(f"Found existing support panel message: {message.id}")

                if message.components:
                    panel_exists = True
                    print("Support panel exists and has components - adding persistent view")
                    view = SupportView()
                    try:
                        await message.edit(view=view)
                        print("Successfully updated message with working view")
                    except Exception as e:
                        print(f"Could not update message view: {e}")
                        panel_exists = False
                else:
                    print("Support panel message exists but has no components")

            except discord.NotFound:
                print(f"Stored support panel message {self.support_panel_message_id} not found, will recreate")
                self.support_panel_message_id = None
                self.save_support_panel_data()
            except Exception as e:
                print(f"Error checking support panel: {e}")

        if not panel_exists:
            print("Creating new support panel...")
            await self.create_support_panel()

    async def create_support_panel(self):
        """Create the support panel embed and buttons"""
        support_channel = self.bot.get_channel(1386212545479708704)
        if not support_channel:
            print("Support channel not found!")
            return

        embed = discord.Embed(
            title="Support & Ticket System",
            description="**Need assistance or want to report a player?**\nOur support team is here to help you with any questions or concerns.",
            color=0x2F3136
        )

        embed.add_field(
            name="General Support",
            value="• Questions about server rules or gameplay\n• Technical issues or bugs\n• Account-related inquiries\n• General assistance needed\n\n*A staff member will respond promptly to assist you.*",
            inline=True
        )

        embed.add_field(
            name="Player Reports",
            value="• Rule violations by other players\n• Cheating or exploiting reports\n• Inappropriate behavior reports\n• Evidence required for all reports\n\n*All reports are reviewed by our moderation team.*",
            inline=True
        )

        embed.add_field(
            name="Frequently Asked Questions",
            value=(
                "**Before opening a ticket, check if your question is answered below:**\n\n"
                f"• **Server Information & Rules** → <
                f"• **How do I create templates?** → <
                f"• **Custom crafting recipes** → <
                f"• **Appeal infractions** → Use Infraction Appeal in <
                f"• **Server guides & tutorials** → <
                "*Still need help? Click a button below to open a private ticket.*"
            ),
            inline=False
        )

        embed.add_field(
            name="Ticket Guidelines",
            value=(
                "• **One ticket per user** - Please wait for your current ticket to be resolved\n"
                "• **Be patient** - Our staff will respond as soon as possible\n"
                "• **Provide details** - The more information you give, the faster we can help\n"
                "• **Stay respectful** - Maintain a professional tone in all interactions"
            ),
            inline=False
        )

        embed.set_footer(
            text="Professional Support • Powered by TheNewLife Staff Team",
            icon_url="https://cdn.discordapp.com/attachments/123456789/123456789/server_icon.png"
        )
        embed.set_thumbnail(url="https://cdn.discordapp.com/attachments/123456789/123456789/support_icon.png")

        view = SupportView()
        message = await support_channel.send(embed=embed, view=view)

        self.support_panel_message_id = message.id
        self.save_support_panel_data()
        print("✔ Support panel created and saved!")

    @commands.command(name='support_panel')
    @commands.has_permissions(administrator=True)
    async def setup_support_panel(self, ctx):
        """Set up the support panel in the support channel (manually)"""
        support_channel = self.bot.get_channel(1386212545479708704)
        if not support_channel:
            await ctx.send("Support channel not found!")
            return

        try:
            await support_channel.purge(limit=100)
        except:
            pass

        await self.create_support_panel()
        await ctx.send("✔ Support panel has been set up and will persist across restarts!")

    @commands.command(name='fix_support')
    @commands.has_permissions(administrator=True)
    async def fix_support_panel(self, ctx, message_id: Optional[int] = None):
        """Fix the support panel by adding working buttons to existing message"""
        support_channel = self.bot.get_channel(1386212545479708704)
        if not support_channel:
            await ctx.send("Support channel not found!")
            return

        target_message_id = message_id or self.support_panel_message_id or 1419543749872062474

        try:
            message = await support_channel.fetch_message(target_message_id)

            view = SupportView()
            await message.edit(view=view)

            self.support_panel_message_id = message.id
            self.save_support_panel_data()

            await ctx.send(f"✔ Support panel fixed! Message ID {message.id} now has working buttons.")

        except discord.NotFound:
            await ctx.send(f"✖ Message with ID {target_message_id} not found!")
        except Exception as e:
            await ctx.send(f"✖ Error fixing support panel: {e}")

    @commands.command(name='close')
    @commands.has_any_role(1374421915938324583, 1376432927444963420)
    async def close_ticket(self, ctx):
        """Request to close a ticket"""
        is_support_ticket = ctx.channel.name.startswith(('gen-', 'rep-'))
        is_whitelist_ticket = ctx.channel.name.startswith('whitelist-')

        if not is_support_ticket and not is_whitelist_ticket:
            await ctx.send("This command can only be used in ticket channels.", delete_after=5)
            await ctx.message.delete()
            return

        if is_support_ticket:
            ticket_owner = await self.find_ticket_owner(ctx.channel)
        else:
            whitelist_cog = self.bot.get_cog('WhitelistCog')
            if whitelist_cog:
                ticket_owner = await whitelist_cog.find_whitelist_ticket_owner(ctx.channel)
            else:
                ticket_owner = None

        if not ticket_owner:
            await ctx.send("Could not find ticket owner.", delete_after=5)
            await ctx.message.delete()
            return

        await ctx.message.delete()

        embed = discord.Embed(
            title="Ticket Close Request",
            description="**A staff member has requested to close this ticket.**",
            color=0xFF8C00
        )
        embed.add_field(
            name="Next Steps",
            value="• Click **Close Ticket** if your issue has been resolved\n• Click **Keep Open** if you still need assistance",
            inline=False
        )
        embed.add_field(
            name="No Rush",
            value="Take your time to decide. This ticket will remain open until you make a choice.",
            inline=False
        )
        embed.set_footer(
            text="TheNewLife Support Team • Professional Service",
            icon_url="https://cdn.discordapp.com/attachments/123456789/123456789/staff_icon.png"
        )

        if is_whitelist_ticket:
            whitelist_cog = self.bot.get_cog('WhitelistCog')
            if whitelist_cog:
                from cogs.whitelist import WhitelistCloseRequestView
                view = WhitelistCloseRequestView()
            else:
                view = CloseRequestView()
        else:
            view = CloseRequestView()

        await ctx.send(f"{ticket_owner.mention}", embed=embed, view=view)
        await bot_log(f"[Support] Ticket close requested by {ctx.author} in {ctx.channel}")

    @commands.command(name='tclose')
    @commands.has_any_role(1374421915938324583, 1376432927444963420)
    async def timed_close(self, ctx, duration: str):
        """Close ticket after specified time (e.g., 1h, 30m, 2d)"""
        is_support_ticket = ctx.channel.name.startswith(('gen-', 'rep-'))
        is_whitelist_ticket = ctx.channel.name.startswith('whitelist-')

        if not is_support_ticket and not is_whitelist_ticket:
            await ctx.send("This command can only be used in ticket channels.", delete_after=5)
            return

        try:
            time_seconds = self.parse_duration(duration)
            if time_seconds is None:
                await ctx.send("Invalid duration format. Use: 1h, 30m, 2d, etc.", delete_after=5)
                await ctx.message.delete()
                return
        except:
            await ctx.send("Invalid duration format. Use: 1h, 30m, 2d, etc.", delete_after=5)
            await ctx.message.delete()
            return

        if ctx.channel.id in self.close_timers:
            self.close_timers[ctx.channel.id].cancel()

        if is_whitelist_ticket:
            whitelist_cog = self.bot.get_cog('WhitelistCog')
            if whitelist_cog:
                if ctx.channel.id in whitelist_cog.close_timers:
                    whitelist_cog.close_timers[ctx.channel.id].cancel()

                embed = discord.Embed(
                    title="Whitelist Ticket Auto-Close Scheduled",
                    description=f"This ticket will automatically close in **{duration}** if no further action is taken.",
                    color=0xFFCC00
                )
                await ctx.send(embed=embed)

                whitelist_cog.close_timers[ctx.channel.id] = asyncio.create_task(
                    whitelist_cog.delayed_close_whitelist(ctx.channel, time_seconds)
                )
                return

        await ctx.message.delete()

        task = asyncio.create_task(self.delayed_close(ctx.channel, time_seconds))
        self.close_timers[ctx.channel.id] = task

        embed = discord.Embed(
            title="Timed Close",
            description=f"This ticket will automatically close in **{duration}**",
            color=discord.Color.yellow()
        )
        embed.add_field(
            name="Cancel Timer",
            value="Use `!tcancel` to cancel the automatic close",
            inline=False
        )

        await ctx.send(embed=embed)
        await bot_log(f"[Support] Ticket close scheduled for {ctx.channel} in {duration}")

    @commands.command(name='tcancel')
    @commands.has_any_role(1374421915938324583)
    async def cancel_timed_close(self, ctx):
        """Cancel timed close"""
        if not ctx.channel.name.startswith(('gen-', 'rep-')):
            await ctx.send("This command can only be used in ticket channels.", delete_after=5)
            await ctx.message.delete()
            return

        if ctx.channel.id in self.close_timers:
            self.close_timers[ctx.channel.id].cancel()
            del self.close_timers[ctx.channel.id]

            await ctx.message.delete()

            embed = discord.Embed(
                title="Timer Cancelled",
                description="The automatic close timer has been cancelled.",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed, delete_after=10)
            await bot_log(f"[Support] Ticket close timer cancelled for {ctx.channel}")
        else:
            await ctx.send("No active timer found for this ticket.", delete_after=5)
            await ctx.message.delete()

    @commands.command(name='transcribe')
    @commands.has_any_role(1374421915938324583, 1376432927444963420)
    async def transcribe_ticket(self, ctx):
        """Create a transcript of the current ticket channel"""
        is_support_ticket = ctx.channel.name.startswith(('gen-', 'rep-'))
        is_whitelist_ticket = ctx.channel.name.startswith('whitelist-')

        if not is_support_ticket and not is_whitelist_ticket:
            await ctx.send("This command can only be used in ticket channels.", delete_after=5)
            await ctx.message.delete()
            return

        await ctx.message.delete()

        transcript_content = await self.create_transcript(ctx.channel)

        prefix = "whitelist_transcript" if is_whitelist_ticket else "transcript"
        transcript_filename = f"{prefix}_{ctx.channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        transcript_path = os.path.join("data", "transcripts", transcript_filename)

        os.makedirs(os.path.dirname(transcript_path), exist_ok=True)

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript_content)

        transcript_url = await self.upload_transcript(transcript_path, transcript_filename)

        message_count = transcript_content.count('[') - 2  # Rough count excluding header brackets

        transcript_channel = self.bot.get_channel(1419539388937015316)
        if transcript_channel:
            ticket_type = "Whitelist Ticket" if is_whitelist_ticket else "Support Ticket"
            embed = discord.Embed(
                title=f"{ticket_type} Transcript Generated",
                description=f"Transcript for {ctx.channel.mention}",
                color=0x00FF7F
            )
            embed.add_field(name="Channel", value=ctx.channel.name, inline=True)
            embed.add_field(name="Generated by", value=ctx.author.mention, inline=True)
            embed.add_field(name="Messages", value=str(message_count), inline=True)
            embed.add_field(name="View Transcript", value=f"[Click here to view online]({transcript_url})", inline=False)
            if transcript_url.startswith('http'):
                embed.add_field(name="Direct Link", value=transcript_url, inline=False)
            embed.timestamp = datetime.now()

            await transcript_channel.send(embed=embed)

        confirm_embed = discord.Embed(
            title="Transcript Created ✔",
            description=f"A transcript has been generated and uploaded online.\n[View Transcript]({transcript_url})" if transcript_url.startswith('http') else "A transcript has been generated and saved locally.",
            color=0x00FF7F
        )
        if transcript_url.startswith('http'):
            confirm_embed.add_field(name="External Link", value="The transcript is hosted on GitHub Gist for easy viewing", inline=False)

        await ctx.send(embed=confirm_embed, delete_after=15)

    async def create_transcript(self, channel):
        """Create a pretty text transcript of channel messages"""
        messages = []
        async for message in channel.history(limit=None, oldest_first=True):
            messages.append(message)

        if not messages:
            return "No messages found in this channel."

        transcript_lines = []
        transcript_lines.append("=" * 80)
        transcript_lines.append(f"DISCORD SUPPORT TICKET TRANSCRIPT")
        transcript_lines.append("=" * 80)
        transcript_lines.append(f"Channel:
        transcript_lines.append(f"Channel ID: {channel.id}")
        transcript_lines.append(f"Transcript Created: {datetime.now().strftime('%B %d, %Y at %I:%M %p UTC')}")
        transcript_lines.append(f"Total Messages: {len(messages)}")
        transcript_lines.append("=" * 80)
        transcript_lines.append("")

        current_date = None
        for message in messages:
            message_date = message.created_at.strftime('%B %d, %Y')
            if current_date != message_date:
                current_date = message_date
                transcript_lines.append("")
                transcript_lines.append(f"--- {message_date} ---")
                transcript_lines.append("")

            timestamp = message.created_at.strftime('%I:%M %p')

            author_name = message.author.display_name
            if message.author.bot:
                author_name += " [BOT]"

            transcript_lines.append(f"[{timestamp}] {author_name}:")

            if message.content:
                content_lines = message.content.split('\n')
                for line in content_lines:
                    transcript_lines.append(f"    {line}")
            else:
                transcript_lines.append("    [No text content]")

            if message.attachments:
                transcript_lines.append("    Attachments:")
                for attachment in message.attachments:
                    transcript_lines.append(f"      - {attachment.filename} ({attachment.size} bytes)")
                    transcript_lines.append(f"        {attachment.url}")

            if message.embeds:
                transcript_lines.append("    Embeds:")
                for embed in message.embeds:
                    if embed.title:
                        transcript_lines.append(f"      Title: {embed.title}")
                    if embed.description:
                        desc = embed.description[:200] + "..." if len(embed.description) > 200 else embed.description
                        transcript_lines.append(f"      Description: {desc}")

            if message.reactions:
                reactions_list = []
                for reaction in message.reactions:
                    reactions_list.append(f"{reaction.emoji} ({reaction.count})")
                transcript_lines.append(f"    Reactions: {', '.join(reactions_list)}")

            if message.edited_at:
                edit_time = message.edited_at.strftime('%I:%M %p on %B %d, %Y')
                transcript_lines.append(f"    (Edited at {edit_time})")

            transcript_lines.append("")

        transcript_lines.append("=" * 80)
        transcript_lines.append("END OF TRANSCRIPT")
        transcript_lines.append("=" * 80)

        return '\n'.join(transcript_lines)

    async def upload_transcript(self, file_path, filename):
        """Upload transcript to dpaste for web viewing"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                transcript_content = f.read()

            async with aiohttp.ClientSession() as session:
                try:
                    dpaste_data = {
                        'content': transcript_content,
                        'syntax': 'text',  # Changed from 'json' to 'text'
                        'title': f'Discord Support Transcript - {filename}',
                        'expiry_days': 365  # 1 year expiry
                    }

                    async with session.post(
                        'https://dpaste.com/api/v2/',
                        data=dpaste_data,
                        headers={'User-Agent': 'Discord Support Bot'}
                    ) as response:
                        if response.status == 201:
                            paste_url = await response.text()
                            return paste_url.strip()
                        else:
                            print(f"dpaste failed with status: {response.status}")
                            response_text = await response.text()
                            print(f"Response: {response_text}")
                except Exception as e:
                    print(f"dpaste failed: {e}")

                try:
                    mystbin_data = {
                        'data': transcript_content,
                        'syntax': 'json'
                    }

                    async with session.post(
                        'https://mystb.in/api/pastes',
                        json=mystbin_data,
                        headers={'Content-Type': 'application/json'}
                    ) as response:
                        if response.status == 201:
                            result = await response.json()
                            return f"https://mystb.in/{result['id']}"
                        else:
                            print(f"mystb.in failed with status: {response.status}")
                except Exception as e:
                    print(f"mystb.in failed: {e}")

                try:
                    async with session.post(
                        'https://termbin.com',
                        data=transcript_content,
                        headers={'Content-Type': 'text/plain'}
                    ) as response:
                        if response.status == 200:
                            url = await response.text()
                            return url.strip()
                        else:
                            print(f"termbin failed with status: {response.status}")
                except Exception as e:
                    print(f"termbin failed: {e}")

        except Exception as e:
            print(f"Error uploading transcript: {e}")

        return f"Transcript saved locally as: {filename}"

    async def find_ticket_owner(self, channel):
        """Find the ticket owner using stored ticket data"""
        for user_id, ticket_data in self.active_tickets.items():
            if isinstance(ticket_data, dict):
                if ticket_data.get("channel_id") == channel.id:
                    owner_id = ticket_data.get("owner_id", int(user_id))
                    return channel.guild.get_member(owner_id)
            else:
                if ticket_data == channel.id:
                    return channel.guild.get_member(int(user_id))

        staff_role = channel.guild.get_role(1374421915938324583)
        if not staff_role:
            return None

        for member in channel.members:
            if member.bot:
                continue

            if staff_role in member.roles:
                continue

            return member

        return None

    async def log_ticket_closure(self, channel, closed_by, close_reason="Manual closure"):
        """Log ticket closure to logging channel with transcript link"""
        log_channel = self.bot.get_channel(1401761548300582952)
        if not log_channel:
            return

        ticket_owner = await self.find_ticket_owner(channel)

        transcript_content = await self.create_transcript(channel)
        transcript_filename = f"transcript_{channel.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        transcript_path = os.path.join("data", "transcripts", transcript_filename)

        os.makedirs(os.path.dirname(transcript_path), exist_ok=True)

        with open(transcript_path, "w", encoding="utf-8") as f:
            f.write(transcript_content)

        transcript_url = await self.upload_transcript(transcript_path, transcript_filename)

        message_count = transcript_content.count('[') - 2  # Rough count excluding header brackets

        embed = discord.Embed(
            title="Ticket Closed",
            description=f"Ticket {channel.name} has been closed",
            color=0xFF4444
        )
        embed.add_field(name="Channel", value=channel.mention, inline=True)
        embed.add_field(name="Closed by", value=closed_by.mention, inline=True)
        embed.add_field(name="Ticket Owner", value=ticket_owner.mention if ticket_owner else "Unknown", inline=True)
        embed.add_field(name="Reason", value=close_reason, inline=True)
        embed.add_field(name="Closed at", value=datetime.now().strftime('%B %d, %Y at %I:%M %p'), inline=True)
        embed.add_field(name="Messages", value=str(message_count), inline=True)

        if transcript_url.startswith('http'):
            embed.add_field(name="Transcript", value=f"[View Online]({transcript_url})", inline=False)
        else:
            embed.add_field(name="Transcript", value="Saved locally", inline=False)

        if ticket_owner:
            embed.set_thumbnail(url=ticket_owner.avatar.url if ticket_owner.avatar else ticket_owner.default_avatar.url)

        await log_channel.send(embed=embed)
        await bot_log(f"[Support] Ticket closed: {channel.name} by {closed_by} - Reason: {close_reason}")

    async def close_ticket_by_staff(self, channel, staff_member):
        """Close a ticket channel by staff member"""
        try:
            await self.log_ticket_closure(channel, staff_member, f"Closed by {staff_member.name}")

            user_to_remove = None
            for user_id, ticket_data in self.active_tickets.items():
                current_channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                if current_channel_id == channel.id:
                    user_to_remove = user_id
                    break

            if user_to_remove:
                del self.active_tickets[user_to_remove]
                self.save_active_tickets()

            await asyncio.sleep(3)
            await channel.delete()

        except Exception as e:
            print(f"Error closing ticket by staff: {e}")

    async def delayed_close(self, channel, seconds):
        """Delayed close function"""
        try:
            await asyncio.sleep(seconds)

            await self.log_ticket_closure(channel, self.bot.user, "Automatic timer closure")

            embed = discord.Embed(
                title="Ticket Closed (Automatic)",
                description="This ticket was automatically closed due to inactivity.",
                color=discord.Color.red()
            )
            embed.add_field(name="Closed at", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            embed.add_field(name="Reason", value="Automatic close timer", inline=True)

            await channel.send(embed=embed)
            await asyncio.sleep(5)

            user_to_remove = None
            for user_id, ticket_data in self.active_tickets.items():
                current_channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                if current_channel_id == channel.id:
                    user_to_remove = user_id
                    break

            if user_to_remove:
                del self.active_tickets[user_to_remove]
                self.save_active_tickets()

            if channel.id in self.close_timers:
                del self.close_timers[channel.id]

            await channel.delete()

        except asyncio.CancelledError:
            pass

    def parse_duration(self, duration_str):
        """Parse duration string (1h, 30m, 2d) to seconds"""
        duration_str = duration_str.lower().strip()

        if duration_str.endswith('s'):
            return int(duration_str[:-1])
        elif duration_str.endswith('m'):
            return int(duration_str[:-1]) * 60
        elif duration_str.endswith('h'):
            return int(duration_str[:-1]) * 3600
        elif duration_str.endswith('d'):
            return int(duration_str[:-1]) * 86400
        else:
            return None

    async def create_ticket(self, interaction: discord.Interaction, ticket_type: str):
        """Create a ticket channel"""
        user = interaction.user
        guild = interaction.guild

        if not guild:
            await interaction.response.send_message("✖ This command can only be used in a server!", ephemeral=True)
            return

        if user.id in self.active_tickets:
            ticket_data = self.active_tickets[user.id]
            existing_channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
            if existing_channel_id:
                existing_channel = guild.get_channel(existing_channel_id)
                if existing_channel:
                    await interaction.response.send_message(
                        f"✖ You already have an open ticket: {existing_channel.mention}",
                        ephemeral=True
                    )
                    return
            del self.active_tickets[user.id]
            self.save_active_tickets()

        category = guild.get_channel(1381864421067849800)
        staff_role = guild.get_role(1374421915938324583)

        if not category or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message("✖ Support category not found!", ephemeral=True)
            return

        if not staff_role:
            await interaction.response.send_message("✖ Staff role not found!", ephemeral=True)
            return

        username_prefix = user.display_name[:4].lower().replace(" ", "")
        if ticket_type == "general":
            channel_name = f"gen-{username_prefix}-{user.discriminator}"
        else:
            channel_name = f"rep-{username_prefix}-{user.discriminator}"

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            staff_role: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True)
        }

        try:
            channel = await category.create_text_channel(
                name=channel_name,
                overwrites=overwrites,
                reason=f"Ticket created by {user}"
            )

            self.active_tickets[user.id] = {
                "channel_id": channel.id,
                "owner_id": user.id
            }
            self.save_active_tickets()

            if ticket_type == "general":
                embed = discord.Embed(
                    title="General Support Ticket",
                    description="**Welcome to your private support channel!**\nThank you for reaching out to our support team.",
                    color=0x00FF7F
                )
                embed.add_field(
                    name="Ticket Purpose",
                    value="This ticket is for general questions about:\n• Server rules and gameplay\n• Technical issues or bugs\n• Account-related inquiries\n• Any other assistance needed",
                    inline=False
                )
                embed.add_field(
                    name="Response Time",
                    value="A staff member will respond to your ticket as soon as possible. Please be patient and provide as much detail as you can about your issue.",
                    inline=False
                )
                embed.add_field(
                    name="Pro Tip",
                    value="Screenshots, error messages, and step-by-step descriptions help us resolve your issue faster!",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="Player Report Ticket",
                    description="**Welcome to your private report channel!**\nThank you for helping keep our community safe.",
                    color=0xFF4444
                )
                embed.add_field(
                    name="Report Requirements",
                    value="Please provide the following information:\n• **Player's username** (exact spelling)\n• **Player's Discord** (if known)\n• **Rule violation details**\n• **Evidence** (screenshots, video, chat logs)",
                    inline=False
                )
                embed.add_field(
                    name="Review Process",
                    value="Our moderation team will review your report thoroughly. All evidence will be examined and appropriate action will be taken if the report is valid.",
                    inline=False
                )
                embed.add_field(
                    name="Important Notice",
                    value="**False reports may result in disciplinary action.** Please ensure your report is accurate and provide genuine evidence.",
                    inline=False
                )

            embed.set_footer(
                text=f"Ticket
                icon_url=user.avatar.url if user.avatar else user.default_avatar.url
            )
            embed.set_author(
                name=f"Support Ticket • {user.display_name}",
                icon_url=user.avatar.url if user.avatar else user.default_avatar.url
            )

            staff_view = StaffSupportView()

            welcome_msg = f"**{user.mention}** • @here\n*A new support ticket has been created. Staff will respond shortly.*"
            await channel.send(welcome_msg, embed=embed, view=staff_view)

            await interaction.response.send_message(
                f"✔ **Support ticket created successfully!**\nYour ticket: {channel.mention}\n\n*Please describe your issue in detail and our staff will assist you promptly.*",
                ephemeral=True
            )

            await bot_log(f"[Support] Ticket created: {channel.name} by {user}")

        except discord.Forbidden:
            await interaction.response.send_message("✖ I don't have permission to create channels!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"✖ Error creating ticket: {str(e)}", ephemeral=True)
            await bot_log(f"[Support] Error creating ticket for {user}: {str(e)}")

class SupportView(ui.View):
    """Main support panel view"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='General Support', style=discord.ButtonStyle.primary, custom_id='general_ticket')
    async def general_ticket(self, interaction: discord.Interaction, button: ui.Button):
        """Create general support ticket"""
        if hasattr(interaction.client, 'get_cog'):
            bot = cast(commands.Bot, interaction.client)
            cog = cast(SupportCog, bot.get_cog('SupportCog'))
            if cog:
                await cog.create_ticket(interaction, "general")
            else:
                await interaction.response.send_message("✖ Support system temporarily unavailable. Please try again later.", ephemeral=True)
        else:
            await interaction.response.send_message("✖ Support system temporarily unavailable. Please try again later.", ephemeral=True)

    @ui.button(label='Report Player', style=discord.ButtonStyle.danger, custom_id='report_ticket')
    async def report_ticket(self, interaction: discord.Interaction, button: ui.Button):
        """Create report ticket"""
        if hasattr(interaction.client, 'get_cog'):
            bot = cast(commands.Bot, interaction.client)
            cog = cast(SupportCog, bot.get_cog('SupportCog'))
            if cog:
                await cog.create_ticket(interaction, "report")
            else:
                await interaction.response.send_message("✖ Support system temporarily unavailable. Please try again later.", ephemeral=True)
        else:
            await interaction.response.send_message("✖ Support system temporarily unavailable. Please try again later.", ephemeral=True)

class CloseRequestView(ui.View):
    """View for close request confirmation"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Close Ticket', style=discord.ButtonStyle.danger, custom_id='confirm_close')
    async def confirm_close(self, interaction: discord.Interaction, button: ui.Button):
        """Confirm ticket closure"""
        if not interaction.channel or not hasattr(interaction.channel, 'delete'):
            await interaction.response.send_message("✖ Unable to close this channel. Please contact an administrator.", ephemeral=True)
            return

        embed = discord.Embed(
            title="Ticket Closed Successfully",
            description="**This support ticket has been closed at your request.**\nThank you for using our support system!",
            color=0x32CD32
        )
        embed.add_field(name="Closed by", value=interaction.user.mention, inline=True)
        embed.add_field(name="Closed at", value=datetime.now().strftime('%B %d, %Y at %I:%M %p'), inline=True)
        embed.add_field(name="Status", value="**Resolved**", inline=True)
        embed.set_footer(
            text="Thank you for choosing TheNewLife Support • Have a great day!",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
        )

        await interaction.response.send_message(embed=embed)

        if hasattr(interaction.client, 'get_cog'):
            bot = cast(commands.Bot, interaction.client)
            cog = cast(SupportCog, bot.get_cog('SupportCog'))
            if cog and interaction.channel:
                await cog.log_ticket_closure(interaction.channel, interaction.user, "User requested closure")

        if hasattr(interaction.client, 'get_cog'):
            bot = cast(commands.Bot, interaction.client)
            cog = cast(SupportCog, bot.get_cog('SupportCog'))
            if cog and interaction.channel:
                user_to_remove = None
                for user_id, ticket_data in cog.active_tickets.items():
                    current_channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                    if current_channel_id == interaction.channel.id:
                        user_to_remove = user_id
                        break

                if user_to_remove:
                    del cog.active_tickets[user_to_remove]
                    cog.save_active_tickets()

        await asyncio.sleep(3)
        if isinstance(interaction.channel, (discord.TextChannel, discord.Thread)):
            await interaction.channel.delete()
        await bot_log(f"[Support] Ticket closed by {interaction.user} in {interaction.channel}")

    @ui.button(label='Keep Open', style=discord.ButtonStyle.success, custom_id='cancel_close')
    async def cancel_close(self, interaction: discord.Interaction, button: ui.Button):
        """Cancel ticket closure"""
        embed = discord.Embed(
            title="Ticket Remains Open",
            description="**This ticket will stay open for continued support.**\nOur staff team has been notified that you still need assistance.",
            color=0x00FF7F
        )
        embed.add_field(
            name="What's Next?",
            value="A staff member will continue to assist you with your issue. Please provide any additional details if needed.",
            inline=False
        )
        embed.set_footer(
            text="TheNewLife Support Team • We're here to help!",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else interaction.user.default_avatar.url
        )

        await interaction.response.send_message("@here **Ticket assistance still needed!**", embed=embed)

class StaffSupportView(ui.View):
    """Staff view for managing support tickets - now properly persistent"""

    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label="Assign to Me", style=discord.ButtonStyle.primary, emoji="👤", custom_id="staff_support:assign")
    async def assign_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_staff_permissions(interaction):
            await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎧 Ticket Assigned",
            description=f"This ticket has been assigned to {interaction.user.mention}",
            color=discord.Color.blue()
        )

        await interaction.response.send_message(embed=embed)
        await bot_log(f"[Support] Ticket assigned to {interaction.user} in {interaction.channel}")

    @ui.button(label="Mark as Resolved", style=discord.ButtonStyle.success, emoji="✅", custom_id="staff_support:resolve")
    async def resolve_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_staff_permissions(interaction):
            await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
            return

        ticket_owner = await self.find_ticket_owner(interaction.channel)
        if not ticket_owner:
            await interaction.response.send_message("Could not find ticket owner.", ephemeral=True)
            return

        modal = ResolveTicketModal(ticket_owner.id, self)
        await interaction.response.send_modal(modal)

    @ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="staff_support:close")
    async def close_ticket(self, interaction: discord.Interaction, button: ui.Button):
        if not await self.check_staff_permissions(interaction):
            await interaction.response.send_message("You don't have permission to use this.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🔒 Ticket Closed",
            description=f"This ticket has been closed by {interaction.user.mention}",
            color=discord.Color.red()
        )

        for item in self.children:
            item.disabled = True

        await interaction.response.edit_message(embed=embed, view=self)

        ticket_owner = await self.find_ticket_owner(interaction.channel)
        if ticket_owner:
            try:
                dm_embed = discord.Embed(
                    title="Support Ticket Closed",
                    description=f"Your support ticket has been closed by staff.",
                    color=discord.Color.red()
                )
                await ticket_owner.send(embed=dm_embed)
            except:
                pass

        if interaction.channel.name.startswith(('gen-', 'rep-', 'ticket-', 'support-')):
            cog = interaction.client.get_cog('SupportCog')
            if cog:
                await cog.close_ticket_by_staff(interaction.channel, interaction.user)
        await bot_log(f"[Support] Ticket closed by {interaction.user} in {interaction.channel}")

    async def find_ticket_owner(self, channel):
        """Find the ticket owner from the channel"""
        if hasattr(channel.guild, 'get_member'):
            bot = getattr(channel, 'guild', None)
            if bot:
                cog = None
                for cog_name, cog_instance in bot._connection._get_client().cogs.items():
                    if cog_name == 'SupportCog':
                        cog = cog_instance
                        break

                if cog:
                    for user_id, ticket_data in cog.active_tickets.items():
                        current_channel_id = ticket_data.get("channel_id") if isinstance(ticket_data, dict) else ticket_data
                        if current_channel_id == channel.id:
                            return channel.guild.get_member(int(user_id))

        staff_roles = ["Admin", "Moderator", "Staff", "Support", "admin", "moderator", "staff", "support"]
        for member in channel.members:
            if member.bot:
                continue
            member_roles = [role.name for role in member.roles]
            if not any(role in staff_roles for role in member_roles):
                if not member.guild_permissions.manage_guild:
                    return member

        return None

    async def check_staff_permissions(self, interaction):
        """Check if user has staff permissions"""
        staff_roles = ["Admin", "Moderator", "Staff", "Support", "admin", "moderator", "staff", "support"]
        user_roles = [role.name for role in interaction.user.roles]

        if any(role in staff_roles for role in user_roles):
            return True

        if interaction.user.guild_permissions.manage_guild:
            return True

        return False

class ResolveTicketModal(ui.Modal, title="Resolve Support Ticket"):
    def __init__(self, user_id, view):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.view = view

    resolution = ui.TextInput(
        label="Resolution Details",
        placeholder="Describe how this issue was resolved...",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000
    )

    async def on_submit(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title=f"✅ Ticket Resolved",
            description=f"This ticket has been resolved by {interaction.user.mention}",
            color=discord.Color.green()
        )
        embed.add_field(name="Resolution", value=self.resolution.value, inline=False)

        await interaction.response.send_message(embed=embed)

        user = interaction.guild.get_member(self.user_id)
        if user:
            try:
                dm_embed = discord.Embed(
                    title="Support Ticket Resolved",
                    description=f"Your support ticket has been resolved!",
                    color=discord.Color.green()
                )
                dm_embed.add_field(name="Resolution", value=self.resolution.value, inline=False)
                await user.send(embed=dm_embed)
            except:
                pass

async def setup(bot):
    await bot.add_cog(SupportCog(bot))
