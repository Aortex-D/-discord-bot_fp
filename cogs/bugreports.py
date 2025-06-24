import os
import discord
import datetime
from discord.ext import commands
from discord import app_commands, ui, Interaction
from dotenv import load_dotenv
from utils.loader import load_data, save_data
from utils.commands import COMMANDS_REFERENCE, get_group_role_id
from datetime import datetime, timezone
import asyncio

def has_command_role(command_name: str):
    async def predicate(interaction: Interaction):
        command = next((c for c in COMMANDS_REFERENCE if c["name"] == command_name), None)
        if not command:
            await interaction.response.send_message("\u26a0\ufe0f Command not registered in permissions config.", ephemeral=True)
            return False

        required_role_id = get_group_role_id(command["group"])
        admin_role_id = get_group_role_id("admin")

        if any(role.id == required_role_id or role.id == admin_role_id for role in interaction.user.roles):
            return True

        await interaction.response.send_message("\u274c You do not have permission to use this command.", ephemeral=True)
        return False
    return app_commands.check(predicate)

class BugReportManager:
    def __init__(self, bot):
        self.bot = bot
        self.reports = load_data("bugrep")
        self.next_id = max([report.get("id", 0) for report in self.reports]) + 1 if self.reports else 1

    async def _load_reports(self):
        return await asyncio.to_thread(load_data, "bugrep")

    async def _save_reports(self):
        await asyncio.to_thread(save_data, "bugrep", self.reports)

    async def add_report(self, report_data: dict):
        report_data["id"] = self.next_id
        self.reports.append(report_data)
        await self._save_reports()
        self.next_id += 1
        return report_data["id"]

    async def get_report_by_id(self, report_id: int):
        return next((report for report in self.reports if report.get("id") == report_id), None)

    async def delete_report(self, report_id: int):
        initial_count = len(self.reports)
        self.reports = [report for report in self.reports if report.get("id") != report_id]
        if len(self.reports) < initial_count:
            await self._save_reports()
            return True
        return False

    async def get_filtered_and_sorted_reports(self, category_filter: str = "all", sort_by: str = "id_ascending"):
        if category_filter == "all":
            filtered_reports = self.reports
        else:
            filtered_reports = [r for r in self.reports if r.get('category') and r['category'].lower() == category_filter.lower()]

        if sort_by == "id_ascending":
            filtered_reports.sort(key=lambda x: x.get('id', 0))
        elif sort_by == "date_ascending":
            filtered_reports.sort(key=lambda x: datetime.strptime(x.get('reportedAt', '1970-01-01'), "%Y-%m-%d"))
        elif sort_by == "date_descending":
            filtered_reports.sort(key=lambda x: datetime.strptime(x.get('reportedAt', '1970-01-01'), "%Y-%m-%d"), reverse=True)
        elif sort_by == "severity_high":
            severity_order = {"very high": 0, "high": 1, "medium": 2, "low": 3, "n/a": 4}
            filtered_reports.sort(key=lambda x: severity_order.get(x.get('severity', 'n/a').lower(), 99))
        elif sort_by == "severity_low":
            severity_order = {"very high": 0, "high": 1, "medium": 2, "low": 3, "n/a": 4}
            filtered_reports.sort(key=lambda x: severity_order.get(x.get('severity', 'n/a').lower(), 99), reverse=True)

        return filtered_reports

    

