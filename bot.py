# =========================
# LSRP Network System™®  — Application Core + Auth + Anti-ping + Jarvis
# Focus build: application system + /auth_grant (UNCHANGED) + anti-ping + role/callsign on PS4 + /jarvis
# Hardened: defers, persistent views, error logging, restart-safe Accept/Deny
# =========================

# -------------------------
# Standard library imports
# -------------------------
import os
import sys
import time
import random
import threading
import asyncio
import logging
import traceback
import io
from typing import Dict, List, Tuple
import urllib.parse

# -------------------------
# Third-party imports
# -------------------------
import requests
import discord
from discord import app_commands, Embed, Object
from discord.ext import commands, tasks
from discord.ui import View, Button, Select
from flask import Flask, request, redirect, render_template_string

# -------------------------
# LOGGING (flush to console)
# -------------------------
def setup_logging():
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(asctime)s] [%(levelname)8s] %(name)s: %(message)s"))
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    logging.getLogger("discord").setLevel(logging.INFO)
    logging.getLogger("discord.http").setLevel(logging.INFO)

setup_logging()

# -------------------------
# ENV / CONSTANTS
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# Owner (for DM error reporting if needed)
OWNER_ID = 1176071547476262986

# OAuth (already configured in your app)
CLIENT_ID = os.getenv("CLIENT_ID") or "1397974568706117774"
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or "KcaapGwCEsH_JDlIbrAX3lghSC-tDREN"
# ✅ Always use your new subdomain — no Railway fallback
REDIRECT_URI = "https://auth.lsrpnetwork.com/auth"

# Guilds
HQ_GUILD_ID      = int(os.getenv("HQ_GUILD_ID", "1294319617539575808"))
PS4_GUILD_ID     = int(os.getenv("PS4_GUILD_ID", "1324117813878718474"))
PS5_GUILD_ID     = int(os.getenv("PS5_GUILD_ID", "1401903156274790441"))
XBOX_OG_GUILD_ID = int(os.getenv("XBOX_OG_GUILD_ID", "1375494043831898334"))

PLATFORM_GUILDS = {
    "PS4":    PS4_GUILD_ID,
    "PS5":    PS5_GUILD_ID,
    "XboxOG": XBOX_OG_GUILD_ID,
}

# ----- Extra config for utility commands -----
PRIORITY_LOG_CHANNEL_ID = int(os.getenv("PRIORITY_LOG_CHANNEL_ID", "0"))   # channel to log priority start/end
SESSION_PING_ROLE_ID    = int(os.getenv("SESSION_PING_ROLE_ID", "0"))     # role to ping for sessions (optional)

# Channels / Roles (HQ guild)
PANEL_CHANNEL_ID          = 1324115220725108877
APP_REVIEW_CHANNEL_ID     = 1366431401054048357
AUTH_CODE_LOG_CHANNEL     = 1395135616177668186
APPLICATION_TIPS_CHANNEL  = 1370854351828029470  # #application-tips

STAFF_CAN_POST_PANEL_ROLE = 1384558588478886022  # also permission to use /auth_grant

ROLE_DENIED_12H           = 1323755533492027474  # "Denied Member (12 hours)"
ROLE_PENDING              = 1323758692918624366  # "Application Pending"

# HQ applicant roles
APPLICANT_PLATFORM_ROLES = {
    "PS4":    1401961522556698739,
    "PS5":    1401961758502944900,
    "XboxOG": 1401961991756578817,
}
APPLICANT_DEPT_ROLES = {
    "PSO":  1370719624051691580,
    "CO":   1323758149009936424,
    "SAFR": 1370719781488955402,
}

# Optional: “Accepted” roles in HQ (kept for future)
ACCEPTED_PLATFORM_ROLES = {
    "PS4":    1367753287872286720,
    "PS5":    1367753535839797278,
    "XboxOG": 1367753756367912960,
}

# Anti-ping settings
PROTECTED_USER_ID = 1176071547476262986  # you
ANTI_PING_GUILDS = {
    HQ_GUILD_ID: 1338855588381200426,     # HQ Management Team
    PS4_GUILD_ID: 1375046488194809917,    # PS4 Management Team
}

# Application timing
APP_TOTAL_TIME_SECONDS = 35 * 60   # 35 minutes overall timer
CODE_TTL_SECONDS       = 5 * 60    # 5 minutes code TTL

# Application panel imagery
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1317589676336611381/1405147584456032276/Sunset_Photography_Tumblr_Banner.png?ex=689dc52a&is=689c73aa&hm=f7fd9a078016e1fc61d54391e5d57bf61f0c1f6b09e82b8163b16eae312c0f1a&"
ACCEPT_GIF_URL  = "https://cdn.discordapp.com/attachments/1317589676336611381/1402368709783191713/Animated_LSRP.gif?ex=689d8c63&is=689c3ae3&hm=5cd9a2cff01d151238b2fd245a8128ada27122b5f4d7d1d2214332c0324dd3fb&"

# PS4 main guild dept + starter rank roles (on successful OAuth join)
# PSO sub-department roles
ROLE_PSO_MAIN            = 1375046521904431124
ROLE_SASP                = 1401347813958226061
ROLE_BCSO                = 1401347339796348938
ROLE_PSO_CATEGORY        = 1404575562290434190         # “Public Safety Rank(s)”
ROLE_BCSO_CATEGORY       = 1375046520469979256         # “Sheriffs Office Rank(s)”
ROLE_PSO_STARTER         = 1375046543329202186         # Cadet

# CO roles
ROLE_CO_MAIN             = 1375046547678429195
ROLE_CO_CATEGORY         = 1375046548747980830         # “Civilian Operations Rank(s)”
ROLE_CO_STARTER          = 1375046566150406155         # Probationary Civ

# SAFR roles
ROLE_SAFR_MAIN           = 1401347818873946133
ROLE_SAFR_CATEGORY       = 1375046571653201961         # “Fire/EMS Rank(s)”
ROLE_SAFR_STARTER        = 1375046583153856634         # Probationary Firefighter

# -------------------------
# Discord Bot Setup
# -------------------------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# -------------------------
# In-memory stores
# -------------------------
app_sessions: Dict[int, dict] = {}  # user_id -> {dept, subdept, platform, started_at, deadline, answers: [(q,a),...] }
pending_codes: Dict[int, dict] = {} # user_id -> {code, timestamp, dept, platform, subdept}

# -------------------------
# Helpers
# -------------------------
def dept_color(dept: str) -> discord.Color:
    if dept == "PSO":
        return discord.Color.blue()
    if dept == "CO":
        return discord.Color.green()
    return discord.Color.red()  # SAFR

def readable_remaining(deadline: float) -> str:
    left = max(0, int(deadline - time.time()))
    m, s = divmod(left, 60)
    return f"{m}m {s}s"

