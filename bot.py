# =====================================================
# LSRP Network System™® — Application Bot (Clean Build)
# Application System Only: Panel + PSO/CO/SAFR (with Q4 buttons)
# =====================================================

import os
import random
import asyncio
import logging

import discord
from discord import app_commands, Embed, Object
from discord.ext import commands
from discord.ui import View, Button, Select

# -------------------------
# LOGGING
# -------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("application_bot")

# -------------------------
# ENV VARS / CONSTANTS
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
HQ_GUILD_ID = 1324117813878718474
PS5_GUILD_ID = 1401903156274790441

VERIFIED_ROLE_ID = 1367753287872286720
OFFICIAL_ROLE_ID = 1401961522556698739

PS4_SASP_ROLE = 1401347813958226061
PS4_BCSO_ROLE = 1401347339796348938
PS5_SASP_ROLE = 1407034121808646269
PS5_BCSO_ROLE = 1407034123561734245

APPLICATION_TIPS_CHANNEL = 1370854351828029470
APPLICATION_PANEL_CHANNEL_ID = 1324115220725108877
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1317589676336611381/1405147584456032276/Sunset_Photography_Tumblr_Banner.png?ex=68a8f9ea&is=68a7a86a&hm=81583a9d5a173b7399c77a186e6d2bf07611d5441d4f943d0e3f25a351cfde01&"


CALLSIGN_LOG_CHANNEL = 1396076403052773396
STAFF_REVIEW_CHANNEL = 1366431401054048357

# =====================================================
# DISCORD SETUP
# =====================================================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="?", intents=intents)
tree = bot.tree

# =====================================================
# SECTION 1 - Application Panel View
# =====================================================
class ApplicationPanel(View):
    def __init__(self):
        super().__init__(timeout=None)  # must be None for persistence
        self.select = Select(
            placeholder="Select a department to apply for...",
            custom_id="application_panel_select",  # REQUIRED for persistence
            options=[
                discord.SelectOption(label="Public Safety Office (PSO)", value="pso"),
                discord.SelectOption(label="Civilian Operations (CO)", value="co"),
                discord.SelectOption(label="San Andreas Fire & Rescue (SAFR)", value="safr"),
            ]
        )
        self.select.callback = self.select_callback
        self.add_item(self.select)

    async def select_callback(self, interaction: discord.Interaction):
        choice = self.select.values[0]

        if choice == "pso":
            await interaction.response.send_message(
                "✅ Starting your **PSO Application** in DMs!", ephemeral=True
            )
            channel = await interaction.user.create_dm()
            await run_pso_application(interaction.user, channel)

        elif choice == "co":
            await interaction.response.send_message(
                "✅ Starting your **Civilian Operations Application** in DMs!", ephemeral=True
            )
            channel = await interaction.user.create_dm()
            await run_co_application(interaction.user, channel)

        elif choice == "safr":
            await interaction.response.send_message(
                "✅ Starting your **SAFR Application** in DMs!", ephemeral=True
            )
            channel = await interaction.user.create_dm()
            await run_safr_application(interaction.user, channel)


# =====================================================
# SECTION 2 - Panel Posting (Auto on Startup)
# =====================================================
async def post_panel(channel: discord.TextChannel):
    tips_channel_mention = f"<#{APPLICATION_TIPS_CHANNEL}>"

    title = "## 📥 Los Santos Roleplay Network™® — Applications."
    intro = (
        "**Hello prospective members!**\n\n"
        "*We’re excited to have you on board—now it’s time to apply for access to our Main Server. "
        "This is your first step toward becoming a fully engaged member and jumping into the action!*\n\n"
        f"*For guidance, please head to {tips_channel_mention} where you’ll find everything you need to know about the process.*"
    )

    tips = (
        "### 📌 A Few Tips Before You Start:\n"
        "**1. Read the `Rules` Carefully.**\n\n"
        "> Before submitting, make sure you’ve read through __all server rules and guidelines.__\n\n"
        "**2. Take Your Time.**\n\n"
        "> Don’t rush — fill out your application truthfully and provide good detail about your RP experience and goals.\n\n"
        "**3. Be Honest & Authentic.**\n\n"
        "> New to RP? That’s fine. Tell us how you plan to grow - everyone starts somewhere and we’re here to support you."
    )

    what_next = (
        "### ⏳ What Happens Next?\n\n"
        "*Once you submit, staff will review your application and get back to you within 30 minutes.*\n"
        "Please keep your DMs open so the bot can message you with next steps."
    )

    choose_path = (
        "## 🧭 Choose Your Path.\n\n"
        "**Use the menu below to select your department:**\n"
        "• `PSO` — *Public Safety Office (Law Enforcement: BCSO / SASP)*\n"
        "• `CO` — *Civilian Operations (Civilian Roleplay)*\n"
        "• `SAFR` — *San Andreas Fire & Rescue (Fire & EMS)*"
    )

    embed = discord.Embed(
        description=f"{title}\n\n{intro}\n\n{tips}\n\n{what_next}\n\n{choose_path}",
        color=discord.Color.blurple()
    )
    embed.set_image(url=PANEL_IMAGE_URL)

    await channel.send(embed=embed, view=ApplicationPanel())

