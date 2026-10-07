# ============================================================
# TOKYOMS MM TICKET BOT
# ============================================================

import os
import re
import asyncio
import discord

from discord.ext import commands
from discord.ui import Modal, TextInput, View, button
from discord import ButtonStyle


# ============================================================
# CONFIG
# ============================================================

TOKEN = os.getenv("DISCORD_TOKEN")

MIDDLEMAN_ROLE_ID = int(
    os.getenv("MIDDLEMAN_ROLE_ID", "1557255996647153714")
)

OWNER_ROLE_ID = int(
    os.getenv("OWNER_ROLE_ID", "1556390123203989644")
)

TICKET_CATEGORY_ID = int(
    os.getenv("TICKET_CATEGORY_ID", "1557256486176952351")
)


# ============================================================
# TOKYOMS BANNERS / ICON
# ============================================================

PANEL_BANNER_URL = (
    "https://media.discordapp.net/attachments/"
    "1551900302146281554/1557109839681953904/"
    "TMS_banner.gif?backend=b2&ex=6ac69b0b&is=6ab5498b"
    "&hm=2ba841228ebf004e747f0687006b4cefe0991bbf9091156599a2030725e31951"
    "&=&width=894&height=503"
)

TICKET_BANNER_URL = (
    "https://media.discordapp.net/attachments/"
    "1551900302146281554/1557109839681953904/"
    "TMS_banner.gif?backend=b2&ex=6ac69b0b&is=6ab5498b"
    "&hm=2ba841228ebf004e747f0687006b4cefe0991bbf9091156599a2030725e31951"
    "&=&width=894&height=503"
)

PANEL_ICON_URL = (
    "https://media.discordapp.net/attachments/"
    "1551900302146281554/1557109836552998963/"
    "TMS.gif?backend=b2&ex=6ac69b0a&is=6ac5498a"
    "&hm=a2bc18bf216f7d76df204e0a5be8c1d682dbffba503703c73f66d7365b47cfc4"
    "&="
)


# ============================================================
# TOKYOMS COLOR
# ============================================================

TOKYOMS_PINK = discord.Color.from_rgb(
    255,
    182,
    193
)


# ============================================================
# TOKEN CHECK
# ============================================================

if not TOKEN:
    raise RuntimeError(
        "DISCORD_TOKEN is not set"
    )


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
# STORAGE
# ============================================================

tickets = {}


# ============================================================
# HELPERS
# ============================================================

def get_middleman_role(
    guild: discord.Guild
):
    if not MIDDLEMAN_ROLE_ID:
        return None

    return guild.get_role(
        MIDDLEMAN_ROLE_ID
    )


def get_owner_role(
    guild: discord.Guild
):
    if not OWNER_ROLE_ID:
        return None

    return guild.get_role(
        OWNER_ROLE_ID
    )


def is_middleman(
    member: discord.Member
):
    role = get_middleman_role(
        member.guild
    )

    if not role:
        return False

    return role in member.roles


def is_owner(
    member: discord.Member
):
    role = get_owner_role(
        member.guild
    )

    if not role:
        return False

    return role in member.roles


def clean_channel_name(
    name: str
):
    name = name.lower()

    name = re.sub(
        r"[^a-z0-9-]",
        "-",
        name
    )

    name = re.sub(
        r"-+",
        "-",
        name
    )

    return name[:90]


async def find_user(
    guild: discord.Guild,
    value: str
):
    value = value.strip()

    # ========================================================
    # MENTION
    # ========================================================

    match = re.fullmatch(
        r"<@!?(\d+)>",
        value
    )

    if match:
        user_id = int(
            match.group(1)
        )

    elif value.isdigit():
        user_id = int(value)

    else:
        member = discord.utils.find(
            lambda m:
            m.name.lower() == value.lower()
            or m.display_name.lower() == value.lower(),
            guild.members
        )

        if member:
            return member

        return None

    try:
        return (
            guild.get_member(user_id)
            or await guild.fetch_member(user_id)
        )

    except discord.NotFound:
        return None

    except discord.HTTPException:
        return None


# ============================================================
# MIDDLEMAN REQUEST MODAL
# ============================================================