async def report_interaction_error(interaction: discord.Interaction, err: Exception, prefix: str):
    # Console
    logging.error("%s:\n%s", prefix, "".join(traceback.format_exception(type(err), err, err.__traceback__)))
    # Ephemeral notice to clicker
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ An error occurred. Staff has been notified.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ An error occurred. Staff has been notified.", ephemeral=True)
    except Exception:
        pass
    # DM owner
    try:
        owner = bot.get_user(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        await owner.send(f"**{prefix}** in **{getattr(interaction.guild, 'name', 'DM')} / #{getattr(interaction.channel, 'name', '?')}**\n```\n{repr(err)}\n```")
    except Exception:
        pass
    # Post in AUTH_CODE_LOG_CHANNEL if exists
    try:
        ch = bot.get_channel(AUTH_CODE_LOG_CHANNEL)
        if ch:
            await ch.send(f"**{prefix}**\n```\n{''.join(traceback.format_exception(type(err), err, err.__traceback__))[:1900]}\n```")
    except Exception:
        pass

# -------------------------
# Question Sets (20 per department)
# -------------------------
COMMON_4 = [
    ("Q1",  "What's your Discord username?"),
    ("Q2",  "How old are you IRL?"),
    ("Q3",  "What's your Date of Birth IRL?"),
    ("Q4",  "How did you find us? (type one): Instagram / Tiktok / Partnership / Friend / Other"),
]

PSO_SPECIFIC_16 = [
    ("Q5",  "What attracts you to Public Safety work within LSRP?"),
    ("Q6",  "Do you have prior law enforcement RP experience? If yes, where and what rank?"),
    ("Q7",  "Explain the difference between BCSO and SASP jurisdictions."),
    ("Q8",  "Scenario: First on a shots-fired scene with civilians nearby. What’s your immediate plan?"),
    ("Q9",  "Rate your radio discipline 1–10 and explain."),
    ("Q10", "Confirm you’ll follow all PSO SOPs and sub-department rules. (Yes/No + any comments)"),
    ("Q11", "List three traffic stop safety steps you always follow."),
    ("Q12", "When should lethal force be considered appropriate?"),
    ("Q13", "How do you de-escalate a hostile subject during a stop?"),
    ("Q14", "Describe how you’d coordinate with another unit during a pursuit."),
    ("Q15", "How do you handle chain of command disagreements in-session?"),
    ("Q16", "What’s your approach to scene containment and perimeter setup?"),
    ("Q17", "Name two examples of powergaming to avoid as LEO."),
    ("Q18", "How do you balance realistic RP with server pacing?"),
    ("Q19", "A fellow officer violates SOP mid-scene. What do you do?"),
    ("Q20", "What’s your long-term goal inside PSO (training, supervision, specialty units)?"),
]

CO_SPECIFIC_16 = [
    ("Q5",  "What kinds of civilian stories do you enjoy (legal/illegal/entrepreneur)?"),
    ("Q6",  "How do you avoid low-effort/chaotic RP while staying engaging?"),
    ("Q7",  "Describe a creative civilian scene you’ve run or want to run here."),
    ("Q8",  "Are you comfortable with passive RP (dialogue/world-building)? Why?"),
    ("Q9",  "What conflicts should civilians avoid initiating and why?"),
    ("Q10", "Confirm you’ll follow all CO guidelines. (Yes/No + any comments)"),
    ("Q11", "What’s your approach to building a civilian character background?"),
    ("Q12", "How do you RP consequences after illegal activities?"),
    ("Q13", "Give an example of non-violent conflict you’d like to portray."),
    ("Q14", "How do you keep civilian RP fun for others on slow nights?"),
    ("Q15", "Explain metagaming and how you avoid it as a civilian."),
    ("Q16", "How do you signal intent OOC when coordination is needed (without breaking immersion)?"),
    ("Q17", "What’s a good reason to call for emergency services from a civ POV?"),
    ("Q18", "How will you use businesses or public locations to spark roleplay?"),
    ("Q19", "What would make you step back and let another player lead a scene?"),
    ("Q20", "Your long-term CO goals (gang mgmt, business owner, advisor, etc.)?"),
]

SAFR_SPECIFIC_16 = [
    ("Q5",  "Why do you want to join San Andreas Fire & Rescue?"),
    ("Q6",  "Any prior Fire/EMS RP? Certifications or knowledge to share?"),
    ("Q7",  "Scenario: Multi-vehicle collision with fire & multiple injured. First 3 priorities?"),
    ("Q8",  "Are you comfortable with medical RP steps (triage, BLS)?"),
    ("Q9",  "What does teamwork mean to you in emergency services?"),
    ("Q10", "Confirm you’ll follow all SAFR protocols. (Yes/No + any comments)"),
    ("Q11", "How do you assess scene safety before entering a structure?"),
    ("Q12", "When would you call for additional alarms or mutual aid?"),
    ("Q13", "Explain basic triage tags and how you’d apply them."),
    ("Q14", "Describe the handoff to EMS or hospital in RP."),
    ("Q15", "How do you communicate with LEO at a chaotic fire scene?"),
    ("Q16", "What tools/equipment would you mention during a structure fire RP?"),
    ("Q17", "How do you portray fatigue/limitations realistically in long scenes?"),
    ("Q18", "What’s your approach to patient consent & refusal scenarios?"),
    ("Q19", "How would you handle conflicting commands from multiple supervisors?"),
    ("Q20", "Your long-term SAFR goals (EMS specialization, officer track, training)?"),
]

DEPT_QUESTIONS = {
    "PSO":  COMMON_4 + PSO_SPECIFIC_16,
    "CO":   COMMON_4 + CO_SPECIFIC_16,
    "SAFR": COMMON_4 + SAFR_SPECIFIC_16,
}

# -------------------------
# Base View with error hook
# -------------------------
class SafeView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        await report_interaction_error(interaction, error, f"View error in '{getattr(item, 'custom_id', getattr(item, 'label', '?'))}'")

# -------------------------
# Application Panel (public)
# -------------------------
class DepartmentSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select a department to begin…",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Public Safety Office (PSO)", value="PSO", description="BCSO / SASP"),
                discord.SelectOption(label="Civilian Operations (CO)", value="CO", description="Civilian Roleplay"),
                discord.SelectOption(label="San Andreas Fire & Rescue (SAFR)", value="SAFR", description="Fire & EMS"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        try:
            # ACK fast to avoid "Interaction Failed"
            await interaction.response.defer(ephemeral=True)

            dept = self.values[0]
            user = interaction.user

            # Initialize session
            app_sessions[user.id] = {
                "dept": dept,
                "guild_id": interaction.guild.id if interaction.guild else None,
                "answers": [],
                "started_at": time.time(),
                "deadline": time.time() + APP_TOTAL_TIME_SECONDS,
            }

            color = dept_color(dept)

            # DM intro
            dm = await user.create_dm()
            intro = Embed(
                title="📋 Los Santos Roleplay Network™® | Application",
                description=(
                    f"Department selected: **{dept}**\n\n"
                    "I’ll guide you through the application here in DMs.\n"
                    f"⏳ You have **35 minutes** to complete all questions.\n"
                    "If your DMs are closed, please enable them and select again."
                ),
                color=color,
            )
            await dm.send(embed=intro)

            # If PSO, ask sub-department; SAFR/CO skip subdept → platform
            if dept == "PSO":
                await dm.send(
                    embed=Embed(
                        title="Sub-Department Selection",
                        description="Choose your **PSO** sub-department:",
                        color=color),
                    view=SubDeptView(user.id)
                )
            else:
                await dm.send(
                    embed=Embed(
                        title="Platform Selection",
                        description="Choose your platform:",
                        color=color),
                    view=PlatformView(user.id)
                )

            # Assign applicant roles in HQ (where the panel lives)
            if interaction.guild and interaction.guild.id == HQ_GUILD_ID:
                roles_to_add = []
                dept_role_id = APPLICANT_DEPT_ROLES.get(dept)
                if dept_role_id:
                    r = interaction.guild.get_role(dept_role_id)
                    if r: roles_to_add.append(r)
                pending_role = interaction.guild.get_role(ROLE_PENDING)
                if pending_role:
                    roles_to_add.append(pending_role)
                member = interaction.guild.get_member(user.id) or await interaction.guild.fetch_member(user.id)
                if roles_to_add:
                    try:
                        await member.add_roles(*roles_to_add, reason="Application started")
                    except Exception:
                        pass

            await interaction.followup.send("📬 I’ve sent you a DM to continue your application.", ephemeral=True)

        except discord.Forbidden:
            if not interaction.response.is_done():
                await interaction.response.send_message("⚠️ I couldn’t DM you. Please enable DMs and select again.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ I couldn’t DM you. Please enable DMs and select again.", ephemeral=True)
        except Exception as e:
            await report_interaction_error(interaction, e, "DepartmentSelect callback failed")

class ApplicationPanel(SafeView):
    def __init__(self):
        super().__init__(timeout=None)  # persistent
        self.add_item(DepartmentSelect())

class SubDeptSelect(Select):
    def __init__(self, user_id: int):
        super().__init__(
            placeholder="Select sub-department…",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Blaine County Sheriff's Office (BCSO)", value="BCSO"),
                discord.SelectOption(label="San Andreas State Police (SASP)", value="SASP"),
            ],
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This menu isn’t for you.", ephemeral=True)
        sess = app_sessions.setdefault(self.user_id, {})
        sess["subdept"] = self.values[0]
        dept = sess.get("dept", "PSO")
        color = dept_color(dept)
        emb = Embed(title="Platform Selection", description="Choose your platform:", color=color)
        await interaction.response.edit_message(embed=emb, view=PlatformView(self.user_id))

class PlatformSelect(Select):
    def __init__(self, user_id: int):
        super().__init__(
            placeholder="Select platform…",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="PlayStation 4", value="PS4"),
                discord.SelectOption(label="PlayStation 5", value="PS5"),
                discord.SelectOption(label="Xbox Old Gen", value="XboxOG"),
            ],
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This menu isn’t for you.", ephemeral=True)

        sess = app_sessions.setdefault(self.user_id, {})
        sess["platform"] = self.values[0]
        dept = sess.get("dept", "CO")
        color = dept_color(dept)

        # Add platform applicant role in HQ (if panel came from HQ)
        if sess.get("guild_id") == HQ_GUILD_ID:
            guild = bot.get_guild(HQ_GUILD_ID)
            if guild:
                member = guild.get_member(self.user_id) or await guild.fetch_member(self.user_id)
                plat_role_id = APPLICANT_PLATFORM_ROLES.get(sess["platform"])
                roles_to_add = []
                if plat_role_id:
                    r = guild.get_role(plat_role_id)
                    if r: roles_to_add.append(r)
                if roles_to_add:
                    try:
                        await member.add_roles(*roles_to_add, reason="Application started (platform selected)")
                    except Exception:
                        pass

        # Start questions
        emb = Embed(
            title="Application Details Confirmed",
            description=(f"**Department:** {dept}\n"
                         f"**Sub-Department:** {sess.get('subdept', 'N/A')}\n"
                         f"**Platform:** {sess['platform']}\n\n"
                         f"✅ Selections saved. I’ll now begin your application questions.\n"
                         f"⏳ Time left: **{readable_remaining(sess['deadline'])}**"),
            color=color
        )
        await interaction.response.edit_message(embed=emb, view=None)

        await run_questions(interaction.user)

