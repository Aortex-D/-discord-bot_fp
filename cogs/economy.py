import os
import discord
import asyncio
from discord.ext import commands
from discord import app_commands, Interaction, ui, Embed
from utils.loader import load_data, save_data
from utils.commands import get_admin_info


class LeaderboardView(ui.View):
    def __init__(self, bot, pages):
        super().__init__(timeout=300)
        self.bot = bot
        self.pages = pages
        self.current_page = 0

    async def update_message(self, interaction):
        await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)

    @ui.button(label="◀", style=discord.ButtonStyle.blurple)
    async def prev_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page > 0:
            self.current_page -= 1
            await self.update_message(interaction)

    @ui.button(label="▶", style=discord.ButtonStyle.blurple)
    async def next_page(self, interaction: Interaction, button: ui.Button):
        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await self.update_message(interaction)

class Economy(commands.Cog):
    def __init__(self, bot):
        self.data = load_data("economy")
        self.bot = bot

    async def get_balance(self, user_id):
        data_list = await asyncio.to_thread(load_data, "economy")
        data = {entry["id"]: entry["balance"] for entry in data_list}
        return data.get(str(user_id), 0)

    async def _add_points_to_data(self, user_id, amount):
        data_list = await asyncio.to_thread(load_data, "economy")
        data = {entry["id"]: entry["balance"] for entry in data_list}

        uid = str(user_id)
        data[uid] = data.get(uid, 0) + amount

        updated = [{"id": k, "balance": v} for k, v in data.items()]
        await asyncio.to_thread(save_data, "economy", updated)
        return data[uid]


    async def _remove_points_from_data(self, user_id, amount):
        data_list = await asyncio.to_thread(load_data, "economy")
        data = {entry["id"]: entry["balance"] for entry in data_list}

        uid = str(user_id)
        current = data.get(uid, 0)
        new_balance = max(current - amount, 0)
        data[uid] = new_balance

        updated = [{"id": k, "balance": v} for k, v in data.items()]
        await asyncio.to_thread(save_data, "economy", updated)
        return new_balance


    async def _reset_balance_in_data(self, user_id):
        data_list = await asyncio.to_thread(load_data, "economy")
        data = {entry["id"]: entry["balance"] for entry in data_list}

        uid = str(user_id)
        if uid in data:
            del data[uid]

        updated = [{"id": k, "balance": v} for k, v in data.items()]
        await asyncio.to_thread(save_data, "economy", updated)

    async def get_userstats(self, user_id):
        data_list = await asyncio.to_thread(load_data, "btdb")
        user_id = str(user_id)
        for entry in data_list:
            if entry.get("id") == user_id:
                return {
                    "approved": entry.get("approved_bug_reports", 0),
                    "fixed": entry.get("fixed_bug_reports", 0),
                    "pending": entry.get("pend_bug_reports", 0),
                    "declined": entry.get("declined_bug_reports", 0)
                }
        return {
            "approved": 0,
            "fixed": 0,
            "pending": 0,
            "declined": 0
        }



    @commands.Cog.listener()
    async def on_ready(self):
        print("--- Economy cog is ready! ---")

    def is_admin():
        async def predicate(interaction: discord.Interaction) -> bool:
            if get_admin_info(interaction.user.id):
                return True
            else:
                await interaction.response.send_message("❌ Only admins can use this command.", ephemeral=True)
                return False
        return app_commands.check(predicate)

    @app_commands.command(name="balance", description="Check your current balance.")
    async def balance(self, interaction: Interaction):
        user_id = interaction.user.id
        balance = await self.get_balance(user_id)
        await interaction.response.send_message(
            f"Your balance is **{balance} points**, {interaction.user.mention}.", ephemeral=True
        )

    @app_commands.command(name="userstats", description="View bug report stats and balance of a user.")
    @app_commands.describe(user="User whose stats you want to check")
    async def stats(self, interaction: discord.Interaction, user: discord.User):
        await interaction.response.defer()

        balance = await self.get_balance(user.id)
        all_reports = await asyncio.to_thread(load_data, "bugrep")
        user_id = str(user.id)

        stats = {"approved": 0, "fixed": 0, "pending": 0, "declined": 0}

        for report in all_reports:
            if report.get("reporterID") == user_id:
                status = report.get("status", "pending").lower()
                if status in stats:
                    stats[status] += 1

        total = sum(stats.values())

        embed = discord.Embed(
            title="📊 User Stats",
            color=discord.Color.blue(),
            timestamp=interaction.created_at
        )
        embed.add_field(name="**User**", value=user.mention, inline=False)
        embed.add_field(name="**Balance**", value=f"{balance} points", inline=False)
        embed.add_field(name="**🐛 Bug Reports**", value=(
            f"Pending Bug Reports: `{stats['pending']}`\n"
            f"Approved Bug Reports: `{stats['approved']}`\n"
            f"Fixed Bug Reports: `{stats['fixed']}`\n"
            f"Declined Bug Reports: `{stats['declined']}`\n"
            f"**Total Bug Reports:** `{total}`"
        ), inline=False)
        embed.set_footer(text=f"Requested by {interaction.user}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await interaction.followup.send(embed=embed)


    # Define a Group for points commands
    points_group = app_commands.Group(name="points", description="Commands for managing user points.")

    @points_group.command(name="add", description="Add points to a user.")
    @is_admin()
    @app_commands.describe(user="The user to add points to", value="Amount of points to add")
    async def add_points(self, interaction: Interaction, user: discord.User, value: int):
        # Call the renamed internal method to add points
        new_balance = await self._add_points_to_data(user.id, value)
        embed = discord.Embed(
            title="Points Added",
            description=f"**{value}** points have been added to {user.mention}.",
            color=discord.Color.green()
        )
        embed.add_field(name="Total Points", value=new_balance, inline=False)
        embed.set_footer(text=f"User ID: {user.id}")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await interaction.response.send_message(embed=embed)

    @points_group.command(name="remove", description="Remove points from a user.")
    @is_admin()
    @app_commands.describe(user="The user to remove points from", value="Amount of points to remove")
    async def remove_points(self, interaction: Interaction, user: discord.User, value: int):
        # Call the renamed internal method to remove points
        new_balance = await self._remove_points_from_data(user.id, value)
        embed = discord.Embed(
            title="Points Removed",
            description=f"**{value}** points have been removed from {user.mention}.",
            color=discord.Color.red()
        )
        embed.add_field(name="Total Points", value=new_balance, inline=False)
        embed.set_footer(text=f"User ID: {user.id}")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await interaction.response.send_message(embed=embed)

    @points_group.command(name="reset", description="Reset a user's balance to 0")
    @is_admin()
    @app_commands.describe(user="The user to reset points for")
    async def reset_points(self, interaction: Interaction, user: discord.User):
        embed = discord.Embed(
            title="⚠️ Confirm Reset",
            description=f"Are you sure you want to reset {user.mention}'s balance to 0?",
            color=discord.Color.orange()
        )
        # Pass 'self' (the Economy cog instance) as the manager to the view
        view = ConfirmResetView(user, self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="leaderboard", description="View leaderboard by points or bug reports.")
    @app_commands.describe(choice="Select type of leaderboard to show")
    @app_commands.choices(choice=[
        app_commands.Choice(name="Points", value="points"),
        app_commands.Choice(name="Bug Reports", value="bugs")
    ])
    async def leaderboard(self, interaction: Interaction, choice: app_commands.Choice[str]):
        await interaction.response.defer()

        pages = []
        entries_per_page = 10

        if choice.value == "points":
            economy_data = await asyncio.to_thread(load_data, "economy")
            sorted_data = sorted(economy_data, key=lambda x: x.get("balance", 0), reverse=True)

            for i in range(0, len(sorted_data), entries_per_page):
                embed = Embed(
                    title="🏆 Points Leaderboard",
                    description="",
                    color=discord.Color.gold(),
                    timestamp=interaction.created_at
                )
                for j, entry in enumerate(sorted_data[i:i + entries_per_page], start=i + 1):
                    user_id = int(entry["id"])
                    balance = entry["balance"]
                    user = await self.bot.fetch_user(user_id)
                    embed.description += f"**#{j} {user.display_name if user else 'Unknown'}:** {balance} points\n"
                embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
                pages.append(embed)

        elif choice.value == "bugs":
            bug_data = await asyncio.to_thread(load_data, "bugrep")
            bug_counts = {}

            for report in bug_data:
                uid = report.get("reporterID")
                if uid:
                    bug_counts[uid] = bug_counts.get(uid, 0) + 1

            sorted_bugs = sorted(bug_counts.items(), key=lambda x: x[1], reverse=True)

            for i in range(0, len(sorted_bugs), entries_per_page):
                embed = Embed(
                    title="🏆 Bug Reports Leaderboard",
                    description="",
                    color=discord.Color.blue(),
                    timestamp=interaction.created_at
                )
                for j, (uid, count) in enumerate(sorted_bugs[i:i + entries_per_page], start=i + 1):
                    user = await self.bot.fetch_user(int(uid))
                    embed.description += f"**#{j} {user.display_name if user else 'Unknown'}:** {count} bugs\n"
                embed.set_footer(text=f"Requested by {interaction.user.display_name}", icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
                pages.append(embed)

        view = LeaderboardView(self.bot, pages)
        await interaction.followup.send(embed=pages[0], view=view)

class ConfirmResetView(ui.View):
    def __init__(self, user: discord.User, manager):
        super().__init__(timeout=60)
        self.user = user
        self.manager = manager # This manager is now the Economy cog instance

    @ui.button(label="Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: Interaction, button: ui.Button):
        # Call the renamed internal method via the manager
        await self.manager._reset_balance_in_data(self.user.id)
        embed = discord.Embed(
            title="Points Reset",
            description=f"{self.user.mention}'s balance has been reset to 0.",
            color=discord.Color.red()
        )
        embed.set_footer(text=f"User ID: {self.user.id}")
        embed.set_author(name=interaction.user.display_name, icon_url=interaction.user.avatar.url if interaction.user.avatar else None)
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @ui.button(label="Cancel", style=discord.ButtonStyle.gray)
    async def cancel(self, interaction: Interaction, button: ui.Button):
        embed = discord.Embed(
            title="Reset Cancelled",
            description=f"Reset of {self.user.mention}'s balance has been cancelled.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

async def setup(bot):
    await bot.add_cog(Economy(bot))