class MiddlemanRequestModal(Modal):

    def __init__(
        self,
        selected_game: str
    ):

        super().__init__(
            title=f"🌸 {selected_game} Middleman Request"
        )

        self.selected_game = selected_game

        # ====================================================
        # TRADER
        # ====================================================

        self.trader_input = TextInput(
            label="Trader Username / User ID",
            placeholder="Enter the other trader's username or ID",
            required=True,
            max_length=100
        )

        # ====================================================
        # YOUR TRADE
        # ====================================================

        self.giving_input = TextInput(
            label="What Are You Giving?",
            placeholder="Clearly list everything you are giving",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )

        # ====================================================
        # TRADER TRADE
        # ====================================================

        self.trader_giving_input = TextInput(
            label="What Is Your Trader Giving?",
            placeholder="Clearly list everything they are giving",
            required=True,
            style=discord.TextStyle.paragraph,
            max_length=4000
        )

        # ====================================================
        # PRIVATE SERVER
        # ====================================================

        self.private_input = TextInput(
            label="Can You Join Private Server Links?",
            placeholder="Yes or No",
            required=True,
            max_length=20
        )

        self.add_item(
            self.trader_input
        )

        self.add_item(
            self.giving_input
        )

        self.add_item(
            self.trader_giving_input
        )

        self.add_item(
            self.private_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        guild = interaction.guild

        if guild is None:
            return

        # ====================================================
        # FIND TRADER
        # ====================================================

        trader = await find_user(
            guild,
            self.trader_input.value
        )

        if not trader:

            await interaction.response.send_message(
                "🌸 I couldn't find that user. "
                "Please enter their Discord ID or mention.",
                ephemeral=True
            )

            return

        # ====================================================
        # SELF TRADE CHECK
        # ====================================================

        if trader.id == interaction.user.id:

            await interaction.response.send_message(
                "🌸 You can't use yourself as the other trader.",
                ephemeral=True
            )

            return

        # ====================================================
        # CATEGORY
        # ====================================================

        category = None

        if TICKET_CATEGORY_ID:

            category = guild.get_channel(
                TICKET_CATEGORY_ID
            )

            if category and not isinstance(
                category,
                discord.CategoryChannel
            ):
                category = None

        # ====================================================
        # PERMISSIONS
        # ====================================================

        overwrites = {

            guild.default_role:
                discord.PermissionOverwrite(
                    view_channel=False
                ),

            interaction.user:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                ),

            trader:
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True
                )
        }

        # ====================================================
        # MIDDLEMAN ROLE
        # ====================================================

        mm_role = get_middleman_role(
            guild
        )

        if mm_role:

            overwrites[mm_role] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True
                )
            )

        # ====================================================
        # OWNER ROLE
        # ====================================================

        owner_role = get_owner_role(
            guild
        )

        if owner_role:

            overwrites[owner_role] = (
                discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True,
                    attach_files=True,
                    embed_links=True,
                    manage_messages=True
                )
            )

        # ====================================================
        # CHANNEL NAME
        # ====================================================

        channel_name = clean_channel_name(
            f"{self.selected_game}-{interaction.user.name}"
        )

        # ====================================================
        # CREATE CHANNEL
        # ====================================================

        try:

            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overwrites,
                reason="TokyoMs middleman ticket created"
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "🌸 I don't have permission to create ticket channels.",
                ephemeral=True
            )

            return

        except discord.HTTPException:

            await interaction.response.send_message(
                "🌸 Discord failed to create the ticket. Please try again.",
                ephemeral=True
            )

            return

        # ====================================================
        # SAVE TICKET
        # ====================================================

        tickets[channel.id] = {

            "owner": interaction.user.id,

            "trader": trader.id,

            "game": self.selected_game,

            "giving":
                self.giving_input.value,

            "trader_giving":
                self.trader_giving_input.value,

            "private_links":
                self.private_input.value,

            "claimed_by":
                None
        }

        # ====================================================
        # CREATION RESPONSE
        # ====================================================

        await interaction.response.send_message(
            f"🌸 Your **{self.selected_game}** "
            f"Middleman ticket has been created: "
            f"{channel.mention}",
            ephemeral=True
        )

        # ====================================================
        # WELCOME EMBED
        # ====================================================

        welcome = discord.Embed(

            title="🌸 TokyoMs | Middleman Service",

            description=(
                f"**🌸 Welcome {interaction.user.mention}!**\n\n"

                "Thank you for using "
                "**TokyoMs Middleman Services.**\n\n"

                "A trusted Middleman will assist you with "
                "your trade and help make sure everything "
                "goes smoothly.\n\n"

                "## 🌸 Before We Begin\n"

                "• Make sure both traders agree to the trade.\n"
                "• Clearly provide all trade details.\n"
                "• Do not leave or cancel the trade without "
                "informing the Middleman.\n"
                "• Never share passwords, cookies, or "
                "verification codes.\n\n"

                "🌸 **Please wait patiently for an official "
                "Middleman to claim your ticket.**\n\n"

                "**Fake or troll tickets may result in "
                "punishment.**"
            ),

            color=TOKYOMS_PINK
        )

        # ====================================================
        # TICKET BANNER
        # ====================================================

        if TICKET_BANNER_URL:

            welcome.set_image(
                url=TICKET_BANNER_URL
            )

        welcome.set_footer(
            text="🌸 TokyoMs • Trusted & Secure Middleman Service"
        )

        # ====================================================
        # TRADE DETAILS
        # ====================================================

        details = discord.Embed(

            title="🌸 Trade Details",

            description=(
                "**Please carefully check the information "
                "below before proceeding.**"
            ),

            color=TOKYOMS_PINK
        )

        details.add_field(
            name="🌸 Game",
            value=self.selected_game,
            inline=False
        )

        details.add_field(
            name="🌸 What Are You Giving?",
            value=self.giving_input.value,
            inline=False
        )

        details.add_field(
            name="🌸 What Is Your Trader Giving?",
            value=self.trader_giving_input.value,
            inline=False
        )

        details.add_field(
            name="🌸 Trader",
            value=(
                f"{trader.mention}\n"
                f"`{trader.id}`"
            ),
            inline=False
        )

        details.add_field(
            name="🌸 Private Server Links",
            value=self.private_input.value,
            inline=False
        )

        details.set_footer(
            text="🌸 TokyoMs • Check all trade details carefully"
        )

        # ====================================================
        # PING
        # ====================================================

        ping_message = (
            f"🌸 {interaction.user.mention} "
            f"{trader.mention}"
        )

        if mm_role:

            ping_message += (
                f" {mm_role.mention}"
            )

        # ====================================================
        # SEND TICKET
        # ====================================================

        await channel.send(

            content=ping_message,

            embeds=[
                welcome,
                details
            ],

            view=TicketView()
        )