class SubDeptView(SafeView):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(SubDeptSelect(user_id))

class PlatformView(SafeView):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(PlatformSelect(user_id))

async def run_questions(user: discord.User):
    """Walk the user through all questions in DM, enforce overall 35-min deadline, then post review."""
    sess = app_sessions.get(user.id)
    if not sess:
        return
    dept = sess["dept"]
    questions = DEPT_QUESTIONS[dept]
    deadline = sess["deadline"]
    color = dept_color(dept)

    dm = await user.create_dm()
    for qkey, qtext in questions:
        # Deadline check
        if time.time() > deadline:
            try:
                await dm.send(embed=Embed(
                    title="⏳ Time Expired",
                    description="Your application time has expired (35 minutes). Please start again from the panel.",
                    color=discord.Color.orange()
                ))
            except Exception:
                pass
            return

        prompt = Embed(
            title=f"{qkey}",
            description=qtext + f"\n\n_Time remaining: **{readable_remaining(deadline)}**_",
            color=color
        )
        await dm.send(embed=prompt)

        def check(m: discord.Message):
            return m.author.id == user.id and m.channel.id == dm.id

        try:
            # Allow up to remaining time for this question, max 5 minutes per Q
            remaining = max(1, int(deadline - time.time()))
            timeout = min(remaining, 300)
            msg = await bot.wait_for("message", check=check, timeout=timeout)
            sess["answers"].append((qtext, msg.content.strip()))
        except asyncio.TimeoutError:
            try:
                await dm.send(embed=Embed(
                    title="⏳ Time Expired",
                    description="Your application timed out. Please start again from the panel.",
                    color=discord.Color.orange()
                ))
            except Exception:
                pass
            return

    # Done → post to review channel
    await post_review(user)

def _quote_block(text: str) -> str:
    """Make a Discord quote block, safely under field limits."""
    # Discord embed field value max is 1024 chars. Keep a little headroom.
    MAX = 950
    text = text.strip()
    if len(text) > MAX:
        text = text[:MAX - 15].rstrip() + " … [truncated]"
    # Prefix each line with '>' so multi-line answers render cleanly
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines() or [" "])

import io  # make sure this is at the top of your file if not already there

