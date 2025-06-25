import discord
from dotenv import load_dotenv
from discord.ext import commands
import os
from flask import Flask
from threading import Thread
from discord import Interaction
import asyncio
from utils.loader import _initialize_mongo_connection, close_mongo_connection, load_data, save_data

app = Flask('')


@app.route('/', methods=['GET', 'HEAD'])
def home():
    print("⚡ Ping received on / route")
    return "This is a keep-alive server.", 200


def run():
    app.run(host='0.0.0.0', port=8080)


def keep_alive():
    t = Thread(target=run)
    t.start()
    print("Keep-alive server is running.")


load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
keep_alive()
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="/", intents=intents)


# --- Async Wrappers for loader functions (can be defined here or in a common utils file) ---
async def async_load_data(name: str):
    return await asyncio.to_thread(load_data, name)


async def async_save_data(name: str, data):
    await asyncio.to_thread(save_data, name, data)


# --- End Async Wrappers ---


@bot.event
async def on_ready():
    print("Connecting to MongoDB and setting up cogs...")
    try:
        _initialize_mongo_connection()
    except Exception as e:
        print(f"CRITICAL ERROR: Failed to connect to MongoDB on startup: {e}")
        await bot.close()
        return

    from cogs.shop import MainGUIButtons
    bot.add_view(MainGUIButtons(bot))
    activity = discord.Game(name="Beta Testers 👀")
    await bot.change_presence(status=discord.Status.dnd, activity=activity)
    print(f"🌐 Logged in as {bot.user} (ID: {bot.user.id})\n")

    # Loading cogs
    for cog_name in ['economy', 'shop', 'bugreports', 'misc']:
        try:
            await bot.load_extension(f'cogs.{cog_name}')
            print(f"✅ Loaded cogs.{cog_name}")
        except Exception as e:
            print(f"❌ Failed to load cogs.{cog_name}: {e}")

    # Now sync commands
    try:
        synced = await bot.tree.sync()
        print(f"✅ Synced {len(synced)} command(s) from main on_ready.\n")
    except Exception as e:
        print(f"❌ Failed to sync commands from main on_ready: {e}\n")
    names = ", ".join(f"/{cmd.name}" for cmd in synced)
    print(f"🔗 Synced: {names}")
    update_log_channel_id = os.getenv("UPDATE_LOG_CHANNEL_ID")
    if update_log_channel_id:
        try:
            update_channel = bot.get_channel(int(update_log_channel_id))
            if update_channel:
                embed = discord.Embed(
                    title="🚀 Bot has been updated",
                    description="**Changes**\n- Updated /modify -> Now deletes data from db once user is kicked.",
                    color=discord.Color.green()
                )
                embed.set_footer(text=f"Updated by _Suspected_")
                embed.timestamp = discord.utils.utcnow()
                await update_channel.send(embed=embed)
        except Exception as e:
            print(f"❌ Failed to send startup message: {e}")

@bot.event
async def on_disconnect():
    print("Bot disconnected. Attempting to close MongoDB connection...")
    close_mongo_connection()  # Close connection on disconnect


bot.run(TOKEN)