# =====================================================
# SECTION 3 - Q4 Button View
# =====================================================
class Q4Buttons(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.choice = None

    @discord.ui.button(label="Friend", style=discord.ButtonStyle.blurple)
    async def friend(self, interaction: discord.Interaction, button: Button):
        self.choice = "Friend"
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Instagram", style=discord.ButtonStyle.blurple)
    async def instagram(self, interaction: discord.Interaction, button: Button):
        self.choice = "Instagram"
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Partnership", style=discord.ButtonStyle.blurple)
    async def partnership(self, interaction: discord.Interaction, button: Button):
        self.choice = "Partnership"
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Other", style=discord.ButtonStyle.blurple)
    async def other(self, interaction: discord.Interaction, button: Button):
        self.choice = "Other"
        self.disable_all_items()
        await interaction.response.edit_message(view=self)
        self.stop()

# =====================================================
# SECTION 3.1 - Platform & Sub-Department Selectors
# =====================================================
class PlatformSelect(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.value = None

    @discord.ui.select(
        placeholder="Select your platform...",
        options=[
            discord.SelectOption(label="PS4", value="PS4"),
            discord.SelectOption(label="PS5", value="PS5"),
        ],
        custom_id="platform_select"
    )
    async def select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.value = select.values[0]
        await interaction.response.defer()
        self.stop()


class SubDeptSelect(View):
    def __init__(self):
        super().__init__(timeout=60)
        self.value = None

    @discord.ui.select(
        placeholder="Select your sub-department...",
        options=[
            discord.SelectOption(label="San Andreas State Police (SASP)", value="SASP"),
            discord.SelectOption(label="Blaine County Sheriff's Office (BCSO)", value="BCSO"),
        ],
        custom_id="subdept_select"
    )
    async def select(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.value = select.values[0]
        await interaction.response.defer()
        self.stop()


# =====================================================
# SECTION 4 - PSO Application Flow (with platform + sub-dept)
# =====================================================
async def run_pso_application(user: discord.User, channel: discord.DMChannel):
    # Step 1: Platform select
    pview = PlatformSelect()
    await channel.send("Please select your platform:", view=pview)
    await pview.wait()
    platform = pview.value or "Not selected"

    # Step 2: Sub-department select
    sview = SubDeptSelect()
    await channel.send("Please select your sub-department:", view=sview)
    await sview.wait()
    subdept = sview.value or "Not selected"

    # Step 3: Confirmation embed
    confirm = discord.Embed(
        title="Application Details Confirmed",
        description=f"**Department:** PSO\n**Sub-Department:** {subdept}\n**Platform:** {platform}\n\n"
                    "✅ Selections saved. I'll now begin your application questions.\n"
                    "⏳ Time left: 35 minutes",
        color=discord.Color.blue()
    )
    await channel.send(embed=confirm)

    # Step 3.1: Staff log
    log_channel = bot.get_channel(STAFF_REVIEW_CHANNEL)
    if log_channel:
        await log_channel.send(
            f"📋 **New PSO Application Started**\n"
            f"👤 Applicant: {user.mention}\n"
            f"🛡 Sub-Department: {subdept}\n"
            f"🎮 Platform: {platform}"
        )

    # Step 4: Run questions
    responses = []
    for q in PSO_QUESTIONS:
        if q.startswith("4."):
            embed = discord.Embed(title="PSO Application", description="4. How did you find us?", color=discord.Color.blue())
            view = Q4Buttons()
            await channel.send(embed=embed, view=view)
            await view.wait()
            responses.append(("4. How did you find us?", view.choice or "No response"))
            continue

        embed = discord.Embed(title="PSO Application", description=q, color=discord.Color.blue())
        await channel.send(embed=embed)
        try:
            msg = await bot.wait_for("message", timeout=300, check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel))
            responses.append((q, msg.content))
        except asyncio.TimeoutError:
            await channel.send("⏳ Application timed out. Please re-apply.")
            return None
    return responses


# =====================================================
# SECTION 5 - Civilian Ops Application Flow (with platform)
# =====================================================
async def run_co_application(user: discord.User, channel: discord.DMChannel):
    # Step 1: Platform select
    pview = PlatformSelect()
    await channel.send("Please select your platform:", view=pview)
    await pview.wait()
    platform = pview.value or "Not selected"

    # Step 2: Confirmation embed
    confirm = discord.Embed(
        title="Application Details Confirmed",
        description=f"**Department:** Civilian Operations\n**Platform:** {platform}\n\n"
                    "✅ Selections saved. I'll now begin your application questions.\n"
                    "⏳ Time left: 35 minutes",
        color=discord.Color.green()
    )
    await channel.send(embed=confirm)

    # Step 2.1: Staff log
    log_channel = bot.get_channel(STAFF_REVIEW_CHANNEL)
    if log_channel:
        await log_channel.send(
            f"📋 **New Civilian Operations Application Started**\n"
            f"👤 Applicant: {user.mention}\n"
            f"🎮 Platform: {platform}"
        )

    # Step 3: Run questions
    responses = []
    for q in CIVILIAN_QUESTIONS:
        if q.startswith("4."):
            embed = discord.Embed(title="Civilian Ops Application", description="4. How did you find us?", color=discord.Color.green())
            view = Q4Buttons()
            await channel.send(embed=embed, view=view)
            await view.wait()
            responses.append(("4. How did you find us?", view.choice or "No response"))
            continue

        embed = discord.Embed(title="Civilian Ops Application", description=q, color=discord.Color.green())
        await channel.send(embed=embed)
        try:
            msg = await bot.wait_for("message", timeout=300, check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel))
            responses.append((q, msg.content))
        except asyncio.TimeoutError:
            await channel.send("⏳ Application timed out. Please re-apply.")
            return None
    return responses


# =====================================================
# SECTION 6 - SAFR Application Flow (with platform)
# =====================================================
async def run_safr_application(user: discord.User, channel: discord.DMChannel):
    # Step 1: Platform select
    pview = PlatformSelect()
    await channel.send("Please select your platform:", view=pview)
    await pview.wait()
    platform = pview.value or "Not selected"

    # Step 2: Confirmation embed
    confirm = discord.Embed(
        title="Application Details Confirmed",
        description=f"**Department:** San Andreas Fire & Rescue\n**Platform:** {platform}\n\n"
                    "✅ Selections saved. I'll now begin your application questions.\n"
                    "⏳ Time left: 35 minutes",
        color=discord.Color.red()
    )
    await channel.send(embed=confirm)

    # Step 2.1: Staff log
    log_channel = bot.get_channel(STAFF_REVIEW_CHANNEL)
    if log_channel:
        await log_channel.send(
            f"📋 **New SAFR Application Started**\n"
            f"👤 Applicant: {user.mention}\n"
            f"🎮 Platform: {platform}"
        )

    # Step 3: Run questions
    responses = []
    for q in SAFR_QUESTIONS:
        if q.startswith("4."):
            embed = discord.Embed(title="SAFR Application", description="4. How did you find us?", color=discord.Color.red())
            view = Q4Buttons()
            await channel.send(embed=embed, view=view)
            await view.wait()
            responses.append(("4. How did you find us?", view.choice or "No response"))
            continue

        embed = discord.Embed(title="SAFR Application", description=q, color=discord.Color.red())
        await channel.send(embed=embed)
        try:
            msg = await bot.wait_for("message", timeout=300, check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel))
            responses.append((q, msg.content))
        except asyncio.TimeoutError:
            await channel.send("⏳ Application timed out. Please re-apply.")
            return None
    return responses