def _quote_block(text: str) -> str:
    """Make a Discord quote block, safely under field limits."""
    MAX = 950  # embed field limit safety
    text = text.strip()
    if len(text) > MAX:
        text = text[:MAX - 15].rstrip() + " … [truncated]"
    return "\n".join(f"> {line}" if line.strip() else ">" for line in text.splitlines() or [" "])

async def post_review(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess:
        return

    dept     = sess.get("dept", "N/A")
    subdept  = sess.get("subdept", "N/A")
    platform = sess.get("platform", "N/A")
    answers: List[Tuple[str, str]] = sess.get("answers", [])
    color    = dept_color(dept)

    # ---------- Build embed with fields ----------
    review_embed = Embed(
        title="🗂️ New Application Submitted",
        color=color,
        description=(
            f"**Applicant:** {user.mention} (`{user.id}`)\n"
            f"**Department:** {dept}\n"
            f"**Sub-Department:** {subdept}\n"
            f"**Platform:** {platform}\n"
        )
    )
    review_embed.set_footer(text=f"applicant:{user.id}|dept:{dept}|sub:{subdept}|platform:{platform}")

    for idx, (qtext, ans) in enumerate(answers, start=1):
        qname = f"Q{idx}: {qtext}"
        if len(qname) > 250:
            qname = qname[:247] + "…"
        review_embed.add_field(name=qname, value=_quote_block(ans), inline=False)

    posted_ok = False
    try:
        guild = bot.get_guild(HQ_GUILD_ID)
        if not guild:
            raise RuntimeError("HQ_GUILD_ID not found or bot not in guild.")
        ch = guild.get_channel(APP_REVIEW_CHANNEL_ID)
        if not ch:
            raise RuntimeError("APP_REVIEW_CHANNEL_ID not found.")

        view = ReviewButtonsPersistent()
        await ch.send(embed=review_embed, view=view)
        posted_ok = True

    except Exception as e:
        # fallback to text file
        try:
            full_text_lines = [
                f"Applicant: {user} ({user.id})",
                f"Department: {dept}",
                f"Sub-Department: {subdept}",
                f"Platform: {platform}",
                "",
                "=== Application Responses ===",
            ]
            for idx, (qtext, ans) in enumerate(answers, start=1):
                full_text_lines.append(f"\nQ{idx}: {qtext}\n{ans}")
            payload = "\n".join(full_text_lines).encode("utf-8")

            file = discord.File(io.BytesIO(payload), filename=f"application_{user.id}.txt")

            fallback = Embed(
                title="🗂️ New Application Submitted (Attachment)",
                description=(
                    f"**Applicant:** {user.mention} (`{user.id}`)\n"
                    f"**Department:** {dept}\n"
                    f"**Sub-Department:** {subdept}\n"
                    f"**Platform:** {platform}\n\n"
                    "Full responses are attached as a text file."
                ),
                color=color
            )
            fallback.set_footer(text=f"applicant:{user.id}|dept:{dept}|sub:{subdept}|platform:{platform}")

            guild = bot.get_guild(HQ_GUILD_ID)
            ch = guild.get_channel(APP_REVIEW_CHANNEL_ID) if guild else None
            if ch:
                view = ReviewButtonsPersistent()
                await ch.send(embed=fallback, file=file, view=view)
                posted_ok = True
        except Exception as e2:
            try:
                await report_interaction_error(None, e2, "post_review fallback failed")
            except Exception:
                pass

    # ---------- DM applicant ----------
    try:
        dm = await user.create_dm()
        if posted_ok:
            msg = (
                "✅ **Application Submitted**\n"
                "Your application has been delivered to staff for review. "
                "You’ll receive a DM once a decision is made."
            )
        else:
            msg = (
                "✅ **Application Saved**\n"
                "We received your answers, but there was a temporary issue delivering them to staff. "
                "Staff will be notified and will pull your application shortly—no action needed on your end."
            )
        await dm.send(embed=Embed(title="Application Status", description=msg, color=color))
    except Exception:
        pass

    try:
        app_sessions.pop(user.id, None)
    except Exception:
        pass


# ---------- Review Buttons (Persistent) ----------
class ReviewButtonsPersistent(SafeView):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id=ACCEPT_ID)
    async def accept(self, interaction: discord.Interaction, button: Button):
        try:
            if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
                return await interaction.response.send_message("🚫 You can’t accept applications.", ephemeral=True)

            await interaction.response.defer(ephemeral=True)

            emb = interaction.message.embeds[0] if interaction.message.embeds else None
            footer = emb.footer.text if emb and emb.footer and emb.footer.text else ""
            meta = dict([pair.split(":", 1) for pair in footer.split("|") if ":" in pair])
            user_id = int(meta.get("applicant", "0"))
            dept    = meta.get("dept", "N/A")
            subdept = meta.get("sub", "N/A")
            platform= meta.get("platform", "N/A")

            await interaction.followup.send(
                f"✅ Accepted. Please run **/auth_grant** for <@{user_id}> "
                f"(Dept `{dept}` | Platform `{platform}`) to grant main server access.",
                ephemeral=True
            )

            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            if user:
                try:
                    lines = [f"Congratulations! You’ve been **accepted** into **{dept}**."]
                    if dept == "PSO" and subdept and subdept != "N/A":
                        lines.append(f"Assigned sub-department: **{subdept}**.")
                    lines.append("")
                    lines.append("**Next steps**")
                    lines.append("• A staff member will issue you a **one-time 6-digit verification code** soon.")
                    lines.append("• The code comes from the bot via DM and **expires 5 minutes** after it is sent.")
                    lines.append("• Keep your DMs **open** and respond promptly. Do **not** share your code.")
                    lines.append("")
                    lines.append("**Expectations**")
                    lines.append("• Follow all community regulations and your department’s SOPs.")
                    lines.append("• Be respectful and maintain professional RP standards at all times.")
                    lines.append("• You’ll receive main server access right after you complete verification.")

                    e = Embed(
                        title="🎉 Application Accepted",
                        description="\n".join(lines),
                        color=dept_color(dept)
                    )
                    await user.send(embed=e)
                except Exception:
                    pass

            # disable buttons
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await report_interaction_error(interaction, e, "Accept button failed")

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id=DENY_ID)
    async def deny(self, interaction: discord.Interaction, button: Button):
        try:
            if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
                return await interaction.response.send_message("🚫 You can’t deny applications.", ephemeral=True)

            await interaction.response.defer(ephemeral=True)

            emb = interaction.message.embeds[0] if interaction.message.embeds else None
            footer = emb.footer.text if emb and emb.footer and emb.footer.text else ""
            meta = dict([pair.split(":", 1) for pair in footer.split("|") if ":" in pair])
            user_id = int(meta.get("applicant", "0"))

            await interaction.followup.send("❌ Application denied. Denied role applied (12h).", ephemeral=True)

            guild = bot.get_guild(HQ_GUILD_ID)
            if guild:
                try:
                    member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                    role = guild.get_role(ROLE_DENIED_12H)
                    if role:
                        await member.add_roles(role, reason="Application denied")
                except Exception:
                    pass

            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            if user:
                try:
                    await user.send(embed=Embed(
                        title="❌ Application Denied",
                        description=(
                            "Your application was reviewed and **denied** at this time.\n"
                            "You may re-apply after the cooldown period. If you have questions, open a support ticket."
                        ),
                        color=discord.Color.red()
                    ))
                except Exception:
                    pass

            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await report_interaction_error(interaction, e, "Deny button failed")

            # Disable buttons on the original staff message
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await report_interaction_error(interaction, e, "Accept button failed")

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id=DENY_ID)
    async def deny(self, interaction: discord.Interaction, button: Button):
        try:
            if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
                return await interaction.response.send_message("🚫 You can’t deny applications.", ephemeral=True)

            await interaction.response.defer(ephemeral=True)

            emb = interaction.message.embeds[0] if interaction.message.embeds else None
            footer = emb.footer.text if emb and emb.footer and emb.footer.text else ""
            meta = dict([pair.split(":", 1) for pair in footer.split("|") if ":" in pair])
            user_id = int(meta.get("applicant", "0"))

            await interaction.followup.send("❌ Application denied. Denied role applied (12h).", ephemeral=True)

            # Add denied role in HQ
            guild = bot.get_guild(HQ_GUILD_ID)
            if guild:
                try:
                    member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                    role = guild.get_role(ROLE_DENIED_12H)
                    if role:
                        await member.add_roles(role, reason="Application denied")
                except Exception:
                    pass

            # Notify applicant
            user = bot.get_user(user_id) or await bot.fetch_user(user_id)
            if user:
                try:
                    await user.send(embed=Embed(
                        title="❌ Application Denied",
                        description=(
                            "Your application was reviewed and **denied** at this time.\n"
                            "You may re-apply after the cooldown period. If you have questions, open a support ticket."
                        ),
                        color=discord.Color.red()
                    ))
                except Exception:
                    pass

            # Disable buttons
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

        except Exception as e:
            await report_interaction_error(interaction, e, "Deny button failed")

