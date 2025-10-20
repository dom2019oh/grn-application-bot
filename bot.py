# =====================================================
# Grant Roleplay Network™ — Application & Auth System
# Apple-Icy Blue Visual Upgrade (Glassmorphic Edition)
# =====================================================

# -------------------------
# Imports
# -------------------------
import os
import time
import random
import asyncio
import threading
import traceback
from typing import Dict, List, Tuple

import requests
import discord
from discord import app_commands, Embed, Object
from discord.ext import commands
from discord.ui import View, Select
from flask import Flask, request, redirect, render_template, render_template_string
import urllib.parse

# -------------------------
# Visual Theme
# -------------------------
GRN_COLOR = discord.Color.from_rgb(100, 180, 255)  # Icy-blue accent
FOOTER_TEXT = "Grant Roleplay Network™ • Apply Smart • Play Realistic"

# -------------------------
# Core IDs / Guilds / Channels (GRN HQ)
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# Guilds
HQ_GUILD_ID  = 1421153253797924969   # GRN HQ
PS4_GUILD_ID = int(os.getenv("PS4_GUILD_ID", "1324117813878718474"))
PS5_GUILD_ID = int(os.getenv("PS5_GUILD_ID", "1401903156274790441"))
XBOX_OG_GUILD_ID = int(os.getenv("XBOX_OG_GUILD_ID", "1375494043831898334"))

PLATFORM_GUILDS = {
    "PS4":    PS4_GUILD_ID,
    "PS5":    PS5_GUILD_ID,
    "XboxOG": XBOX_OG_GUILD_ID,
}

# Channels (GRN HQ)
APP_REVIEW_CHANNEL_ID    = 1421155155717394554
APPLICATION_TIPS_CHANNEL = 1421155134364319758
PANEL_CHANNEL_ID         = 1421155133185724557
AUTH_CODE_LOG_CHANNEL    = 1421155191780151357
DECISION_LOG_CHANNEL     = 1421155157588181202

# Staff role (GRN HQ) to operate panel/auth
STAFF_CAN_POST_PANEL_ROLE = 1421154927907966996

# Applicant / Pending / Denied roles (HQ)
ROLE_PENDING    = 1421154999001681982
ROLE_DENIED_12H = 1421155002789134448
ROLE_VERIFIED   = 1421154985315667999   # Verified Member
ROLE_OFFICIAL   = 1421154984556232825   # Official Member

# Applicant roles (HQ) — dept + platform
APPLICANT_DEPT_ROLES = {
    "PSO":  1421154995272814677,
    "CO":   1421154996531237053,
    "SAFR": 1421154997575483577,
}
APPLICANT_PLATFORM_ROLES = {
    "PS4":    1421154989920882791,
    "PS5":    1421154992466825346,
    "XboxOG": 1421154994186354770,
}

# Accepted (platform) roles — HQ
ACCEPTED_PLATFORM_ROLES = {
    "PS4":    1421154988721176727,
    "PS5":    1421154991019790510,
    "XboxOG": 1421154993590763591,
}

# PSO subdept roles (PS4 & PS5 mirror)
ROLE_SASP_PS4 = 1401347813958226061
ROLE_BCSO_PS4 = 1401347339796348938
ROLE_SASP_PS5 = 1407034121808646269
ROLE_BCSO_PS5 = 1407034123561734245

# -------------------------
# PS4 department structure
# -------------------------
ROLE_SASP_CATEGORY_PS4 = 1404575562290434190
ROLE_BCSO_CATEGORY_PS4 = 1375046520469979256
ROLE_SASP_CADET_PS4    = 1375046543329202186
ROLE_BCSO_PROB_PS4     = 1404903885432164362
ROLE_CO_MAIN_PS4       = 1375046547678429195
ROLE_CO_CATEGORY_PS4   = 1375046548747980830
ROLE_CO_STARTER_PS4    = 1375046566150406155
ROLE_SAFR_MAIN_PS4     = 1401347818873946133
ROLE_SAFR_CATEGORY_PS4 = 1375046571653201961
ROLE_SAFR_STARTER_PS4  = 1375046583153856634

# -------------------------
# PS5 department structure
# -------------------------
ROLE_SASP_CATEGORY_PS5 = 1407034075532886172
ROLE_BCSO_CATEGORY_PS5 = 1407034086945587332
ROLE_SASP_CADET_PS5    = 1407034074190708816
ROLE_BCSO_PROB_PS5     = 1407034085917986999
ROLE_CO_MAIN_PS5       = 1407034124648317079
ROLE_CO_CATEGORY_PS5   = 1407034105345872023
ROLE_CO_STARTER_PS5    = 1407034103978655757
ROLE_SAFR_MAIN_PS5     = 1407034125713408053
ROLE_SAFR_CATEGORY_PS5 = 1407034115311669409
ROLE_SAFR_STARTER_PS5  = 1407034114082738178

# -------------------------
# Visuals (banners / gifs)
# -------------------------
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1421126179934568578/1422535377926881330/GRN_-_Application_Panel_Banner_.gif"
ACCEPT_GIF_URL  = "https://media.discordapp.net/attachments/1421126179934568578/1422535637873201173/GRN_-_HQ_Banner_1.gif"

# -------------------------
# OAuth Configuration
# -------------------------
CLIENT_ID     = os.getenv("CLIENT_ID") or "1397974568706117774"
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or "KcaapGwCEsH_JDlIbrAX3lghSC-tDREN"
REDIRECT_URI  = "https://auth.grantrp.com/auth"

# -------------------------
# Timing / Expiry
# -------------------------
APP_TOTAL_TIME_SECONDS = 35 * 60  # 35 minutes per application
CODE_TTL_SECONDS       = 5 * 60   # 5 minutes per auth code

