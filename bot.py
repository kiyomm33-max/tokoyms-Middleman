# ============================================================
# 🌸 TOKYOMS MIDDLEMAN TICKET BOT
# ============================================================

import os
import re
import json
import asyncio
import discord

from discord.ext import commands
from discord.ui import Modal, TextInput, View, button
from discord import ButtonStyle


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

MIDDLEMAN_ROLE_ID = int(os.getenv("MIDDLEMAN_ROLE_ID", "1557255996647153714"))
OWNER_ROLE_ID = int(os.getenv("OWNER_ROLE_ID", "1556390123203989644"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "1557256486176952351"))

# Persistent ticket file.
# This is a backup, but ticket information is ALSO stored in
# the Discord channel topic so the claim system can recover
# even when the bot restarts.
TICKET_FILE = "tickets.json"

# TokyoMs images supplied for the server.
PANEL_BANNER_URL = (
    "https://media.discordapp.net/attachments/1551900302146281554/"
    "1557109839681953904/TMS_banner.gif?backend=b2&ex=6ac69b0b&"
    "is=6ab5498b&hm=2ba841228ebf004e747f0687006b4cefe0991bbf9091156599a2030725e31951&"
    "=&width=894&height=503"
)

TICKET_BANNER_URL = PANEL_BANNER_URL

PANEL_ICON_URL = (
    "https://media.discordapp.net/attachments/1551900302146281554/"
    "1557100302146281554/TMS.gif"
)

# Use the exact thumbnail URL from your server if needed.
# If the URL above stops working because Discord changes its CDN URL,
# replace it with your current TMS.gif attachment URL.

PINK = discord.Color.from_rgb(255, 182, 193)


# ============================================================
# TOKEN CHECK
# ============================================================

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set.")


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


# ============================================================
# IN-MEMORY + PERSISTENT STORAGE
# ============================================================

tickets = {}


def load_tickets():
    global tickets

    try:
        if os.path.exists(TICKET_FILE):
            with open(TICKET_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)

            tickets = {
                int(channel_id): data
                for channel_id, data in raw.items()
            }

    except (json.JSONDecodeError, OSError, ValueError):
        tickets = {}


def save_tickets():
    try:
        with open(TICKET_FILE, "w", encoding="utf-8") as f:
            json.dump(
                {str(k): v for k, v in tickets.items()},
                f,
                indent=4
            )
    except OSError as e:
        print(f"[TICKETS] Could not save tickets.json: {e}")


load_tickets()


# ============================================================
# ROLE HELPERS
# ============================================================

def get_middleman_role(guild: discord.Guild):
    return guild.get_role(MIDDLEMAN_ROLE_ID) if MIDDLEMAN_ROLE_ID else None


def get_owner_role(guild: discord.Guild):
    return guild.get_role(OWNER_ROLE_ID) if OWNER_ROLE_ID else None


def is_middleman(member: discord.Member):
    role = get_middleman_role(member.guild)
    return role is not None and role in member.roles


def is_owner(member: discord.Member):
    role = get_owner_role(member.guild)
    return role is not None and role in member.roles


# ============================================================
# GENERAL HELPERS
# ============================================================

def clean_channel_name(name: str):
    name = name.lower()
    name = re.sub(r"[^a-z0-9-]", "-", name)
    name = re.sub(r"-+", "-", name)
    return name[:90].strip("-") or "middleman-ticket"


async def find_user(guild: discord.Guild, value: str):
    value = value.strip()

    match = re.fullmatch(r"<@!?(\d+)>", value)

    if match:
        user_id = int(match.group(1))

    elif value.isdigit():
        user_id = int(value)

    else:
        member = discord.utils.find(
            lambda m:
                m.name.lower() == value.lower()
                or m.display_name.lower() == value.lower(),
            guild.members
        )

        return member

    try:
        return guild.get_member(user_id) or await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None


# ============================================================
# TICKET TOPIC STORAGE
# ============================================================
# The channel topic contains the ticket data.
#
# Example:
# tmsticket|owner=123|trader=456|game=Murder Mystery 2|claimed=0
#
# This is the IMPORTANT fix for:
# "Ticket data was not found."
# ============================================================

