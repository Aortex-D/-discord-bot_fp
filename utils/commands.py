import dotenv
import os
from dotenv import load_dotenv
load_dotenv()

# Role IDs
ADMIN_ROLE_ID = 1386648144443609088
BETA_TESTER_ROLE_ID = 1059436991088967770
VERIFIED_ROLE_ID = 1350767423493771354
NONE_ROLE_ID = 0  # fallback/default

ADMINS = {
    1193398190314111117, # .Suspected.
    702511581560307752, # Koban4ik
    335416744212693002, # Danielo
    230718188457951232 # 2pb
}

GROUPS = {
    "admin": ADMIN_ROLE_ID,
    "beta tester": BETA_TESTER_ROLE_ID,
    "verified": VERIFIED_ROLE_ID,
    "none": NONE_ROLE_ID
}

def get_admin_info(user_id: int) -> bool:
    return user_id in ADMINS

def get_group_role_id(input_value: str) -> int:
    return GROUPS.get(input_value.lower(), GROUPS["none"])


# Do not delete this list, it does not affect all the commands, but it does some & used to generate the help command.
COMMANDS_REFERENCE = [
    # setup command
    { "name": "setup", "description": "Opens the main GUI panel.", "group": "admin" },
    # economy commands
    { "name": "balance", "description": "Shows your current balance", "group": "none" },
    { "name": "userstats", "description": "Shows the stats of a specific user.", "group": "beta tester" },
    { "name": "add_points", "description": "Add points to a user.", "group": "admin" },
    { "name": "remove_points", "description": "Remove points from a user.", "group": "admin" },
    { "name": "reset_points", "description": "Reset a user's points.", "group": "admin" },
    # bug reports commands
    { "name": "buglist", "description": "Gets list of all pending bugs", "group": "none" },
    { "name": "submitbug", "description": "Submits a bug ", "group": "none" },
    # misc commands
    { "name": "modify", "description": "Update Beta Tester's Data on the bot", "group": "admin" },
    { "name": "absence", "description": "Give or remove the absence role", "group": "none" },
    { "name": "help", "description": "Shows a list of commands available to you", "group": "none" },
    { "name": "ping", "description": "Check the bot's latency", "group": "none" },
    { "name": "stop", "description": "Stops the bot", "group": "admin" },
    { "name": "update", "description": "Send the update log of bot", "group": "admin" },
]

def list_commands_by_group(group: str) -> list:
    return [cmd for cmd in COMMANDS_REFERENCE if cmd["group"] == group.lower()]
