import discord
from discord import app_commands
from discord.ext import commands
import os
import json
from typing import Dict
from bot import bot_log

SUGGESTIONS_CHANNEL_ID = 1388221470865489930
GUILD_ID = 1372672239245459498

def ensure_data_dir() -> str:
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    base = os.path.abspath(base)
    os.makedirs(base, exist_ok=True)
    return base

class SuggestionStore:
    def __init__(self):
        self.path = os.path.join(ensure_data_dir(), "suggestions.json")
        self.data = {"suggestions": {}}
        self._load()

    def _load(self):
        try:
            if os.path.exists(self.path):
                with open(self.path, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
        except Exception:
            self.data = {"suggestions": {}}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self.data, f, indent=2)
        except Exception:
            pass

    def init_suggestion(self, message_id: int, author_id: int, channel_id: int):
        self.data["suggestions"][str(message_id)] = {
            "author_id": author_id,
            "channel_id": channel_id,
            "votes": {},
            "up": 0,
            "down": 0,
        }
        self._save()

    def get_counts(self, message_id: int):
        s = self.data["suggestions"].get(str(message_id))
        if not s:
            return 0, 0
        return int(s.get("up", 0)), int(s.get("down", 0))

    def apply_vote(self, message_id: int, user_id: int, vote: int):
        key = str(message_id)
        s = self.data["suggestions"].get(key)
        if not s:
            return 0, 0
        votes: Dict[str, int] = s.get("votes", {})
        current = int(votes.get(str(user_id), 0))

        if current == 1:
            s["up"] = max(0, int(s.get("up", 0)) - 1)
        elif current == -1:
            s["down"] = max(0, int(s.get("down", 0)) - 1)

        if vote == 1:
            s["up"] = int(s.get("up", 0)) + 1
            votes[str(user_id)] = 1
        elif vote == -1:
            s["down"] = int(s.get("down", 0)) + 1
            votes[str(user_id)] = -1
        else:
            votes.pop(str(user_id), None)

        s["votes"] = votes
        self.data["suggestions"][key] = s
        self._save()
        return int(s.get("up", 0)), int(s.get("down", 0))

class SuggestionView(discord.ui.View):
    def __init__(self, store: SuggestionStore, message_id: int, up: int, down: int):
        super().__init__(timeout=None)
        self.store = store
        self.message_id = message_id
        self.upvote.label = f"⬆ Upvote ({up})"
        self.downvote.label = f"⬇ Downvote ({down})"

    @discord.ui.button(style=discord.ButtonStyle.success, label="⬆ Upvote (0)")
    async def upvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        key = str(self.message_id)
        current = 0
        data = self.store.data.get("suggestions", {}).get(key)
        if data:
            current = int(data.get("votes", {}).get(str(user_id), 0))
        new_vote = 0 if current == 1 else 1
        up, down = self.store.apply_vote(self.message_id, user_id, new_vote)
        await self._update(interaction, up, down)

    @discord.ui.button(style=discord.ButtonStyle.danger, label="⬇ Downvote (0)")
    async def downvote(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_id = interaction.user.id
        key = str(self.message_id)
        current = 0
        data = self.store.data.get("suggestions", {}).get(key)
        if data:
            current = int(data.get("votes", {}).get(str(user_id), 0))
        new_vote = 0 if current == -1 else -1
        up, down = self.store.apply_vote(self.message_id, user_id, new_vote)
        await self._update(interaction, up, down)

    async def _update(self, interaction: discord.Interaction, up: int, down: int):
        self.upvote.label = f"⬆ Upvote ({up})"
        self.downvote.label = f"⬇ Downvote ({down})"
        try:
            msg = interaction.message
            embed = msg.embeds[0] if msg.embeds else None
            if embed:
                found = False
                for i, field in enumerate(embed.fields):
                    if field.name.lower() == "votes":
                        embed.set_field_at(i, name="Votes", value=f"👍 {up} • 👎 {down}", inline=False)
                        found = True
                        break
                if not found:
                    embed.add_field(name="Votes", value=f"👍 {up} • 👎 {down}", inline=False)
                await interaction.response.edit_message(embed=embed, view=self)
            else:
                await interaction.response.edit_message(view=self)
        except Exception:
            try:
                await interaction.response.defer()
            except Exception:
                pass

class Suggestions(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.store = SuggestionStore()

    @app_commands.command(name="suggest", description="Submit a server suggestion")
    @app_commands.describe(suggestion="Your suggestion text")
    @app_commands.guilds(discord.Object(id=GUILD_ID))
    async def suggest(self, interaction: discord.Interaction, suggestion: str):
        if not suggestion or not suggestion.strip():
            await interaction.response.send_message("Please provide a suggestion.", ephemeral=True)
            return
        if len(suggestion) > 1800:
            await interaction.response.send_message("Suggestion is too long. Please keep it under 1800 characters.", ephemeral=True)
            return

        channel = interaction.client.get_channel(SUGGESTIONS_CHANNEL_ID)
        if channel is None:
            await interaction.response.send_message("Suggestions channel not found.", ephemeral=True)
            return

        author = interaction.user

        embed = discord.Embed(description=suggestion.strip(), color=discord.Color.blurple())
        embed.set_footer(text=f"Suggested by {author.display_name}")
        embed.add_field(name="Votes", value="👍 0 • 👎 0", inline=False)

        msg = await channel.send(embed=embed)

        self.store.init_suggestion(msg.id, author.id, channel.id)
        await bot_log(f"[Suggestions] Suggestion submitted by {author.id}")

        view = SuggestionView(self.store, msg.id, 0, 0)
        await msg.edit(view=view)

        thread_name = f"Discussion: {suggestion.strip()[:60]}"
        try:
            thread = await msg.create_thread(name=thread_name, auto_archive_duration=1440)
            await thread.send(f"{author.mention} this is where you can discuss your suggestion.")
        except Exception as e:
            await bot_log(f"[Suggestions] Error: {e}")

        await interaction.response.send_message("Your suggestion has been posted!", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Suggestions(bot))