# -------------------------
# Bot Setup
# -------------------------
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# -------------------------
# In-memory Stores
# -------------------------
app_sessions: Dict[int, dict]  = {}  # Application progress
pending_codes: Dict[int, dict] = {}  # Pending auth codes

# =====================================================
# Utility Helpers / Core Logic
# =====================================================

# -------------------------
# Helper Functions
# -------------------------
def dept_color(dept: str) -> discord.Color:
    """Return department-specific accent color."""
    if dept == "PSO": 
        return GRN_COLOR
    if dept == "CO":  
        return discord.Color.from_rgb(130, 255, 180)
    if dept == "SAFR": 
        return discord.Color.from_rgb(255, 140, 100)
    return GRN_COLOR

def readable_remaining(deadline: float) -> str:
    left = max(0, int(deadline - time.time()))
    m, s = divmod(left, 60)
    return f"{m}m {s}s"

async def report_interaction_error(interaction: discord.Interaction | None, err: Exception, prefix: str):
    """Graceful error reporting."""
    print(prefix, "".join(traceback.format_exception(type(err), err, err.__traceback__)))
    try:
        if interaction:
            msg = "❌ An unexpected error occurred. Staff has been notified."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)
    except Exception:
        pass
    try:
        ch = bot.get_channel(AUTH_CODE_LOG_CHANNEL)
        if ch:
            await ch.send(f"**{prefix}**\n```py\n{repr(err)}\n```")
    except Exception:
        pass

# =====================================================
# Panel UI Elements
# =====================================================

class SafeView(View):
    """View subclass with global error trap."""
    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        await report_interaction_error(interaction, error, f"View error in '{getattr(item,'custom_id',getattr(item,'label','?'))}'")

# -------------------------
# Platform Select Dropdown
# -------------------------
class PlatformSelect(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder="Select your platform…",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="PlayStation 5", value="PS5",
                    emoji=discord.PartialEmoji(name="ps5", id=1421416176377925672)
                ),
                discord.SelectOption(
                    label="PlayStation 4", value="PS4",
                    emoji=discord.PartialEmoji(name="ps4", id=1421207705682448415)
                ),
                discord.SelectOption(
                    label="Xbox Old Gen", value="XboxOG",
                    emoji=discord.PartialEmoji(name="xbox", id=1421415600219230310)
                ),
            ],
            custom_id=f"platform_select_{user_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        sess = app_sessions.get(self.user_id)
        if not sess or interaction.user.id != self.user_id:
            return await interaction.response.send_message("This selector isn’t for you.", ephemeral=True)
        sess["platform"] = self.values[0]
        await interaction.response.edit_message(view=None)
        self.view.stop()

class PlatformSelectView(SafeView):
    def __init__(self, user_id: int, *, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.add_item(PlatformSelect(user_id))

# -------------------------
# Sub-Department Select Dropdown (PSO)
# -------------------------
class SubdeptSelect(discord.ui.Select):
    def __init__(self, user_id: int):
        self.user_id = user_id
        super().__init__(
            placeholder="Select PSO Sub-Department…",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(
                    label="SASP (San Andreas State Police)",
                    value="SASP",
                    emoji=discord.PartialEmoji(name="sasp", id=1429130587926565017)
                ),
                discord.SelectOption(
                    label="BCSO (Blaine County Sheriff’s Office)",
                    value="BCSO",
                    emoji=discord.PartialEmoji(name="bcso", id=1429129827495182459)
                ),
            ],
            custom_id=f"subdept_select_{user_id}"
        )

    async def callback(self, interaction: discord.Interaction):
        sess = app_sessions.get(self.user_id)
        if not sess or interaction.user.id != self.user_id:
            return await interaction.response.send_message("This selector isn’t for you.", ephemeral=True)
        sess["subdept"] = self.values[0]
        await interaction.response.edit_message(view=None)
        self.view.stop()

class SubdeptSelectView(SafeView):
    def __init__(self, user_id: int, *, timeout: float = 120):
        super().__init__(timeout=timeout)
        self.add_item(SubdeptSelect(user_id))