# -------------------------
# Panel posting (new copy)
# -------------------------
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
        title="",
        description=f"{title}\n\n{intro}\n\n{tips}\n\n{what_next}\n\n{choose_path}",
        color=discord.Color.blurple()
    )
    embed.set_image(url=PANEL_IMAGE_URL)

    await channel.send(embed=embed, view=ApplicationPanel())

@tree.command(name="post_application_panel", description="Post the permanent application panel in the current channel.")
async def post_application_panel_slash(interaction: discord.Interaction):
    try:
        if interaction.guild is None:
            return await interaction.response.send_message("Use this inside the target channel.", ephemeral=True)
        if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        await post_panel(interaction.channel)
        await interaction.followup.send("✅ Panel posted here.", ephemeral=True)
    except Exception as e:
        await report_interaction_error(interaction, e, "post_application_panel failed")

@bot.command(name="?post_application_panel")
async def post_application_panel_prefix(ctx: commands.Context):
    if not ctx.guild:
        return
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in getattr(ctx.author, "roles", [])):
        return await ctx.reply("🚫 You don’t have permission.")
    await post_panel(ctx.channel)
    try:
        await ctx.message.delete()
    except Exception:
        pass

# -------------------------
# /auth_grant — generate 6-digit and DM (UNCHANGED)
# -------------------------
@tree.command(name="auth_grant", description="Generate a one-time 6-digit auth code (expires in 5 minutes).")
@app_commands.describe(
    user="The applicant to authorize",
    department="Department (PSO / CO / SAFR)",
    platform="Platform (PS4 / PS5 / XboxOG)"
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
    platform: app_commands.Choice[str]
):
    try:
        if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        subdept = app_sessions.get(user.id, {}).get("subdept", "N/A")

        code = random.randint(100000, 999999)
        pending_codes[user.id] = {
            "code": code,
            "timestamp": time.time(),
            "dept": department.value,
            "platform": platform.value,
            "subdept": subdept,
        }

        # Log to HQ
        hq = bot.get_guild(HQ_GUILD_ID)
        log_ch = hq.get_channel(AUTH_CODE_LOG_CHANNEL) if hq else None
        if log_ch:
            await log_ch.send(
                f"🔐 **Auth Code Generated**\n"
                f"User: {user.mention} (`{user.id}`)\n"
                f"Department: `{department.value}`  |  Platform: `{platform.value}`  |  Subdept: `{subdept}`\n"
                f"Code: **{code}** (expires in 5 minutes)\n"
                f"Granted by: {interaction.user.mention}"
            )

        # DM applicant (code + link + button)
        try:
            e = Embed(
                title="🔐 Los Santos Roleplay Network™® — Authorization",
                description=(
                    f"**This is your 1 time 6 digit code:** `{code}`\n"
                    f"**Once this code is used in the authorization link it will no longer be valid.**\n\n"
                    f"[Main Server Verification Link]({REDIRECT_URI})"
                ),
                color=dept_color(department.value),
            )
            e.set_image(url=ACCEPT_GIF_URL)
            view = SafeView()
            view.add_item(discord.ui.Button(label="Open Verification", url=REDIRECT_URI, style=discord.ButtonStyle.link))
            await user.send(embed=e, view=view)
        except Exception:
            pass

        await interaction.followup.send(f"✅ Code sent to {user.mention}'s DMs.", ephemeral=True)
    except Exception as e:
        await report_interaction_error(interaction, e, "auth_grant failed")

# -------------------------
# OAuth mini web server
# -------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "✅ LSRP Network System is running."

_HTML_FORM = """
<!doctype html><html><head><meta charset="utf-8"><title>LSRP Auth</title></head>
<body style="font-family:system-ui;margin:40px;max-width:780px">
<h2>Los Santos Roleplay Network™® — Authorization</h2>
<p>Enter the 6-digit code the bot sent you in DMs to finish joining.</p>
<form method="POST">
  <input name="pin" maxlength="6" pattern="\\d{6}" required placeholder="123456" />
  <button type="submit">Confirm</button>
</form>
<p style="color:gray">If you opened this directly, go back to your DM and use the link again.</p>
</body></html>
"""