# ============================================================
# GAME SELECT
# ============================================================

class GameSelect(
    discord.ui.Select
):

    def __init__(self):

        options = [

            discord.SelectOption(
                label="Murder Mystery 2",
                emoji="🔪",
                description="Request a TokyoMs MM for MM2",
                value="Murder Mystery 2"
            ),

            discord.SelectOption(
                label="Blox Fruits",
                emoji="🍎",
                description="Request a TokyoMs MM for Blox Fruits",
                value="Blox Fruits"
            ),

            discord.SelectOption(
                label="Adopt Me",
                emoji="🐶",
                description="Request a TokyoMs MM for Adopt Me",
                value="Adopt Me"
            ),

            discord.SelectOption(
                label="Steal a Brainrot",
                emoji="🧠",
                description="Request a TokyoMs MM for SAB",
                value="Steal a Brainrot"
            ),

            discord.SelectOption(
                label="Others",
                emoji="🌸",
                description="Request a TokyoMs MM for another game",
                value="Others"
            )
        ]

        super().__init__(

            placeholder="🌸 Select a game...",

            min_values=1,

            max_values=1,

            options=options,

            custom_id="game_selection"
        )

    async def callback(
        self,
        interaction: discord.Interaction
    ):

        selected_game = self.values[0]

        await interaction.response.send_modal(
            MiddlemanRequestModal(
                selected_game
            )
        )


# ============================================================
# REQUEST PANEL VIEW
# ============================================================