def make_ticket_topic(ticket):
    game = str(ticket.get("game", "Others")).replace("|", "")
    return (
        f"tmsticket|"
        f"owner={ticket.get('owner', 0)}|"
        f"trader={ticket.get('trader', 0)}|"
        f"game={game}|"
        f"claimed={ticket.get('claimed_by') or 0}"
    )


def parse_ticket_topic(topic):
    if not topic or not topic.startswith("tmsticket|"):
        return None

    parts = topic.split("|")
    data = {}

    for part in parts[1:]:
        if "=" not in part:
            continue

        key, value = part.split("=", 1)
        data[key] = value

    try:
        owner = int(data.get("owner", "0"))
        trader = int(data.get("trader", "0"))
        claimed = int(data.get("claimed", "0"))
    except ValueError:
        return None

    if not owner or not trader:
        return None

    return {
        "owner": owner,
        "trader": trader,
        "game": data.get("game", "Others"),
        "claimed_by": claimed or None,
        "giving": "",
        "trader_giving": "",
        "private_links": ""
    }


def get_ticket(channel: discord.abc.GuildChannel):
    """
    Get ticket data from memory first.

    If it isn't in memory, recover it from the channel topic.
    This fixes the claim button when the temporary dictionary
    does not contain the channel ID.
    """

    if channel.id in tickets:
        return tickets[channel.id]

    recovered = parse_ticket_topic(getattr(channel, "topic", ""))

    if recovered:
        tickets[channel.id] = recovered
        save_tickets()
        return recovered

    return None


async def save_ticket_to_channel(channel, ticket):
    try:
        await channel.edit(
            topic=make_ticket_topic(ticket),
            reason="Update middleman ticket data"
        )
    except discord.Forbidden:
        print(f"[TICKETS] Missing permission to edit topic in #{channel.name}")
    except discord.HTTPException as e:
        print(f"[TICKETS] Could not update topic: {e}")


# ============================================================
# MIDDLEMAN REQUEST MODAL
# ============================================================

class MiddlemanRequestModal(Modal):

    def __init__(self, selected_game: str):
        super().__init__(title=f"{selected_game} Middleman Request")

        self.selected_game = selected_game

        self.trader_input = TextInput(
            label="Trader Username / User ID",
            placeholder="Enter trader username or ID",
            required=True,
            max_length=100
        )

        self.giving_input = TextInput(
            label="What Are You Giving?",
            placeholder="Enter what you are giving",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )

        self.trader_giving_input = TextInput(
            label="What Is Your Trader Giving?",
            placeholder="Enter what your trader is giving",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )

        self.private_input = TextInput(
            label="Can You Join Private Server Links?",
            placeholder="Yes or No",
            required=True,
            max_length=20
        )

        self.add_item(self.trader_input)
        self.add_item(self.giving_input)
        self.add_item(self.trader_giving_input)
        self.add_item(self.private_input)

    async def on_submit(self, interaction: discord.Interaction):

        guild = interaction.guild

        if guild is None:
            await interaction.response.send_message(
                "❌ This can only be used inside a server.",
                ephemeral=True
            )
            return

        trader = await find_user(
            guild,
            self.trader_input.value
        )

        if not trader:
            await interaction.response.send_message(
                "❌ I couldn't find that user. Please use their Discord ID or mention.",
                ephemeral=True
            )
            return

        if trader.id == interaction.user.id:
            await interaction.response.send_message(
                "❌ You can't use yourself as the other trader.",
                ephemeral=True
            )
            return

        category = None

        if TICKET_CATEGORY_ID:
            possible_category = guild.get_channel(TICKET_CATEGORY_ID)

            if isinstance(possible_category, discord.CategoryChannel):
                category = possible_category

        mm_role = get_middleman_role(guild)
        owner_role = get_owner_role(guild)

        overwrites = {
            guild.default_role: discord.PermissionOverwrite(
                view_channel=False
            ),

            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            ),

            trader: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )
        }

        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )

        if owner_role:
            overwrites[owner_role] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )

        channel_name = clean_channel_name(
            f"{self.selected_game}-{interaction.user.name}"
        )

        # Build the ticket before creating the channel.
        ticket = {
            "owner": interaction.user.id,
            "trader": trader.id,
            "game": self.selected_game,
            "giving": self.giving_input.value,
            "trader_giving": self.trader_giving_input.value,
            "private_links": self.private_input.value,
            "claimed_by": None
        }

        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                topic=make_ticket_topic(ticket),
                reason="TokyoMs middleman ticket created"
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to create ticket channels.",
                ephemeral=True
            )
            return

        except discord.HTTPException as e:
            await interaction.response.send_message(
                f"❌ Discord failed to create the ticket.\n`{e}`",
                ephemeral=True
            )
            return

        # Save under the EXACT channel ID Discord returned.
        tickets[channel.id] = ticket
        save_tickets()

        await interaction.response.send_message(
            f"🌸 Your **{self.selected_game}** middleman ticket has been created: {channel.mention}",
            ephemeral=True
        )

        welcome = discord.Embed(
            title="🌸 Welcome to your Ticket!",
            description=(
                f"Hello {interaction.user.mention}, thanks for opening a "
                "**TokyoMs Middleman Service Ticket!**\n\n"
                f"**Game:** {self.selected_game}\n\n"
                "A middleman will assist you shortly.\n"
                "Provide all trade details clearly.\n"
                "Fake/troll tickets may result in consequences."
            ),
            color=PINK
        )

        if TICKET_BANNER_URL:
            welcome.set_image(url=TICKET_BANNER_URL)

        welcome.set_footer(
            text="🌸 TokyoMs • Please wait for a middleman"
        )

        details = discord.Embed(
            title="🌸 Trade Details",
            color=PINK
        )

        details.add_field(
            name="Game",
            value=self.selected_game,
            inline=False
        )

        details.add_field(
            name="What Are You Giving?",
            value=self.giving_input.value,
            inline=False
        )

        details.add_field(
            name="What Is Your Trader Giving?",
            value=self.trader_giving_input.value,
            inline=False
        )

        details.add_field(
            name="Trader",
            value=f"{trader.mention}\n`{trader.id}`",
            inline=False
        )

        details.add_field(
            name="Can Join Private Server Links?",
            value=self.private_input.value,
            inline=False
        )

        details.set_footer(text="🌸 TokyoMs Middleman Service")

        ping_message = (
            f"{interaction.user.mention} {trader.mention}"
        )

        if mm_role:
            ping_message += f" {mm_role.mention}"

        try:
            await channel.send(
                content=ping_message,
                embeds=[welcome, details],
                view=TicketView()
            )
        except discord.HTTPException as e:
            print(f"[TICKET] Could not send ticket message: {e}")