# --- Modal for Bug Report Submission ---
class BugReportModal(ui.Modal, title='🐞 Bug Report'):
    def __init__(self, bot: commands.Bot, category: str = "N/A", severity: str = "N/A", manager: BugReportManager = None):
        super().__init__()
        self.bot = bot # Store the bot instance
        self.category = category
        self.severity = severity
        self.manager = manager # Store the manager instance to save reports

        # Define TextInput fields
        self.bug_title = ui.TextInput(
            label='Title:',
            placeholder='Enter a concise title (e.g., "Wrong item in shop")',
            max_length=100,
            style=discord.TextStyle.short,
            required=True
        )
        self.bug_description = ui.TextInput(
            label='Describe The Bug:',
            placeholder='Provide a detailed description of the bug...',
            max_length=2000,
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.steps_to_reproduce = ui.TextInput(
            label='Describe Steps To Reproduce The Bug:',
            placeholder='List steps to reliably reproduce the bug (e.g., "1. Go to...", "2. Click...", "3. Observe...")',
            max_length=2000,
            style=discord.TextStyle.paragraph,
            required=True
        )

        # Add TextInput fields to the modal
        self.add_item(self.bug_title)
        self.add_item(self.bug_description)
        self.add_item(self.steps_to_reproduce)

    async def on_submit(self, interaction: Interaction):
        """Handles the submission of the bug report modal."""
        bug_report_channel_id = os.getenv("BUG_REPORT_CHANNEL_ID")

        if not bug_report_channel_id:
            print("Error: BUG_REPORT_CHANNEL_ID not set in environment variables.")
            await interaction.response.send_message(
                "🐛 An error occurred: Bug report channel not configured. Please contact an administrator.",
                ephemeral=True
            )
            return

        try:
            report_channel = interaction.client.get_channel(int(bug_report_channel_id))
            if not report_channel:
                await interaction.response.send_message(
                    "🐛 An error occurred: Could not find the configured bug report channel. Please contact an administrator.",
                    ephemeral=True
                )
                print(f"Error: Could not find channel with ID {bug_report_channel_id}")
                return

            report_data = {
                "title": self.bug_title.value,
                "severity": self.severity,
                "category": self.category,
                "reporterID": str(interaction.user.id),
                "reportedAt": interaction.created_at.strftime("%Y-%m-%d"),
                "description": self.bug_description.value,
                "reproducesteps": self.steps_to_reproduce.value.replace('\n', '\\n'), 
            }

            report_id = await self.manager.add_report(report_data)


            # Create an embed to send to the Discord channel for administrators
            embed = discord.Embed(
                title=f"🚨 New Bug Report: {self.bug_title.value}",
                color=discord.Color.red(),
                timestamp=interaction.created_at
            )
            embed.set_author(
                name=f"Reported by {interaction.user.display_name}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            embed.add_field(name="Reporter", value=f"<@{interaction.user.id}> ({interaction.user.id})", inline=False)
            embed.add_field(name="Category", value=self.category.capitalize(), inline=True)
            embed.add_field(name="Severity", value=self.severity.capitalize(), inline=True)
            embed.add_field(name="Description", value=self.bug_description.value, inline=False)
            embed.add_field(name="Steps to Reproduce", value=self.steps_to_reproduce.value, inline=False)
            embed.set_footer(text=f"Bug Report ID: {report_id}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            
            await report_channel.send(embed=embed)

            # Confirm submission to the user
            await interaction.response.send_message(
                f"✅ Your bug report (ID: `{report_id}`) has been submitted! Thank you for helping us improve.",
                ephemeral=True
            )

        except ValueError:
            await interaction.response.send_message(
                "🐛 An error occurred: Invalid BUG_REPORT_CHANNEL_ID. Please contact an administrator.",
                ephemeral=True
            )
            print("Error: BUG_REPORT_CHANNEL_ID is not a valid integer.")
        except Exception as e:
            await interaction.response.send_message(
                "🐛 An unexpected error occurred while submitting your bug report. Please try again later.",
                ephemeral=True
            )
            print(f"An unexpected error occurred in BugReportModal on_submit: {e}")


# --- View for Bug Report Actions (Fixed/Decline) ---
class BugReportActionsView(ui.View):
    def __init__(self, bot: commands.Bot, manager: BugReportManager, report_id: int, report_data: dict):
        super().__init__(timeout=300) # Timeout after 5 minutes
        self.message = None
        self.bot = bot
        self.manager = manager
        self.report_id = report_id
        self.report_data = report_data # Store the full report data

    async def on_timeout(self):
        # Disable buttons when the view times out
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.edit(view=self)

    @ui.button(label="Fixed", style=discord.ButtonStyle.green, custom_id="bug_fixed")
    async def fixed_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True) # Defer the response to show thinking

        archive_channel_id = os.getenv("BUG_ARCHIVE_CHANNEL_ID")
        if not archive_channel_id:
            await interaction.followup.send(
                "❌ Error: Bug archive channel not configured. Cannot archive.",
                ephemeral=True
            )
            print("Error: BUG_ARCHIVE_CHANNEL_ID not set in environment variables.")
            return

        try:
            archive_channel = self.bot.get_channel(int(archive_channel_id))
            if not archive_channel:
                await interaction.followup.send(
                    "❌ Error: Could not find the configured bug archive channel. Cannot archive.",
                    ephemeral=True
                )
                print(f"Error: Could not find archive channel with ID {archive_channel_id}")
                return
            
            if self.message:
                updated_embed = self.message.embeds[0]
                updated_embed.color = discord.Color.green()
                for i, field in enumerate(updated_embed.fields):
                    if field.name.lower() == "status":
                        updated_embed.set_field_at(i, name="Status", value="`VERIFIED`", inline=False)
                        break
                else:
                    fields = updated_embed.fields
                    updated_embed.clear_fields()
                    updated_embed.add_field(name="Status", value="`VERIFIED`", inline=False)
                    for field in fields:
                        updated_embed.add_field(name=field.name, value=field.value, inline=field.inline)



            archive_embed = discord.Embed(
                title=f"✅ FIXED",
                color=discord.Color.green(), # Green color for fixed
                timestamp=interaction.created_at
            )
            archive_embed.add_field(name="Title", value=self.report_data.get('title', 'N/A'), inline=False)
            archive_embed.add_field(name="Status", value="FIXED", inline=False)
            archive_embed.add_field(name="Category", value=self.report_data.get('category', 'N/A').capitalize(), inline=True)
            archive_embed.add_field(name="Severity", value=self.report_data.get('severity', 'N/A').capitalize(), inline=True)
            archive_embed.add_field(name="Reporter", value=f"<@{self.report_data.get('reporterID', 'N/A')}>", inline=True)
            archive_embed.add_field(name="Reported At", value=self.report_data.get('reportedAt', 'N/A'), inline=True)
            archive_embed.add_field(name="Description", value=self.report_data.get('description', 'N/A'), inline=False)
            reproduce_steps_display = self.report_data.get('reproducesteps', 'N/A').replace('\\n', '\n')
            archive_embed.add_field(name="Steps to Reproduce", value=reproduce_steps_display, inline=False)
            # Add "Fixed by" to the footer with the fixer's logo
            archive_embed.set_footer(
                text=f"Fixed by: {interaction.user.display_name} - Bug Report ID: {self.report_id}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None # Use fixer's avatar
            )
            await archive_channel.send(embed=archive_embed)

            # --- Reward Logic ---
            reward_channel_id = os.getenv("BUG_POINT_REWARD_CHANNEL_ID")
            severity_points = {
                "low": 2,
                "medium": 3,
                "high": 5,
                "very high": 8
            }
            reporter_id = self.report_data.get("reporterID")
            severity = self.report_data.get("severity", "").lower()
            points = severity_points.get(severity, 0)

            if reward_channel_id and points > 0:
                try:
                    reward_channel = self.bot.get_channel(int(reward_channel_id))
                    if reward_channel:
                        eco = self.bot.get_cog("Economy")
                        if eco:
                            await eco._add_points_to_data(int(reporter_id), points)
                            reporter = await self.bot.fetch_user(int(reporter_id))
                            
                            reward_embed = discord.Embed(
                                title="🏆 Reward!",
                                description=f"Gave **{points}** points to {reporter.mention} for reporting a **{self.report_data.get('severity', 'N/A').capitalize()}** severity bug.",
                                color=discord.Color.gold(),
                                timestamp=datetime.now(timezone.utc)
                            )

                            reward_embed.add_field(name="Bug Title", value=self.report_data.get("title", "N/A"), inline=False)
                            reward_embed.add_field(name="Bug ID", value=str(self.report_id), inline=True)
                            reward_embed.set_thumbnail(url=reporter.avatar.url if reporter.avatar else None)

                            reward_embed.set_footer(
                                text=f"Fixed by {interaction.user.display_name}",
                                icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None
                            )

                            await reward_channel.send(embed=reward_embed)
                        else:
                            print("Warning: Economy cog not found. Cannot add points.")
                except Exception as e:
                    print(f"Error sending reward embed or adding points: {e}")
            
            # Delete the report after it's fixed and processed
            await self.manager.delete_report(self.report_id)

            
            if self.message:
                updated_embed = self.message.embeds[0]
                updated_embed.color = discord.Color.green()
                for i, field in enumerate(updated_embed.fields):
                    if field.name.lower() == "status":
                        updated_embed.set_field_at(i, name="Status", value="`VERIFIED`", inline=False)
                        break
                else:
                    fields = updated_embed.fields
                    updated_embed.clear_fields()
                    updated_embed.add_field(name="Status", value="`VERIFIED`", inline=False)
                    for field in fields:
                        updated_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                await self.message.edit(embed=updated_embed, view=None)

            await interaction.followup.send(f"✅ Bug report `{self.report_id}` marked as fixed and archived.", ephemeral=True)



            self.stop() # Stop the view
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while marking report as fixed: {e}", ephemeral=True)


    @ui.button(label="Declined", style=discord.ButtonStyle.red, custom_id="bug_declined")
    async def declined_button(self, interaction: Interaction, button: ui.Button):
        await interaction.response.defer(ephemeral=True) # Defer the response

        # Create an embed for the archive channel for declined reports
        archive_channel_id = os.getenv("BUG_ARCHIVE_CHANNEL_ID")
        if not archive_channel_id:
            await interaction.followup.send(
                "❌ Error: Bug archive channel not configured. Cannot archive.",
                ephemeral=True
            )
            print("Error: BUG_ARCHIVE_CHANNEL_ID not set in environment variables.")
            return

        try:
            archive_channel = self.bot.get_channel(int(archive_channel_id))
            if not archive_channel:
                await interaction.followup.send(
                    "❌ Error: Could not find the configured bug archive channel. Cannot archive.",
                    ephemeral=True
                )
                print(f"Error: Could not find archive channel with ID {archive_channel_id}")
                return
            

            if self.message:
                updated_embed = self.message.embeds[0]
                updated_embed.color = discord.Color.red()
                for i, field in enumerate(updated_embed.fields):
                    if field.name.lower() == "status":
                        updated_embed.set_field_at(i, name="Status", value="`DECLINED`", inline=False)
                        break
                else:
                    fields = updated_embed.fields
                    updated_embed.clear_fields()
                    updated_embed.add_field(name="Status", value="`DECLINED`", inline=False)
                    for field in fields:
                        updated_embed.add_field(name=field.name, value=field.value, inline=field.inline)

                await self.message.edit(embed=updated_embed, view=None)

            else:
                # This 'else' block seems redundant given the 'if self.message' above.
                # If self.message is None, the initial 'if self.message' would handle it.
                # Keeping it for now as per "dont remove any important part of code"
                # but it might not be strictly reachable in practice.
                fields = updated_embed.fields
                updated_embed.clear_fields()
                updated_embed.add_field(name="Status", value="`DECLINED`", inline=False)
                for field in fields:
                    updated_embed.add_field(name=field.name, value=field.value, inline=field.inline)


                await self.message.edit(embed=updated_embed, view=None)



            archive_embed = discord.Embed(
                title=f"❌ DECLINED",
                description=f"Bug Report #{self.report_id} has been declined by {interaction.user.display_name}.",
                color=discord.Color.red(), # Red color for declined
                timestamp=interaction.created_at
            )
            archive_embed.add_field(name="Title", value=self.report_data.get('title', 'N/A'), inline=False)
            archive_embed.add_field(name="Status", value="DECLINED", inline=False)
            archive_embed.add_field(name="Category", value=self.report_data.get('category', 'N/A').capitalize(), inline=True)
            archive_embed.add_field(name="Severity", value=self.report_data.get('severity', 'N/A').capitalize(), inline=True)
            archive_embed.add_field(name="Reporter", value=f"<@{self.report_data.get('reporterID', 'N/A')}>", inline=True)
            archive_embed.add_field(name="Reported At", value=self.report_data.get('reportedAt', 'N/A'), inline=True)
            archive_embed.add_field(name="Description", value=self.report_data.get('description', 'N/A'), inline=False)
            reproduce_steps_display = self.report_data.get('reproducesteps', 'N/A').replace('\\n', '\n')
            archive_embed.add_field(name="Steps to Reproduce", value=reproduce_steps_display, inline=False)
            archive_embed.set_footer(
                text=f"Declined by: {interaction.user.display_name} - Bug Report ID: {self.report_id}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            await archive_channel.send(embed=archive_embed)
            
            # Delete the report after it's declined and processed
            await self.manager.delete_report(self.report_id)

            
            if self.message:
                updated_embed = self.message.embeds[0]
                updated_embed.color = discord.Color.red()
                for i, field in enumerate(updated_embed.fields):
                    if field.name.lower() == "status":
                        updated_embed.set_field_at(i, name="Status", value="`DECLINED`", inline=False)
                        break
                else:
                    fields = updated_embed.fields
                    updated_embed.clear_fields()
                    updated_embed.add_field(name="Status", value="`DECLINED`", inline=False)
                    for field in fields:
                        updated_embed.add_field(name=field.name, value=field.value, inline=field.inline)
                await self.message.edit(embed=updated_embed, view=None)

            await interaction.followup.send(f"❌ Bug report `{self.report_id}` marked as declined and archived.", ephemeral=True)



            self.stop() # Stop the view
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while marking report as declined: {e}", ephemeral=True)


# --- Command Cog ---
class bugreports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bug_report_manager = BugReportManager(bot)

    @app_commands.command(
        name="submitbug",
        description="Submit a bug report for review."
    )
    @has_command_role("submitbug")
    @app_commands.describe(
        severity="How severe is this bug?",
        category="What part of the bot does this bug affect?"
    )
    @app_commands.choices(
        severity=[
            app_commands.Choice(name="Low", value="low"),
            app_commands.Choice(name="Medium", value="medium"),
            app_commands.Choice(name="High", value="high"),
            app_commands.Choice(name="Very High", value="very high")
        ],
        category=[
            app_commands.Choice(name="Mining", value="mining"),
            app_commands.Choice(name="Foraging", value="foraging"),
            app_commands.Choice(name="Dungeons", value="dungeons"),
            app_commands.Choice(name="Slayers", value="slayers"),
            app_commands.Choice(name="Island", value="island"),
            app_commands.Choice(name="Fishing", value="fishing"),
            app_commands.Choice(name="Others", value="others"),
        ]
    )
    async def submit_bug(self, interaction: Interaction, severity: str, category: str):
        """Allows users to submit a bug report via a modal."""
        # Pass the bot and manager instances to the modal
        await interaction.response.send_modal(BugReportModal(self.bot, category, severity, self.bug_report_manager))

    @app_commands.command(
        name="getreport",
        description="Get details of a specific bug report by ID (Admin only)."
    )
    @has_command_role("getreport")
    @app_commands.describe(report_id="The ID of the bug report")
    async def get_report(self, interaction: Interaction, report_id: int):
        await interaction.response.defer(ephemeral=True)
        report = await self.bug_report_manager.get_report_by_id(report_id)

        if report:
            embed = discord.Embed(
                title=f"Bug Report #{report.get('id')} - {report.get('title', 'N/A')}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Severity", value=report.get('severity', 'N/A').capitalize(), inline=True)
            embed.add_field(name="Category", value=report.get('category', 'N/A').capitalize(), inline=True)
            embed.add_field(name="Reporter", value=f"<@{report.get('reporterID', 'N/A')}>", inline=True)
            embed.add_field(name="Reported At", value=report.get('reportedAt', 'N/A'), inline=True)
            embed.add_field(name="Description", value=report.get('description', 'N/A'), inline=False)

            reproduce_steps_display = report.get('reproducesteps', 'N/A').replace('\\n', '\n')
            embed.add_field(name="Steps to Reproduce", value=reproduce_steps_display, inline=False)

            bug_actions_view = BugReportActionsView(self.bot, self.bug_report_manager, report_id, report)
            msg = await interaction.followup.send(embed=embed, view=bug_actions_view, ephemeral=False)
            bug_actions_view.message = msg

        else:
            await interaction.followup.send(f"❌ Bug report with ID `{report_id}` not found.", ephemeral=True)


    @app_commands.command(name="buglist", description="Shows all pending bug reports with pagination and sorting (Admin only).")
    @has_command_role("buglist")
    async def bug_list(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        self.bug_report_manager.reports = await self.bug_report_manager._load_reports()
        view = BugListPaginationView(self.bot, self.bug_report_manager, interaction.user)
        await view.initialize_and_send(interaction)


class BugListPaginationView(ui.View):
    def __init__(self, bot: commands.Bot, manager, author: discord.User):
        super().__init__(timeout=300)
        self.bot = bot
        self.manager = manager
        self.author = author
        self.current_page = 0
        self.reports_per_page = 4
        self.current_category_filter = "all"
        self.current_sort_by = "id_ascending"

        self.category_options = [
            discord.SelectOption(label="All Categories", value="all", default=True),
            discord.SelectOption(label="Mining", value="mining"),
            discord.SelectOption(label="Foraging", value="foraging"),
            discord.SelectOption(label="Dungeons", value="dungeons"),
            discord.SelectOption(label="Slayers", value="slayers"),
            discord.SelectOption(label="Island", value="island"),
            discord.SelectOption(label="Fishing", value="fishing"),
            discord.SelectOption(label="Others", value="others"),
        ]

        self.sort_options = [
            discord.SelectOption(label="Sort by ID (Ascending)", value="id_ascending"),
            discord.SelectOption(label="Sort by Date (Ascending)", value="date_ascending"),
            discord.SelectOption(label="Sort by Date (Descending)", value="date_descending"),
            discord.SelectOption(label="Sort by Severity (High to Low)", value="severity_high"),
            discord.SelectOption(label="Sort by Severity (Low to High)", value="severity_low"),
        ]

        # Initialize reports and total_pages
        self.reports = []  # ← temporary until loaded async
        self.total_pages = 1

        self._add_navigation_buttons()  # Add buttons initially
        self._refresh_select_menu()     # Add the select menu initially

    def _add_navigation_buttons(self):
        # Remove existing navigation buttons before adding them to avoid duplicates
        # We must make a copy of self.children as we are modifying it during iteration.
        for item in list(self.children): 
            if isinstance(item, discord.ui.Button) and item.label in ["«", "◀", "▶", "»"]:
                self.remove_item(item)

        # Define and add new button instances with their callbacks
        first = discord.ui.Button(label="«", style=discord.ButtonStyle.blurple, row=1)
        first.callback = self.first_page_button_callback
        self.add_item(first)

        prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.blurple, row=1)
        prev.callback = self.previous_button_callback
        self.add_item(prev)

        next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.blurple, row=1)
        next_btn.callback = self.next_button_callback
        self.add_item(next_btn)

        last = discord.ui.Button(label="»", style=discord.ButtonStyle.blurple, row=1)
        last.callback = self.last_page_button_callback
        self.add_item(last)

    class SortSelect(ui.Select):
        def __init__(self, parent_view):
            # Combine category and sort options for the dropdown
            options = parent_view.category_options + [
                # Using a disabled option as a visual separator if needed,
                # or simply remove if not desired.
                discord.SelectOption(label="--- Sort By ---", value="divider_sort") 
            ] + parent_view.sort_options
            super().__init__(placeholder="Sort & Filter", options=options, row=0)
            self.parent_view = parent_view

        async def callback(self, interaction: Interaction):
            if interaction.user.id != self.parent_view.author.id:
                await interaction.response.send_message("You are not the requester of this interaction.", ephemeral=True)
                return

            selected_value = self.values[0]
            
            # Reset default for all options
            for option in self.options:
                option.default = False

            # Set default for the selected option
            for opt in self.options:
                if opt.value == selected_value:
                    opt.default = True
                    break

            if selected_value in [opt.value for opt in self.parent_view.category_options]:
                self.parent_view.current_category_filter = selected_value
            elif selected_value != "divider_sort": # Exclude the divider from being set as sort_by
                self.parent_view.current_sort_by = selected_value

            # Re-filter and re-sort reports
            self.parent_view.reports = await self.parent_view.manager.get_filtered_and_sorted_reports(
                self.parent_view.current_category_filter,
                self.parent_view.current_sort_by
            )
            self.parent_view.current_page = 0
            self.parent_view.total_pages = max(1, (len(self.parent_view.reports) + self.parent_view.reports_per_page - 1) // self.parent_view.reports_per_page)
            
            self.parent_view._refresh_select_menu() # Re-add select menu with updated default
            await self.parent_view._send_current_page(interaction)


    def _refresh_select_menu(self):
        # Remove existing select menu before adding a new one
        for item in list(self.children):
            if isinstance(item, discord.ui.Select):
                self.remove_item(item)
        self.add_item(self.SortSelect(self))


    async def initialize_and_send(self, interaction: Interaction):
        # Always re-fetch reports and calculate total_pages before initial send
        self.reports = await self.manager.get_filtered_and_sorted_reports(
            self.current_category_filter,
            self.current_sort_by
        )
        self.total_pages = max(1, (len(self.reports) + self.reports_per_page - 1) // self.reports_per_page)
        self.current_page = 0 # Ensure we always start on the first page

        self._add_navigation_buttons()  # Re-add navigation buttons to ensure their presence and correct callbacks
        self._refresh_select_menu()     # Re-add the select menu with updated defaults
        self._update_buttons()          # Update button states based on current_page and total_pages

        embed = self._create_bug_list_embed()
        self.message = await interaction.followup.send(
            embed=embed,
            view=self,
            ephemeral=True
        )

    async def _send_current_page(self, interaction: Interaction):
        # Always re-fetch reports and calculate total_pages before sending updated page
        self.reports = await self.manager.get_filtered_and_sorted_reports(self.current_category_filter, self.current_sort_by)
        self.total_pages = max(1, (len(self.reports) + self.reports_per_page - 1) // self.reports_per_page)
        
        self._add_navigation_buttons() # Re-add buttons on every page change
        self._update_buttons()         # Update button states after page change
        embed = self._create_bug_list_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    def _update_buttons(self):
        # Re-find buttons by their labels or custom_ids to ensure robustness
        first_button = next((item for item in self.children if isinstance(item, discord.ui.Button) and item.label == "«"), None)
        previous_button = next((item for item in self.children if isinstance(item, discord.ui.Button) and item.label == "◀"), None)
        next_button = next((item for item in self.children if isinstance(item, discord.ui.Button) and item.label == "▶"), None)
        last_button = next((item for item in self.children if isinstance(item, discord.ui.Button) and item.label == "»"), None)

        if first_button:
            first_button.disabled = (self.current_page == 0)
        if previous_button:
            previous_button.disabled = (self.current_page == 0)
        if next_button:
            next_button.disabled = (self.current_page >= self.total_pages - 1)
        if last_button:
            last_button.disabled = (self.current_page >= self.total_pages - 1)

    async def first_page_button_callback(self, interaction: Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You are not the requester of this interaction.", ephemeral=True)
            return
        self.current_page = 0
        await self._send_current_page(interaction)

    async def previous_button_callback(self, interaction: Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You are not the requester of this interaction.", ephemeral=True)
            return
        self.current_page = max(0, self.current_page - 1)
        await self._send_current_page(interaction)

    async def next_button_callback(self, interaction: Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You are not the requester of this interaction.", ephemeral=True)
            return
        self.current_page = min(self.total_pages - 1, self.current_page + 1)
        await self._send_current_page(interaction)

    async def last_page_button_callback(self, interaction: Interaction):
        if interaction.user.id != self.author.id:
            await interaction.response.send_message("You are not the requester of this interaction.", ephemeral=True)
            return
        self.current_page = self.total_pages - 1
        await self._send_current_page(interaction)

    def _create_bug_list_embed(self):
        start_index = self.current_page * self.reports_per_page
        end_index = start_index + self.reports_per_page
        page_reports = self.reports[start_index:end_index]

        embed = discord.Embed(
            title="🐞 Bug Reports",
            description=f"Page {self.current_page + 1}/{self.total_pages}",
            color=discord.Color.blue()
        )

        if not page_reports:
            embed.description += "\nNo reports available for the current filter/sort criteria."
        else:
            for report in page_reports:
                embed.add_field(
                    name=f"#{report['id']} - {report['title']}",
                    value=(
                        f"**Severity:** {report['severity'].capitalize()}\n"
                        f"**Category:** {report['category'].capitalize()}\n"
                        f"**Bug ID:** {report['id']}\n"
                        f"**Reporter:** <@{report['reporterID']}>\n"
                        f"**Reported At:** {report['reportedAt']}\n"
                        f"**Description:** {report['description']}"
                    ),
                    inline=False
                )
        return embed


    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if hasattr(self, 'message'):
            await self.message.edit(view=self)

async def setup(bot):
    await bot.add_cog(bugreports(bot))