class TicketPanelView(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

        self.add_item(
            GameSelect()
        )


# ============================================================
# ADD USER MODAL
# ============================================================

class AddUserModal(Modal):

    def __init__(
        self,
        channel: discord.TextChannel
    ):

        super().__init__(
            title="🌸 Add User"
        )

        self.channel = channel

        self.user_input = TextInput(
            label="User ID / Username",
            placeholder="Enter the user's ID or username",
            required=True,
            max_length=100
        )

        self.add_item(
            self.user_input
        )

    async def on_submit(
        self,
        interaction: discord.Interaction
    ):

        # ====================================================
        # ONLY MIDDLEMAN
        # ====================================================

        if not is_middleman(
            interaction.user
        ):

            await interaction.response.send_message(
                "🌸 Only a Middleman can add users to this ticket.",
                ephemeral=True
            )

            return

        # ====================================================
        # CHECK CLAIM
        # ====================================================

        ticket = tickets.get(
            self.channel.id
        )

        if ticket:

            claimed_by = ticket[
                "claimed_by"
            ]

            if claimed_by:

                if claimed_by != interaction.user.id:

                    await interaction.response.send_message(
                        "🌸 Only the Middleman who claimed this "
                        "ticket can add users.",
                        ephemeral=True
                    )

                    return

        # ====================================================
        # FIND USER
        # ====================================================

        user = await find_user(
            interaction.guild,
            self.user_input.value
        )

        if not user:

            await interaction.response.send_message(
                "🌸 User not found.",
                ephemeral=True
            )

            return

        # ====================================================
        # ADD USER
        # ====================================================

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
                f"🌸 {user.mention} was added by "
                f"{interaction.user.mention}."
            )

        except discord.Forbidden:

            await interaction.response.send_message(
                "🌸 I don't have permission to add that user.",
                ephemeral=True
            )


# ============================================================
# TICKET VIEW
# ============================================================