@flask_app.route("/auth", methods=["GET", "POST"])
def oauth_handler():
    code = request.args.get("code")
    if not code:
        auth_url = (
            "https://discord.com/oauth2/authorize?"
            + urllib.parse.urlencode({
                "client_id": CLIENT_ID,
                "response_type": "code",
                "redirect_uri": "https://auth.lsrpnetwork.com/auth",  # ✅ updated domain
                "scope": "identify guilds.join"
            })
        )
        return redirect(auth_url, code=302)

    if request.method == "GET":
        return render_template_string(_HTML_FORM)

    pin = (request.form.get("pin") or "").strip()

    token_resp = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://auth.lsrpnetwork.com/auth",  # ✅ updated domain
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15
    )
    if token_resp.status_code != 200:
        return f"Token exchange failed: {token_resp.text}", 400
    access_token = token_resp.json().get("access_token")

    me = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15
    )
    if me.status_code != 200:
        return f"User fetch failed: {me.text}", 400
    user_id = int(me.json()["id"])

    pdata = pending_codes.get(user_id)
    if not pdata:
        return "No active authorization found. Ask staff to run /auth_grant again.", 400

    if time.time() - float(pdata["timestamp"]) > CODE_TTL_SECONDS:
        pending_codes.pop(user_id, None)
        return "Your code expired. Ask staff to generate a new one.", 400
    if pin != str(pdata["code"]):
        return "Invalid code. Please go back and try again.", 400

    # Join target guild
    target_guild_id = PLATFORM_GUILDS.get(pdata["platform"])
    if not target_guild_id:
        return "Platform guild not configured.", 500

    put_resp = requests.put(
        f"https://discord.com/api/guilds/{target_guild_id}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
        json={"access_token": access_token},
        timeout=15
    )
    if put_resp.status_code not in (200, 201, 204):
        if not (put_resp.status_code == 400 and "already" in put_resp.text.lower()):
            return f"Guild join failed: {put_resp.status_code} {put_resp.text}", 400

    # ============================
    # Auto roles + callsigns (PS4 + PS5 handled separately)
    # ============================

    # For PS4 guild
    try:
        if target_guild_id == PS4_GUILD_ID:
            g = bot.get_guild(PS4_GUILD_ID)
            if g:
                fut = asyncio.run_coroutine_threadsafe(g.fetch_member(user_id), bot.loop)
                m = g.get_member(user_id)
                try:
                    m = m or fut.result(timeout=10)
                except Exception:
                    m = g.get_member(user_id)
                if m:
                    dept = pdata["dept"]
                    sub = pdata.get("subdept", "N/A")
                    to_add = []

                    if dept == "PSO":
                        r_main = g.get_role(ROLE_PSO_MAIN)
                        r_cat  = g.get_role(ROLE_PSO_CATEGORY)
                        r_start= g.get_role(ROLE_PSO_STARTER)
                        if r_main: to_add.append(r_main)
                        if r_cat:  to_add.append(r_cat)
                        if r_start:to_add.append(r_start)
                        if sub == "SASP":
                            r = g.get_role(ROLE_SASP)
                            if r: to_add.append(r)
                        elif sub == "BCSO":
                            r = g.get_role(ROLE_BCSO)
                            if r: to_add.append(r)
                            rbc = g.get_role(ROLE_BCSO_CATEGORY)
                            if rbc: to_add.append(rbc)
                        cs = f"C-{random.randint(1000, 1999)} | {m.name}"
                        try:
                            asyncio.run_coroutine_threadsafe(m.edit(nick=cs, reason="Initial PSO callsign"), bot.loop).result(timeout=10)
                        except Exception:
                            pass

                    elif dept == "CO":
                        r_main = g.get_role(ROLE_CO_MAIN)
                        r_cat  = g.get_role(ROLE_CO_CATEGORY)
                        r_start= g.get_role(ROLE_CO_STARTER)
                        if r_main: to_add.append(r_main)
                        if r_cat:  to_add.append(r_cat)
                        if r_start:to_add.append(r_start)
                        cs = f"CIV-{random.randint(1000, 1999)} | {m.name}"
                        try:
                            asyncio.run_coroutine_threadsafe(m.edit(nick=cs, reason="Initial CO callsign"), bot.loop).result(timeout=10)
                        except Exception:
                            pass

                    elif dept == "SAFR":
                        r_main = g.get_role(ROLE_SAFR_MAIN)
                        r_cat  = g.get_role(ROLE_SAFR_CATEGORY)
                        r_start= g.get_role(ROLE_SAFR_STARTER)
                        if r_main: to_add.append(r_main)
                        if r_cat:  to_add.append(r_cat)
                        if r_start:to_add.append(r_start)
                        cs = f"FF-{random.randint(100, 999)} | {m.name}"
                        try:
                            asyncio.run_coroutine_threadsafe(m.edit(nick=cs, reason="Initial SAFR callsign"), bot.loop).result(timeout=10)
                        except Exception:
                            pass

                    if to_add:
                        try:
                            asyncio.run_coroutine_threadsafe(m.add_roles(*to_add, reason="Initial dept roles"), bot.loop).result(timeout=10)
                        except Exception:
                            pass
    except Exception:
        pass

    # For PS5 guild
    try:
        if target_guild_id == PS5_GUILD_ID:
            g = bot.get_guild(PS5_GUILD_ID)
            if g:
                fut = asyncio.run_coroutine_threadsafe(g.fetch_member(user_id), bot.loop)
                m = g.get_member(user_id)
                try:
                    m = m or fut.result(timeout=10)
                except Exception:
                    m = g.get_member(user_id)
                if m:
                    dept = pdata["dept"]
                    sub = pdata.get("subdept", "N/A")
                    to_add = []

                    if dept == "PSO":
                        r_main = g.get_role(ROLE_PSO_MAIN_PS5)
                        r_cat  = g.get_role(ROLE_PSO_CATEGORY_PS5)
                        r_start= g.get_role(ROLE_PSO_STARTER_PS5)
                        if r_main: to_add.append(r_main)
                        if r_cat:  to_add.append(r_cat)
                        if r_start:to_add.append(r_start)
                        if sub == "SASP":
                            r = g.get_role(ROLE_SASP_PS5)
                            if r: to_add.append(r)
                        elif sub == "BCSO":
                            r = g.get_role(ROLE_BCSO_PS5)
                            if r: to_add.append(r)
                            rbc = g.get_role(ROLE_BCSO_CATEGORY_PS5)
                            if rbc: to_add.append(rbc)
                        cs = f"C-{random.randint(1000, 1999)} | {m.name}"
                        try:
                            asyncio.run_coroutine_threadsafe(m.edit(nick=cs, reason="Initial PSO callsign (PS5)"), bot.loop).result(timeout=10)
                        except Exception:
                            pass

                    elif dept == "CO":
                        r_main = g.get_role(ROLE_CO_MAIN_PS5)
                        r_cat  = g.get_role(ROLE_CO_CATEGORY_PS5)
                        r_start= g.get_role(ROLE_CO_STARTER_PS5)
                        if r_main: to_add.append(r_main)
                        if r_cat:  to_add.append(r_cat)
                        if r_start:to_add.append(r_start)
                        cs = f"CIV-{random.randint(1000, 1999)} | {m.name}"
                        try:
                            asyncio.run_coroutine_threadsafe(m.edit(nick=cs, reason="Initial CO callsign (PS5)"), bot.loop).result(timeout=10)
                        except Exception:
                            pass

                    elif dept == "SAFR":
                        r_main = g.get_role(ROLE_SAFR_MAIN_PS5)
                        r_cat  = g.get_role(ROLE_SAFR_CATEGORY_PS5)
                        r_start= g.get_role(ROLE_SAFR_STARTER_PS5)
                        if r_main: to_add.append(r_main)
                        if r_cat:  to_add.append(r_cat)
                        if r_start:to_add.append(r_start)
                        cs = f"FF-{random.randint(100, 999)} | {m.name}"
                        try:
                            asyncio.run_coroutine_threadsafe(m.edit(nick=cs, reason="Initial SAFR callsign (PS5)"), bot.loop).result(timeout=10)
                        except Exception:
                            pass

                    if to_add:
                        try:
                            asyncio.run_coroutine_threadsafe(m.add_roles(*to_add, reason="Initial dept roles (PS5)"), bot.loop).result(timeout=10)
                        except Exception:
                            pass
    except Exception:
        pass

    # Log success in HQ
    try:
        hq = bot.get_guild(HQ_GUILD_ID)
        log_ch = hq.get_channel(AUTH_CODE_LOG_CHANNEL) if hq else None
        if log_ch:
            asyncio.run_coroutine_threadsafe(
                log_ch.send(
                    f"✅ **Auth success** for <@{user_id}> | Dept `{pdata['dept']}` | "
                    f"Subdept `{pdata.get('subdept','N/A')}` | Platform `{pdata['platform']}` | Code `{pdata['code']}`"
                ),
                bot.loop
            )
    except Exception:
        pass

    pending_codes.pop(user_id, None)
    return "✅ Success! You can close this tab and return to Discord."

