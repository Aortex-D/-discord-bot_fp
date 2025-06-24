import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, Embed
import os
from dotenv import load_dotenv
from utils.loader import load_data, save_data
from datetime import datetime, timezone
from utils.commands import GROUPS, COMMANDS_REFERENCE, get_admin_info


ABSENCE_ROLE_ID = int(os.getenv("ABSENCE_ROLE_ID"))


class CogReloadSelect(discord.ui.Select):

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        options = [
            discord.SelectOption(label="economy", value="cogs.economy"),
            discord.SelectOption(label="shop", value="cogs.shop"),
            discord.SelectOption(label="bugreports", value="cogs.bugreports"),
            discord.SelectOption(label="misc", value="cogs.misc"),
        ]
        super().__init__(placeholder="Select a cog to reload",
                         options=options,
                         min_values=1,
                         max_values=1)

    async def callback(self, interaction: discord.Interaction):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
            return
         

        selected_cog = self.values[0]
        try:
            await self.bot.reload_extension(selected_cog)
            await interaction.response.edit_message(
                content=f"✅ Reloaded `{selected_cog}` successfully.",
                view=None)
        except Exception as e:
            await interaction.response.edit_message(
                content=f"❌ Failed to reload `{selected_cog}`:\n```{e}```",
                view=None)


class CogReloadView(discord.ui.View):

    def __init__(self, bot):
        super().__init__(timeout=60)
        self.add_item(CogReloadSelect(bot))


