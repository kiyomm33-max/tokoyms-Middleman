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

TOKEN = os.getenv("DISCORD_TOKEN")
MIDDLEMAN_ROLE_ID = int(os.getenv("MIDDLEMAN_ROLE_ID", "1558800992626020444"))
OWNER_ROLE_ID = int(os.getenv("OWNER_ROLE_ID", "1556390123203989644"))
TICKET_CATEGORY_ID = int(os.getenv("TICKET_CATEGORY_ID", "1558794011911782490"))
EMBED_COLOR = discord.Color.from_rgb(255, 103, 47)

if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set")

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="$", intents=intents, help_command=None)
tickets = {}

def get_middleman_role(guild):
    return guild.get_role(MIDDLEMAN_ROLE_ID)

def get_owner_role(guild):
    return guild.get_role(OWNER_ROLE_ID)

def is_middleman(member):
    role = get_middleman_role(member.guild)
    return role in member.roles if role else False

def is_owner(member):
    role = get_owner_role(member.guild)
    return role in member.roles if role else False

def clean_channel_name(name):
    name = re.sub(r"[^a-z0-9-]", "-", name.lower())
    return re.sub(r"-+", "-", name)[:90]

async def find_user(guild, value):
    value = value.strip()
    match = re.fullmatch(r"<@!?(\d+)>", value)
    if match:
        user_id = int(match.group(1))
    elif value.isdigit():
        user_id = int(value)
    else:
        return discord.utils.find(
            lambda m: m.name.lower() == value.lower()
            or m.display_name.lower() == value.lower(),
            guild.members
        )
    try:
        return guild.get_member(user_id) or await guild.fetch_member(user_id)
    except (discord.NotFound, discord.HTTPException):
        return None

class MiddlemanRequestModal(Modal):
    def __init__(self, selected_game):
        super().__init__(title=f"{selected_game} Middleman Request")
        self.selected_game = selected_game
        self.trader_input = TextInput(label="Trader Username / User ID", placeholder="Enter trader username or ID", required=True, max_length=100)
        self.giving_input = TextInput(label="What Are You Giving?", placeholder="Enter what you are giving", required=True, style=discord.TextStyle.paragraph, max_length=4000)
        self.trader_giving_input = TextInput(label="What Is Your Trader Giving?", placeholder="Enter what your trader is giving", required=True, style=discord.TextStyle.paragraph, max_length=4000)
        self.private_input = TextInput(label="Can You Join Private Server Links?", placeholder="Yes or No", required=True, max_length=20)
        for item in (self.trader_input, self.giving_input, self.trader_giving_input, self.private_input):
            self.add_item(item)

    async def on_submit(self, interaction):
        guild = interaction.guild
        if guild is None:
            return
        trader = await find_user(guild, self.trader_input.value)
        if not trader:
            await interaction.response.send_message("❌ I couldn't find that user. Please use their Discord ID or mention.", ephemeral=True)
            return
        if trader.id == interaction.user.id:
            await interaction.response.send_message("❌ You can't use yourself as the other trader.", ephemeral=True)
            return
        category = guild.get_channel(TICKET_CATEGORY_ID)
        if not isinstance(category, discord.CategoryChannel):
            category = None
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True),
            trader: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
        }
        mm_role = get_middleman_role(guild)
        if mm_role:
            overwrites[mm_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True, manage_messages=True)
        owner_role = get_owner_role(guild)
        if owner_role:
            overwrites[owner_role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True, manage_messages=True)
        try:
            channel = await guild.create_text_channel(
                name=clean_channel_name(f"{self.selected_game}-{interaction.user.name}"),
                category=category, overwrites=overwrites, reason="Middleman ticket created"
            )
        except (discord.Forbidden, discord.HTTPException):
            await interaction.response.send_message("❌ Could not create ticket. Check bot permissions.", ephemeral=True)
            return
        tickets[channel.id] = {
            "owner": interaction.user.id, "trader": trader.id,
            "game": self.selected_game, "giving": self.giving_input.value,
            "trader_giving": self.trader_giving_input.value,
            "private_links": self.private_input.value, "claimed_by": None
        }
        await interaction.response.send_message(f"✅ Your **{self.selected_game}** middleman ticket has been created: {channel.mention}", ephemeral=True)
        welcome = discord.Embed(
            title="👑 Welcome to your Ticket!",
            description=f"Hello {interaction.user.mention}, thanks for opening a **Middleman Service Ticket!**\n\n🎮 **Game:** {self.selected_game}\n\nA middleman will assist you shortly.\nProvide all trade details clearly.\nFake/troll tickets will result in consequences.",
            color=EMBED_COLOR
        )
        files = []
        if BANNER_FILE.is_file():
            files.append(discord.File(BANNER_FILE, filename="u7buy_banner.png"))
            welcome.set_image(url="attachment://u7buy_banner.png")
        welcome.set_footer(text="U7BUY MARKETPLACE • Please wait for a middleman")
        details = discord.Embed(title="📋 Trade Details", color=EMBED_COLOR)
        details.add_field(name="🎮 Game", value=self.selected_game, inline=False)
        details.add_field(name="What Are You Giving?", value=self.giving_input.value[:1024], inline=False)
        details.add_field(name="What Is Your Trader Giving?", value=self.trader_giving_input.value[:1024], inline=False)
        details.add_field(name="Trader", value=f"{trader.mention}\n`{trader.id}`", inline=False)
        details.add_field(name="Can Join Private Server Links?", value=self.private_input.value, inline=False)
        details.set_footer(text="U7BUY MARKETPLACE Service")
        ping = f"{interaction.user.mention} {trader.mention}"
        if mm_role:
            ping += f" {mm_role.mention}"
        await channel.send(content=ping, embeds=[welcome, details], view=TicketView(), files=files)

class GameSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Steal a Brainrot", emoji="🧠", value="Steal a Brainrot"),
            discord.SelectOption(label="Adopt Me", emoji="🐶", value="Adopt Me"),
            discord.SelectOption(label="Murder Mystery 2", emoji="🔪", value="Murder Mystery 2"),
            discord.SelectOption(label="Grow A Garden", emoji="🌱", value="Grow A Garden"),
            discord.SelectOption(label="Blade Ball", emoji="⚔️", value="Blade Ball"),
            discord.SelectOption(label="Others", emoji="📝", value="Others")
        ]
        super().__init__(placeholder="Select a game...", min_values=1, max_values=1, options=options, custom_id="game_selection")

    async def callback(self, interaction):
        await interaction.response.send_modal(MiddlemanRequestModal(self.values[0]))

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(GameSelect())

class AddUserModal(Modal):
    def __init__(self, channel):
        super().__init__(title="Add User")
        self.channel = channel
        self.user_input = TextInput(label="User ID / Username", placeholder="eg: 1234567890", required=True, max_length=100)
        self.add_item(self.user_input)

    async def on_submit(self, interaction):
        if not is_middleman(interaction.user):
            await interaction.response.send_message("❌ Only a middleman can add users.", ephemeral=True)
            return
        ticket = tickets.get(self.channel.id)
        if ticket and ticket["claimed_by"] and ticket["claimed_by"] != interaction.user.id:
            await interaction.response.send_message("❌ Only the claimed middleman can add users.", ephemeral=True)
            return
        user = await find_user(interaction.guild, self.user_input.value)
        if not user:
            await interaction.response.send_message("❌ User not found.", ephemeral=True)
            return
        try:
            await self.channel.set_permissions(user, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True)
            await interaction.response.send_message(f"✅ Added {user.mention} to the ticket.", ephemeral=True)
            await self.channel.send(f"➕ {user.mention} was added by {interaction.user.mention}.")
        except discord.Forbidden:
            await interaction.response.send_message("❌ I don't have permission to add that user.", ephemeral=True)

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @button(label="Claim Ticket", emoji="✅", style=ButtonStyle.success, custom_id="claim_ticket")
    async def claim_ticket(self, interaction, button):
        if not is_middleman(interaction.user):
            await interaction.response.send_message("❌ Only a middleman can claim this ticket.", ephemeral=True)
            return
        ticket = tickets.get(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket data was not found.", ephemeral=True)
            return
        if ticket["claimed_by"]:
            await interaction.response.send_message("❌ This ticket is already claimed.", ephemeral=True)
            return
        ticket["claimed_by"] = interaction.user.id
        mm_role = get_middleman_role(interaction.guild)
        if mm_role:
            await interaction.channel.set_permissions(mm_role, view_channel=False, send_messages=False, read_message_history=False)
        await interaction.channel.set_permissions(interaction.user, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True, manage_messages=True)
        await interaction.response.send_message(f"✅ {interaction.user.mention} has claimed this ticket!")

    @button(label="Unclaim Ticket", emoji="🔓", style=ButtonStyle.secondary, custom_id="unclaim_ticket")
    async def unclaim_ticket(self, interaction, button):
        ticket = tickets.get(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket data was not found.", ephemeral=True)
            return
        if ticket["claimed_by"] != interaction.user.id:
            await interaction.response.send_message("❌ Only the claimed middleman can unclaim.", ephemeral=True)
            return
        await interaction.channel.set_permissions(interaction.user, overwrite=None)
        mm_role = get_middleman_role(interaction.guild)
        if mm_role:
            await interaction.channel.set_permissions(mm_role, view_channel=True, send_messages=True, read_message_history=True, attach_files=True, embed_links=True, manage_messages=True)
        ticket["claimed_by"] = None
        await interaction.response.send_message(f"🔓 {interaction.user.mention} has unclaimed the ticket.")

    @button(label="Close Ticket", emoji="🔒", style=ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction, button):
        ticket = tickets.get(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Ticket data was not found.", ephemeral=True)
            return
        if ticket["claimed_by"] != interaction.user.id and not is_owner(interaction.user):
            await interaction.response.send_message("❌ Only the claimed middleman or Owner can close.", ephemeral=True)
            return
        await interaction.response.send_message("🔒 Closing this ticket in 5 seconds...")
        await asyncio.sleep(5)
        tickets.pop(interaction.channel.id, None)
        try:
            await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")
        except (discord.NotFound, discord.Forbidden):
            pass

    @button(label="Add User", emoji="➕", style=ButtonStyle.primary, custom_id="add_user")
    async def add_user(self, interaction, button):
        if not is_middleman(interaction.user):
            await interaction.response.send_message("❌ Only a middleman can use Add User.", ephemeral=True)
            return
        ticket = tickets.get(interaction.channel.id)
        if ticket and ticket["claimed_by"] and ticket["claimed_by"] != interaction.user.id:
            await interaction.response.send_message("❌ Only the claimed middleman can add users.", ephemeral=True)
            return
        await interaction.response.send_modal(AddUserModal(interaction.channel))

@bot.command(name="panel")
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="U7BUY Marketplace | MM Service",
        description=(
            "Welcome to our middleman Service centre.\n\n"
            "At U7BUY MARKETPLACE, we value and provide a safe and secure way to exchange your goods.\n\n"
            "**If you've found a trade and want to ensure your safety, you can use our middleman service.**\n\n"
            "Our middleman service helps both users complete their agreed trade.\n\n"
            "---\n**Usage Conditions:**\n"
            "• Select the correct game before requesting a middleman.\n"
            "• Both parties agree to trade before requesting a middleman.\n"
            "• State the trade details clearly.\n"
            "• Fake or troll tickets will result in punishments."
        ),
        color=EMBED_COLOR
    )
    files = []
    if BANNER_FILE.is_file():
        files.append(discord.File(BANNER_FILE, filename="u7buy_banner.png"))
        embed.set_image(url="attachment://u7buy_banner.png")
    if ICON_FILE.is_file():
        files.append(discord.File(ICON_FILE, filename="u7buy_icon.webp"))
        embed.set_thumbnail(url="attachment://u7buy_icon.webp")
    embed.set_footer(text="U7BUY Marketplace • Trusted & Secure")
    await ctx.send(embed=embed, view=TicketPanelView(), files=files)

@ticketpanel.error
async def ticketpanel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need Administrator permission to use `$panel`.", delete_after=5)

@bot.event
async def on_ready():
    if not getattr(bot, "_u7buy_views_registered", False):
        bot.add_view(TicketPanelView())
        bot.add_view(TicketView())
        bot._u7buy_views_registered = True
    print("========================================")
    print(f"Logged in as {bot.user}")
    print(f"Bot ID: {bot.user.id}")
    print("U7BUY Marketplace MM Ticket System Online")
    print("========================================")

bot.run(TOKEN)
