import discord
from discord.ext import commands
from discord import ui
import json
import os
from datetime import datetime
from bot import bot_log

class ServerInfoView(ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @ui.button(label='Server Info', style=discord.ButtonStyle.primary, custom_id='server_info_button')
    async def server_info(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="NewLifeSMP Server Information",
            color=discord.Color.blue()
        )
        java_info = (
            "**IP**: Newlife.Nestcore.Dev\n\n"
            "**Required Mods**:\n"
            "• [Simple Voice Chat](https://modrinth.com/plugin/simple-voice-chat)\n"
            "• [Voice Messages](https://modrinth.com/plugin/voicemessages)\n"
            "• [Vivecraft](https://modrinth.com/mod/vivecraft)\n"
            "• [Customizable Player Models](https://modrinth.com/plugin/custom-player-models)\n\n"
            "**Modpack**: https://modrinth.com/modpack/thenewlife-modpack\n"
            "**Performance Modpack**: https://modrinth.com/modpack/thenewlife-performance"
        )
        bedrock_info = (
            "Friend `NewLifeSMP` on bedrock **TEMPORARILY FRIEND** `ChickenCrazy861`\n\n"
            "**IP**: 23.167.232.146\n"
            "**Port**: 25656\n\n"
            "For VoiceChat Run **`/dvc start`** **(This is required to play)**"
        )
        embed.add_field(name="Java Edition", value=java_info, inline=False)
        embed.add_field(name="Bedrock Edition", value=bedrock_info, inline=False)
        embed.set_footer(text="Join the server and have fun!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label='Minecraft Wiki', style=discord.ButtonStyle.secondary, custom_id='wiki_button')
    async def minecraft_wiki(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(
            title="Armor Upgrading Guide",
            description="**Important**: To get iron armor, you must upgrade leather armor using the upgrader!",
            color=discord.Color.orange()
        )
        upgrader_images = [
            "https://i.postimg.cc/QtL0WRSw/upgrader.png",
            "https://i.postimg.cc/VN0KvY9X/upgrader1.webp",
            "https://i.postimg.cc/sgNn3BWV/upgrader2.webp",
            "https://i.postimg.cc/Jzn6w3G6/upgrader3.webp",
            "https://i.postimg.cc/MKtPr3Kf/upgrader4.webp",
        ]
        embed.set_image(url=upgrader_images[0])
        embed.add_field(
            name="How to Upgrade Armor",
            value="Use the upgrader blocks shown in the images to upgrade your leather armor to iron armor and beyond!",
            inline=False,
        )
        embed.add_field(
            name="Additional Images",
            value="[Image 2]({}) | [Image 3]({}) | [Image 4]({}) | [Image 5]({})".format(
                upgrader_images[1], upgrader_images[2], upgrader_images[3], upgrader_images[4]
            ),
            inline=False,
        )
        embed.set_footer(text="Click the links above to view all upgrader examples!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label='Marketplace Rules', style=discord.ButtonStyle.danger, custom_id='marketplace_rules_button')
    async def marketplace_rules(self, interaction: discord.Interaction, button: ui.Button):
        embed = discord.Embed(title="Marketplace Rules", color=discord.Color.red())
        rules_text = (
            "**Rule 1**: Pay your rent on time, or lose your plot and possibly the items inside.\n"
            "**Rule 2**: Your shop can be no bigger than the designated area.\n"
            "**Rule 3**: Keep your shop well lit.\n"
            "**Rule 4**: 1 Plot Per Person"
        )
        embed.add_field(name="Market Rules:", value=rules_text, inline=False)
        embed.set_image(url="https://i.postimg.cc/qMZc3Pvw/mcplace-rules.webp")
        embed.set_footer(text="Follow these rules to maintain your marketplace plot!")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label='My Moderations', style=discord.ButtonStyle.secondary, custom_id='my_moderations_button')
    async def my_moderations(self, interaction: discord.Interaction, button: ui.Button):
        try:
            with open("data/moderation_cases.json", "r") as f:
                data = json.load(f)
            cases = data.get("cases", [])
        except (FileNotFoundError, json.JSONDecodeError):
            cases = []
        user_cases = [case for case in cases if case.get("target_id") == interaction.user.id]
        if not user_cases:
            embed = discord.Embed(
                title="My Moderations",
                description="You have no moderation history.",
                color=discord.Color.green(),
            )
        else:
            user_cases.sort(key=lambda x: x.get("case_number", 0), reverse=True)
            embed = discord.Embed(
                title="My Moderations",
                description=f"You have {len(user_cases)} moderation record(s)",
                color=discord.Color.orange(),
            )
            for case in user_cases[:10]:
                reason = case.get('reason', '')
                case_info = (
                    f"**Type**: {case.get('type','Unknown')}\n"
                    f"**Reason**: {reason[:150]}{'...' if len(reason) > 150 else ''}\n"
                    f"**Date**: {case.get('date','N/A')} at {case.get('time','N/A')}"
                )
                embed.add_field(
                    name=f"Case #{case.get('case_number','?')}",
                    value=case_info,
                    inline=False,
                )
            if len(user_cases) > 10:
                embed.set_footer(text=f"Showing 10 of {len(user_cases)} records.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @ui.button(label='Infraction Appeal', style=discord.ButtonStyle.secondary, custom_id='infraction_appeal_button')
    async def infraction_appeal(self, interaction: discord.Interaction, button: ui.Button):
        try:
            with open("data/moderation_cases.json", "r") as f:
                data = json.load(f)
            cases = data.get("cases", [])
        except (FileNotFoundError, json.JSONDecodeError):
            cases = []
        user_cases = [case for case in cases if case.get("target_id") == interaction.user.id]
        if not user_cases:
            embed = discord.Embed(
                title="No Infractions Found",
                description="You have no infractions to appeal.",
                color=discord.Color.green(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        user_cases.sort(key=lambda x: x.get("case_number", 0), reverse=True)
        view = AppealSelectionView(user_cases, interaction.user)
        embed = discord.Embed(
            title="Select Infraction to Appeal",
            description="Choose which infraction you would like to appeal:",
            color=discord.Color.blue(),
        )
        for case in user_cases[:5]:
            reason = case.get('reason', '')
            case_info = f"**Type**: {case.get('type','Unknown')}\n**Date**: {case.get('date','N/A')}\n**Reason**: {reason[:100]}{'...' if len(reason) > 100 else ''}"
            embed.add_field(
                name=f"Case #{case.get('case_number','?')}",
                value=case_info,
                inline=False,
            )
        if len(user_cases) > 5:
            embed.set_footer(text=f"Showing 5 of {len(user_cases)} infractions. Recent cases shown first.")
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AppealDecisionView(ui.View):
    def __init__(self, appeal_data):
        super().__init__(timeout=None)
        self.appeal_data = appeal_data

    @ui.button(label='Approve', style=discord.ButtonStyle.success, custom_id='approve_appeal')
    async def approve_appeal(self, interaction: discord.Interaction, button: ui.Button):
        try:
            with open("data/appeals.json", "r") as f:
                appeals_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            await interaction.response.send_message("Appeal data not found.", ephemeral=True)
            return
        for appeal in appeals_data.get("appeals", []):
            if appeal.get("appeal_number") == self.appeal_data.get("appeal_number"):
                appeal["status"] = "approved"
                appeal["reviewed_by"] = str(interaction.user)
                appeal["reviewed_at"] = datetime.now().isoformat()
                break
        with open("data/appeals.json", "w") as f:
            json.dump(appeals_data, f, indent=2)
        try:
            user = interaction.client.get_user(self.appeal_data.get("user_id"))
            if user:
                embed = discord.Embed(
                    title="Appeal Approved",
                    description=f"Your appeal for Case #{self.appeal_data.get('case_number')} has been approved.",
                    color=discord.Color.green(),
                )
                embed.add_field(name="Appeal #", value=str(self.appeal_data.get("appeal_number")), inline=True)
                embed.add_field(name="Reviewed by", value=str(interaction.user), inline=True)
                await user.send(embed=embed)
        except discord.Forbidden:
            pass
        staff_channel = interaction.client.get_channel(1401409232212852787)
        if staff_channel and isinstance(staff_channel, discord.TextChannel):
            embed = discord.Embed(
                title=f"Appeal Approved • Case #{self.appeal_data.get('case_number')}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Appeal #", value=str(self.appeal_data.get("appeal_number")), inline=True)
            embed.add_field(name="User", value=self.appeal_data.get("user_name", "Unknown"), inline=True)
            embed.add_field(name="Reviewed by", value=str(interaction.user), inline=True)
            embed.add_field(name="Original Reason", value=str(self.appeal_data.get("original_infraction", {}).get("reason", ""))[:500], inline=False)
            embed.add_field(name="Appeal Reason", value=str(self.appeal_data.get("appeal_reason", ""))[:500], inline=False)
            await staff_channel.send(embed=embed)
        try:
            if interaction.message:
                await interaction.message.delete()
        except (discord.NotFound, AttributeError):
            pass
        await interaction.response.send_message("Appeal approved and user notified.", ephemeral=True)

    @ui.button(label='Deny', style=discord.ButtonStyle.danger, custom_id='deny_appeal')
    async def deny_appeal(self, interaction: discord.Interaction, button: ui.Button):
        modal = DenyReasonModal(self.appeal_data)
        await interaction.response.send_modal(modal)

    @ui.button(label='Notify Me', style=discord.ButtonStyle.secondary, custom_id='notify_toggle')
    async def toggle_notify(self, interaction: discord.Interaction, button: ui.Button):
        try:
            with open("data/notify_users.json", "r") as f:
                notify_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            notify_data = {"notify_users": []}
        user_id = interaction.user.id
        notify_users = notify_data.get("notify_users", [])
        if user_id in notify_users:
            notify_users.remove(user_id)
            message = "You will no longer be notified of new appeals."
        else:
            notify_users.append(user_id)
            message = "You will now be notified of new appeals."
        notify_data["notify_users"] = notify_users
        os.makedirs("data", exist_ok=True)
        with open("data/notify_users.json", "w") as f:
            json.dump(notify_data, f, indent=2)
        await interaction.response.send_message(message, ephemeral=True)

class DenyReasonModal(ui.Modal):
    def __init__(self, appeal_data):
        super().__init__(title="Reason for Denial")
        self.appeal_data = appeal_data
        self.reason_input = ui.TextInput(
            label="Why is this appeal being denied?",
            placeholder="Enter the reason for denying this appeal...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        denial_reason = self.reason_input.value
        try:
            with open("data/appeals.json", "r") as f:
                appeals_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            await interaction.response.send_message("Appeal data not found.", ephemeral=True)
            return
        for appeal in appeals_data.get("appeals", []):
            if appeal.get("appeal_number") == self.appeal_data.get("appeal_number"):
                appeal["status"] = "denied"
                appeal["denial_reason"] = denial_reason
                appeal["reviewed_by"] = str(interaction.user)
                appeal["reviewed_at"] = datetime.now().isoformat()
                break
        with open("data/appeals.json", "w") as f:
            json.dump(appeals_data, f, indent=2)
        try:
            user = interaction.client.get_user(self.appeal_data.get("user_id"))
            if user:
                embed = discord.Embed(
                    title="Appeal Denied",
                    description=f"Your appeal for Case #{self.appeal_data.get('case_number')} has been denied.",
                    color=discord.Color.red(),
                )
                embed.add_field(name="Appeal #", value=str(self.appeal_data.get("appeal_number")), inline=True)
                embed.add_field(name="Reviewed by", value=str(interaction.user), inline=True)
                embed.add_field(name="Reason", value=denial_reason, inline=False)
                await user.send(embed=embed)
        except discord.Forbidden:
            pass
        staff_channel = interaction.client.get_channel(1401409232212852787)
        if staff_channel and isinstance(staff_channel, discord.TextChannel):
            embed = discord.Embed(
                title=f"Appeal Denied • Case #{self.appeal_data.get('case_number')}",
                color=discord.Color.red(),
            )
            embed.add_field(name="Appeal #", value=str(self.appeal_data.get("appeal_number")), inline=True)
            embed.add_field(name="User", value=self.appeal_data.get("user_name", "Unknown"), inline=True)
            embed.add_field(name="Reviewed by", value=str(interaction.user), inline=True)
            embed.add_field(name="Denial Reason", value=denial_reason[:500], inline=False)
            embed.add_field(name="Original Reason", value=str(self.appeal_data.get("original_infraction", {}).get("reason", ""))[:500], inline=False)
            embed.add_field(name="Appeal Reason", value=str(self.appeal_data.get("appeal_reason", ""))[:500], inline=False)
            await staff_channel.send(embed=embed)
        try:
            if interaction.message:
                await interaction.message.delete()
        except (discord.NotFound, AttributeError):
            pass
        await interaction.response.send_message("Appeal denied and user notified.", ephemeral=True)

class AppealSelectionView(ui.View):
    def __init__(self, user_cases, user):
        super().__init__(timeout=300)
        self.user_cases = user_cases
        self.user = user
        if len(user_cases) > 0:
            options = []
            for case in user_cases[:25]:
                label = f"Case #{case.get('case_number','?')}"
                description = f"{case.get('date','N/A')} - {case.get('reason','')[:50]}{'...' if len(case.get('reason','')) > 50 else ''}"
                options.append(discord.SelectOption(
                    label=label[:100],
                    description=description[:100],
                    value=str(case.get('case_number','0')),
                ))
            select = CaseSelectDropdown(options, self.user_cases, self.user)
            self.add_item(select)

class CaseSelectDropdown(ui.Select):
    def __init__(self, options, user_cases, user):
        super().__init__(placeholder="Select a case to appeal...", options=options)
        self.user_cases = user_cases
        self.user = user

    async def callback(self, interaction: discord.Interaction):
        selected_case_number = int(self.values[0])
        selected_case = next((case for case in self.user_cases if case.get('case_number') == selected_case_number), None)
        if not selected_case:
            await interaction.response.send_message("Case not found.", ephemeral=True)
            return
        modal = AppealReasonModal(selected_case, self.user)
        await interaction.response.send_modal(modal)

class AppealReasonModal(ui.Modal):
    def __init__(self, case, user):
        super().__init__(title=f"Appeal Case #{case.get('case_number','?')}")
        self.case = case
        self.user = user
        self.reason_input = ui.TextInput(
            label="Why should this infraction be removed?",
            placeholder="Explain why you believe this infraction should be appealed...",
            style=discord.TextStyle.paragraph,
            max_length=1000,
            required=True,
        )
        self.add_item(self.reason_input)

    async def on_submit(self, interaction: discord.Interaction):
        appeal_reason = self.reason_input.value
        try:
            with open("data/appeals.json", "r") as f:
                appeals_data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            appeals_data = {"appeals": [], "next_appeal_number": 1}
        appeal_number = appeals_data.get("next_appeal_number", 1)
        appeals_data["next_appeal_number"] = appeal_number + 1
        appeal_data = {
            "appeal_number": appeal_number,
            "case_number": self.case.get("case_number"),
            "user_id": self.user.id,
            "user_name": str(self.user),
            "appeal_reason": appeal_reason,
            "original_infraction": self.case,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
            "date": datetime.now().strftime("%m/%d/%Y"),
            "time": datetime.now().strftime("%I:%M %p"),
        }
        appeals_data.setdefault("appeals", []).append(appeal_data)
        os.makedirs("data", exist_ok=True)
        with open("data/appeals.json", "w") as f:
            json.dump(appeals_data, f, indent=2)
        bot = interaction.client
        appeals_channel = bot.get_channel(1419528947561005138)
        if appeals_channel and isinstance(appeals_channel, discord.TextChannel):
            embed = discord.Embed(
                title=f"Infraction Appeal • Case #{self.case.get('case_number','?')}",
                color=discord.Color.yellow(),
                timestamp=discord.utils.utcnow(),
            )
            embed.add_field(name="User", value=f"{self.user.mention} ({self.user.id})", inline=True)
            embed.add_field(name="Case #", value=str(self.case.get("case_number","?")), inline=True)
            embed.add_field(name="Original Infraction", value=self.case.get("type","Unknown"), inline=True)
            embed.add_field(name="Original Reason", value=self.case.get("reason",""), inline=False)
            embed.add_field(name="Appeal Reason", value=appeal_reason, inline=False)
            embed.add_field(name="Date", value=f"{self.case.get('date','N/A')} at {self.case.get('time','N/A')}", inline=True)
            try:
                with open("data/notify_users.json", "r") as f:
                    notify_data = json.load(f)
                notify_users = notify_data.get("notify_users", [])
            except (FileNotFoundError, json.JSONDecodeError):
                notify_users = []
            mentions = " ".join([f"<@{user_id}>" for user_id in notify_users]) if notify_users else ""
            view = AppealDecisionView(appeal_data)
            message = await appeals_channel.send(content=mentions, embed=embed, view=view)
            appeal_data["message_id"] = message.id
            with open("data/appeals.json", "w") as f:
                json.dump(appeals_data, f, indent=2)
        embed = discord.Embed(
            title="✔ Appeal Submitted",
            description=f"Your appeal for Case #{self.case.get('case_number','?')} has been submitted.",
            color=discord.Color.green(),
        )
        embed.set_footer(text="Staff will review your appeal and respond accordingly.")
        await interaction.response.send_message(embed=embed, ephemeral=True)

class InfoCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.info_channel_id = 1401403574403207300
        self.persistent_view = ServerInfoView()
        self.bot.add_view(self.persistent_view)

    @commands.command(name='setup_info')
    async def setup_info(self, ctx):
        authorized_users = [1237471534541439068]
        if ctx.author.id not in authorized_users:
            await ctx.send("✖ You don't have permission to use this command.")
            return
        channel = self.bot.get_channel(self.info_channel_id)
        if not channel:
            await ctx.send("✖ Info channel not found.")
            return
        embed = discord.Embed(
            title="NewLifeSMP Server",
            description=(
                "Welcome to NewLifeSMP! Click the button below to get detailed server connection information, "
                "including IPs, required mods, and setup instructions for both Java and Bedrock editions."
            ),
            color=discord.Color.green(),
        )
        if ctx.guild and ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)
        embed.add_field(
            name="Quick Info",
            value="Java & Bedrock compatible server with voice chat support",
            inline=False,
        )
        await channel.send(embed=embed, view=self.persistent_view)
        await ctx.send("✔ Info embed has been set up in the info channel.")
        await bot_log(f"[Info] Info command used by {ctx.author}")

    @commands.Cog.listener()
    async def on_ready(self):
        print("Info cog loaded - Persistent view ready")

async def setup(bot):
    await bot.add_cog(InfoCommands(bot))
