# ============================================================
# U7BUY MARKETPLACE MIDDLEMAN TICKET BOT
# ============================================================

import os
import re
import asyncio
import discord

from discord.ext import commands
from discord.ui import Modal, TextInput, View, button
from discord import ButtonStyle
from pathlib import Path

ASSET_DIR = Path(__file__).resolve().parent
BANNER_FILE = ASSET_DIR / "u7buy_banner.png"
ICON_FILE = ASSET_DIR / "u7buy_icon.webp"


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

MIDDLEMAN_ROLE_ID = int(
    os.getenv("MIDDLEMAN_ROLE_ID", "1558800992626020444")
)

OWNER_ROLE_ID = int(
    os.getenv("OWNER_ROLE_ID", "1556390123203989644")
)

TICKET_CATEGORY_ID = int(
    os.getenv("TICKET_CATEGORY_ID", "1558794011911782490")
)

# GOLDEN ORANGE EMBED COLOR
EMBED_COLOR = discord.Color.from_rgb(255, 103, 47)


# ============================================================
# BANNERS / ICON
# ============================================================

PANEL_BANNER_URL = None  # Banner attached from local U7BUY image

TICKET_BANNER_URL = None  # Banner attached from local U7BUY image

PANEL_ICON_URL = None  # Logo attached from local U7BUY image


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")


# ============================================================
# BOT
# ============================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(
    command_prefix="$",
    intents=intents,
    help_command=None
)

tickets = {}


# ============================================================
# HELPERS
# ============================================================

def get_middleman_role(guild: discord.Guild):
    return guild.get_role(MIDDLEMAN_ROLE_ID) if MIDDLEMAN_ROLE_ID else None


def get_owner_role(guild: discord.Guild):
    return guild.get_role(OWNER_ROLE_ID) if OWNER_ROLE_ID else None


def is_middleman(member: discord.Member):
    role = get_middleman_role(member.guild)
    return role in member.roles if role else False


def is_owner(member: discord.Member):
    role = get_owner_role(member.guild)
    return role in member.roles if role else False


def clean_channel_name(name: str):