# -------------------------
# Department Dropdown (Menu at Panel)
# -------------------------
class DepartmentSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Choose your department…",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(
                    label="Public Safety Office (PSO)", value="PSO",
                    emoji=discord.PartialEmoji(name="pso", id=1421545956901650584)
                ),
                discord.SelectOption(
                    label="Civilian Operations (CO)", value="CO",
                    emoji=discord.PartialEmoji(name="civ", id=1429127933573730464)
                ),
                discord.SelectOption(
                    label="San Andreas Fire & Rescue (SAFR)", value="SAFR",
                    emoji=discord.PartialEmoji(name="safr", id=1421561107037814835)
                ),
            ],
            custom_id="grn_app_panel_dept_select"
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer(ephemeral=True)
            dept = self.values[0]
            user = interaction.user
            app_sessions[user.id] = {
                "dept": dept,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "answers": [],
                "started_at": time.time(),
                "deadline": time.time() + APP_TOTAL_TIME_SECONDS,
                "platform": None,
                "subdept": "N/A",
            }
            color = dept_color(dept)
            dm = await user.create_dm()

            intro = Embed(
                title="📋 Grant Roleplay Network™ — Application",
                description=f"Department selected: **{dept}**\n\nBefore we start, please confirm a few details below.",
                color=color
            ).set_footer(text=FOOTER_TEXT)
            await dm.send(embed=intro)

            # Platform select
            plat_embed = Embed(
                title="Select Platform",
                description="Choose your **platform** below.",
                color=color
            ).set_footer(text=FOOTER_TEXT)
            plat_view = PlatformSelectView(user.id)
            plat_msg = await dm.send(embed=plat_embed, view=plat_view)
            plat_timeout = await plat_view.wait()
            if plat_timeout or not app_sessions[user.id].get("platform"):
                await dm.send("⏳ Selector timed out. Please select from the panel again.")
                app_sessions.pop(user.id, None)
                return
            await plat_msg.edit(embed=Embed(
                title="Select Platform",
                description=f"✅ **Platform selected:** `{app_sessions[user.id]['platform']}`",
                color=discord.Color.green()
            ).set_footer(text=FOOTER_TEXT), view=None)

            # PSO sub-dept if needed
            if dept == "PSO":
                sub_embed = Embed(
                    title="Select PSO Sub-Department",
                    description="Choose your **PSO Sub-Department** below.",
                    color=color
                ).set_footer(text=FOOTER_TEXT)
                sub_view = SubdeptSelectView(user.id)
                sub_msg = await dm.send(embed=sub_embed, view=sub_view)
                sub_timeout = await sub_view.wait()
                if sub_timeout or not app_sessions[user.id].get("subdept") or app_sessions[user.id]["subdept"] == "N/A":
                    await dm.send("⏳ Selector timed out. Please select from the panel again.")
                    app_sessions.pop(user.id, None)
                    return
                await sub_msg.edit(embed=Embed(
                    title="Select PSO Sub-Department",
                    description=f"✅ **Sub-Department selected:** `{app_sessions[user.id]['subdept']}`",
                    color=discord.Color.green()
                ).set_footer(text=FOOTER_TEXT), view=None)

            sess = app_sessions[user.id]
            confirm = Embed(
                title="✅ Application Details Confirmed",
                description="Selections saved. I’ll now begin your application questions.",
                color=color
            )
            confirm.add_field(name="Department", value=sess["dept"], inline=False)
            confirm.add_field(name="Sub-Department", value=sess.get("subdept","N/A"), inline=False)
            confirm.add_field(name="Platform", value=sess.get("platform","N/A"), inline=False)
            confirm.set_footer(text=f"{FOOTER_TEXT} | Time left: {readable_remaining(sess['deadline'])}")
            await dm.send(embed=confirm)

            await run_questions(user)
            await interaction.followup.send("📬 I’ve sent you a DM to continue your application.", ephemeral=True)

        except discord.Forbidden:
            msg="⚠️ I couldn’t DM you. Please enable DMs and select again."
            if interaction.response.is_done(): await interaction.followup.send(msg, ephemeral=True)
            else: await interaction.response.send_message(msg, ephemeral=True)
        except Exception as e:
            await report_interaction_error(interaction, e, "DepartmentSelect callback failed")

class ApplicationPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DepartmentSelect())

# -------------------------
# Application Panel Embed (Front Panel)
# -------------------------
async def post_panel(channel: discord.TextChannel):
    tips_channel_mention = f"<#{APPLICATION_TIPS_CHANNEL}>"

    title = "## Grant Roleplay Network™ — Application Center"
    intro = (
        "> **Welcome to the GRN HQ Application Portal.**\n\n"
        "We’re thrilled to have you here. This is your first step toward "
        "accessing our main servers and becoming an official member of the network.\n\n"
        f"For additional guidance, visit {tips_channel_mention} before applying."
    )
    tips = (
        "### Before You Begin\n"
        "1️⃣ **Read the Rules** — ensure you understand all community standards.\n"
        "2️⃣ **Take Your Time** — provide detailed, honest answers.\n"
        "3️⃣ **Be Authentic** — experience isn’t required; attitude is.\n"
    )
    what_next = (
        "### What Happens After Submission\n"
        "Once submitted, our staff will review your application within **30 minutes**.\n"
        "Please keep your **DMs open** to receive updates about your status."
    )
    choose_path = (
        "## Choose Your Department\n"
        "Use the dropdown below to begin your application:\n"
        "• `PSO` — *Public Safety Office (Law Enforcement: BCSO / SASP)*\n"
        "• `CO` — *Civilian Operations (Civilian Roleplay)*\n"
        "• `SAFR` — *San Andreas Fire & Rescue (Fire & EMS)*"
    )

    embed = discord.Embed(
        description=f"{title}\n\n{intro}\n\n{tips}\n\n{what_next}\n\n{choose_path}",
        color=GRN_COLOR
    )
    embed.set_image(url=PANEL_IMAGE_URL)
    embed.set_footer(text=FOOTER_TEXT)
    await channel.send(embed=embed, view=ApplicationPanel())

# =====================================================
# Section 3 — Department Questions, DM Flow & Review System
# =====================================================

# -------------------------
# Department Question Sets
# -------------------------
COMMON_4 = [
    ("Q1",  "What's your Discord username? (e.g. officialdom2019og)"),
    ("Q2",  "How old are you in real life?"),
    ("Q3",  "What's your real Date of Birth? (e.g. 16th June 2010)"),
    ("Q4",  "How did you find us? (Instagram / TikTok / Partnership / Friend / Other)"),
]

PSO_SPECIFIC_16 = [
    ("Q5",  "What attracts you to Public Safety work within Grant Roleplay?"),
    ("Q6",  "Do you have prior law enforcement RP experience? If yes, where and what rank?"),
    ("Q7",  "Explain the difference between BCSO and SASP jurisdictions."),
    ("Q8",  "Scenario: First on a shots-fired scene with civilians nearby. What’s your immediate plan?"),
    ("Q9",  "Rate your radio discipline 1–10 and explain."),
    ("Q10", "Confirm you’ll follow all PSO SOPs and sub-department rules. (Yes/No + any comments)"),
    ("Q11", "List three traffic-stop safety steps you always follow."),
    ("Q12", "When should lethal force be considered appropriate?"),
    ("Q13", "How do you de-escalate a hostile subject during a stop?"),
    ("Q14", "Describe how you’d coordinate with another unit during a pursuit."),
    ("Q15", "How do you handle chain-of-command disagreements in-session?"),
    ("Q16", "What’s your approach to scene containment and perimeter setup?"),
    ("Q17", "Name two examples of power-gaming to avoid as LEO."),
    ("Q18", "How do you balance realistic RP with server pacing?"),
    ("Q19", "A fellow officer violates SOP mid-scene. What do you do?"),
    ("Q20", "What’s your long-term goal inside PSO (training, supervision, specialty units)?"),
]