class misc(commands.Cog):

    def __init__(self, bot):
        self.bot = bot
        self.bt_listener.start()

    @app_commands.command(name="reload", description="Reload a specific cog.")
    async def reload_command(self, interaction: Interaction):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
            return
         

        await interaction.response.send_message(
            content="Please select a cog to reload:",
            view=CogReloadView(self.bot),
            ephemeral=False)

    @app_commands.command(name="ping", description="Check the bot's latency")
    async def ping(self, interaction: Interaction):
        latency = round(self.bot.latency * 1000)
        await interaction.response.send_message(
            f"🏓 Pong! Latency is `{latency}ms`", ephemeral=True)

    @app_commands.command(name="update", description="Updates the bot")
    async def update(self, interaction: discord.Interaction):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
            return
         

        # ✅ Prepare embed
        embed = discord.Embed(title="📢 New Bot Update!",
                              timestamp=datetime.datetime.utcnow(),
                              color=discord.Color.orange())

        upd_txt = ("\n"
                   "**New features:**\n"
                   "- Added Shop!\n"
                   "- Upated Bug Report Command\n"
                   "- Added a new command /buglist\n"
                   "- Added a new /absence command\n"
                   "- Added new misc cmds: /ping, /help \n"
                   "- Added graphics on few commands.\n"
                   "- Added points logging channel.\n"
                   "- Updated /userstats. (Now everyone can use it! + few changes)\n"
                   "- Added update logger.\n"
                   "- Optimized code for better performance\n"
                   "\n"
                   "**Bug Fixes:**\n"
                   "- Fixed issue with shop gui.\n"
                   "- Fixed issue with /submitbug command.\n"
                   "- Fixed issue with /buglist command.\n"
                   "- Fixed issue with /absence command.\n"
                   "- Fixed issue with /help command.\n"
                   "- Fixed issue with shop gui. 2.0\n"
                   "- Added desc cap in /buglist command.\n"
                   "- Added realtime user data loader.\n"
                   "\n"
                   "**NOTE**\n"
                   "Big thanks to the testers who helped in testing the bot! Your feedback was super valuable, really pushing the bot forward. We couldn't have done it without you all. ❤"
                )
        
        "Rewards"

        embed.add_field(name="\u200b", value=upd_txt, inline=False)
        embed.set_image(
            url=
            "https://drive.usercontent.google.com/download?id=10Rv5O9724GpyZIo5J264Wmc_JDumyi3Q&export=view&authuser=0"
        )
        embed.set_footer(text=f"Updated by: {interaction.user.display_name}",
                         icon_url=interaction.user.avatar.url
                         if interaction.user.avatar else None)

        # ✅ Send to update log channel
        channel_id = int(os.getenv("UPDATE_LOG_CHANNEL_ID"))
        channel = self.bot.get_channel(channel_id)
        if channel:
            await channel.send(embed=embed)
            await interaction.response.send_message(
                "✅ Update log sent successfully.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "⚠️ Could not find the update log channel.")

    @app_commands.command(name="absence",
                          description="Give or remove the absence role")
    @app_commands.describe(option="Choose to get or remove the absence role")
    @app_commands.choices(option=[
        app_commands.Choice(name="Gives you the absence role", value="get"),
        app_commands.Choice(name="Removes the absence role from you",
                            value="remove")
    ])
    async def absence(self, interaction: Interaction,
                      option: app_commands.Choice[str]):
        role = interaction.guild.get_role(ABSENCE_ROLE_ID)
        if not role:
            await interaction.response.send_message(
                "❌ Absence role not found.", ephemeral=True)
            return

        member = interaction.user

        if option.value == "get":
            if role in member.roles:
                await interaction.response.send_message(
                    "⚠️ You already have the absence role.", ephemeral=True)
            else:
                await member.add_roles(role,
                                       reason="User requested absence role.")
                await interaction.response.send_message(
                    "✅ Absence role has been given.", ephemeral=True)

        elif option.value == "remove":
            if role not in member.roles:
                await interaction.response.send_message(
                    "⚠️ You don't have the absence role.", ephemeral=True)
            else:
                await member.remove_roles(role,
                                          reason="User removed absence role.")
                await interaction.response.send_message(
                    "✅ Absence role has been removed.", ephemeral=True)

    @app_commands.command(
        name="help", description="Shows a list of commands available to you")
    async def help(self, interaction: Interaction):
        user_role_ids = [role.id for role in interaction.user.roles]

        # Filter commands based on user's role access
        visible_commands = []
        for cmd in COMMANDS_REFERENCE:
            required_role_id = GROUPS.get(cmd["group"].lower())
            if required_role_id in user_role_ids or required_role_id == GROUPS[
                    "none"]:
                visible_commands.append(
                    f"• **/{cmd['name']}** — {cmd['description']}")

        if not visible_commands:
            await interaction.response.send_message(
                "You don’t have access to any commands.", ephemeral=True)
            return

        help_text = "**Available Commands:**\n\n" + "\n".join(visible_commands)
        await interaction.response.send_message(help_text, ephemeral=True)


    @app_commands.command(
        name="modify",
        description="Modify a user by ID (verified / blacklist / unverified)")
    @app_commands.describe(user_id="The Discord ID of the user",
                           status="The action to perform")
    @app_commands.choices(status=[
        app_commands.Choice(name="verified", value="verified"),
        app_commands.Choice(name="blacklist", value="blacklist"),
        app_commands.Choice(name="unverified", value="unverified")
    ])
    async def modify_slash(self, interaction: Interaction, user_id: str,
                           status: app_commands.Choice[str]):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
            return
         

        status_value = status.value

        # Load current btdb
        data_list = load_data("btdb")
        data = {entry["id"]: entry for entry in data_list}

        # Modify the entry
        data[user_id] = {"id": user_id, "status": status_value}

        # Save updated data
        save_data("btdb", list(data.values()))

        await interaction.response.send_message(
            f"✅ `{user_id}` marked as `{status_value}`.", ephemeral=True)

        # Send log to log channel
        log_channel_id = int(os.getenv("MEM_BOT_LOG_CHANNEL_ID"))
        channel = self.bot.get_channel(log_channel_id)
        if channel:
            embed = Embed(title="ROLE UPDATE:",
                          description="No change has been made.",
                          color=discord.Color.orange())
            await channel.send(embed=embed)

    @tasks.loop(seconds=5)
    async def bt_listener(self):
        guild = discord.utils.get(self.bot.guilds)
        if not guild:
            return

        data_list = load_data("btdb")
        data = {entry["id"]: entry for entry in data_list}

        updated = False
        log_channel_id = int(os.getenv("MEM_BOT_LOG_CHANNEL_ID"))
        log_channel = self.bot.get_channel(log_channel_id)

        verified_role = guild.get_role(int(os.getenv("BT_ROLE_ID")))
        blacklist_role = guild.get_role(int(os.getenv("BT_BLACKLIST_ROLE_ID")))

        new_data = data.copy()

        for user_id, info in data.items():
            try:
                member = await guild.fetch_member(int(user_id))
            except:
                continue

            status = info.get("status")

            if status == "verified" and verified_role and verified_role not in member.roles:
                await member.add_roles(verified_role,
                                       reason="Auto-verified from DB")
                updated = True
                if log_channel:
                    await log_channel.send(embed=Embed(
                        title="ROLE UPDATE:",
                        description=f"Gave verified role to <@{user_id}>",
                        color=discord.Color.green()))

            elif status == "blacklist" and blacklist_role and blacklist_role not in member.roles:
                await member.add_roles(blacklist_role,
                                       reason="Auto-blacklisted from DB")
                updated = True
                if log_channel:
                    await log_channel.send(embed=Embed(
                        title="ROLE UPDATE:",
                        description=f"Gave blacklist role to <@{user_id}>",
                        color=discord.Color.red()))

            elif status == "unverified":
                try:
                    await member.kick(reason="Marked as unverified")
                    del new_data[user_id]
                    updated = True
                    if log_channel:
                        await log_channel.send(embed=Embed(
                            title="ROLE UPDATE:",
                            description=f"Kicked unverified user <@{user_id}>",
                            color=discord.Color.dark_gray()))
                except discord.Forbidden:
                    continue

        if updated:
            await save_data("btdb", [{
                "id": k,
                **v
            } for k, v in new_data.items()])

    @bt_listener.before_loop
    async def before_bt_listener(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(misc(bot))
