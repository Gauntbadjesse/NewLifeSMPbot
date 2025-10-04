import discord
from discord.ext import commands
import json
import os
from bot import bot_log

class Welcome(commands.Cog):
    """Welcome system and member counter"""

    def __init__(self, bot):
        self.bot = bot

        self.WELCOME_CHANNEL_ID = 1374421925790482483
        self.WHITELIST_CHANNEL_ID = 1376427874978103418
        self.MEMBER_COUNTER_CHANNEL_ID = 1403210992925802577

        self.WELCOME_ROLE_ID = 1374421919373328434

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """Handle new member joins"""
        try:
            welcome_channel = self.bot.get_channel(self.WELCOME_CHANNEL_ID)
            if not welcome_channel:
                print(f"❌ Welcome channel {self.WELCOME_CHANNEL_ID} not found")
                return

            member_count = member.guild.member_count

            embed = discord.Embed(
                title="🎉 Welcome to New Life SMP!",
                description=f"Welcome {member.mention} to the New Life SMP! We are now at **{member_count}** members!",
                color=discord.Color.green()
            )

            embed.add_field(
                name="📝 Get Whitelisted",
                value=f"Ready to join the server? Apply for whitelist in <
                inline=False
            )

            embed.add_field(
                name="🏠 Server Info",
                value="Make sure to read the rules and have fun building in our community!",
                inline=False
            )

            embed.set_thumbnail(url=member.display_avatar.url)

            embed.set_footer(
                text=f"Member
                icon_url=member.guild.icon.url if member.guild.icon else None
            )

            await welcome_channel.send(embed=embed)
            await bot_log(f"[Welcome] {member} joined the server.")

            try:
                role = member.guild.get_role(self.WELCOME_ROLE_ID)
                if role:
                    await member.add_roles(role)
                    print(f"✅ Assigned role {role.name} to {member.display_name}")
                else:
                    print(f"❌ Welcome role {self.WELCOME_ROLE_ID} not found")
            except discord.Forbidden:
                print(f"❌ No permission to assign role to {member.display_name}")
            except discord.HTTPException as e:
                print(f"❌ Failed to assign role to {member.display_name}: {e}")

            await self.update_member_counter(member.guild)

            print(f"✅ Welcomed {member.display_name} ({member.id}) - Guild now has {member_count} members")

        except Exception as e:
            print(f"❌ Error in on_member_join: {e}")
            await bot_log(f"[Welcome] Error in on_member_join: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member):
        """Handle member leaves (update counter)"""
        try:
            await self.update_member_counter(member.guild)

            member_count = member.guild.member_count
            print(f"📤 {member.display_name} left - Guild now has {member_count} members")
            await bot_log(f"[Welcome] {member} left the server.")

        except Exception as e:
            print(f"❌ Error in on_member_remove: {e}")
            await bot_log(f"[Welcome] Error in on_member_remove: {e}")

    async def update_member_counter(self, guild):
        """Update the member counter channel name"""
        try:
            member_counter_channel = guild.get_channel(self.MEMBER_COUNTER_CHANNEL_ID)
            if not member_counter_channel:
                print(f"❌ Member counter channel {self.MEMBER_COUNTER_CHANNEL_ID} not found")
                return

            member_count = guild.member_count
            new_name = f"Members - {member_count}"

            if member_counter_channel.name != new_name:
                await member_counter_channel.edit(name=new_name)
                print(f"📊 Updated member counter to: {new_name}")

        except discord.Forbidden:
            print(f"❌ No permission to edit member counter channel")
        except discord.HTTPException as e:
            print(f"❌ Failed to update member counter: {e}")
        except Exception as e:
            print(f"❌ Error updating member counter: {e}")

    @commands.command(name='test_welcome')
    @commands.has_permissions(administrator=True)
    async def test_welcome(self, ctx, member: discord.Member = None):
        """Test the welcome system (Admin only)"""
        if member is None:
            member = ctx.author

        await self.on_member_join(member)
        await ctx.send(f"✅ Tested welcome system for {member.mention}")

    @commands.command(name='update_counter')
    @commands.has_permissions(administrator=True)
    async def update_counter_command(self, ctx):
        """Manually update member counter (Admin only)"""
        await self.update_member_counter(ctx.guild)
        member_count = ctx.guild.member_count
        await ctx.send(f"📊 Updated member counter to: **{member_count}** members")

    @commands.command(name='welcome_stats')
    @commands.has_permissions(manage_guild=True)
    async def welcome_stats(self, ctx):
        """Show welcome system statistics"""
        guild = ctx.guild
        member_count = guild.member_count

        welcome_channel = guild.get_channel(self.WELCOME_CHANNEL_ID)
        counter_channel = guild.get_channel(self.MEMBER_COUNTER_CHANNEL_ID)
        welcome_role = guild.get_role(self.WELCOME_ROLE_ID)

        embed = discord.Embed(
            title="📊 Welcome System Stats",
            color=discord.Color.blue()
        )

        embed.add_field(
            name="👥 Server Members",
            value=f"{member_count}",
            inline=True
        )

        embed.add_field(
            name="📢 Welcome Channel",
            value=welcome_channel.mention if welcome_channel else "❌ Not found",
            inline=True
        )

        embed.add_field(
            name="📊 Counter Channel",
            value=counter_channel.mention if counter_channel else "❌ Not found",
            inline=True
        )

        embed.add_field(
            name="🏷️ Welcome Role",
            value=welcome_role.mention if welcome_role else "❌ Not found",
            inline=True
        )

        embed.add_field(
            name="📝 Whitelist Channel",
            value=f"<
            inline=True
        )

        if welcome_role:
            role_member_count = len(welcome_role.members)
            embed.add_field(
                name="🏷️ Members with Welcome Role",
                value=f"{role_member_count}",
                inline=True
            )

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Welcome(bot))