# ============================================================
# GAME SELECT
# ============================================================

class GameSelect(discord.ui.Select):

    def __init__(self):

        options = [
            discord.SelectOption(
                label="Murder Mystery 2",
                emoji="🔪",
                value="Murder Mystery 2"
            ),
            discord.SelectOption(
                label="Blox Fruits",
                emoji="🍎",
                value="Blox Fruits"
            ),
            discord.SelectOption(
                label="Adopt Me",
                emoji="🐶",
                value="Adopt Me"
            ),
            discord.SelectOption(
                label="Steal a Brainrot",
                emoji="🧠",
                value="Steal a Brainrot"
            ),
            discord.SelectOption(
                label="Grow A Garden",
                emoji="🌱",
                value="Grow A Garden"
            ),
            discord.SelectOption(
                label="Blade Ball",
                emoji="⚔️",
                value="Blade Ball"
            ),
            discord.SelectOption(
                label="Others",
                emoji="📝",
                value="Others"
            )
        ]

        super().__init__(
            placeholder="Select a game...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="tokyoms_game_selection"
        )

    async def callback(self, interaction: discord.Interaction):

        await interaction.response.send_modal(
            MiddlemanRequestModal(self.values[0])
        )


# ============================================================
# PANEL VIEW
# ============================================================

class TicketPanelView(View):

    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GameSelect())


# ============================================================
# ADD USER MODAL
# ============================================================