def run_web():
    port = int(os.environ.get("PORT", "8080"))
    flask_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# =========================
# Utility / Fun / Ops Commands
# =========================

def _has_mgmt_perms(interaction: discord.Interaction) -> bool:
    mgmt_role_id = ANTI_PING_GUILDS.get(interaction.guild.id) if interaction.guild else None
    allowed = False
    if isinstance(interaction.user, discord.Member):
        user_roles = [r.id for r in interaction.user.roles]
        if mgmt_role_id and mgmt_role_id in user_roles:
            allowed = True
        if STAFF_CAN_POST_PANEL_ROLE in user_roles:
            allowed = True
    return allowed

@tree.command(name="jarvis", description="Have Jarvis deliver a friendly (totally not menacing) greeting.")
@app_commands.describe(target="Who should Jarvis address?")
async def jarvis_cmd(interaction: discord.Interaction, target: discord.Member):
    try:
        if not _has_mgmt_perms(interaction):
            return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)
        await interaction.response.send_message(
            f"Greetings {target.mention}, it's Tony's Assistant, **Jarvis** here. "
            "You have been selected as a test subject for the new **AIM-09 Inter-Continental Ballistic Missile**. "
            "It’s rapidly approaching, so I suggest you start packing. 💼🚀",
            ephemeral=False
        )
    except Exception as e:
        await report_interaction_error(interaction, e, "jarvis_cmd failed")

# ---- Priority controls ----
active_priority: dict | None = None

@tree.command(name="priority_start", description="Start a priority scene and log it.")
@app_commands.describe(user="Who is involved", kind="Type of priority")
@app_commands.choices(kind=[
    app_commands.Choice(name="Shooting", value="Shooting"),
    app_commands.Choice(name="Robbery", value="Robbery"),
    app_commands.Choice(name="Pursuit", value="Pursuit"),
    app_commands.Choice(name="Other", value="Other"),
])
async def priority_start(interaction: discord.Interaction, user: discord.Member, kind: app_commands.Choice[str]):
    try:
        if not _has_mgmt_perms(interaction):
            return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)
        global active_priority
        if active_priority:
            return await interaction.response.send_message("⚠️ A priority is already active. End it first.", ephemeral=True)

        active_priority = {
            "user_id": user.id,
            "kind": kind.value,
            "started_by": interaction.user.id,
            "ts": int(time.time())
        }

        embed = Embed(
            title="🚨 Priority Started",
            description=f"**User:** {user.mention}\n**Type:** {kind.value}\n**Time:** <t:{active_priority['ts']}:F>",
            color=discord.Color.red()
        )
        await interaction.response.send_message("✅ Priority started.", ephemeral=True)

        if PRIORITY_LOG_CHANNEL_ID:
            ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
    except Exception as e:
        await report_interaction_error(interaction, e, "priority_start failed")

@tree.command(name="priority_end", description="End the active priority and log it.")
async def priority_end(interaction: discord.Interaction):
    try:
        if not _has_mgmt_perms(interaction):
            return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)
        global active_priority
        if not active_priority:
            return await interaction.response.send_message("❌ No active priority.", ephemeral=True)

        user = interaction.guild.get_member(active_priority["user_id"]) or interaction.user
        embed = Embed(
            title="✅ Priority Ended",
            description=f"**User:** {user.mention}\n**Type:** {active_priority['kind']}\n**Ended:** <t:{int(time.time())}:F>",
            color=discord.Color.green()
        )
        active_priority = None
        await interaction.response.send_message("✅ Priority ended.", ephemeral=True)

        if PRIORITY_LOG_CHANNEL_ID:
            ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
            if ch:
                await ch.send(embed=embed)
    except Exception as e:
        await report_interaction_error(interaction, e, "priority_end failed")

# ---- Session announce helpers ----
def _maybe_ping_session_role(guild: discord.Guild) -> str | None:
    if not guild:
        return None
    if not SESSION_PING_ROLE_ID:
        return None
    r = guild.get_role(SESSION_PING_ROLE_ID)
    return r.mention if r else None

