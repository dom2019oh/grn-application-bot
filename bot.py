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

APPLICATION_TIPS_CHANNEL = 1400933920534560989
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
        self.add_item(Select(
            placeholder="Select a department to apply for...",
            custom_id="application_panel_select",  # REQUIRED for persistence
            options=[
                discord.SelectOption(label="Public Safety Office (PSO)", value="pso"),
                discord.SelectOption(label="Civilian Operations (CO)", value="co"),
                discord.SelectOption(label="San Andreas Fire & Rescue (SAFR)", value="safr"),
            ]
        ))


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
# SECTION 4 - PSO Application Flow (20 Questions, Q4 buttons)
# =====================================================
PSO_QUESTIONS = [
    "1. What is your Discord username?",
    "2. How old are you in real life?",
    "3. Please state your Date of Birth. (e.g., 16th June 2010)",
    "4. BUTTONS",  # special case
    "5. Explain the 'No Life Rule' in the best of your ability.",
    "6. What does VDM, RDM, and FRP mean? Describe.",
    "7. Do you have any roleplay experience?",
    "8. What time zone are you from?",
    "9. Describe what a 10-11 means.",
    "10. You see a suspect with a knife coming at you. Choose: Ask him / Taser / Run / Shoot",
    "11. What does a 10-80 mean?",
    "12. How would you handle a 10-11?",
    "13. You arrive at a robbery scene, suspect yells 'I have a bomb!!' – what do you do?",
    "14. What does Code 1, 2, and 3 mean?",
    "15. When you go on duty, what 10 codes do you use?",
    "16. As a cadet, are you eligible to drive on your own?",
    "17. You see a sniper on a hilltop. You have a pistol and radio. What do you do?",
    "18. How would you handle a noise complaint?",
    "19. Choose the correct cadet loadout.",
    "20. What is a 10-99?"
]

async def run_pso_application(user: discord.User, channel: discord.DMChannel):
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
# SECTION 5 - Civilian Ops Application Flow (20 Questions, Q4 buttons)
# =====================================================
CIVILIAN_QUESTIONS = [
    "1. What is your Discord username?",
    "2. How old are you in real life?",
    "3. Please state your Date of Birth.",
    "4. BUTTONS",
    "5. You are driving and run a red light. Police pull you over. How do you respond?",
    "6. What is FailRP? Explain with an example.",
    "7. What is FearRP? Explain with an example.",
    "8. You crash your vehicle into another. How do you handle it?",
    "9. Your character just lost their job. What are some legal RP scenarios you could pursue?",
    "10. What are three things civilians CANNOT do in roleplay?",
    "11. Explain the difference between passive RP and active RP.",
    "12. What are some examples of creative civilian roleplay scenes you would do?",
    "13. You are in a bank when a robbery happens. What do you do?",
    "14. If your character was drunk, how would you RP that realistically?",
    "15. You win the lottery in-game. What would your RP look like after that?",
    "16. Someone meta-games against you. How do you respond?",
    "17. How do you ensure you are not powergaming during a scene?",
    "18. What are some examples of realistic civilian crimes you could roleplay?",
    "19. How would you RP a court appearance or traffic ticket?",
    "20. Why do you want to be part of Civilian Operations?"
]

async def run_co_application(user: discord.User, channel: discord.DMChannel):
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
# SECTION 6 - SAFR Application Flow (20 Questions, Q4 buttons)
# =====================================================
SAFR_QUESTIONS = [
    "1. What is your Discord username?",
    "2. How old are you in real life?",
    "3. Please state your Date of Birth.",
    "4. BUTTONS",
    "5. Explain what 'staging' means when arriving at a fire/EMS scene.",
    "6. What is the difference between ALS and BLS?",
    "7. You arrive at a car crash. What steps do you take?",
    "8. You see a burning building. What are your priorities?",
    "9. You arrive at a scene with multiple victims. How do you triage?",
    "10. What does 'Code 0' mean in Fire/EMS?",
    "11. How do you handle roleplaying a patient refusing treatment?",
    "12. How would you roleplay smoke inhalation?",
    "13. What tools does a firefighter typically carry?",
    "14. What are the three sides of the fire triangle?",
    "15. How would you roleplay CPR?",
    "16. You’re first on scene to a vehicle fire. Walk through your actions.",
    "17. How do you roleplay dispatching an ambulance?",
    "18. You respond to a false alarm. How do you roleplay that?",
    "19. How would you RP burnout or exhaustion after a long shift?",
    "20. Why do you want to join SAFR?"
]

async def run_safr_application(user: discord.User, channel: discord.DMChannel):
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