class AddUserModal(Modal):

    def __init__(self, channel):
        super().__init__(title="Add User")
        self.channel = channel

        self.user_input = TextInput(
            label="User ID / Username",
            placeholder="eg: 1234567890",
            required=True,
            max_length=100
        )

        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):

        if not is_middleman(interaction.user):
            await interaction.response.send_message(
                "❌ Only a middleman can add users to this ticket.",
                ephemeral=True
            )
            return

        ticket = get_ticket(self.channel)

        if not ticket:
            await interaction.response.send_message(
                "❌ Ticket data was not found.",
                ephemeral=True
            )
            return

        if ticket.get("claimed_by"):
            if ticket["claimed_by"] != interaction.user.id:
                await interaction.response.send_message(
                    "❌ Only the middleman who claimed this ticket can add users.",
                    ephemeral=True
                )
                return

        user = await find_user(
            interaction.guild,
            self.user_input.value
        )

        if not user:
            await interaction.response.send_message(
                "❌ User not found.",
                ephemeral=True
            )
            return

        try:
            await self.channel.set_permissions(
                user,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True
            )

            await interaction.response.send_message(
                f"🌸 Added {user.mention} to the ticket.",
                ephemeral=True
            )

            await self.channel.send(
                f"🌸 {user.mention} was added by {interaction.user.mention}."
            )

        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I don't have permission to add that user.",
                ephemeral=True
            )


# ============================================================
# TICKET VIEW
# ============================================================

class TicketView(View):

    def __init__(self):
        super().__init__(timeout=None)

    # --------------------------------------------------------
    # CLAIM
    # --------------------------------------------------------

    @button(
        label="Claim Ticket",
        emoji="✅",
        style=ButtonStyle.success,
        custom_id="tokyoms_claim_ticket"
    )
    async def claim_ticket(self, interaction, button):

        if not is_middleman(interaction.user):
            await interaction.response.send_message(
                "❌ Only a middleman can claim this ticket.",
                ephemeral=True
            )
            return

        channel = interaction.channel

        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "❌ This button can only be used in a ticket channel.",
                ephemeral=True
            )
            return

        # IMPORTANT FIX:
        # Recover ticket data from the channel topic if it is not
        # present in the in-memory dictionary.
        ticket = get_ticket(channel)

        if not ticket:
            await interaction.response.send_message(
                "❌ This channel is not registered as a TokyoMs ticket.",
                ephemeral=True
            )
            return

        claimed_by = ticket.get("claimed_by")

        if claimed_by:
            claimed_user = interaction.guild.get_member(claimed_by)

            name = (
                claimed_user.mention
                if claimed_user
                else f"`{claimed_by}`"
            )

            await interaction.response.send_message(
                f"❌ This ticket is already claimed by {name}.",
                ephemeral=True
            )
            return

        # Claim it.
        ticket["claimed_by"] = interaction.user.id
        tickets[channel.id] = ticket
        save_tickets()

        # Save the claim directly into the Discord channel topic.
        await save_ticket_to_channel(channel, ticket)

        mm_role = get_middleman_role(interaction.guild)

        # Hide the ticket from the entire MM role.
        if mm_role:
            try:
                await channel.set_permissions(
                    mm_role,
                    view_channel=False,
                    send_messages=False,
                    read_message_history=False
                )
            except discord.HTTPException:
                pass

        # Give the claiming middleman direct access.
        try:
            await channel.set_permissions(
                interaction.user,
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )
        except discord.HTTPException:
            await interaction.response.send_message(
                "❌ I couldn't update the ticket permissions.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            f"🌸 {interaction.user.mention} has claimed this ticket!"
        )

    # --------------------------------------------------------
    # UNCLAIM
    # --------------------------------------------------------

    @button(
        label="Unclaim Ticket",
        emoji="🔓",
        style=ButtonStyle.secondary,
        custom_id="tokyoms_unclaim_ticket"
    )
    async def unclaim_ticket(self, interaction, button):

        channel = interaction.channel
        ticket = get_ticket(channel)

        if not ticket:
            await interaction.response.send_message(
                "❌ This channel is not registered as a TokyoMs ticket.",
                ephemeral=True
            )
            return

        if ticket.get("claimed_by") != interaction.user.id:
            await interaction.response.send_message(
                "❌ Only the middleman who claimed this ticket can unclaim it.",
                ephemeral=True
            )
            return

        ticket["claimed_by"] = None
        tickets[channel.id] = ticket
        save_tickets()

        await save_ticket_to_channel(channel, ticket)

        # Remove the personal claim overwrite.
        try:
            await channel.set_permissions(
                interaction.user,
                overwrite=None
            )
        except discord.HTTPException:
            pass

        mm_role = get_middleman_role(interaction.guild)

        if mm_role:
            try:
                await channel.set_permissions(
                    mm_role,
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True
                )
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            f"🔓 {interaction.user.mention} has unclaimed the ticket."
        )

    # --------------------------------------------------------
    # CLOSE
    # --------------------------------------------------------

    @button(
        label="Close Ticket",
        emoji="🔒",
        style=ButtonStyle.danger,
        custom_id="tokyoms_close_ticket"
    )
    async def close_ticket(self, interaction, button):

        channel = interaction.channel
        ticket = get_ticket(channel)

        if not ticket:
            await interaction.response.send_message(
                "❌ This channel is not registered as a TokyoMs ticket.",
                ephemeral=True
            )
            return

        allowed = (
            ticket.get("claimed_by") == interaction.user.id
            or is_owner(interaction.user)
        )

        if not allowed:
            await interaction.response.send_message(
                "❌ Only the claimed middleman or Owner can close this ticket.",
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            "🔒 Closing this ticket in 5 seconds..."
        )

        await asyncio.sleep(5)

        tickets.pop(channel.id, None)
        save_tickets()

        try:
            await channel.delete(
                reason=f"TokyoMs ticket closed by {interaction.user}"
            )
        except (discord.NotFound, discord.Forbidden):
            pass

    # --------------------------------------------------------
    # ADD USER
    # --------------------------------------------------------

    @button(
        label="Add User",
        emoji="➕",
        style=ButtonStyle.primary,
        custom_id="tokyoms_add_user"
    )
    async def add_user(self, interaction, button):

        if not is_middleman(interaction.user):
            await interaction.response.send_message(
                "❌ Only a middleman can use **Add User**.",
                ephemeral=True
            )
            return

        ticket = get_ticket(interaction.channel)

        if not ticket:
            await interaction.response.send_message(
                "❌ This channel is not registered as a TokyoMs ticket.",
                ephemeral=True
            )
            return

        if ticket.get("claimed_by"):
            if ticket["claimed_by"] != interaction.user.id:
                await interaction.response.send_message(
                    "❌ Only the middleman who claimed this ticket can use Add User.",
                    ephemeral=True
                )
                return

        await interaction.response.send_modal(
            AddUserModal(interaction.channel)
        )