class TicketView(View):

    def __init__(self):

        super().__init__(
            timeout=None
        )

    # ========================================================
    # CLAIM
    # ========================================================

    @button(
        label="Claim Ticket",
        emoji="✅",
        style=ButtonStyle.success,
        custom_id="claim_ticket"
    )
    async def claim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_middleman(
            interaction.user
        ):

            await interaction.response.send_message(
                "🌸 Only an official Middleman can claim this ticket.",
                ephemeral=True
            )

            return

        ticket = tickets.get(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "🌸 Ticket data was not found.",
                ephemeral=True
            )

            return

        if ticket["claimed_by"]:

            claimed_user = (
                interaction.guild.get_member(
                    ticket["claimed_by"]
                )
            )

            name = (
                claimed_user.mention
                if claimed_user
                else "another Middleman"
            )

            await interaction.response.send_message(
                f"🌸 This ticket is already claimed by {name}.",
                ephemeral=True
            )

            return

        ticket["claimed_by"] = (
            interaction.user.id
        )

        mm_role = get_middleman_role(
            interaction.guild
        )

        if mm_role:

            await interaction.channel.set_permissions(

                mm_role,

                view_channel=False,
                send_messages=False,
                read_message_history=False
            )

        await interaction.channel.set_permissions(

            interaction.user,

            view_channel=True,
            send_messages=True,
            read_message_history=True,
            attach_files=True,
            embed_links=True,
            manage_messages=True
        )

        await interaction.response.send_message(
            f"🌸 {interaction.user.mention} has claimed this ticket!\n\n"
            "Please wait patiently while the trade is handled."
        )


    # ========================================================
    # UNCLAIM
    # ========================================================

    @button(
        label="Unclaim Ticket",
        emoji="🔓",
        style=ButtonStyle.secondary,
        custom_id="unclaim_ticket"
    )
    async def unclaim_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        ticket = tickets.get(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "🌸 Ticket data was not found.",
                ephemeral=True
            )

            return

        if ticket["claimed_by"] != interaction.user.id:

            await interaction.response.send_message(
                "🌸 Only the Middleman who claimed this "
                "ticket can unclaim it.",
                ephemeral=True
            )

            return

        await interaction.channel.set_permissions(
            interaction.user,
            overwrite=None
        )

        mm_role = get_middleman_role(
            interaction.guild
        )

        if mm_role:

            await interaction.channel.set_permissions(

                mm_role,

                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True,
                embed_links=True,
                manage_messages=True
            )

        ticket["claimed_by"] = None

        await interaction.response.send_message(
            f"🌸 {interaction.user.mention} has unclaimed the ticket.\n\n"
            "The ticket is now available for another official Middleman."
        )


    # ========================================================
    # CLOSE
    # ========================================================

    @button(
        label="Close Ticket",
        emoji="🔒",
        style=ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        ticket = tickets.get(
            interaction.channel.id
        )

        if not ticket:

            await interaction.response.send_message(
                "🌸 Ticket data was not found.",
                ephemeral=True
            )

            return

        allowed = False

        if (
            ticket["claimed_by"]
            == interaction.user.id
        ):
            allowed = True

        if is_owner(
            interaction.user
        ):
            allowed = True

        if not allowed:

            await interaction.response.send_message(
                "🌸 Only the claimed Middleman or Owner "
                "can close this ticket.",
                ephemeral=True
            )

            return

        await interaction.response.send_message(
            "🌸 This ticket will be closed in **5 seconds**..."
        )

        await asyncio.sleep(5)

        tickets.pop(
            interaction.channel.id,
            None
        )

        try:

            await interaction.channel.delete(
                reason=(
                    f"TokyoMs ticket closed by "
                    f"{interaction.user}"
                )
            )

        except discord.NotFound:
            pass

        except discord.Forbidden:
            pass


    # ========================================================
    # ADD USER
    # ========================================================

    @button(
        label="Add User",
        emoji="➕",
        style=ButtonStyle.primary,
        custom_id="add_user"
    )
    async def add_user(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button
    ):

        if not is_middleman(
            interaction.user
        ):

            await interaction.response.send_message(
                "🌸 Only a Middleman can use **Add User**.",
                ephemeral=True
            )

            return

        ticket = tickets.get(
            interaction.channel.id
        )

        if ticket:

            if ticket["claimed_by"]:

                if ticket["claimed_by"] != interaction.user.id:

                    await interaction.response.send_message(
                        "🌸 Only the Middleman who claimed "
                        "this ticket can use **Add User**.",
                        ephemeral=True
                    )

                    return

        await interaction.response.send_modal(
            AddUserModal(
                interaction.channel
            )
        )


# ============================================================
# TOKYOMS PANEL COMMAND
# ============================================================

@bot.command(
    name="panel"
)
@commands.has_permissions(
    administrator=True
)
async def ticketpanel(
    ctx: commands.Context
):

    embed = discord.Embed(

        title="🌸 TokyoMs | Middleman Service",

        description=(

            "**Welcome to the TokyoMs Middleman Service!**\n\n"

            "🌸 **Trade safely with the help of an official "
            "TokyoMs Middleman.**\n\n"

            "Our Middleman Service is designed to help traders "
            "complete their trades safely and smoothly.\n\n"

            "## 🌸 How To Use\n"

            "• Select the correct game below.\n"
            "• Enter the other trader's username or ID.\n"
            "• Clearly provide what you are giving.\n"
            "• Clearly provide what the other trader is giving.\n"
            "• Wait for an official Middleman to claim your ticket.\n\n"

            "## 🌸 Important\n"

            "• Both traders must agree to the trade.\n"
            "• Never share your password, cookies, or verification codes.\n"
            "• Always check the trade details before confirming.\n"
            "• Fake or troll tickets are not allowed.\n\n"

            "**🌸 Trade safely. Use TokyoMs Middleman Services.**"
        ),

        color=TOKYOMS_PINK
    )

    # ========================================================
    # PANEL BANNER
    # ========================================================

    if PANEL_BANNER_URL:

        embed.set_image(
            url=PANEL_BANNER_URL
        )

    # ========================================================
    # PANEL ICON
    # ========================================================

    if PANEL_ICON_URL:

        embed.set_thumbnail(
            url=PANEL_ICON_URL
        )

    # ========================================================
    # FOOTER
    # ========================================================

    embed.set_footer(
        text="🌸 TokyoMs • Trusted & Secure"
    )

    # ========================================================
    # SEND PANEL
    # ========================================================

    await ctx.send(

        embed=embed,

        view=TicketPanelView()
    )


# ============================================================
# COMMAND ERROR
# ============================================================

@ticketpanel.error
async def ticketpanel_error(
    ctx: commands.Context,
    error
):

    if isinstance(
        error,
        commands.MissingPermissions
    ):

        await ctx.send(
            "🌸 You need **Administrator** permission "
            "to use `$panel`.",
            delete_after=5
        )


# ============================================================
# READY
# ============================================================

@bot.event
async def on_ready():

    bot.add_view(
        TicketPanelView()
    )

    bot.add_view(
        TicketView()
    )

    print(
        "========================================"
    )

    print(
        f"Logged in as {bot.user}"
    )

    print(
        f"Bot ID: {bot.user.id}"
    )

    print(
        "🌸 TokyoMs Middleman Ticket System Online"
    )

    print(
        "========================================"
    )


# ============================================================
# RUN
# ============================================================

bot.run(TOKEN)
