# =====================================================
# LSRP Network System™® — Application Bot (Clean Application System)
# - Original panel & DM flow preserved
# - Q4 uses buttons (all departments) with robust failsafes
# - Pre-step selectors (Platform; Sub-dept for PSO) + green confirmation embed
# - HQ swap (Verified -> Official) + remove Applicant roles on Accept
# - PS5 mirroring for SASP / BCSO same as PS4
# - /auth_grant unchanged (grants Verified + Official)
# =====================================================

import os
import random
import asyncio
import logging
from typing import List, Tuple, Optional, Dict

import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import View, Button, Select

# =====================================================
# LOGGING
# =====================================================
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("lsrp-application-bot")

# =====================================================
# CONFIG / CONSTANTS
# =====================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")  # set in Railway variables

# Guilds
HQ_GUILD_ID = 1324117813878718474
PS5_GUILD_ID = 1401903156274790441  # info only

# Channels
APPLICATION_PANEL_CHANNEL_ID = 1324115220725108877  # where panel auto-posts
APPLICATION_TIPS_CHANNEL = 1370854351828029470     # mention in panel body
STAFF_REVIEW_CHANNEL = 1366431401054048357         # where full apps go for review
CALLSIGN_LOG_CHANNEL = 1396076403052773396         # callsign logs (kept)

# Roles (HQ)
VERIFIED_ROLE_ID = 1367753287872286720
OFFICIAL_ROLE_ID = 1401961522556698739

# Sub-department roles (PS4 & PS5)
PS4_SASP_ROLE = 1401347813958226061
PS4_BCSO_ROLE = 1401347339796348938
PS5_SASP_ROLE = 1407034121808646269
PS5_BCSO_ROLE = 1407034123561734245

# Optional: explicit Applicant role IDs (leave [] to use name fallback: contains "applicant")
APPLICANT_ROLE_IDS: List[int] = []

# Panel banner (replace with your CDN link if needed)
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1324115220725108877/000000000000000000/banner.png"

# App timing
APPLICATION_TIMEOUT_SECS = 45 * 60  # 45 minutes window

# =====================================================
# DISCORD SETUP
# =====================================================
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="?", intents=intents)
tree = bot.tree