CO_SPECIFIC_16 = [
    ("Q5",  "What kinds of civilian stories do you enjoy (legal / illegal / entrepreneur)?"),
    ("Q6",  "How do you avoid low-effort or chaotic RP while keeping it engaging?"),
    ("Q7",  "Describe a creative civilian scene you’ve run or want to run here."),
    ("Q8",  "Are you comfortable with passive RP (dialogue / world-building)? Why?"),
    ("Q9",  "What conflicts should civilians avoid initiating and why?"),
    ("Q10", "Confirm you’ll follow all CO guidelines. (Yes/No + any comments)"),
    ("Q11", "What’s your approach to building a civilian character background?"),
    ("Q12", "How do you RP consequences after illegal activities?"),
    ("Q13", "Give an example of a non-violent conflict you’d like to portray."),
    ("Q14", "How do you keep civilian RP fun for others on slow nights?"),
    ("Q15", "Explain metagaming and how you avoid it as a civilian."),
    ("Q16", "How do you signal intent OOC when coordination is needed (without breaking immersion)?"),
    ("Q17", "What’s a good reason to call for emergency services from a civilian POV?"),
    ("Q18", "How will you use businesses or public locations to spark roleplay?"),
    ("Q19", "When would you step back and let another player lead a scene?"),
    ("Q20", "Your long-term CO goals (gang mgmt, business owner, advisor, etc.)?"),
]

SAFR_SPECIFIC_16 = [
    ("Q5",  "Why do you want to join San Andreas Fire & Rescue?"),
    ("Q6",  "Any prior Fire/EMS RP? Certifications or knowledge to share?"),
    ("Q7",  "Scenario: Multi-vehicle collision with fire & multiple injured. First three priorities?"),
    ("Q8",  "Are you comfortable with medical RP steps (triage / BLS)?"),
    ("Q9",  "What does teamwork mean to you in emergency services?"),
    ("Q10", "Confirm you’ll follow all SAFR protocols. (Yes/No + any comments)"),
    ("Q11", "How do you assess scene safety before entering a structure?"),
    ("Q12", "When would you call for additional alarms or mutual aid?"),
    ("Q13", "Explain basic triage tags and how you’d apply them."),
    ("Q14", "Describe the hand-off to EMS or hospital in RP."),
    ("Q15", "How do you communicate with LEO at a chaotic fire scene?"),
    ("Q16", "What tools or equipment would you mention during a structure-fire RP?"),
    ("Q17", "How do you portray fatigue or limitations realistically in long scenes?"),
    ("Q18", "What’s your approach to patient consent and refusal scenarios?"),
    ("Q19", "How would you handle conflicting commands from multiple supervisors?"),
    ("Q20", "Your long-term SAFR goals (EMS specialization, officer track, training)?"),
]

DEPT_QUESTIONS = {
    "PSO":  COMMON_4 + PSO_SPECIFIC_16,
    "CO":   COMMON_4 + CO_SPECIFIC_16,
    "SAFR": COMMON_4 + SAFR_SPECIFIC_16,
}

