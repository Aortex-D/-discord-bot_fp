import os
import discord
import datetime
from collections import defaultdict
from typing import Optional
from discord.ext import commands
from discord import app_commands, ui, Interaction
from dotenv import load_dotenv
from utils.loader import load_data, save_data, _get_db
from utils.commands import get_admin_info
from datetime import datetime, timezone
import asyncio

class BugReportManager:
    def __init__(self, bot):
        self.bot = bot
        self.reports = load_data("bugrep")
        # Ensure 'status' is present for existing reports or initialize
        for report in self.reports:
            if "status" not in report:
                report["status"] = "pending"
        self.next_id = max([report.get("id", 0) for report in self.reports]) + 1 if self.reports else 1

    async def _load_reports(self):
        reports = await asyncio.to_thread(load_data, "bugrep")
        for report in reports:
            if "status" not in report:
                report["status"] = "pending"
        return reports

    async def _save_reports(self):
        await asyncio.to_thread(save_data, "bugrep", self.reports)

    async def add_report(self, report_data: dict):
        report_data["id"] = self.next_id
        report_data["status"] = "pending" # New reports are always pending initially 
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

    async def update_report_status(self, report_id: int, new_status: str):
        report = await self.get_report_by_id(report_id)
        if report:
            report["status"] = new_status
            await self._save_reports()
            return True
        return False

    async def get_filtered_and_sorted_reports(self, category_filter: str = "all", status_filter: str = "all", sort_by: str = "id_ascending"):
        filtered_reports = self.reports

        if category_filter != "all":
            filtered_reports = [r for r in filtered_reports if r.get('category') and r['category'].lower() == category_filter.lower()]
        
        if status_filter != "all":
            filtered_reports = [r for r in filtered_reports if r.get('status') and r['status'].lower() == status_filter.lower()]


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
    def __init__(self, bot: commands.Bot, category: str = "N/A", severity: str = "N/A", manager: BugReportManager = None, original_reporter_id: str = None):
        super().__init__()
        self.bot = bot # Store the bot instance
        self.category = category
        self.severity = severity
        self.manager = manager # Store the manager instance to save reports
        self.original_reporter_id = original_reporter_id

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
            max_length=800, # Changed from 2000 to 800 
            style=discord.TextStyle.paragraph,
            required=True
        )
        self.steps_to_reproduce = ui.TextInput(
            label='Describe Steps To Reproduce The Bug:',
            placeholder='List steps to reliably reproduce the bug (e.g., "1. Go to...", "2. Click...", "3. Observe...")',
            max_length=500, # Changed from 2000 to 500 
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
                "status": "pending", # Set status to pending on submission 
                "category": self.category,
                "reporterID": str(interaction.user.id),
                "reportedAt": interaction.created_at.strftime("%Y-%m-%d"),
                "description": self.bug_description.value,
                "reproducesteps": self.steps_to_reproduce.value.replace('\n', '\\n'), 
            }
            if self.original_reporter_id: # Add original_reporter if provided 
                report_data["original_reporter"] = self.original_reporter_id

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
            if self.original_reporter_id:
                embed.add_field(name="Original Reporter", value=f"{self.original_reporter_id}", inline=False)
            embed.add_field(name="Category", value=self.category.capitalize(), inline=True)
            embed.add_field(name="Severity", value=self.severity.capitalize(), inline=True)
            embed.add_field(name="Status", value="`PENDING`", inline=True) # Display pending status 
            embed.add_field(name="Description", value=self.bug_description.value, inline=False)
            embed.add_field(name="Steps to Reproduce", value=self.steps_to_reproduce.value, inline=False)
            embed.set_footer(text=f"Bug Report ID: {report_id}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
            
            # Send with approval view 
            view = BugReportApprovalView(self.bot, self.manager, report_id, report_data)
            message = await report_channel.send(embed=embed, view=view)
            view.message = message
            self.bot.add_view(view)


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

class BugReportApprovalView(ui.View):
    def __init__(self, bot: commands.Bot, manager: BugReportManager, report_id: int = 0, report_data: dict = None):
        super().__init__(timeout=None)  # No timeout for persistence
        self.message = None
        self.bot = bot
        self.manager = manager
        self.report_id = report_id
        self._initial_report_id = report_id  # Store initial for first send
        self._initial_report_data = report_data  # Store initial for first send
        self.report_data = report_data 

    # Helper method to dynamically get report_id and report_data
    async def _get_current_report_info(self, interaction: Interaction):
        report_id = self._initial_report_id
        report_data = self._initial_report_data

        if interaction.message and interaction.message.embeds:
            footer_text = interaction.message.embeds[0].footer.text
            if footer_text and "Bug Report ID:" in footer_text:
                try:
                    # Extract ID from footer (e.g., "Bug Report ID: 123")
                    extracted_id_str = footer_text.split("Bug Report ID:")[-1].strip()
                    report_id = int(extracted_id_str)
                    # Now fetch the full report data from the manager
                    report_data = await self.manager.get_report_by_id(report_id)
                except ValueError:
                    print(f"Warning: Could not parse report ID from footer: {footer_text}")
                except Exception as e:
                    print(f"Error fetching report data in BugReportApprovalView: {e}")
        
        # If no report_data found from embed, and initial data was set, use it.
        # This covers cases where it's a fresh interaction on a newly sent message.
        if not report_data and self._initial_report_data:
            report_data = self._initial_report_data
            report_id = self._initial_report_id

        # If still no report_data (e.g., after bot restart and message is old), try to fetch using initial ID
        if not report_data and report_id != 0:
            report_data = await self.manager.get_report_by_id(report_id)

        return report_id, report_data

    @ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="bug_approve")
    async def approve_button(self, interaction: Interaction, button: ui.Button):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

        report_id, report_data = await self._get_current_report_info(interaction)
        self.report_id = report_id
        self.report_data = report_data
        if not report_data:
            await interaction.followup.send("❌ Error: Could not retrieve report data for this interaction. The report might have been deleted or corrupted.", ephemeral=True)
            return
        bug_approved_channel_id = os.getenv("BUG_APPROVED_CHANNEL_ID")
        if not bug_approved_channel_id:
            await interaction.followup.send("❌ Error: Bug approved channel not configured. Cannot approve.", ephemeral=True)
            return

        try:
            approved_channel = self.bot.get_channel(int(bug_approved_channel_id))

            eco = self.bot.get_cog("Economy")
            # Use report_data for original_reporter and reporterID
            reporter_discord_id = report_data.get("reporterID")
            points_recipient_id = int(reporter_discord_id)

            if report_data.get("original_reporter"):
                # Auto give 1 point
                eco = self.bot.get_cog("Economy")
                if eco:
                    await eco._add_points_to_data(points_recipient_id, 1)
                    reporter_user = await self.bot.fetch_user(points_recipient_id)

                    # Reward embed
                    reward_channel_id = os.getenv("BUG_POINT_REWARD_CHANNEL_ID")
                    if reward_channel_id:
                        reward_channel = self.bot.get_channel(int(reward_channel_id))
                        if reward_channel:
                            reward_embed = discord.Embed(
                                title="🏆 Reward!",
                                description=f"Gave **1** point to {reporter_user.mention} for reporting a bug.",
                                color=discord.Color.gold(),
                                timestamp=datetime.now(timezone.utc)
                            )
                            reward_embed.add_field(name="Bug Title", value=report_data.get("title", "N/A"), inline=False)
                            reward_embed.add_field(name="Bug ID", value=str(self.report_id), inline=True)
                            reward_embed.set_thumbnail(url=reporter_user.avatar.url if reporter_user.avatar else None)
                            reward_embed.set_footer(
                                text=f"Approved by {interaction.user.display_name}",
                                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
                            )
                            await reward_channel.send(embed=reward_embed)

                # ✅ Update status
                await self.manager.update_report_status(self.report_id, "approved")

                # Send to approve log channel
                await self.manager.update_report_status(self.report_id, "approved")
        
                # Send to approved channel
                bug_approved_channel_id = os.getenv("BUG_APPROVED_CHANNEL_ID")
                if bug_approved_channel_id:
                    approved_channel = self.bot.get_channel(int(bug_approved_channel_id))
                    if approved_channel:
                        approved_embed = self._create_approved_embed(interaction, "approved")
                        view = BugReportActionsView(self.bot, self.manager, self.report_id, self.report_data)
                        approved_message = await approved_channel.send(embed=approved_embed, view=view)
                        view.message = approved_message

                # ✅ Delete the report message
                if self.message:
                    try:
                        await self.message.delete()
                    except discord.HTTPException:
                        pass

                # ✅ Confirm to approver
                await interaction.followup.send(
                    f"✅ Bug report `{self.report_id}` approved and 1 point given to the reporter.",
                    ephemeral=True
                )
                self.stop()
                return

            else:
                point_selection_view = PointSelectionView(self.bot, self.manager, self.report_id, self.report_data, self.message)
                points_org_msg = await interaction.followup.send(
                    embed=discord.Embed(
                        title="🎁 Reward Points",
                        description="Please select how many points to award.",
                        color=discord.Color.blue()
                    ),
                    view=point_selection_view,
                    ephemeral=True
                )
                point_selection_view.original_message = points_org_msg
                return
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while approving the report: {e}", ephemeral=True)
            print(f"Error in approve_button: {e}")


    @ui.button(label="Decline", style=discord.ButtonStyle.red, custom_id="bug_decline")
    async def decline_button(self, interaction: Interaction, button: ui.Button):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        report_id, report_data = await self._get_current_report_info(interaction)
        if not report_data:
            await interaction.followup.send("❌ Error: Could not retrieve report data for this interaction. The report might have been deleted or corrupted.", ephemeral=True)
            return
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
            
            archive_embed = discord.Embed(
                title=f"❌ DECLINED",
                description=f"Bug Report #{report_id} has been declined by {interaction.user.display_name}.",
                color=discord.Color.red(),
                timestamp=interaction.created_at
            )
            archive_embed.add_field(name="Title", value=self.report_data.get('title', 'N/A'), inline=False)
            archive_embed.add_field(name="Status", value="DECLINED", inline=False)
            archive_embed.add_field(name="Category", value=self.report_data.get('category', 'N/A').capitalize(), inline=True)
            archive_embed.add_field(name="Severity", value=self.report_data.get('severity', 'N/A').capitalize(), inline=True)
            archive_embed.add_field(name="Reporter", value=f"<@{self.report_data.get('reporterID', 'N/A')}>", inline=True)
            if self.report_data.get("original_reporter"):
                archive_embed.add_field(name="Original Reporter", value=f"{self.report_data.get('original_reporter')}", inline=True)
            archive_embed.add_field(name="Reported At", value=self.report_data.get('reportedAt', 'N/A'), inline=True)
            archive_embed.add_field(name="Description", value=self.report_data.get('description', 'N/A'), inline=False)
            reproduce_steps_display = self.report_data.get('reproducesteps', 'N/A').replace('\\n', '\n')
            archive_embed.add_field(name="Steps to Reproduce", value=reproduce_steps_display, inline=False)
            archive_embed.set_footer(
                text=f"Declined by: {interaction.user.display_name} - Bug Report ID: {self.report_id}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            await archive_channel.send(embed=archive_embed)
            
            # Delete the report from the database and original message 
            await self.manager.update_report_status(self.report_id, "declined")
        
            if self.message:
                await self.message.delete()

            await interaction.followup.send(f"❌ Bug report `{self.report_id}` marked as declined and archived.", ephemeral=True)
            self.stop() # Stop the view
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while marking report as declined: {e}", ephemeral=True)

    def _create_approved_embed(self, interaction: Interaction, status: str):
        embed = discord.Embed(
            title=f"✅ Approved Bug Report: {self.report_data['title']}",
            color=discord.Color.green(),
            timestamp=interaction.created_at
        )
        embed.set_author(
            name=f"Reported by {self.report_data['reporterID']}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        embed.add_field(name="Reporter", value=f"<@{self.report_data['reporterID']}> ({self.report_data['reporterID']})", inline=False)
        if self.report_data.get("original_reporter"):
            embed.add_field(name="Original Reporter", value=f"{self.report_data['original_reporter']}", inline=False)
        embed.add_field(name="Category", value=self.report_data['category'].capitalize(), inline=True)
        embed.add_field(name="Severity", value=self.report_data['severity'].capitalize(), inline=True)
        embed.add_field(name="Status", value=f"`{status.upper()}`", inline=True)
        embed.add_field(name="Description", value=self.report_data['description'], inline=False)
        embed.add_field(name="Steps to Reproduce", value=self.report_data['reproducesteps'].replace('\\n', '\n'), inline=False)
        embed.set_footer(text=f"Bug Report ID: {self.report_id}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        return embed

# --- View for Point Selection (for unassigned original_reporter) ---
class PointSelectionView(ui.View):
    def __init__(self, bot: commands.Bot, manager: BugReportManager, report_id: int, report_data: dict, original_message: discord.Message):
        super().__init__(timeout=180) # Timeout after 3 minutes for point selection
        self.bot = bot
        self.manager = manager
        self.report_id = report_id
        self.report_data = report_data
        self.original_message = original_message # Store original message to delete it

        for i in range(1, 6): # Buttons for 1 to 5 points
            button = ui.Button(label=f"{i} Points", style=discord.ButtonStyle.blurple, custom_id=f"points_{i}")
            button.callback = lambda interaction, points=i: self._give_points_and_finalize(interaction, points)
            self.add_item(button)

    async def interaction_check(self, interaction: Interaction) -> bool:
        # This check needs to be more robust. It should ensure only the person
        # who initiated the ephemeral message can click.
        # For now, if the interaction.message (the ephemeral message) is set,
        # we can assume it's valid, as it's sent ephemeral to the approver.
        # If you need to restrict it further, you would store the approver's ID in __init__
        # and check interaction.user.id against it here.
        return True # Allows all interactions for now. Consider more restrictive logic if needed.

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.original_message:  # ← FIXED: use original_message not self.message
            await self.original_message.edit(view=self)


    async def _give_points_and_finalize(self, interaction: Interaction, points: int):
        await interaction.response.defer(ephemeral=True)

        reporter_id = int(self.report_data["reporterID"])
        eco = self.bot.get_cog("Economy")
        if eco:
            await eco._add_points_to_data(reporter_id, points)
            reporter_user = await self.bot.fetch_user(reporter_id)

            reward_channel_id = os.getenv("BUG_POINT_REWARD_CHANNEL_ID")
            if reward_channel_id:
                try:
                    reward_channel = self.bot.get_channel(int(reward_channel_id))
                    if reward_channel:
                        reward_embed = discord.Embed(
                            title="🏆 Reward!",
                            description=f"Gave **{points}** points to {reporter_user.mention} for reporting a bug.",
                            color=discord.Color.gold(),
                            timestamp=datetime.now(timezone.utc)
                        )
                        reward_embed.add_field(name="Bug Title", value=self.report_data.get("title", "N/A"), inline=False)
                        reward_embed.add_field(name="Bug ID", value=str(self.report_id), inline=True)
                        reward_embed.set_thumbnail(url=reporter_user.avatar.url if reporter_user.avatar else None)
                        reward_embed.set_footer(
                            text=f"Approved by {interaction.user.display_name}",
                            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
                        )
                        await reward_channel.send(embed=reward_embed)
                except Exception as e:
                    print(f"Error sending reward embed: {e}")
        else:
            print("Warning: Economy cog not found. Cannot add points.")

        await self.manager.update_report_status(self.report_id, "approved")
        
        # Send to approved channel
        bug_approved_channel_id = os.getenv("BUG_APPROVED_CHANNEL_ID")
        if bug_approved_channel_id:
            approved_channel = self.bot.get_channel(int(bug_approved_channel_id))
            if approved_channel:
                approved_embed = self._create_approved_embed(interaction, "approved")
                view = BugReportActionsView(self.bot, self.manager, self.report_id, self.report_data)
                approved_message = await approved_channel.send(embed=approved_embed, view=view)
                view.message = approved_message

        if self.original_message: # Delete original message from BUG_REPORT_CHANNEL_ID
            await self.original_message.delete()
        
        await interaction.followup.send(f"✅ Bug report `{self.report_id}` approved and {points} points given to reporter.", ephemeral=True)
        self.stop() # Stop this view after action

    def _create_approved_embed(self, interaction: Interaction, status: str):
        embed = discord.Embed(
            title=f"✅ Approved Bug Report: {self.report_data['title']}",
            color=discord.Color.green(),
            timestamp=interaction.created_at
        )
        embed.set_author(
            name=f"Reported by {self.report_data['reporterID']}",
            icon_url=interaction.user.avatar.url if interaction.user.avatar else None
        )
        embed.add_field(name="Reporter", value=f"<@{self.report_data['reporterID']}> ({self.report_data['reporterID']})", inline=False)
        if self.report_data.get("original_reporter"):
            embed.add_field(name="Original Reporter", value=f"{self.report_data['original_reporter']}", inline=False)
        embed.add_field(name="Category", value=self.report_data['category'].capitalize(), inline=True)
        embed.add_field(name="Severity", value=self.report_data['severity'].capitalize(), inline=True)
        embed.add_field(name="Status", value=f"`{status.upper()}`", inline=True)
        embed.add_field(name="Description", value=self.report_data['description'], inline=False)
        embed.add_field(name="Steps to Reproduce", value=self.report_data['reproducesteps'].replace('\\n', '\n'), inline=False)
        embed.set_footer(text=f"Bug Report ID: {self.report_id}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)
        return embed

# --- View for Bug Report Actions (Fixed/Decline) ---
class BugReportActionsView(ui.View):
    def __init__(self, bot: commands.Bot, manager: BugReportManager, report_id: int, report_data: dict):
        super().__init__(timeout=None) # Timeout is None for persistence 
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
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

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
            if self.report_data.get("original_reporter"):
                archive_embed.add_field(name="Original Reporter", value=f"{self.report_data.get('original_reporter')}", inline=True)
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

            # Delete the report after it's fixed and processed
            await self.manager.update_report_status(self.report_id, "fixed")

            if self.message: # Delete message from BUG_APPROVED_CHANNEL_ID 
                await self.message.delete()

            await interaction.followup.send(f"✅ Bug report `{self.report_id}` marked as fixed and archived.", ephemeral=True)
            self.stop() # Stop the view
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while marking report as fixed: {e}", ephemeral=True)


    @ui.button(label="Declined", style=discord.ButtonStyle.red, custom_id="bug_declined")
    async def declined_button(self, interaction: Interaction, button: ui.Button):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this button.", ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)

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
            if self.report_data.get("original_reporter"):
                archive_embed.add_field(name="Original Reporter", value=f"{self.report_data.get('original_reporter')}", inline=True)
            archive_embed.add_field(name="Reported At", value=self.report_data.get('reportedAt', 'N/A'), inline=True)
            archive_embed.add_field(name="Description", value=self.report_data.get('description', 'N/A'), inline=False)
            reproduce_steps_display = self.report_data.get('reproducesteps', 'N/A').replace('\\n', '\n')
            archive_embed.add_field(name="Steps to Reproduce", value=reproduce_steps_display, inline=False)
            archive_embed.set_footer(
                text=f"Declined by: {interaction.user.display_name} - Bug Report ID: {self.report_id}",
                icon_url=interaction.user.avatar.url if interaction.user.avatar else None
            )
            await archive_channel.send(embed=archive_embed)
            
            await self.manager.update_report_status(self.report_id, "declined")


            if self.message: # Delete message from BUG_APPROVED_CHANNEL_ID 
                await self.message.delete()

            await interaction.followup.send(f"❌ Bug report `{self.report_id}` marked as declined and archived.", ephemeral=True)
            self.stop() # Stop the view
        except Exception as e:
            await interaction.followup.send(f"❌ An error occurred while marking report as declined: {e}", ephemeral=True)


# --- Command Cog ---
class bugreports(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bug_report_manager = BugReportManager(bot)

    async def setup_hook(self) -> None: # For persistent views 
        self.bot.add_view(BugReportApprovalView(self.bot, self.bug_report_manager, 0, {}))
        self.bot.add_view(BugReportActionsView(self.bot, self.bug_report_manager, 0, {}))

    @app_commands.command(
        name="submitbug",
        description="Submit a bug report for review."
    )
    @app_commands.describe(
        severity="How severe is this bug?",
        category="What part of the bot does this bug affect?",
        original_reporter="Optional: The original reporter of the bug if different from you."
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
    # Add a cooldown: 1 use per user per guild every 600 seconds (10 minutes)
    @app_commands.checks.cooldown(1, 180, key=lambda i: (i.guild_id, i.user.id))
    async def submit_bug(self, interaction: Interaction, severity: str, category: str, original_reporter: Optional[str] = None):
        await interaction.response.send_modal(BugReportModal(self.bot, category, severity, self.bug_report_manager, original_reporter))


    @app_commands.command(name="buglist", description="Shows all pending bug reports with pagination and sorting (Admin only).")
    async def bug_list(self, interaction: Interaction):
        await interaction.response.defer(ephemeral=True)
        self.bug_report_manager.reports = await self.bug_report_manager._load_reports()
        view = BugListPaginationView(self.bot, self.bug_report_manager, interaction.user)
        await view.initialize_and_send(interaction)

    @app_commands.command(
        name="dumpstats",
        description="Shows bug report statistics for a specific date (Admin only)."
    )
    @app_commands.describe(
        date="The date to check stats for in YYYY-MM-DD format."
    )
    async def dump_stats(self, interaction: Interaction, date: str):
        """
        Calculates and displays bug report statistics for a given date,
        including total reports and reports per user.
        """
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        if not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        await interaction.response.defer() # Defer without ephemeral=True for a public response later

        try:
            # Validate date format
            datetime.strptime(date, "%Y-%m-%d")

            # Load all reports from the manager (ensures data is fresh)
            all_reports = await self.bug_report_manager._load_reports()

            # Filter reports for the specified date
            daily_reports = [
                report for report in all_reports
                if report.get('reportedAt') == date
            ]

            report_counts = len(daily_reports)
            reporter_counts = defaultdict(int)

            for report in daily_reports:
                reporter_id = report.get('reporterID')
                if reporter_id:
                    reporter_counts[reporter_id] += 1

            # Prepare the embed message
            embed = discord.Embed(
                title="📊 Bug Report Stats",
                color=discord.Color.purple(),
                timestamp=datetime.now(timezone.utc)
            )

            embed.add_field(
                name="\u200b", # Zero width space for spacing
                value=f"On **{date}**, **{report_counts}** bugs were reported.",
                inline=False
            )

            if reporter_counts:
                # Sort reporters by the number of bugs reported (descending)
                sorted_reporters = sorted(reporter_counts.items(), key=lambda item: item[1], reverse=True)
                
                reporter_list_str = []
                for reporter_id, count in sorted_reporters:
                    reporter_list_str.append(f"• <@{reporter_id}> reported **{count}** bugs.")
                
                # Join the list into a string, limiting the display if too many reporters
                display_limit = 10 # You can adjust this number
                if len(reporter_list_str) > display_limit:
                    embed.add_field(
                        name="Top Reporters:",
                        value="\n".join(reporter_list_str[:display_limit]) + f"\n...and more.",
                        inline=False
                    )
                else:
                    embed.add_field(
                        name="Reporters:",
                        value="\n".join(reporter_list_str) if reporter_list_str else "No specific reporters found for this date.",
                        inline=False
                    )
            else:
                embed.add_field(
                    name="Reporters:",
                    value="No bug reports found for this date.",
                    inline=False
                )

            embed.set_footer(text=f"Issued by {interaction.user.display_name}",
                             icon_url=interaction.user.avatar.url if interaction.user.avatar else None)

            # Send the message non-ephemerally
            await interaction.followup.send(embed=embed)

        except ValueError:
            await interaction.followup.send(
                f"❌ Invalid date format. Please use YYYY-MM-DD (e.g., 2023-01-15).",
                ephemeral=True
            )
        except Exception as e:
            await interaction.followup.send(
                f"❌ An error occurred while fetching bug stats: {e}",
                ephemeral=True
            )
            print(f"An error occurred in /dumpstats command: {e}")

    @app_commands.command(
        name="loadreports",
        description="Clears a bug report channel and re-sends all reports of a specific status (Admin only)."
    )
    @app_commands.describe(
        report_type="Select which type of reports to load."
    )
    @app_commands.choices(
        report_type=[
            app_commands.Choice(name="Pending Reports", value="pending"),
            app_commands.Choice(name="Approved Reports", value="approved"),
        ]
    )
    async def load_reports(self, interaction: Interaction, report_type: str):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        if not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this command.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True) # Defer to prevent timeout

        channel_id_env_var = ""
        embed_color = discord.Color.blue() # Default color
        view_class = None # To hold the view class (Approval or Actions)

        if report_type == "pending":
            channel_id_env_var = "BUG_REPORT_CHANNEL_ID"
            embed_color = discord.Color.red()
            view_class = BugReportApprovalView
            status_text = "`PENDING`"
        elif report_type == "approved":
            channel_id_env_var = "BUG_APPROVED_CHANNEL_ID"
            embed_color = discord.Color.green()
            view_class = BugReportActionsView
            status_text = "`APPROVED`"
        else:
            await interaction.followup.send("Invalid report type selected.", ephemeral=True)
            return

        channel_id = os.getenv(channel_id_env_var)
        if not channel_id:
            await interaction.followup.send(f"❌ Error: {channel_id_env_var} not set in environment variables.", ephemeral=True)
            return

        try:
            target_channel = self.bot.get_channel(int(channel_id))
            if not target_channel:
                await interaction.followup.send(f"❌ Error: Could not find the configured channel with ID {channel_id}.", ephemeral=True)
                return

            # Step 1: Clear existing messages in the channel
            await interaction.followup.send(f"🔄 Clearing existing logs in {target_channel.mention}...")
            deleted_count = 0
            # Fetch messages and delete those sent by the bot
            # Using a loop to handle potential large number of messages
            async for message in target_channel.history(limit=None):
                if message.author == self.bot.user: # Only delete messages sent by the bot
                    try:
                        await message.delete()
                        deleted_count += 1
                    except discord.Forbidden:
                        print(f"Error: Bot does not have permissions to delete message {message.id} in {target_channel.name}. Please grant 'Manage Messages'.")
                        await interaction.followup.send(f"❌ Error: Missing permissions to delete messages in {target_channel.mention}. Please grant 'Manage Messages'.", ephemeral=True)
                        return # Exit if permissions are missing
                    except discord.HTTPException as http_exc:
                        print(f"HTTP error deleting message {message.id}: {http_exc}")
                        # Continue or break depending on the severity of the HTTP error
                await asyncio.sleep(1) # Small delay to respect rate limits during bulk deletion

            await interaction.followup.send(f"✅ Cleared {deleted_count} bot messages from {target_channel.mention}.")

            # Step 2: Load all reports of the specified type
            await self.bug_report_manager._load_reports() # Ensure reports are up-to-date from your data source
            reports_to_resend = await self.bug_report_manager.get_filtered_and_sorted_reports(status_filter=report_type)

            if not reports_to_resend:
                await interaction.followup.send(f"ℹ️ No {report_type} reports found to re-send.", ephemeral=True)
                return

            # Step 3: Resend reports to the channel
            sent_count = 0
            for report in reports_to_resend:
                try:
                    embed = discord.Embed(
                        title=f"🚨 Bug Report: {report['title']}" if report_type == "pending" else f"✅ Approved Bug Report: {report['title']}",
                        color=embed_color,
                        timestamp=datetime.strptime(report.get('reportedAt', '1970-01-01'), "%Y-%m-%d") if report.get('reportedAt') else datetime.now(timezone.utc)
                    )
                    embed.set_author(
                        name=f"Reported by {report['reporterID']}",
                        icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None # Using bot's avatar as placeholder
                    )
                    embed.add_field(name="Reporter", value=f"<@{report['reporterID']}> ({report['reporterID']})", inline=False)
                    if report.get("original_reporter"):
                        embed.add_field(name="Original Reporter", value=f"{report['original_reporter']}", inline=False)
                    embed.add_field(name="Category", value=report['category'].capitalize(), inline=True)
                    embed.add_field(name="Severity", value=report['severity'].capitalize(), inline=True)
                    embed.add_field(name="Status", value=status_text, inline=True)
                    embed.add_field(name="Description", value=report['description'], inline=False)
                    # Handle reproduceSteps possibly having '\n' replaced with '\\n' in storage
                    reproduce_steps_display = report.get('reproducesteps', 'N/A').replace('\\n', '\n')
                    embed.add_field(name="Steps to Reproduce", value=reproduce_steps_display, inline=False)
                    embed.set_footer(text=f"Bug Report ID: {report['id']}", icon_url=self.bot.user.avatar.url if self.bot.user.avatar else None)

                    # Create and link the appropriate view
                    if view_class:
                        # Ensure report_data is passed correctly, as views need it for their actions
                        view_instance = view_class(self.bot, self.bug_report_manager, report['id'], report)
                        message = await target_channel.send(embed=embed, view=view_instance)
                        view_instance.message = message 
                        self.bot.add_view(view_instance)
                    else:
                        await target_channel.send(embed=embed) # Fallback if no view is needed (though for pending/approved, views are crucial)

                    sent_count += 1
                    await asyncio.sleep(1) 
                except Exception as e:
                    print(f"Error re-sending report {report.get('id', 'N/A')}: {e}")
                    await interaction.followup.send(f"❌ Error re-sending report ID {report.get('id', 'N/A')}: {e}", ephemeral=True)
                    continue # Continue to next report even if one fails

            await interaction.followup.send(f"✅ Successfully re-sent {sent_count} {report_type} reports to {target_channel.mention}.")

        except ValueError:
            await interaction.followup.send(f"❌ An error occurred: Invalid channel ID for {channel_id_env_var}.", ephemeral=True)
            print(f"Error: Channel ID from {channel_id_env_var} is not a valid integer.")
        except Exception as e:
            await interaction.followup.send(f"❌ An unexpected error occurred: {e}", ephemeral=True)
            print(f"An unexpected error occurred in load_reports command: {e}")

class BugListPaginationView(ui.View):
    def __init__(self, bot: commands.Bot, manager, author: discord.User):
        super().__init__(timeout=300)
        self.bot = bot
        self.manager = manager
        self.author = author
        self.current_page = 0
        self.reports_per_page = 4
        self.current_category_filter = "all"
        self.current_status_filter = "all" # New status filter 
        self.current_sort_by = "id_ascending"

        self.category_options = [
            discord.SelectOption(label="All Categories", value="all"),
            discord.SelectOption(label="Mining", value="mining"),
            discord.SelectOption(label="Foraging", value="foraging"),
            discord.SelectOption(label="Dungeons", value="dungeons"),
            discord.SelectOption(label="Slayers", value="slayers"),
            discord.SelectOption(label="Island", value="island"),
            discord.SelectOption(label="Fishing", value="fishing"),
            discord.SelectOption(label="Others", value="others"),
        ]

        self.status_options = [ # New status options 
            discord.SelectOption(label="Pending", value="pending"),
            discord.SelectOption(label="Approved", value="approved"),
            discord.SelectOption(label="Fixed", value="fixed"),
            discord.SelectOption(label="Declined", value="declined")
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
        for item in list(self.children):
            if isinstance(item, discord.ui.Button) and item.label in ["«", "◀", "▶", "»"]:
                self.remove_item(item)

        # Define and add new buttons with proper callbacks
        first = discord.ui.Button(label="«", style=discord.ButtonStyle.blurple, row=1)
        first.callback = self.first_page_button_callback
        prev = discord.ui.Button(label="◀", style=discord.ButtonStyle.blurple, row=1)
        prev.callback = self.previous_button_callback
        next_btn = discord.ui.Button(label="▶", style=discord.ButtonStyle.blurple, row=1)
        next_btn.callback = self.next_button_callback
        last = discord.ui.Button(label="»", style=discord.ButtonStyle.blurple, row=1)
        last.callback = self.last_page_button_callback

        self.add_item(first)
        self.add_item(prev)
        self.add_item(next_btn)
        self.add_item(last)


    class SortSelect(ui.Select):
        def __init__(self, parent_view):
            # Combine category, status, and sort options for the dropdown 
            options = []
            for opt in parent_view.category_options:
                options.append(discord.SelectOption(label=opt.label, value=opt.value, default=opt.default))
            options.append(discord.SelectOption(label="--- Status ---", value="divider_status"))
            for opt in parent_view.status_options:
                options.append(discord.SelectOption(label=opt.label, value=f"status_{opt.value}", default=opt.default))
            options.append(discord.SelectOption(label="--- Sort By ---", value="divider_sort"))
            for opt in parent_view.sort_options:
                options.append(discord.SelectOption(label=opt.label, value=f"sort_{opt.value}", default=opt.default))


            current_category = parent_view.current_category_filter.capitalize() if parent_view.current_category_filter != "all" else "All"
            current_status = parent_view.current_status_filter.capitalize() if parent_view.current_status_filter != "all" else "All"
            current_sort = parent_view.current_sort_by.replace("_", " ").title()

            placeholder = f"Category: {current_category} | Status: {current_status} | Sort: {current_sort}"
            super().__init__(placeholder=placeholder, options=options, row=0)
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
                    # Also update the actual filter values
                    if selected_value in [o.value for o in self.parent_view.category_options]:
                        self.parent_view.current_category_filter = selected_value
                    elif selected_value.startswith("status_"):
                        self.parent_view.current_status_filter = selected_value.replace("status_", "")
                    elif selected_value.startswith("sort_"):
                        self.parent_view.current_sort_by = selected_value.replace("sort_", "")
                    break

            if selected_value in [opt.value for opt in self.parent_view.category_options]:
                self.parent_view.current_category_filter = selected_value
            elif selected_value.startswith("status_"):
                self.parent_view.current_status_filter = selected_value.replace("status_", "")
            elif selected_value.startswith("sort_"):
                self.parent_view.current_sort_by = selected_value.replace("sort_", "")

            # Re-filter and re-sort reports 
            self.parent_view.reports = await self.parent_view.manager.get_filtered_and_sorted_reports(
                self.parent_view.current_category_filter,
                self.parent_view.current_status_filter,
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
            self.current_status_filter, # Pass status filter 
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
        self.reports = await self.manager.get_filtered_and_sorted_reports(
            self.current_category_filter, 
            self.current_status_filter, # Pass status filter 
            self.current_sort_by
        )
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
                        f"**Status:** {report.get('status', 'N/A').capitalize()}\n" # Display status 
                        f"**Severity:** {report['severity'].capitalize()}\n"
                        f"**Category:** {report['category'].capitalize()}\n"
                        f"**Bug ID:** {report['id']}\n"
                        f"**Reporter:** <@{report['reporterID']}>\n"
                        f"**Reported At:** {report['reportedAt']}\n"
                        f"**Description:** {report['description'][:200]}{'...' if len(report['description']) > 200 else ''}"

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
    cog = bugreports(bot)
    await bot.add_cog(cog)
    await cog.setup_hook()