# =====================================================
# SECTION 1 — Persistent Application Panel
# =====================================================
class ApplicationPanel(View):
    """
    Permanent dropdown posted in the panel channel.
    Must have timeout=None and a fixed custom_id for persistence across restarts.
    """
    def __init__(self):
        super().__init__(timeout=None)
        self.select = Select(
            placeholder="Select a department to apply for...",
            custom_id="application_panel_select",  # required for persistence
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

        # Start the chosen application in DMs — original DM flow preserved
        try:
            dm = await interaction.user.create_dm()
        except Exception:
            return await interaction.response.send_message(
                "❌ I couldn't DM you. Please enable DMs and try again.", ephemeral=True
            )

        await interaction.response.send_message(
            f"✅ Starting your **{choice.upper()}** application in DMs…", ephemeral=True
        )

        if choice == "pso":
            await run_pso_application(interaction.user, dm)
        elif choice == "co":
            await run_co_application(interaction.user, dm)
        elif choice == "safr":
            await run_safr_application(interaction.user, dm)


async def post_panel(channel: discord.TextChannel):
    tips_mention = f"<#{APPLICATION_TIPS_CHANNEL}>"

    title = "## 📥 Los Santos Roleplay Network™® — Applications."
    intro = (
        "**Hello prospective members!**\n\n"
        "*We’re excited to have you on board—now it’s time to apply for access to our Main Server. "
        "This is your first step toward becoming a fully engaged member and jumping into the action!*\n\n"
        f"*For guidance, please head to {tips_mention} where you’ll find everything you need to know about the process.*"
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
    next_steps = (
        "### ⏳ What Happens Next?\n\n"
        "*Once you submit, staff will review your application and get back to you within 30 minutes.*\n"
        "Please keep your DMs open so the bot can message you with next steps."
    )
    choose = (
        "## 🧭 Choose Your Path.\n\n"
        "**Use the menu below to select your department:**\n"
        "• `PSO` — *Public Safety Office (Law Enforcement: BCSO / SASP)*\n"
        "• `CO` — *Civilian Operations (Civilian Roleplay)*\n"
        "• `SAFR` — *San Andreas Fire & Rescue (Fire & EMS)*"
    )

    embed = discord.Embed(
        description=f"{title}\n\n{intro}\n\n{tips}\n\n{next_steps}\n\n{choose}",
        color=discord.Color.blurple()
    )
    if PANEL_IMAGE_URL and "http" in PANEL_IMAGE_URL:
        embed.set_image(url=PANEL_IMAGE_URL)

    await channel.send(embed=embed, view=ApplicationPanel())

# =====================================================
# SECTION 2 — Q4 Buttons (robust + failsafes)
# =====================================================
class Q4Buttons(View):
    def __init__(self):
        super().__init__(timeout=120)
        self.choice: Optional[str] = None
        self._locked = False

    async def _finalize(self, interaction: discord.Interaction, value: str):
        if self._locked:
            try:
                if not interaction.response.is_done():
                    await interaction.response.defer()
            except Exception:
                pass
            return

        self._locked = True
        self.choice = value

        try:
            if not interaction.response.is_done():
                await interaction.response.defer()
        except Exception:
            pass

        try:
            self.disable_all_items()
            await interaction.message.edit(view=self)
        except Exception:
            try:
                await interaction.followup.send("Selection saved.", wait=True)
            except Exception:
                pass

        self.stop()

    @discord.ui.button(label="Friend", style=discord.ButtonStyle.blurple, custom_id="q4_friend")
    async def q4_friend(self, interaction: discord.Interaction, button: Button):
        await self._finalize(interaction, "Friend")

    @discord.ui.button(label="Instagram", style=discord.ButtonStyle.blurple, custom_id="q4_instagram")
    async def q4_instagram(self, interaction: discord.Interaction, button: Button):
        await self._finalize(interaction, "Instagram")

    @discord.ui.button(label="Partnership", style=discord.ButtonStyle.blurple, custom_id="q4_partnership")
    async def q4_partnership(self, interaction: discord.Interaction, button: Button):
        await self._finalize(interaction, "Partnership")

    @discord.ui.button(label="Other", style=discord.ButtonStyle.blurple, custom_id="q4_other")
    async def q4_other(self, interaction: discord.Interaction, button: Button):
        await self._finalize(interaction, "Other")


async def ask_q4_with_buttons(channel: discord.DMChannel, title: str, color: discord.Color) -> Optional[str]:
    """Send Q4 with buttons, return the chosen label or None on timeout."""
    view = Q4Buttons()
    msg = await channel.send(
        embed=discord.Embed(title=title, description="How did you find us?", color=color),
        view=view
    )
    try:
        await asyncio.wait_for(view.wait(), timeout=view.timeout or 120)
    except asyncio.TimeoutError:
        try:
            view.disable_all_items()
            await msg.edit(view=view)
        except Exception:
            pass
        return None
    return view.choice or None

# =====================================================
# SECTION 3 — Pre-Application Selectors (embedded)
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
# SECTION 4 — Questions (exact order preserved; Q4 handled by buttons)
# =====================================================
PSO_QUESTIONS = [
    "What is your Discord username?",
    "How old are you in real life?",
    "Please state your Date of Birth. (e.g., 16th June 2010)",
    "How did you find us? (Friend / Instagram / Partnership / Other)",  # Q4 (buttons)
    "Explain the 'No Life Rule' in the best of your ability.",
    "What does VDM, RDM, and FRP mean? Describe in the best of your ability.",
    "Do you have any roleplay experience, if so, please tell us.",
    "What time zone are you from? (e.g., GMT, EST, UTC etc.)",
    "Describe what a 10-11 means. In your own words.",
    "You see a suspect with a knife coming at you. What do you do?",
    "What does a 10-80 mean?",
    "How would you handle a 10-11?",
    "You arrive at a robbery scene, suspect yells 'I have a bomb!!' – what do you do next?",
    "What does Code 1, 2, and 3 mean?",
    "When you go on duty, what 10 codes do you use?",
    "As a cadet, are you eligible to drive on your own?",
    "You see a sniper on a hilltop. You have a pistol and radio. What do you do? (Min 20 words)",
    "How would you handle a noise complaint? (Min 20 words)",
    "Choose the correct cadet loadout.",
    "What is a 10-99?",
]

CIVILIAN_QUESTIONS = [
    "What is your Discord username?",
    "How old are you in real life?",
    "Please state your Date of Birth.",
    "How did you find us? (Friend / Instagram / Partnership / Other)",  # Q4 buttons
    "You are driving and run a red light. Police pull you over. How do you respond?",
    "What is FailRP? Explain with an example.",
    "What is FearRP? Explain with an example.",
    "You crash your vehicle into another. How do you handle it?",
    "Your character just lost their job. What are some legal RP scenarios you could pursue?",
    "What are three things civilians CANNOT do in roleplay?",
    "Explain the difference between passive RP and active RP.",
    "What are some examples of creative civilian roleplay scenes you would do?",
    "You are in a bank when a robbery happens. What do you do?",
    "If your character was drunk, how would you RP that realistically?",
    "You win the lottery in-game. What would your RP look like after that?",
    "Someone meta-games against you. How do you respond?",
    "How do you ensure you are not powergaming during a scene?",
    "What are some examples of realistic civilian crimes you could roleplay?",
    "How would you RP a court appearance or traffic ticket?",
    "Why do you want to be part of Civilian Operations?",
]

SAFR_QUESTIONS = [
    "What is your Discord username?",
    "How old are you in real life?",
    "Please state your Date of Birth.",
    "How did you find us? (Friend / Instagram / Partnership / Other)",  # Q4 buttons
    "Explain what 'staging' means when arriving at a fire/EMS scene.",
    "What is the difference between ALS and BLS?",
    "You arrive at a car crash. What steps do you take?",
    "You see a burning building. What are your priorities?",
    "You arrive at a scene with multiple victims. How do you triage?",
    "What does 'Code 0' mean in Fire/EMS?",
    "How do you handle roleplaying a patient refusing treatment?",
    "How would you roleplay smoke inhalation?",
    "What tools does a firefighter typically carry?",
    "What are the three sides of the fire triangle?",
    "How would you roleplay CPR?",
    "You’re first on scene to a vehicle fire. Walk through your actions.",
    "How do you roleplay dispatching an ambulance?",
    "You respond to a false alarm. How do you roleplay that?",
    "How would you RP burnout or exhaustion after a long shift?",
    "Why do you want to join SAFR?",
]

# =====================================================
# SECTION 5 — Helper functions: HQ swap, remove applicant, PS5 mirroring, callsigns
# =====================================================
async def remove_applicant_roles(member: discord.Member) -> bool:
    """Remove applicant role(s). Uses IDs if provided; else removes any role whose name contains 'applicant'."""
    removed = False
    if APPLICANT_ROLE_IDS:
        for rid in APPLICANT_ROLE_IDS:
            role = member.guild.get_role(rid)
            if role and role in member.roles:
                try:
                    await member.remove_roles(role, reason="Accepted: Remove Applicant role")
                    removed = True
                except Exception:
                    pass
    else:
        for role in list(member.roles):
            if "applicant" in (role.name or "").lower():
                try:
                    await member.remove_roles(role, reason="Accepted: Remove Applicant role (name match)")
                    removed = True
                except Exception:
                    pass
    return removed


async def hq_role_swap(member: discord.Member):
    """Swap HQ Verified -> Official (idempotent)."""
    verified = member.guild.get_role(VERIFIED_ROLE_ID)
    official = member.guild.get_role(OFFICIAL_ROLE_ID)
    if verified and verified in member.roles:
        try:
            await member.remove_roles(verified, reason="Accepted: Verified -> Official swap")
        except Exception:
            pass
    if official and official not in member.roles:
        try:
            await member.add_roles(official, reason="Accepted: grant Official")
        except Exception:
            pass


async def assign_ps_subdept(platform: str, subdept: str, member: discord.Member):
    """
    Assign SASP/BCSO in PS4 or PS5 guild — mirrors PS5 same as PS4.
    platform in {"PS4","PS5"}, subdept in {"SASP","BCSO"}
    """
    try:
        if platform.upper() == "PS4":
            if subdept.upper() == "SASP":
                await member.add_roles(discord.Object(id=PS4_SASP_ROLE), reason="Accepted: PS4 SASP")
            elif subdept.upper() == "BCSO":
                await member.add_roles(discord.Object(id=PS4_BCSO_ROLE), reason="Accepted: PS4 BCSO")
        elif platform.upper() == "PS5":
            if subdept.upper() == "SASP":
                await member.add_roles(discord.Object(id=PS5_SASP_ROLE), reason="Accepted: PS5 SASP")
            elif subdept.upper() == "BCSO":
                await member.add_roles(discord.Object(id=PS5_BCSO_ROLE), reason="Accepted: PS5 BCSO")
    except Exception:
        pass


async def assign_callsign(member: discord.Member, dept_label: str):
    """Optional nick + log (kept from your old behavior)."""
    num = random.randint(1000, 1999)
    callsign = f"C-{num} | {member.name}"
    try:
        await member.edit(nick=callsign)
    except Exception:
        pass
    ch = member.guild.get_channel(CALLSIGN_LOG_CHANNEL)
    if ch:
        try:
            await ch.send(f"📋 Callsign assigned: **{callsign}** → {member.mention} ({dept_label})")
        except Exception:
            pass

# =====================================================
# SECTION 6 — Shared question runner (Q4 uses buttons)
# =====================================================
async def ask_dept_questions(
    user: discord.User,
    channel: discord.DMChannel,
    dept_label: str,
    questions: List[str]
) -> Optional[List[Tuple[str, str]]]:
    """Shared runner for the 20 questions; Q4 handled with buttons."""
    await channel.send(
        embed=discord.Embed(
            title=f"Los Santos Roleplay Network™® | Application",
            description=f"Department selected: **{dept_label}**\n\n"
                        "I'll guide you through the application here in DMs.\n"
                        f"⏳ You have **{APPLICATION_TIMEOUT_SECS // 60} minutes** to complete all questions.\n"
                        "If your DMs are closed, please enable them and select again.",
            color=discord.Color.blurple()
        )
    )

    responses: List[Tuple[str, str]] = []
    start = discord.utils.utcnow()

    for i, q in enumerate(questions, start=1):
        if i == 4:
            answer = await ask_q4_with_buttons(channel, title=f"Q{i}", color=discord.Color.blurple())
            if answer is None:
                await channel.send("⏳ Timed out waiting for a selection. Please re-apply.")
                return None
            responses.append((f"Q{i}", answer))
            continue

        await channel.send(
            embed=discord.Embed(title=f"Q{i}", description=q, color=discord.Color.blurple())
        )

        def time_left_ok() -> bool:
            elapsed = (discord.utils.utcnow() - start).total_seconds()
            return elapsed < APPLICATION_TIMEOUT_SECS

        try:
            msg = await bot.wait_for(
                "message",
                timeout=max(30, APPLICATION_TIMEOUT_SECS - (discord.utils.utcnow() - start).total_seconds()),
                check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel)
            )
        except asyncio.TimeoutError:
            await channel.send("⏳ Application timed out. Please re-apply.")
            return None

        if not time_left_ok():
            await channel.send("⏳ Application window exceeded 45 minutes. Please re-apply.")
            return None

        responses.append((f"Q{i}", msg.content))

    return responses

# =====================================================
# SECTION 7 — DM Application Flows (pre-step selectors + confirmation embed)
# =====================================================
async def run_pso_application(user: discord.User, channel: discord.DMChannel) -> None:
    # Platform
    pview = PlatformSelect()
    await channel.send(
        embed=discord.Embed(
            title="Los Santos Roleplay Network™® | Application",
            description="Department selected: **PSO**\n\nPlease select your platform below.",
            color=discord.Color.blue()
        ),
        view=pview
    )
    await pview.wait()
    platform = pview.value or "Not selected"

    # Sub-department
    sview = SubDeptSelect()
    await channel.send(
        embed=discord.Embed(
            description="Please select your sub-department below.",
            color=discord.Color.blue()
        ),
        view=sview
    )
    await sview.wait()
    subdept = sview.value or "Not selected"

    # Confirmation
    confirm = discord.Embed(
        title="Application Details Confirmed",
        description=(f"**Department:** PSO\n"
                     f"**Sub-Department:** {subdept}\n"
                     f"**Platform:** {platform}\n\n"
                     "✅ Selections saved. I'll now begin your application questions.\n"
                     f"⏳ Time left: {APPLICATION_TIMEOUT_SECS // 60} minutes"),
        color=discord.Color.green()
    )
    await channel.send(embed=confirm)

    # Qs
    answers = await ask_dept_questions(user, channel, "PSO", PSO_QUESTIONS)
    if answers is None:
        return

    # Submit to staff review
    staff_ch = bot.get_channel(STAFF_REVIEW_CHANNEL)
    if not staff_ch:
        await channel.send("✅ Submitted. Staff will review shortly.")
        return

    embed = discord.Embed(title="📥 New PSO Application", color=discord.Color.blue())
    embed.set_author(name=str(user), icon_url=getattr(user.avatar, "url", discord.Embed.Empty))
    for q, a in answers:
        embed.add_field(name=q, value=a[:1024] if a else "—", inline=False)
    meta = {"dept": "PSO", "platform": platform, "subdept": subdept}
    await staff_ch.send(embed=embed, view=ReviewButtons(applicant_id=user.id, meta=meta))


async def run_co_application(user: discord.User, channel: discord.DMChannel) -> None:
    # Platform
    pview = PlatformSelect()
    await channel.send(
        embed=discord.Embed(
            title="Los Santos Roleplay Network™® | Application",
            description="Department selected: **Civilian Operations**\n\nPlease select your platform below.",
            color=discord.Color.green()
        ),
        view=pview
    )
    await pview.wait()
    platform = pview.value or "Not selected"

    # Confirmation
    confirm = discord.Embed(
        title="Application Details Confirmed",
        description=(f"**Department:** CO\n"
                     f"**Sub-Department:** N/A\n"
                     f"**Platform:** {platform}\n\n"
                     "✅ Selections saved. I'll now begin your application questions.\n"
                     f"⏳ Time left: {APPLICATION_TIMEOUT_SECS // 60} minutes"),
        color=discord.Color.green()
    )
    await channel.send(embed=confirm)

    # Qs
    answers = await ask_dept_questions(user, channel, "CO", CIVILIAN_QUESTIONS)
    if answers is None:
        return

    staff_ch = bot.get_channel(STAFF_REVIEW_CHANNEL)
    if not staff_ch:
        await channel.send("✅ Submitted. Staff will review shortly.")
        return

    embed = discord.Embed(title="📥 New Civilian Ops Application", color=discord.Color.green())
    embed.set_author(name=str(user), icon_url=getattr(user.avatar, "url", discord.Embed.Empty))
    for q, a in answers:
        embed.add_field(name=q, value=a[:1024] if a else "—", inline=False)
    meta = {"dept": "CO", "platform": platform}
    await staff_ch.send(embed=embed, view=ReviewButtons(applicant_id=user.id, meta=meta))


async def run_safr_application(user: discord.User, channel: discord.DMChannel) -> None:
    # Platform
    pview = PlatformSelect()
    await channel.send(
        embed=discord.Embed(
            title="Los Santos Roleplay Network™® | Application",
            description="Department selected: **San Andreas Fire & Rescue**\n\nPlease select your platform below.",
            color=discord.Color.red()
        ),
        view=pview
    )
    await pview.wait()
    platform = pview.value or "Not selected"

    # Confirmation
    confirm = discord.Embed(
        title="Application Details Confirmed",
        description=(f"**Department:** SAFR\n"
                     f"**Sub-Department:** N/A\n"
                     f"**Platform:** {platform}\n\n"
                     "✅ Selections saved. I'll now begin your application questions.\n"
                     f"⏳ Time left: {APPLICATION_TIMEOUT_SECS // 60} minutes"),
        color=discord.Color.red()
    )
    await channel.send(embed=confirm)

    # Qs
    answers = await ask_dept_questions(user, channel, "SAFR", SAFR_QUESTIONS)
    if answers is None:
        return

    staff_ch = bot.get_channel(STAFF_REVIEW_CHANNEL)
    if not staff_ch:
        await channel.send("✅ Submitted. Staff will review shortly.")
        return

    embed = discord.Embed(title="📥 New SAFR Application", color=discord.Color.red())
    embed.set_author(name=str(user), icon_url=getattr(user.avatar, "url", discord.Embed.Empty))
    for q, a in answers:
        embed.add_field(name=q, value=a[:1024] if a else "—", inline=False)
    meta = {"dept": "SAFR", "platform": platform}
    await staff_ch.send(embed=embed, view=ReviewButtons(applicant_id=user.id, meta=meta))

# =====================================================
# SECTION 8 — Staff Review Buttons (Accept / Deny)
# =====================================================
class ReviewButtons(View):
    def __init__(self, applicant_id: int, meta: Dict[str, str]):
        super().__init__(timeout=None)  # persist
        self.applicant_id = applicant_id
        self.meta = meta  # contains dept/platform/subdept

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.green, custom_id="review_accept")
    async def accept(self, interaction: discord.Interaction, button: Button):
        member = interaction.guild.get_member(self.applicant_id)
        if not member:
            await interaction.response.send_message("❌ Member not found in this guild.", ephemeral=True)
            return

        # Remove Applicant roles + HQ swap (Verified -> Official)
        await remove_applicant_roles(member)
        await hq_role_swap(member)

        # Sub-dept on PS4/PS5 if provided (PSO only normally)
        platform = (self.meta.get("platform") or "").upper()
        subdept = (self.meta.get("subdept") or "").upper()
        if platform in {"PS4", "PS5"} and subdept in {"SASP", "BCSO"}:
            await assign_ps_subdept(platform, subdept, member)

        # Callsign (kept)
        await assign_callsign(member, self.meta.get("dept", "Dept"))

        await interaction.response.send_message("✅ Applicant accepted.", ephemeral=True)
        self.disable_all_items()
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        try:
            user = await bot.fetch_user(self.applicant_id)
            await user.send("✅ Your application has been **accepted**! Welcome to Los Santos Roleplay Network™®.")
        except Exception:
            pass

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.red, custom_id="review_deny")
    async def deny(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("❌ Applicant denied.", ephemeral=True)
        self.disable_all_items()
        try:
            await interaction.message.edit(view=self)
        except Exception:
            pass

        try:
            user = await bot.fetch_user(self.applicant_id)
            await user.send("❌ Your application has been **denied**. You may re-apply after the cooldown.")
        except Exception:
            pass

# =====================================================
# SECTION 9 — /auth_grant (kept simple / same behavior)
# =====================================================
@tree.command(name="auth_grant", description="Grant access after application approval.")
@app_commands.describe(member="Member to authorize")
async def auth_grant(interaction: discord.Interaction, member: discord.Member):
    try:
        await member.add_roles(discord.Object(id=VERIFIED_ROLE_ID))
        await member.add_roles(discord.Object(id=OFFICIAL_ROLE_ID))
        await interaction.response.send_message(f"✅ {member.mention} authorized and roles applied.", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Failed: {e}", ephemeral=True)

# =====================================================
# SECTION 10 — Startup: persistent views + auto-post panel
# =====================================================
@bot.event
async def on_ready():
    # Keep dropdown & review buttons alive across restarts
    bot.add_view(ApplicationPanel())
    bot.add_view(ReviewButtons(applicant_id=0, meta={"dept": "N/A"}))  # registers class for persistence

    # Auto-post panel (only if not already present in recent history)
    ch = bot.get_channel(APPLICATION_PANEL_CHANNEL_ID)
    if isinstance(ch, discord.TextChannel):
        try:
            already = False
            async for msg in ch.history(limit=10):
                if msg.author == bot.user and msg.components:
                    already = True
                    break
            if not already:
                await post_panel(ch)
                log.info(f"✅ Posted application panel in #{ch.name}")
        except Exception as e:
            log.error(f"Panel post failed: {e}")
    else:
        log.warning("Panel channel not found or not a text channel.")

    log.info(f"✅ Application Bot ready as {bot.user} ({bot.user.id})")

# =====================================================
# RUN
# =====================================================
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set.")
    bot.run(BOT_TOKEN)