# -------------------------
# DM Question Flow
# -------------------------
async def run_questions(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess:
        return

    dept = sess["dept"]
    questions = DEPT_QUESTIONS[dept]
    deadline = sess["deadline"]
    color = dept_color(dept)
    dm = await user.create_dm()

    for qkey, qtext in questions:
        if time.time() > deadline:
            await dm.send(embed=Embed(
                title="⏳ Time Expired",
                description="Your application time has expired (35 minutes). Please start again from the panel.",
                color=discord.Color.orange()
            ).set_footer(text=FOOTER_TEXT))
            return

        e = Embed(title=qkey, description=f"{qtext}\n\n_Time remaining: **{readable_remaining(deadline)}**_", color=color)
        e.set_footer(text=FOOTER_TEXT)
        await dm.send(embed=e)

        def check(m: discord.Message):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

        try:
            remaining = max(1, int(deadline - time.time()))
            timeout = min(remaining, 300)  # 5 minutes per question max
            msg = await bot.wait_for("message", check=check, timeout=timeout)
            sess["answers"].append((qtext, msg.content.strip()))
        except asyncio.TimeoutError:
            await dm.send(embed=Embed(
                title="⏳ Time Expired",
                description="Your application timed out. Please start again from the panel.",
                color=discord.Color.orange()
            ).set_footer(text=FOOTER_TEXT))
            return

    await post_review(user)

# -------------------------
# Review System (Accept / Deny)
# -------------------------
class ReviewButtons(SafeView):
    def __init__(self, applicant: discord.User, dept: str):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.dept = dept

    async def _log_decision(self, staff: discord.Member, decision: str, color: discord.Color):
        ch = bot.get_channel(DECISION_LOG_CHANNEL)
        if not ch:
            return
        embed = Embed(
            title=f"📋 Application Decision — {decision}",
            color=color,
            description=(
                f"**Applicant:** {self.applicant.mention} (`{self.applicant.id}`)\n"
                f"**Department:** {self.dept}\n"
                f"**Staff Member:** {staff.mention}\n"
                f"**Decision Time:** <t:{int(time.time())}:f>"
            )
        ).set_footer(text=FOOTER_TEXT)
        await ch.send(embed=embed)

    # ---------- Accept ----------
    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id="review_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            for child in self.children: child.disabled = True
            await interaction.message.edit(view=self)

            try:
                e = Embed(
                    title="🎉 Application Accepted",
                    description=(
                        f"Congratulations! You’ve been **accepted** into {self.dept}.\n\n"
                        "A staff member will issue you a **one-time 6-digit verification code** soon.\n"
                        "⚠️ Keep your DMs **open** — the code expires in **5 minutes** once sent."
                    ),
                    color=GRN_COLOR
                )
                e.add_field(
                    name="Next Steps",
                    value="• Wait for staff to issue your code.\n• Do not share it.\n• Complete verification for main-server access.",
                    inline=False
                )
                e.add_field(
                    name="Expectations",
                    value="• Follow all community regulations and SOPs.\n• Be respectful and professional.\n• You’ll receive full access after verification.",
                    inline=False
                )
                e.set_footer(text=FOOTER_TEXT)
                await self.applicant.send(embed=e)
            except Exception:
                await interaction.followup.send("⚠️ Couldn’t DM the applicant (DMs likely closed).", ephemeral=True)

            await self._log_decision(interaction.user, "Accepted", GRN_COLOR)
            await interaction.followup.send(f"✅ Accepted {self.applicant.mention}", ephemeral=True)
        except Exception as e:
            await report_interaction_error(interaction, e, "Accept button failed")

    # ---------- Deny ----------
    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="review_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)
            for child in self.children: child.disabled = True
            await interaction.message.edit(view=self)

            try:
                e = Embed(
                    title="❌ Application Denied",
                    description="Unfortunately, your application was **denied**.\n\nYou may reapply after **12 hours**. \nPlease review the rules before resubmitting.",
                    color=discord.Color.red()
                ).set_footer(text=FOOTER_TEXT)
                await self.applicant.send(embed=e)
            except Exception:
                await interaction.followup.send("⚠️ Couldn’t DM the applicant (DMs likely closed).", ephemeral=True)

            await self._log_decision(interaction.user, "Denied", discord.Color.red())
            await interaction.followup.send(f"❌ Denied {self.applicant.mention}", ephemeral=True)
        except Exception as e:
            await report_interaction_error(interaction, e, "Deny button failed")

# -------------------------
# Post Review Embed (Sent to Staff)
# -------------------------
async def post_review(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess:
        return

    dept = sess.get("dept", "N/A")
    color = dept_color(dept)
    platform = sess.get("platform", "N/A")
    subdept = sess.get("subdept", "N/A")

    review = Embed(
        title="📂 New Application Submitted",
        color=color,
        description=(
            f"**Applicant:** {user.mention} (`{user.id}`)\n"
            f"**Department:** {dept}\n"
            f"**Sub-Department:** {subdept}\n"
            f"**Platform:** {platform}\n"
        )
    ).set_footer(text=FOOTER_TEXT)

    for idx, (q, a) in enumerate(sess.get("answers", []), start=1):
        name = f"Q{idx}: {q}"
        if len(name) > 256: name = name[:253] + "…"
        review.add_field(name=name, value=(a[:1000] if a else "—"), inline=False)

    ch = bot.get_channel(APP_REVIEW_CHANNEL_ID)
    if ch:
        await ch.send(embed=review, view=ReviewButtons(user, dept))

    try:
        await user.send(embed=Embed(
            title="📋 Application Status",
            description="✅ **Application Submitted**\nYour application has been delivered to staff for review. You’ll receive a DM once a decision is made.",
            color=color
        ).set_footer(text=FOOTER_TEXT))
    except Exception:
        pass

    app_sessions.pop(user.id, None)

# =====================================================
# Section 4 — Role Assignment System & /auth_grant Command
# =====================================================

# -------------------------
# PS4 Role Assignment (Mirrored)
# -------------------------
async def assign_ps_roles_ps4(member: discord.Member, dept: str, subdept: str | None):
    """Assign starter roles + callsign for PS4 department."""
    to_add: list[discord.Role] = []

    if dept == "PSO":
        sd = (subdept or "").upper()
        if sd == "SASP":
            for rid in (ROLE_SASP_CATEGORY_PS4, ROLE_SASP_PS4, ROLE_SASP_CADET_PS4):
                if r := member.guild.get_role(rid):
                    to_add.append(r)
        elif sd == "BCSO":
            for rid in (ROLE_BCSO_CATEGORY_PS4, ROLE_BCSO_PS4, ROLE_BCSO_PROB_PS4):
                if r := member.guild.get_role(rid):
                    to_add.append(r)
        try:
            await member.edit(nick=f"C-{random.randint(1000,1999)} | {member.name}", reason="Initial PSO callsign (PS4)")
        except Exception:
            pass

    elif dept == "CO":
        for rid in (ROLE_CO_MAIN_PS4, ROLE_CO_CATEGORY_PS4, ROLE_CO_STARTER_PS4):
            if r := member.guild.get_role(rid):
                to_add.append(r)
        try:
            await member.edit(nick=f"CIV-{random.randint(1000,1999)} | {member.name}", reason="Initial CO callsign (PS4)")
        except Exception:
            pass

    elif dept == "SAFR":
        for rid in (ROLE_SAFR_MAIN_PS4, ROLE_SAFR_CATEGORY_PS4, ROLE_SAFR_STARTER_PS4):
            if r := member.guild.get_role(rid):
                to_add.append(r)
        try:
            await member.edit(nick=f"FF-{random.randint(100,999)} | {member.name}", reason="Initial SAFR callsign (PS4)")
        except Exception:
            pass

    if to_add:
        try:
            await member.add_roles(*to_add, reason="Initial department roles (PS4)")
        except Exception:
            pass
    elif dept == "PSO":
        hq = bot.get_guild(HQ_GUILD_ID)
        if hq and (ch := hq.get_channel(AUTH_CODE_LOG_CHANNEL)):
            await ch.send("⚠️ PSO role assignment skipped on PS4 — verify SASP/BCSO role IDs.")


# -------------------------
# PS5 Role Assignment (Mirrored)
# -------------------------
async def assign_ps_roles_ps5(member: discord.Member, dept: str, subdept: str | None):
    """Assign starter roles + callsign for PS5 department."""
    to_add: list[discord.Role] = []

    if dept == "PSO":
        sd = (subdept or "").upper()
        if sd == "SASP":
            for rid in (ROLE_SASP_CATEGORY_PS5, ROLE_SASP_PS5, ROLE_SASP_CADET_PS5):
                if r := member.guild.get_role(rid):
                    to_add.append(r)
        elif sd == "BCSO":
            for rid in (ROLE_BCSO_CATEGORY_PS5, ROLE_BCSO_PS5, ROLE_BCSO_PROB_PS5):
                if r := member.guild.get_role(rid):
                    to_add.append(r)
        try:
            await member.edit(nick=f"C-{random.randint(1000,1999)} | {member.name}", reason="Initial PSO callsign (PS5)")
        except Exception:
            pass

    elif dept == "CO":
        for rid in (ROLE_CO_MAIN_PS5, ROLE_CO_CATEGORY_PS5, ROLE_CO_STARTER_PS5):
            if r := member.guild.get_role(rid):
                to_add.append(r)
        try:
            await member.edit(nick=f"CIV-{random.randint(1000,1999)} | {member.name}", reason="Initial CO callsign (PS5)")
        except Exception:
            pass

    elif dept == "SAFR":
        for rid in (ROLE_SAFR_MAIN_PS5, ROLE_SAFR_CATEGORY_PS5, ROLE_SAFR_STARTER_PS5):
            if r := member.guild.get_role(rid):
                to_add.append(r)
        try:
            await member.edit(nick=f"FF-{random.randint(100,999)} | {member.name}", reason="Initial SAFR callsign (PS5)")
        except Exception:
            pass

    if to_add:
        try:
            await member.add_roles(*to_add, reason="Initial department roles (PS5)")
        except Exception:
            pass
    elif dept == "PSO":
        hq = bot.get_guild(HQ_GUILD_ID)
        if hq and (ch := hq.get_channel(AUTH_CODE_LOG_CHANNEL)):
            await ch.send("⚠️ PSO role assignment skipped on PS5 — verify SASP/BCSO role IDs.")


# -------------------------
# /auth_grant Command — Generate 6-Digit Code
# -------------------------
@tree.command(name="auth_grant", description="Generate a one-time 6-digit auth code (expires in 5 minutes).")
@app_commands.describe(
    user="The applicant to authorize",
    department="Department (PSO / CO / SAFR)",
    platform="Platform (PS4 / PS5 / XboxOG)",
    subdept="Optional sub-department for PSO (SASP / BCSO)"
)
@app_commands.choices(department=[
    app_commands.Choice(name="PSO", value="PSO"),
    app_commands.Choice(name="CO", value="CO"),
    app_commands.Choice(name="SAFR", value="SAFR"),
])
@app_commands.choices(platform=[
    app_commands.Choice(name="PS4", value="PS4"),
    app_commands.Choice(name="PS5", value="PS5"),
    app_commands.Choice(name="XboxOG", value="XboxOG"),
])
async def auth_grant(
    interaction: discord.Interaction,
    user: discord.Member,
    department: app_commands.Choice[str],
    platform: app_commands.Choice[str],
    subdept: str | None = None
):
    try:
        # Permission check
        if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in getattr(interaction.user, "roles", [])):
            return await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        code = random.randint(100000, 999999)
        pending_codes[user.id] = {
            "code": code,
            "timestamp": time.time(),
            "dept": department.value,
            "platform": platform.value,
            "subdept": (subdept or "").upper() if department.value == "PSO" else "N/A",
        }

        # Log generation
        if hq := bot.get_guild(HQ_GUILD_ID):
            if log_ch := hq.get_channel(AUTH_CODE_LOG_CHANNEL):
                await log_ch.send(
                    f"🔐 **Auth Code Generated**\n"
                    f"User: {user.mention} (`{user.id}`)\n"
                    f"Department: `{department.value}` | Platform: `{platform.value}` | Subdept: `{pending_codes[user.id]['subdept']}`\n"
                    f"Code: **{code}** (expires in 5 minutes)\n"
                    f"Granted by: {interaction.user.mention}"
                )

        # DM applicant
        try:
            e = Embed(
                title="🔐 Grant Roleplay Network™ — Authorization",
                description=(
                    f"**Your one-time 6-digit code:** `{code}`\n"
                    "Use this code on the verification page below. Once redeemed, it becomes invalid.\n\n"
                    f"[Click here to Verify]({REDIRECT_URI})"
                ),
                color=GRN_COLOR
            )
            e.set_image(url=ACCEPT_GIF_URL)
            e.set_footer(text=FOOTER_TEXT)
            v = SafeView()
            v.add_item(discord.ui.Button(label="Open Verification", url=REDIRECT_URI, style=discord.ButtonStyle.link))
            await user.send(embed=e, view=v)
        except Exception:
            await interaction.followup.send("⚠️ Couldn’t DM the applicant (DMs likely closed).", ephemeral=True)

        await interaction.followup.send(f"✅ Code sent to {user.mention}'s DMs.", ephemeral=True)

    except Exception as e:
        await report_interaction_error(interaction, e, "auth_grant failed")

# =====================================================
# Section 5+ — Full Web Auth (Glassmorphism + OAuth2 Auto-Join)
# =====================================================

flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "✅ Grant Roleplay Network™ Auth Service is running."

# -------------------------
# Glassmorphic HTML Page
# -------------------------
_HTML_FORM = """
<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Grant Roleplay Network™ — Authorization</title>
<style>
  html,body {
    margin:0; height:100%; overflow:hidden;
    font-family:-apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  }
  video.bg {
    position:fixed; top:0; left:0; width:100%; height:100%;
    object-fit:cover; z-index:-2;
    filter:blur(8px) brightness(0.8) saturate(120%);
  }
  .overlay {
    position:fixed; top:0; left:0; width:100%; height:100%;
    background:linear-gradient(135deg,rgba(75,160,255,0.15),rgba(255,255,255,0.1));
    z-index:-1;
  }
  .card {
    position:absolute; top:50%; left:50%; transform:translate(-50%,-50%);
    width:340px; padding:40px; border-radius:25px;
    background:rgba(255,255,255,0.15);
    box-shadow:0 8px 40px rgba(0,0,0,0.3);
    backdrop-filter:blur(25px) saturate(180%);
    border:1px solid rgba(255,255,255,0.25);
    text-align:center;
    animation:fadeIn 1s ease forwards;
  }
  h2 { color:#ffffff; margin-bottom:10px; text-shadow:0 0 6px rgba(0,0,0,0.4); }
  p { color:#e0e9ff; opacity:.9; font-size:15px; }
  input,button {
    width:100%; margin-top:15px; padding:12px;
    font-size:16px; border:none; border-radius:12px; text-align:center;
  }
  input {
    background:rgba(255,255,255,0.7); color:#03335a;
    outline:none; transition:box-shadow .2s ease;
  }
  input:focus { box-shadow:0 0 10px #64b4ff; }
  button {
    background:#64b4ff; color:white; cursor:pointer;
    transition:background .25s ease, transform .15s ease;
  }
  button:hover { background:#52a4f0; transform:scale(1.03); }
  @keyframes fadeIn { from{opacity:0;transform:translate(-50%,-46%);} to{opacity:1;transform:translate(-50%,-50%);} }
  .success {
    animation:fadeOut 1.2s forwards;
  }
  @keyframes fadeOut { to{opacity:0; transform:scale(1.1);} }
</style>
</head>
<body>
<video class="bg" autoplay muted loop playsinline>
  <source src="https://auth.grantrp.com/static/glass_bg.mp4" type="video/mp4">
</video>
<div class="overlay"></div>

<div class="card" id="auth-card">
  <h2>Grant Roleplay Network™</h2>
  <p>Enter the 6-digit code you received in Discord DMs.</p>
  <form method="POST" onsubmit="transitionSuccess()">
    <input name="pin" maxlength="6" pattern="\\d{6}" placeholder="123456" required>
    <button type="submit">Confirm</button>
  </form>
  <p style="font-size:13px;margin-top:20px;opacity:.7">
    If you opened this directly, return to your DM and use the link again.
  </p>
</div>

<script>
function transitionSuccess() {
  const card = document.getElementById('auth-card');
  card.classList.add('success');
}
</script>
</body>
</html>
"""

# -------------------------
# OAuth2 + Join Flow
# -------------------------
@flask_app.route("/auth", methods=["GET", "POST"])
def oauth_handler():
    # First-time visit → redirect to Discord OAuth
    if request.method == "GET" and not request.args.get("code"):
        auth_url = (
            "https://discord.com/oauth2/authorize?"
            + urllib.parse.urlencode({
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": REDIRECT_URI,
                "scope": "identify guilds.join"
            })
        )
        return redirect(auth_url, code=302)

    # Render external HTML template (auth.html)
    if request.method == "GET":
        return render_template("auth.html")

    # Handle POST (6-digit pin submission)
    pin = (request.form.get("pin") or "").strip()
    code = request.args.get("code")
    if not pin.isdigit():
        return "<h3>❌ Invalid code format.</h3>", 400

    # -------------------------
    # Token Exchange
    # -------------------------
    token_resp = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15,
    )
    if token_resp.status_code != 200:
        return f"<h3>❌ Token exchange failed:</h3><pre>{token_resp.text}</pre>", 400
    access_token = token_resp.json().get("access_token")
    if not access_token:
        return "<h3>❌ Missing access token.</h3>", 400

    # -------------------------
    # Identify User
    # -------------------------
    me = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15,
    )
    if me.status_code != 200:
        return f"<h3>❌ User fetch failed:</h3><pre>{me.text}</pre>", 400
    user_id = int(me.json()["id"])

    pdata = pending_codes.get(user_id)
    if not pdata:
        return "<h3>❌ No active authorization found. Ask staff to run /auth_grant again.</h3>", 400
    if time.time() - float(pdata["timestamp"]) > CODE_TTL_SECONDS:
        pending_codes.pop(user_id, None)
        return "<h3>❌ Code expired. Ask staff to generate a new one.</h3>", 400
    if pin != str(pdata["code"]):
        return "<h3>❌ Invalid code. Please try again.</h3>", 400

    # -------------------------
    # Auto-Join Target Guild
    # -------------------------
    platform = pdata["platform"]
    target_guild_id = PLATFORM_GUILDS.get(platform)
    if not target_guild_id:
        return "<h3>❌ Platform guild not configured.</h3>", 500

    put_resp = requests.put(
        f"https://discord.com/api/guilds/{target_guild_id}/members/{user_id}",
        headers={
            "Authorization": f"Bot {BOT_TOKEN}",
            "Content-Type": "application/json",
        },
        json={"access_token": access_token},
        timeout=15,
    )
    if put_resp.status_code not in (200, 201, 204):
        if not (put_resp.status_code == 400 and "already" in put_resp.text.lower()):
            return f"<h3>❌ Guild join failed ({put_resp.status_code}):</h3><pre>{put_resp.text}</pre>", 400

    # -------------------------
    # Verify Join + Apply Roles
    # -------------------------
    verify = requests.get(
        f"https://discord.com/api/guilds/{target_guild_id}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}"},
        timeout=15,
    )
    if verify.status_code != 200:
        try:
            hq = bot.get_guild(HQ_GUILD_ID)
            if ch := hq.get_channel(AUTH_CODE_LOG_CHANNEL):
                asyncio.run_coroutine_threadsafe(
                    ch.send(f"⚠️ Join verify failed for <@{user_id}> | {verify.status_code} {verify.text[:800]}"),
                    bot.loop
                )
        except Exception:
            pass
        return "<h3>⚠️ Join verification failed.</h3>", 400

    # -------------------------
    # Async Post-Join Role Assignment
    # -------------------------
    async def _apply():
        try:
            g = bot.get_guild(target_guild_id)
            if not g:
                return
            m = g.get_member(user_id) or await g.fetch_member(user_id)
            if not m:
                return
            dept = pdata["dept"]
            subdept = pdata.get("subdept", "N/A")

            # HQ Role Swap
            hq = bot.get_guild(HQ_GUILD_ID)
            if hq:
                hm = hq.get_member(user_id) or await hq.fetch_member(user_id)
                if hm:
                    # remove pending + verified
                    for rid in (ROLE_PENDING, ROLE_VERIFIED):
                        if r := hq.get_role(rid):
                            try: await hm.remove_roles(r, reason="Auth resolved")
                            except Exception: pass
                    # add accepted + official
                    add_roles = [hq.get_role(ACCEPTED_PLATFORM_ROLES.get(platform)), hq.get_role(ROLE_OFFICIAL)]
                    add_roles = [r for r in add_roles if r]
                    if add_roles:
                        try: await hm.add_roles(*add_roles, reason="Application accepted")
                        except Exception: pass

            # Department assignment
            if target_guild_id == PS4_GUILD_ID:
                await assign_ps_roles_ps4(m, dept, subdept)
            elif target_guild_id == PS5_GUILD_ID:
                await assign_ps_roles_ps5(m, dept, subdept)

            # Success log
            if hq and (log_ch := hq.get_channel(AUTH_CODE_LOG_CHANNEL)):
                await log_ch.send(
                    f"✅ **Auth Success** — <@{user_id}> | `{dept}` | `{subdept}` | `{platform}`"
                )

            # DM user confirmation
            try:
                user = await bot.fetch_user(user_id)
                e = Embed(
                    title="✅ Verification Complete",
                    description="Welcome to **Grant Roleplay Network™** — your access has been granted.",
                    color=GRN_COLOR
                ).set_footer(text=FOOTER_TEXT)
                await user.send(embed=e)
            except Exception:
                pass

        except Exception as e:
            print("apply roles error:", e)

    asyncio.run_coroutine_threadsafe(_apply(), bot.loop)

    pending_codes.pop(user_id, None)
    return render_template("success.html")

