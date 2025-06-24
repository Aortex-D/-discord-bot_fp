import discord
from discord.ext import commands, tasks
from discord import app_commands, Interaction, Embed
import os
import asyncio
from dotenv import load_dotenv
from utils.loader import load_data, save_data
from datetime import datetime, timezone
from utils.commands import GROUPS, COMMANDS_REFERENCE, get_admin_info


ABSENCE_ROLE_ID = int(os.getenv("ABSENCE_ROLE_ID"))


EMBED_CONTENTS = {
    "updatelog": {
        "title": "📢 New Bot Update!",
        "color": discord.Color.orange(),
        "description": ("\n"
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
                        "Big thanks to the testers who helped in testing the bot! Your feedback was super valuable, really pushing the bot forward. We couldn't have done it without you all. ❤"),
        "image_url": "https://drive.usercontent.google.com/download?id=10Rv5O9724GpyZIo5J264Wmc_JDumyi3Q&export=view&authuser=0"
    },
    "welcomemsg": {
        "title": "👋 Welcome to Beta Testers Server!",
        "color": discord.Color.orange(),
        "description": (
                        "Congratulations on becoming a Beta Tester for Fakepixel! As part of the testing team, your task is to help identify bugs, verify reports, and contribute to improving the server. Your participation will support the development process as we work towards creating a stable and polished gameplay experience.\n"
                        "\n"
                        "**🛠 What’s your role here?**\n"
                        "- Report bugs using the /submitbug command whenever you discover an issue.\n"
                        "- Verify bug reports by regularly checking the forum’s bug report section. Review those reports, mark them as verified or unverified, and ensure they are logged properly on behalf of the original reporters.\n"
                        "- Stay active — your activity is monitored to ensure a helpful tester community.\n"
                        "- Earn rewards for every valid bug report or verified forum report. Points can be redeemed for rewards in the shop.\n"
                        "- Inactivity may lead to removal of your tester role.\n"
                        "\n"
                        "**❓ Didn’t receive your roles yet?**\n"
                        "- 🔹 Roles are issued automatically by our system. It may take up to 5 minutes for your role to be issued.\n"
                        "- 🔹 After your application is approved, the administrator who sent you this server’s invite will mark you as verified in our database.\n"
                        "- 🔹 If you believe there’s a delay, please reach out to the administrator who invited you for verification assistance.\n"
                        "\n"
                        "⚡ Let’s work together to make Fakepixel Skyblock the best experience possible!"
        ),
        "image_url": None
    }
}

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

    @app_commands.command(name="sendembed", description="Sends a pre-defined embed message to a channel.")
    @app_commands.describe(embed_type="Choose the type of embed to send",
                           channel="The channel to send the embed to (defaults to update log channel)")
    @app_commands.choices(embed_type=[
        app_commands.Choice(name="Update Log", value="updatelog"),
        app_commands.Choice(name="Welcome Message", value="welcomemsg"),
        # Add choices for any new embed types you add to EMBED_CONTENTS
        # app_commands.Choice(name="Another Embed", value="anotherembed")
    ])
    async def sendembed(self, interaction: discord.Interaction, embed_type: app_commands.Choice[str], channel: discord.TextChannel):
        is_hardcoded_admin = get_admin_info(interaction.user.id)
        member = interaction.guild.get_member(interaction.user.id)
        if not member or not is_hardcoded_admin:
            await interaction.response.send_message("❌ You don't have permission to use this.", ephemeral=True)
            return

        # Get embed data from the dictionary
        embed_info = EMBED_CONTENTS.get(embed_type.value)

        if not embed_info:
            await interaction.response.send_message(f"❌ Embed type `{embed_type.value}` not found.", ephemeral=True)
            return

    # Determine the target channel
        target_channel = channel

        # Prepare embed
        embed = discord.Embed(
            title=embed_info.get("title", "No Title"),
            description=embed_info.get("description", "No description provided."),
            timestamp=datetime.utcnow(),
            color=embed_info.get("color", discord.Color.default())
        )

        if embed_info.get("image_url"):
            embed.set_image(url=embed_info["image_url"])
        footer_user_id = 1193398190314111117
        footer_user = await self.bot.fetch_user(footer_user_id)
        footer_icon_url = footer_user.avatar.url if footer_user.avatar else footer_user.default_avatar.url
        embed.set_footer(text=f"Made by .Suspected.", icon_url=footer_icon_url)
        
        # Send to the target channel
        if target_channel:
            try:
                await target_channel.send(embed=embed)
                await interaction.response.send_message(f"✅ `{embed_type.name}` sent successfully to {target_channel.mention}.", ephemeral=True)
            except discord.Forbidden:
                await interaction.response.send_message(f"❌ I don't have permissions to send messages in {target_channel.mention}.", ephemeral=True)
            except Exception as e:
                await interaction.response.send_message(f"❌ An error occurred while sending the embed: ```{e}```", ephemeral=True)
        else:
            await interaction.response.send_message("⚠️ Could not determine a channel to send the embed.", ephemeral=True)


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

        # Make a copy for updates
        new_data = data.copy()

        for user_id, info in data.items():
            member = guild.get_member(int(user_id))  # Check cache first

            if member is None:
                try:
                    member = await guild.fetch_member(int(user_id))
                    await asyncio.sleep(1)  # Sleep after API hit
                except discord.HTTPException as e:
                    continue

            status = info.get("status")

            try:
                if status == "verified" and verified_role and verified_role not in member.roles:
                    await member.add_roles(verified_role, reason="Auto-verified from DB")
                    updated = True
                    if log_channel:
                        await log_channel.send(embed=Embed(
                            title="ROLE UPDATE:",
                            description=f"Gave verified role to <@{user_id}>",
                            color=discord.Color.green()))

                elif status == "blacklist" and blacklist_role and blacklist_role not in member.roles:
                    await member.add_roles(blacklist_role, reason="Auto-blacklisted from DB")
                    updated = True
                    if log_channel:
                        await log_channel.send(embed=Embed(
                            title="ROLE UPDATE:",
                            description=f"Gave blacklist role to <@{user_id}>",
                            color=discord.Color.red()))

                elif status == "unverified":
                    await member.kick(reason="Marked as unverified")
                    del new_data[user_id]
                    updated = True
                    if log_channel:
                        await log_channel.send(embed=Embed(
                            title="ROLE UPDATE:",
                            description=f"Kicked unverified user <@{user_id}>",
                            color=discord.Color.dark_gray()))
            except discord.Forbidden:
                print(f"[WARN] Missing permissions to modify {user_id}")
                continue

            await asyncio.sleep(1)  # Space out actions to reduce risk of rate limit

        if updated:
            try:
                save_data("btdb", [{"id": k, **v} for k, v in new_data.items()])
            except Exception as e:
                print(f"[ERROR] Failed to save btdb: {e}")

    @bt_listener.before_loop
    async def before_bt_listener(self):
        await self.bot.wait_until_ready()


async def setup(bot):
    await bot.add_cog(misc(bot))
