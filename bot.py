# =========================
# LSRP Network System™®  — Application Core + Auth + Anti-ping
# Focused build: keep application system + /auth_grant + anti-ping + role/callsign on join (PS4)
# =========================

import os
import time
import random
import threading
import asyncio
from typing import Dict, List, Tuple

import requests
import urllib.parse

import discord
from discord import app_commands, Embed, Object
from discord.ext import commands, tasks
from discord.ui import View, Button, Select

from flask import Flask, request, redirect, render_template_string

# -------------------------
# ENV / CONSTANTS
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")

# OAuth (already configured in your app)
CLIENT_ID = os.getenv("CLIENT_ID") or "1397974568706117774"
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or "KcaapGwCEsH_JDlIbrAX3lghSC-tDREN"
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://lsrpnetwork-verification.up.railway.app/auth")

# Guilds
HQ_GUILD_ID      = int(os.getenv("HQ_GUILD_ID", "1294319617539575808"))  # per your last message
PS4_GUILD_ID     = int(os.getenv("PS4_GUILD_ID", "1324117813878718474"))
PS5_GUILD_ID     = int(os.getenv("PS5_GUILD_ID", "1401903156274790441"))
XBOX_OG_GUILD_ID = int(os.getenv("XBOX_OG_GUILD_ID", "1375494043831898334"))

PLATFORM_GUILDS = {
    "PS4":    PS4_GUILD_ID,
    "PS5":    PS5_GUILD_ID,
    "XboxOG": XBOX_OG_GUILD_ID,
}

# Channels / Roles (HQ guild)
PANEL_CHANNEL_ID          = 1324115220725108877
APP_REVIEW_CHANNEL_ID     = 1366431401054048357
AUTH_CODE_LOG_CHANNEL     = 1395135616177668186

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

# Optional: “Accepted” roles in HQ (not used here, but kept for future)
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
# Per-user application session
app_sessions: Dict[int, dict] = {}  # user_id -> {dept, subdept, platform, started_at, answers: [(q,a),...]}
# Pending OAuth codes
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

def now_ts() -> int:
    return int(time.time())

def readable_remaining(deadline: float) -> str:
    left = max(0, int(deadline - time.time()))
    m, s = divmod(left, 60)
    return f"{m}m {s}s"

# -------------------------
# Question Sets
# -------------------------
# The first 4 questions are common to ALL depts.
COMMON_4 = [
    ("Q1", "What's your Discord username?"),
    ("Q2", "How old are you IRL?"),
    ("Q3", "What's your Date of Birth IRL?"),
    ("Q4", "How did you find us? (type one): Instagram / Tiktok / Partnership / Friend / Other"),
]

# Department-specific additions (keep the important dept/roleplay questions)
PSO_SPECIFIC = [
    ("Q5", "What attracts you to **Public Safety** work within LSRP?"),
    ("Q6", "Do you have prior law enforcement roleplay experience? If yes, where and what rank?"),
    ("Q7", "Briefly explain the difference between **BCSO** and **SASP** jurisdictions."),
    ("Q8", "Scenario: You arrive first on a shots-fired scene with civilians nearby. What's your immediate action plan?"),
    ("Q9", "On a scale of 1-10, rate your radio discipline and explain your answer."),
    ("Q10","Confirm you’ll follow all PSO SOPs and sub-department rules. (Yes/No and any comment)"),
]

CO_SPECIFIC = [
    ("Q5", "What kind of civilian stories do you enjoy creating (legal/illegal/entrepreneur)?"),
    ("Q6", "How do you avoid low-effort/chaotic RP while staying engaging for others?"),
    ("Q7", "Describe a recent **creative** civilian scene you ran or would like to try here."),
    ("Q8", "Are you comfortable with passive RP (dialogue, world-building) not centered on combat? Why?"),
    ("Q9", "What conflicts do you think civilians should avoid initiating and why?"),
    ("Q10","Confirm you’ll follow all CO guidelines. (Yes/No and any comment)"),
]

SAFR_SPECIFIC = [
    ("Q5", "Why do you want to join **San Andreas Fire & Rescue**?"),
    ("Q6", "Any prior Fire/EMS RP? Certifications or knowledge you’d like to mention?"),
    ("Q7", "Scenario: Multi-vehicle collision with fire and multiple injured. What are your first 3 priorities?"),
    ("Q8", "Are you comfortable with medical RP steps (triage, basic life support)?"),
    ("Q9", "What does teamwork mean to you in an emergency-services setting?"),
    ("Q10","Confirm you’ll follow all SAFR protocols. (Yes/No and any comment)"),
]

