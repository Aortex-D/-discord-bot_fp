# 🛠️ Beta Tester - Discord Bot

**Author:** \_Suspected\_

---

## 📌 Overview

This project is a custom Discord bot made for the **Fakepixel Beta Tester Discord Server.**  
It's designed to handle bug reporting, offer a reward & shop system for beta tester, and more — all built in a modular and easy-to-manage way.

---

## ✨ What It Can Do

- 🐞 Bug reporting system with auto rewards  
- 💾 Track user's data with MongoDB  
- 🛍️ Buy various items through a simple shop system  
- 🧰 Useful utility and server commands  
- 🧩 Cog-based design to keep things organized  
- 🧪 Persistent storage using MongoDB  

---

## ⚙️ How to Set It Up

### 1. Install Requirements

Make sure Python is installed, then run:

    pip install -r requirements.txt

### 2. Configure Environment Variables

You can use a `.env` file or any secure environment method.

**Required:**

    DISCORD_TOKEN=your_discord_bot_token  
    APPLICATION_ID=your_application_id  
    DATA_MODE=mongo  
    MONGO_URL=your_mongo_connection_url  
    MONGO_DB_NAME=discord_bot

**Optional (for extra features):**

    PURCHASE_CHANNEL_ID=  
    BUG_REPORT_CHANNEL_ID=  
    BUG_ARCHIVE_CHANNEL_ID=  
    BUG_POINT_REWARD_CHANNEL_ID=  
    ABSENCE_ROLE_ID=  
    BT_BLACKLIST_ROLE_ID=  
    BT_ROLE_ID=  
    UPDATE_LOG_CHANNEL_ID=  
    MEM_BOT_LOG_CHANNEL_ID=

### 3. Run the Bot

    python main.py

---

## 🌐 Keep the Bot Online 24/7

Use [UptimeRobot](https://uptimerobot.com) to ping your webserver URL regularly and keep the bot running.

---

## 📂 Project Structure

    main.py  
    requirements.txt  
    .env  
    /cogs  
      ├── bugreports.py  
      ├── economy.py  
      ├── misc.py  
      ├── shop.py  
    /utils  
      ├── loader.py  
      ├── commands.py

---

## 👤 Credits

Made by \_Suspected\_  
Specially built for the **Fakepixel Beta Tester Discord Server**

---

## 📄 License

This bot is not open-source.