class RSVPView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.attending: list[int] = []
        self.not_attending: list[int] = []
        self.late: list[int] = []

    async def _update_embed(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        lines = embed.description.split("▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬")
        # Keep the original session info intact
        session_info = "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬".join(lines[:3])  

        attending_list = "\n".join([f"<@{uid}>" for uid in self.attending]) or "_"
        not_list = "\n".join([f"<@{uid}>" for uid in self.not_attending]) or "_"
        late_list = "\n".join([f"<@{uid}>" for uid in self.late]) or "_"

        rsvp_section = (
            f"✅ Attending ({len(self.attending)}/24)\n{attending_list}\n\n"
            f"❌ Not Attending ({len(self.not_attending)})\n{not_list}\n\n"
            f"⏰ Late ({len(self.late)})\n{late_list}"
        )

        embed.description = session_info + "\n▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n" + rsvp_section
        await interaction.message.edit(embed=embed, view=self)
        await interaction.response.defer()

    @discord.ui.button(label="✅ Attending", style=discord.ButtonStyle.success)
    async def attending_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._remove_user(interaction.user.id)
        self.attending.append(interaction.user.id)
        await self._update_embed(interaction)

    @discord.ui.button(label="❌ Not Attending", style=discord.ButtonStyle.danger)
    async def not_attending_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._remove_user(interaction.user.id)
        self.not_attending.append(interaction.user.id)
        await self._update_embed(interaction)

    @discord.ui.button(label="⏰ Late", style=discord.ButtonStyle.secondary)
    async def late_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        self._remove_user(interaction.user.id)
        self.late.append(interaction.user.id)
        await self._update_embed(interaction)

    def _remove_user(self, user_id: int):
        if user_id in self.attending: self.attending.remove(user_id)
        if user_id in self.not_attending: self.not_attending.remove(user_id)
        if user_id in self.late: self.late.remove(user_id)


@tree.command(name="host_main_session", description="Announce Main Session with RSVP details.")
@app_commands.describe(psn="Host PSN", date_time="When (e.g., Aug 15, 20:00 UTC)", session_type="Patrol, Heist, etc.", aop="Area of Play")
async def host_main_session(interaction: discord.Interaction, psn: str, date_time: str, session_type: str, aop: str):
    try:
        if not _has_mgmt_perms(interaction):
            return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)

        base_desc = (
            f"**Los Santos Roleplay™ PlayStation |** `Main Session`\n\n"
            "> *This message upholds all information regarding the upcoming roleplay session hosted by Los Santos Roleplay. "
            "Please take your time to review the details below and if any questions arise, please ask the host of the session.*\n\n"
            f"**PSN:** {psn}\n\n"
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            "**Commencement Process.**\n"
            "> *At the below time invites will begin being distributed. You will then be directed to your proper briefing channels. "
            "We ask that you're to ensure you are connected to the Session Queue voice channel.*\n\n"
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            "**Session Orientation**\n"
            "> *Before the session begins, all individuals must be orientated accordingly. The orientation will happen after the invites are dispersed and you will be briefed by the highest-ranking official in terms of your department.*\n\n"
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            "**Session Details.**\n"
            f"**Start Time:** {date_time}\n"
            f"• **Session Type:** {session_type}\n"
            f"• **Area of Play:** {aop}\n"
            "• [LSRPNetwork Guidelines](https://discord.com/channels/1324117813878718474/1375046710002319460/1395728361371861103) "
            "• [Priority Guidelines](https://discord.com/channels/1324117813878718474/1399853866337566881) •\n\n"
            "▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬\n"
            "✅ Attending (0/24)\n_\n\n❌ Not Attending (0)\n_\n\n⏰ Late (0)\n_"
        )
        embed = Embed(description=base_desc, color=discord.Color.blurple())

        ping = _maybe_ping_session_role(interaction.guild)
        await interaction.response.send_message(content=ping, embed=embed, view=RSVPView())
    except Exception as e:
        await report_interaction_error(interaction, e, "host_main_session failed")

@tree.command(name="start_session", description="Announce that the session is starting now.")
@app_commands.describe(psn="Host PSN", aop="Area of Play")
async def start_session(interaction: discord.Interaction, psn: str, aop: str):
    try:
        if not _has_mgmt_perms(interaction):
            return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)

        embed = Embed(
            title="🟢 SESSION START NOTICE",
            description=(
                "**The session is now officially starting!**\n\n"
                f"📍 **Host PSN:** {psn}\n"
                f"📍 **AOP:** {aop}\n"
                f"🕒 **Start Time:** <t:{int(time.time())}:F>\n\n"
                "🔊 **Please Ensure:**\n"
                "• You are in correct RP attire.\n"
                "• Your mic is working.\n"
                "• You follow all RP & community guidelines.\n"
                "• You join promptly to avoid being marked absent."
            ),
            color=discord.Color.green()
        )
        ping = _maybe_ping_session_role(interaction.guild)
        await interaction.response.send_message(content=ping, embed=embed, ephemeral=False)
    except Exception as e:
        await report_interaction_error(interaction, e, "start_session failed")

@tree.command(name="end_session", description="Announce that the session has ended.")
async def end_session(interaction: discord.Interaction):
    try:
        if not _has_mgmt_perms(interaction):
            return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)

        embed = Embed(
            title="🔴 SESSION CLOSED",
            description=(
                "**This session has now concluded.**\n\n"
                f"🕒 **End Time:** <t:{int(time.time())}:F>\n\n"
                "🙏 **Thank you to everyone who attended and maintained professionalism throughout the session.**"
            ),
            color=discord.Color.red()
        )
        ping = _maybe_ping_session_role(interaction.guild)
        await interaction.response.send_message(content=ping, embed=embed, ephemeral=False)
    except Exception as e:
        await report_interaction_error(interaction, e, "end_session failed")

# -------------------------
# Watchdog
# -------------------------
FAILED_LIMIT = 3

@tasks.loop(minutes=1)
async def watchdog():
    try:
        if not bot.is_ready():
            watchdog.failures = getattr(watchdog, "failures", 0) + 1
        else:
            await bot.fetch_guild(HQ_GUILD_ID)
            watchdog.failures = 0
        if getattr(watchdog, "failures", 0) >= FAILED_LIMIT:
            os._exit(1)
    except Exception:
        pass

@watchdog.before_loop
async def before_watchdog():
    await bot.wait_until_ready()

# -------------------------
# Global command error hook
# -------------------------
@tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await report_interaction_error(interaction, error, "Slash command error")

# -------------------------
# on_ready — sync + register persistent views + autopost panel
# -------------------------
@bot.event
async def on_ready():
    try:
        # Register persistent views (must have fixed custom_id)
        bot.add_view(ApplicationPanel())
        bot.add_view(ReviewButtonsPersistent())
    except Exception as e:
        logging.error("add_view error: %s", e)

    # quick HQ sync + global sync
    try:
        hq_synced = await tree.sync(guild=Object(id=HQ_GUILD_ID))
        logging.info("✅ Synced %d commands to HQ guild %s", len(hq_synced), HQ_GUILD_ID)
    except Exception as e:
        logging.error("⚠️ HQ sync error: %s", e)

    try:
        global_synced = await tree.sync()
        logging.info("🌍 Pushed %d commands globally", len(global_synced))
    except Exception as e:
        logging.error("⚠️ Global sync error: %s", e)

    if not watchdog.is_running():
        watchdog.start()

    # Autopost panel (once) if not present recently
    try:
        hq = bot.get_guild(HQ_GUILD_ID)
        if hq:
            ch = hq.get_channel(PANEL_CHANNEL_ID)
            if ch:
                async for m in ch.history(limit=25):
                    if m.author == bot.user and m.components:
                        break
                else:
                    await post_panel(ch)
                    logging.info("✅ Application panel posted in #%s", getattr(ch, "name", "?"))
    except Exception as e:
        logging.error("⚠️ Could not autopost panel: %s", e)

    logging.info("🟢 Bot is online as %s", bot.user)

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    # Tip: in Railway variables, set PYTHONUNBUFFERED=1 for real-time logs
    bot.run(BOT_TOKEN)