# =====================================================
# SECTION 7 - Staff Review System
# =====================================================
class ReviewButtons(View):
    def __init__(self, applicant: discord.User, responses: list):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.responses = responses

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        member = guild.get_member(self.applicant.id)
        if member:
            # Remove applicant roles (both PS4 + PS5 applicant roles)
            applicant_roles = [1401961522556698739, 1401961758502944900, 1401961991756578817]
            for role_id in applicant_roles:
                role = guild.get_role(role_id)
                if role and role in member.roles:
                    await member.remove_roles(role)

            # Add official + verified roles
            await member.add_roles(Object(id=VERIFIED_ROLE_ID))
            await member.add_roles(Object(id=OFFICIAL_ROLE_ID))

            # Callsign + log
            await assign_callsign(member, "PSO/CO/SAFR")
            await self.applicant.send("✅ Your application has been **accepted**! Welcome to Los Santos Roleplay Network™®.")

        await interaction.response.send_message("Applicant accepted ✅", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: Button):
        await self.applicant.send("❌ Your application has been **denied**. You may reapply after 12 hours.")
        await interaction.response.send_message("Applicant denied ❌", ephemeral=True)
        self.disable_all_items()
        await interaction.message.edit(view=self)

# =====================================================
# SECTION 8 - Authorization Command (/auth_grant)
# =====================================================
@tree.command(name="auth_grant", description="Grant access after application approval (PS4 + PS5).")
async def auth_grant(interaction: discord.Interaction, member: discord.Member):
    try:
        # Remove applicant roles
        applicant_roles = [1401961522556698739, 1401961758502944900, 1401961991756578817]
        for role_id in applicant_roles:
            role = interaction.guild.get_role(role_id)
            if role and role in member.roles:
                await member.remove_roles(role)

        # Add official + verified roles
        await member.add_roles(Object(id=VERIFIED_ROLE_ID))
        await member.add_roles(Object(id=OFFICIAL_ROLE_ID))

        # Callsign + log
        await assign_callsign(member, "PSO/CO/SAFR")

        await interaction.response.send_message(f"✅ {member.mention} authorized and roles applied.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

# =====================================================
# SECTION 9 - PS5 Mirroring + Callsign Assignment
# =====================================================
async def assign_subdept_roles(member: discord.Member, dept: str, guild_type="PS4"):
    if guild_type == "PS4":
        if dept == "SASP":
            await member.add_roles(Object(id=PS4_SASP_ROLE))
        elif dept == "BCSO":
            await member.add_roles(Object(id=PS4_BCSO_ROLE))
    elif guild_type == "PS5":
        if dept == "SASP":
            await member.add_roles(Object(id=PS5_SASP_ROLE))
        elif dept == "BCSO":
            await member.add_roles(Object(id=PS5_BCSO_ROLE))

async def assign_callsign(member: discord.Member, dept: str):
    callsign_num = random.randint(1000, 1999)
    callsign = f"C-{callsign_num} | {member.name}"
    try:
        await member.edit(nick=callsign)
    except Exception:
        pass
    log_channel = member.guild.get_channel(CALLSIGN_LOG_CHANNEL)
    if log_channel:
        await log_channel.send(f"📋 Callsign assigned: **{callsign}** → {member.mention} ({dept})")

# =====================================================
# SECTION 10 - Startup + Run
# =====================================================
@bot.event
async def on_ready():
    bot.add_view(ApplicationPanel())  # keep dropdown alive
    logger.info("✅ Persistent views loaded.")

    try:
        channel = bot.get_channel(APPLICATION_PANEL_CHANNEL_ID)
        if channel:
            await post_panel(channel)
            logger.info(f"✅ Permanent application panel posted in #{channel.name}")
        else:
            logger.error(f"❌ Could not find panel channel ID: {APPLICATION_PANEL_CHANNEL_ID}")
    except Exception as e:
        logger.error(f"❌ Failed to post panel: {e}")

    logger.info(f"✅ Application Bot ready as {bot.user}")

if __name__ == "__main__":
    bot.run(BOT_TOKEN)