# =====================================================
# Section 6 — Startup & Runner
# =====================================================

@bot.event
async def on_ready():
    """Initialize persistent views, verify HQ connection, and post panel."""
    try:
        # Register persistent dropdown view so it survives restarts
        bot.add_view(ApplicationPanel())

        # Let cache warm up a moment
        await asyncio.sleep(2)

        hq = bot.get_guild(HQ_GUILD_ID)
        if not hq:
            print(f"[⚠] HQ guild {HQ_GUILD_ID} not found. Bot might not be in the server.")
            return

        # Validate panel channel
        ch = hq.get_channel(PANEL_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            print(f"[⚠] Channel {PANEL_CHANNEL_ID} not found or not text-based.")
            return

        # Avoid spamming duplicates
        last_msgs = [m async for m in ch.history(limit=5)]
        if not any("📥" in (m.embeds[0].description if m.embeds else "") for m in last_msgs):
            await post_panel(ch)
            print(f"[✅] Posted new application panel in #{ch.name}")
        else:
            print(f"[ℹ] Panel already present in #{ch.name}")

        print(f"🟢 Ready as {bot.user} ({bot.user.id})")
        print("─────────────────────────────────────────────")
        print(f"Guilds: {len(bot.guilds)} | Pending Codes: {len(pending_codes)}")
        print("─────────────────────────────────────────────")

    except Exception as e:
        print("[❌] Startup error:", e)
        traceback.print_exc()

# -------------------------
# Flask Web Server Runner
# -------------------------
def run_web():
    """Run Flask server in a background thread for auth handling."""
    try:
        port = int(os.environ.get("PORT", "8080"))
        print(f"[🌐] Starting Flask web server on port {port}")
        flask_app.run(host="0.0.0.0", port=port)
    except Exception as e:
        print("[❌] Flask startup failed:", e)
        traceback.print_exc()

# -------------------------
# Launch (Discord + Flask)
# -------------------------
if __name__ == "__main__":
    try:
        # Start the web server in its own thread
        threading.Thread(target=run_web, daemon=True).start()

        # Launch Discord bot
        print("[🚀] Launching GRN Application/Auth System...")
        bot.run(BOT_TOKEN)
    except KeyboardInterrupt:
        print("[🛑] Manual shutdown received.")
    except Exception as e:
        print("[❌] Fatal launch error:", e)
        traceback.print_exc()