# ============================================================
# PANEL COMMAND
# ============================================================

@bot.command(name="panel")
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):

    embed = discord.Embed(
        title="🌸 TokyoMs | Middleman Service",
        description=(
            "Welcome to the **TokyoMs Middleman Service**.\n\n"
            "We provide a safe and secure way to complete trades "
            "with the help of a trusted middleman.\n\n"
            "**How to request a middleman:**\n"
            "Select your game from the menu below and complete "
            "the request form.\n\n"
            "**Usage Conditions:**\n"
            "• Select the correct game.\n"
            "• Both parties must agree to the trade.\n"
            "• State all trade details clearly.\n"
            "• Fake or troll tickets may result in punishment.\n\n"
            "🌸 A middleman will assist you once your ticket is created."
        ),
        color=PINK
    )

    if PANEL_BANNER_URL:
        embed.set_image(url=PANEL_BANNER_URL)

    if PANEL_ICON_URL:
        embed.set_thumbnail(url=PANEL_ICON_URL)

    embed.set_footer(
        text="🌸 TokyoMs • Trusted & Secure"
    )

    await ctx.send(
        embed=embed,
        view=TicketPanelView()
    )


@ticketpanel.error
async def ticketpanel_error(ctx, error):

    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            "❌ You need Administrator permission to use `$panel`.",
            delete_after=5
        )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    # Persistent views allow existing Discord buttons to continue
    # working after a bot restart.
    try:
        bot.add_view(TicketPanelView())
        bot.add_view(TicketView())
    except Exception as e:
        print(f"[VIEWS] Could not register persistent views: {e}")

    # Recover ticket records from existing ticket channel topics.
    recovered = 0

    for guild in bot.guilds:
        for channel in guild.text_channels:
            ticket = parse_ticket_topic(channel.topic)

            if ticket:
                tickets[channel.id] = ticket
                recovered += 1

    save_tickets()

    print("========================================")
    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("🌸 TokyoMs Middleman Ticket System Online")
    print(f"Recovered tickets: {recovered}")
    print("========================================")


# ============================================================
# RUN
# ============================================================

bot.run(TOKEN)