DEPT_QUESTIONS = {
    "PSO": COMMON_4 + PSO_SPECIFIC,
    "CO":  COMMON_4 + CO_SPECIFIC,
    "SAFR":COMMON_4 + SAFR_SPECIFIC,
}

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
        dept = self.values[0]
        user = interaction.user

        # Initialize session
        app_sessions[user.id] = {
            "dept": dept,
            "guild_id": interaction.guild.id,
            "answers": [],
            "started_at": time.time(),
            "deadline": time.time() + APP_TOTAL_TIME_SECONDS,
        }

        color = dept_color(dept)

        # DM intro
        try:
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

            # If PSO, ask sub-department; SAFR skips subdept → platform
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
                plat_role = None  # will be added after platform selection
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

            await interaction.response.send_message("📬 I’ve sent you a DM to continue your application.", ephemeral=True)

        except discord.Forbidden:
            await interaction.response.send_message("⚠️ I couldn’t DM you. Please enable DMs and select again.", ephemeral=True)

class ApplicationPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
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

class SubDeptView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(SubDeptSelect(user_id))

class PlatformView(View):
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

async def post_review(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess:
        return
    dept = sess["dept"]
    subdept = sess.get("subdept", "N/A")
    platform = sess.get("platform", "N/A")
    answers: List[Tuple[str, str]] = sess.get("answers", [])
    color = dept_color(dept)

    # Build review embed
    desc_lines = [
        f"**Applicant:** {user.mention} (`{user.id}`)",
        f"**Department:** {dept}",
        f"**Sub-Department:** {subdept}",
        f"**Platform:** {platform}",
        "",
        "**Application Responses:**",
    ]
    for idx, (qt, ans) in enumerate(answers, start=1):
        desc_lines.append(f"**Q{idx}: {qt}**")
        desc_lines.append(f"> {ans}\n")

    review_embed = Embed(
        title="🗂️ New Application Submitted",
        description="\n".join(desc_lines),
        color=color
    ).set_footer(text="Los Santos Roleplay Network™®")

    guild = bot.get_guild(HQ_GUILD_ID)
    if not guild:
        return
    ch = guild.get_channel(APP_REVIEW_CHANNEL_ID)
    if not ch:
        return

    view = ReviewButtons(user_id=user.id, dept=dept, subdept=subdept, platform=platform)
    msg = await ch.send(embed=review_embed, view=view)

    # DM confirmation to applicant
    try:
        dm = await user.create_dm()
        await dm.send(embed=Embed(
            title="✅ Application Submitted",
            description=(
                "Your application was submitted and is now under review by staff.\n"
                "You will be notified here once a decision is made."
            ),
            color=color
        ))
    except Exception:
        pass

class ReviewButtons(View):
    def __init__(self, user_id: int, dept: str, subdept: str, platform: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.dept = dept
        self.subdept = subdept
        self.platform = platform

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You can’t accept applications.", ephemeral=True)

        # Ping reminder to run /auth_grant
        await interaction.response.send_message(
            f"✅ Accepted. Please run **/auth_grant** for <@{self.user_id}> (Dept `{self.dept}` | Platform `{self.platform}`) to grant main server access.",
            ephemeral=True
        )

        # Notify applicant
        user = bot.get_user(self.user_id) or await bot.fetch_user(self.user_id)
        if user:
            try:
                code_preview = "**This is your 1 time 6 digit code:** `xxxxxx`\n**Once this code is used in the authorization link it will no longer be valid.**"
                e = Embed(
                    title="🎉 Application Accepted",
                    description=(
                        f"Congratulations! You’ve been **accepted** into **{self.dept}**.\n\n"
                        f"{code_preview}\n\n"
                        f"[Main Server Verification Link]({REDIRECT_URI})"
                    ),
                    color=dept_color(self.dept)
                )
                e.set_image(url=ACCEPT_GIF_URL)
                # Also include a button
                view = View()
                view.add_item(discord.ui.Button(label="Open Verification", url=REDIRECT_URI, style=discord.ButtonStyle.link))
                await user.send(embed=e, view=view)
            except Exception:
                pass

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You can’t deny applications.", ephemeral=True)

        await interaction.response.send_message("❌ Application denied. Denied role applied (12h).", ephemeral=True)

        # Add denied role in HQ
        guild = bot.get_guild(HQ_GUILD_ID)
        if guild:
            try:
                member = guild.get_member(self.user_id) or await guild.fetch_member(self.user_id)
                role = guild.get_role(ROLE_DENIED_12H)
                if role:
                    await member.add_roles(role, reason="Application denied")
            except Exception:
                pass

        # Notify applicant
        user = bot.get_user(self.user_id) or await bot.fetch_user(self.user_id)
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

# -------------------------
# Panel posting
# -------------------------
async def post_panel(channel: discord.TextChannel):
    embed = Embed(
        title="📋 Los Santos Roleplay Network™® | Department Applications",
        description=(
            "Welcome to the official **Los Santos Roleplay Network™®** application panel.\n"
            "Select a department below to begin. I will continue your application in DMs.\n\n"
            "**Departments:**\n"
            "• **PSO** – Public Safety Office (Law Enforcement)\n"
            "• **CO** – Civilian Operations (Civilian Roleplay)\n"
            "• **SAFR** – San Andreas Fire & Rescue (Fire & EMS)\n\n"
            "*Please ensure your DMs are open to receive questions.*"
        ),
        color=discord.Color.blurple(),
    )
    embed.set_image(url=PANEL_IMAGE_URL)
    await channel.send(embed=embed, view=ApplicationPanel())

@tree.command(name="post_application_panel", description="Post the permanent application panel in the current channel.")
async def post_application_panel_slash(interaction: discord.Interaction):
    if interaction.guild is None:
        return await interaction.response.send_message("Use this inside the target channel.", ephemeral=True)
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
        return await interaction.response.send_message("🚫 You don’t have permission.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    await post_panel(interaction.channel)
    await interaction.followup.send("✅ Panel posted here.", ephemeral=True)

@bot.command(name="?post_application_panel")
async def post_application_panel_prefix(ctx: commands.Context):
    if not ctx.guild:
        return
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in getattr(ctx.author, "roles", [])):
        return await ctx.reply("🚫 You don’t have permission.")
    await post_panel(ctx.channel)
    # delete the trigger message to keep the channel clean
    try:
        await ctx.message.delete()
    except Exception:
        pass

# -------------------------
# /auth_grant — generate 6-digit and DM
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
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
        return await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)

    # Use the subdept from session if present (for PSO)
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
        view = View()
        view.add_item(discord.ui.Button(label="Open Verification", url=REDIRECT_URI, style=discord.ButtonStyle.link))
        await user.send(embed=e, view=view)
    except Exception:
        pass

    await interaction.followup.send(f"✅ Code sent to {user.mention}'s DMs.", ephemeral=True)

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
                "redirect_uri": REDIRECT_URI,
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
            "redirect_uri": REDIRECT_URI,
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

    # For PS4 guild: auto roles + callsign
    try:
        if target_guild_id == PS4_GUILD_ID:
            g = bot.get_guild(PS4_GUILD_ID)
            if g:
                m = g.get_member(user_id) or asyncio.run_coroutine_threadsafe(g.fetch_member(user_id), bot.loop).result(timeout=10)
                dept = pdata["dept"]
                sub = pdata.get("subdept", "N/A")

                to_add = []

                if dept == "PSO":
                    # main + subdept + category + starter
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
                    # callsign
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

# -------------------------
# Anti-ping
# -------------------------
@bot.event
async def on_message(message: discord.Message):
    # Let commands run
    await bot.process_commands(message)

    if message.author.bot or not message.guild:
        return

    if PROTECTED_USER_ID in [u.id for u in message.mentions]:
        mgmt_role_id = ANTI_PING_GUILDS.get(message.guild.id)
        if mgmt_role_id:
            has_immunity = any(r.id == mgmt_role_id for r in getattr(message.author, "roles", []))
            if not has_immunity:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    warn = (
                        f"Naughty Naughty {message.author.mention}, please don't ping Dom2019og, "
                        "he is a busy man but his DMs are always open.\n"
                        "Pinging him again will result in a written warning. "
                        "If you request help, please open a support ticket in "
                        "https://discord.com/channels/1294319617539575808/1367056555035459606 ."
                    )
                    await message.channel.send(warn, delete_after=12)
                except Exception:
                    pass

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
# on_ready — sync + autopost panel
# -------------------------
@bot.event
async def on_ready():
    # persist view
    try:
        bot.add_view(ApplicationPanel())
    except Exception:
        pass

    # quick HQ sync + global sync
    try:
        hq_synced = await tree.sync(guild=Object(id=HQ_GUILD_ID))
        print(f"✅ Synced {len(hq_synced)} commands to HQ guild {HQ_GUILD_ID}")
    except Exception as e:
        print(f"⚠️ HQ sync error: {e}")

    try:
        global_synced = await tree.sync()
        print(f"🌍 Pushed {len(global_synced)} commands globally")
    except Exception as e:
        print(f"⚠️ Global sync error: {e}")

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
                    print(f"✅ Application panel posted in #{ch.name}")
    except Exception as e:
        print(f"⚠️ Could not autopost panel: {e}")

    print(f"🟢 Bot is online as {bot.user}")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    bot.run(BOT_TOKEN)
