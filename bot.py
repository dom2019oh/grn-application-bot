# =========================
# LSRP Network System™® Bot
# Full build – August 2025
# =========================

# ─────────────────────────────────────────
# IMPORTS
# ─────────────────────────────────────────
import os
import time
import random
import threading
import requests
import urllib.parse
import asyncio
from typing import Dict, List, Tuple, Optional

import discord
from discord import app_commands, Embed, Object
from discord.ext import commands, tasks
from discord.ui import View, Button, Select, button
from flask import Flask, request, redirect, render_template_string

# ─────────────────────────────────────────
# CONFIG (EDIT THESE ONLY)
# ─────────────────────────────────────────

CONFIG = {
    # --- Core tokens & URLs ---
    "BOT_TOKEN": os.getenv("BOT_TOKEN"),
    "CLIENT_ID": os.getenv("CLIENT_ID", "1397974568706117774"),
    "CLIENT_SECRET": os.getenv("CLIENT_SECRET", "KcaapGwCEsH_JDlIbrAX3lghSC-tDREN"),
    "REDIRECT_URI": os.getenv("REDIRECT_URI", "https://lsrpnetwork-verification.up.railway.app/auth"),

    # --- Guilds ---
    "HQ_GUILD_ID":            1294319617539575808,  # HQ (panel lives here)
    "PS4_GUILD_ID":           1324117813878718474,  # Main PS4 guild (roles/callsigns applied here)
    # PS5/Xbox ready for future expansion:
    "PS5_GUILD_ID":           1401903156274790441,
    "XBOX_OG_GUILD_ID":       1375494043831898334,

    # --- Channels (HQ) ---
    "PANEL_CHANNEL_ID":       1324115220725108877,  # Permanent application panel channel (HQ)
    "REVIEW_CHANNEL_ID":      1366431401054048357,  # Application review channel (HQ)
    "OAUTH_LOG_CHANNEL_ID":   1395135616177668186,  # OAuth + actions log (HQ)

    # --- Panel/DM media ---
    "PANEL_IMAGE_URL": "https://cdn.discordapp.com/attachments/1317589676336611381/1405147584456032276/Sunset_Photography_Tumblr_Banner.png?ex=689dc52a&is=689c73aa&hm=f7fd9a078016e1fc61d54391e5d57bf61f0c1f6b09e82b8163b16eae312c0f1a&",
    "ACCEPT_GIF_URL": "https://cdn.discordapp.com/attachments/1317589676336611381/1402368709783191713/Animated_LSRP.gif?ex=689d8c63&is=689c3ae3&hm=5cd9a2cff01d151238b2fd245a8128ada27122b5f4d7d1d2214332c0324dd3fb&",
    "VERIFICATION_LINK": "https://lsrpnetwork-verification.up.railway.app/auth",

    # --- Staff permissions (HQ) ---
    "STAFF_CAN_POST_PANEL_ROLE": 1384558588478886022,  # staff allowed to post panel & use /auth_grant
    "ADMIN_ROLE_ID":             1375046495283318805,  # for /promote permissions
    "MOD_ROLE_ID":               1375046497590054985,  # for /promote permissions

    # --- HQ roles for application state ---
    "ROLE_DENIED_ID":   1323755533492027474,  # denied cooldown (12h)
    "ROLE_PENDING_ID":  1323758692918624366,  # (optional pending tag in HQ)

    # --- Applicant roles (HQ) ---
    "APPLICANT_DEPT_ROLES": {
        "PSO":  1370719624051691580,
        "CO":   1323758149009936424,
        "SAFR": 1370719781488955402,
    },
    # Platform applicants (HQ)
    "APPLICANT_PLATFORM_ROLES": {
        "PS4":   1401961522556698739,
        "PS5":   1401961758502944900,
        "XboxOG":1401961991756578817,
    },
    # Accepted (HQ) — not used in PS4 grants, but kept for UI/labels
    "ACCEPTED_PLATFORM_ROLES": {
        "PS4":   1367753287872286720,
        "PS5":   1367753535839797278,
        "XboxOG":1367753756367912960,
    },

    # --- PS4 Guild Department roles ---
    "PS4_DEPT_ROLES": {
        "PSO_MAIN": 1375046521904431124,
        "SASP":     1401347813958226061,
        "BCSO":     1401347339796348938,
        "CO":       1375046547678429195,
        "SAFR":     1401347818873946133,
    },

    # Category roles for clean role stacking (PS4)
    "PS4_CATEGORY_ROLES": {
        "PSO_RANKS_CATEGORY": 1404575562290434190,     # Public Safety Rank(s)
        "CO_RANKS_CATEGORY":  1375046548747980830,     # Civilian Operations Rank(s)
        "SAFR_RANKS_CATEGORY":1375046571653201961,     # Fire/EMS Rank(s)
        "BCSO_RANKS_CATEGORY":1375046520469979256,     # Sheriff’s Office Rank(s)
    },

    # --- PSO Rank roles (PS4) SASP (kept from previous naming) ---
    "PSO_RANK_ROLES": {
        "Cadet":             1375046543329202186,
        "Trooper":           1375046541869584464,
        "Trooper First Class":1375046540925599815,
        "Sergeant":          1392169682596790395,
        "Master Sergeant":   1375046535410356295,
        "Lieutenant":        1375046533833035778,
        "Captain":           1375046532847501373,
        "Major":             1375046529752105041,
        "Commander":         1375046528963444819,
        "ADOPS":             1375046524567818270,
        "Supervisor":        1375046546554621952,  # additional on Sergeant
    },

    # --- BCSO Rank roles (PS4) ---
    "BCSO_RANK_ROLES": {
        "Probationary Deputy": 1404903885432164362,
        "Deputy":              1401368189543252029,
        "Senior Deputy":       1401368085629370488,
        "Deputy Sergeant":     1401367986614440156,
        "Deputy MSGT":         1401367878770491473,
        "Deputy Lieutenant":   1401347822669922304,
        "Deputy Captain":      1401347820635684994,
        "Undersheriff":        1405177276651278479,
        "Sheriff":             1405178452931379220,
    },

    # --- CO Rank roles (PS4) ---
    "CIV_RANK_ROLES": {
        "Probationary Civ": 1375046566150406155,
        "Civilian 1":       1375046564921475102,
        "Civilian 2":       1375046563231174746,
        "Civilian 3":       1375046562182332436,
        "Civilian 4":       1375046561125498921,
        "Civilian 5":       1375046559544119298,
        "Senior Civilian":  1375046558902390876,
        "Gang Manager":     1375046557292036146,
        "Civilian Advisor": 1375046555173785620,
        "Civ Deputy Director": 1375046551100985387,
        "Civ Director":        1375046550555988050,
    },

    # --- SAFR Rank roles (PS4) ---
    "SAFR_RANK_ROLES": {
        "Probationary Firefighter": 1375046583153856634,
        "Firefighter 1":            1375046585150603357,
        "Firefighter Sergeant":     1375046582034235503,
        "Firefighter Lieutenant":   1375046581111361597,
        "Firefighter Captain":      1375046579047632926,
        "Battalion Chief":          1375046577214849075,
        "Deputy Fire Chief":        1375046575499513966,
        "Fire Chief":               1375046574593413151,
    },

    # --- Session ping role (any guild that uses it) ---
    "SESSION_PING_ROLE_ID": 1375046631237484605,

    # --- Ping immunity (HQ + PS4) ---
    "IMMUNE_USER_ID": 1176071547476262986,  # Dom
    "HQ_IMMUNE_ROLE": 1338855588381200426,  # Management Team (HQ)
    "PS4_IMMUNE_ROLE":1375046488194809917,  # Management Team (PS4)

    # --- Timeouts ---
    "APPLICATION_TTL_SECONDS": 35 * 60,  # 35 minutes
    "AUTH_CODE_TTL_SECONDS":    5 * 60,  # 5 minutes

    # --- Other ---
    "COMMAND_PREFIX": "?",  # for post_application_panel trigger
}

# Basic sanity
if not CONFIG["BOT_TOKEN"]:
    raise RuntimeError("BOT_TOKEN env var is required.")

# ─────────────────────────────────────────
# GLOBALS / STATE
# ─────────────────────────────────────────

# Per-user application session tracker
app_sessions: Dict[int, Dict] = {}  # {user_id: {"dept":..., "answers":[...], "started_at":..., "review_msg_id":..., "platform":"PS4"}}

# Pending OAuth codes (user_id → data)
pending_codes: Dict[int, Dict] = {}  # {user_id: {"code":..., "timestamp":..., "dept":..., "platform":..., "granted_by":...}}

# ─────────────────────────────────────────
# FLASK OAUTH SERVER (runs in background)
# ─────────────────────────────────────────

_WEB = Flask(__name__)

@_WEB.route("/")
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
<p style="color:gray">If you opened this directly, return to your DM and use the link again.</p>
</body></html>
"""

@_WEB.route("/auth", methods=["GET", "POST"])
def oauth_handler():
    # Redirect to OAuth if no ?code
    code = request.args.get("code")
    if not code:
        auth_url = (
            "https://discord.com/oauth2/authorize?"
            + urllib.parse.urlencode({
                "client_id": CONFIG["CLIENT_ID"],
                "response_type": "code",
                "redirect_uri": CONFIG["REDIRECT_URI"],
                "scope": "identify guilds.join"
            })
        )
        return redirect(auth_url, code=302)

    if request.method == "GET":
        return render_template_string(_HTML_FORM)

    pin = (request.form.get("pin") or "").strip()

    # Exchange code for token
    token_resp = requests.post(
        "https://discord.com/api/oauth2/token",
        data={
            "client_id": CONFIG["CLIENT_ID"],
            "client_secret": CONFIG["CLIENT_SECRET"],
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CONFIG["REDIRECT_URI"],
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

    data = pending_codes.get(user_id)
    # Detailed logging to HQ
    try:
        loop = bot.loop
        guild = bot.get_guild(CONFIG["HQ_GUILD_ID"])
        log_ch = guild.get_channel(CONFIG["OAUTH_LOG_CHANNEL_ID"]) if guild else None
        if log_ch:
            asyncio.run_coroutine_threadsafe(
                log_ch.send(f"🔎 Verification attempt: <@{user_id}> | code entered `{pin}` | pending={'yes' if data else 'no'}"),
                loop
            )
    except Exception:
        pass

    if not data:
        return "No active authorization found. Ask staff to run /auth_grant again.", 400

    if time.time() - float(data["timestamp"]) > CONFIG["AUTH_CODE_TTL_SECONDS"]:
        pending_codes.pop(user_id, None)
        return "Your code expired. Ask staff to generate a new one.", 400

    if pin != str(data["code"]):
        return "Invalid code. Please go back and try again.", 400

    # Add member to PS4 guild (current scope)
    target_guild_id = CONFIG["PS4_GUILD_ID"]
    put_resp = requests.put(
        f"https://discord.com/api/guilds/{target_guild_id}/members/{user_id}",
        headers={"Authorization": f"Bot {CONFIG['BOT_TOKEN']}",
                 "Content-Type": "application/json"},
        json={"access_token": access_token},
        timeout=15
    )

    ok = put_resp.status_code in (200, 201, 204) or (put_resp.status_code == 400 and "already" in put_resp.text.lower())

    # Log outcome
    try:
        loop = bot.loop
        guild = bot.get_guild(CONFIG["HQ_GUILD_ID"])
        log_ch = guild.get_channel(CONFIG["OAUTH_LOG_CHANNEL_ID"]) if guild else None
        if log_ch:
            asyncio.run_coroutine_threadsafe(
                log_ch.send(f"{'✅' if ok else '❌'} Verification result for <@{user_id}> | dept `{data['dept']}` | code `{data['code']}` | resp {put_resp.status_code}"),
                loop
            )
    except Exception:
        pass

    if not ok:
        return f"Guild join failed: {put_resp.status_code} {put_resp.text}", 400

    # Success; consume code
    pending_codes.pop(user_id, None)
    return "✅ Success! You can close this tab and return to Discord."

def _run_web():
    port = int(os.environ.get("PORT", "8080"))
    _WEB.run(host="0.0.0.0", port=port)

# Start Flask in background
threading.Thread(target=_run_web, daemon=True).start()

# ─────────────────────────────────────────
# DISCORD CLIENT
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix=CONFIG["COMMAND_PREFIX"], intents=intents)
tree = bot.tree

# ─────────────────────────────────────────
# WATCHDOG RESTART (Railway friendly)
# ─────────────────────────────────────────
@tasks.loop(minutes=1)
async def watchdog():
    try:
        _ = bot.user
    except Exception:
        os._exit(1)

# ─────────────────────────────────────────
# UTILS: Colors, callsigns, roles, logging
# ─────────────────────────────────────────

def dept_color(dept: str) -> discord.Color:
    if dept == "PSO":
        return discord.Color.blue()
    if dept == "CO":
        return discord.Color.green()
    return discord.Color.red()  # SAFR

def ps0_callsign_for_rank(rank: str) -> str:
    # Simplified default – cadet C-####; supervisors get L-/B- as per ranges
    if rank == "Cadet":
        return f"C-{random.randint(1000,1999)}"
    # Generic officer band B-###, leadership L-###
    mapping = {
        "Trooper": "B",
        "Trooper First Class": "B",
        "Sergeant": "B",
        "Master Sergeant": "B",
        "Lieutenant": "L",
        "Captain": "L",
        "Major": "L",
        "Commander": "L",
        "ADOPS": "L",
    }
    prefix = mapping.get(rank, "B")
    num = random.randint(100, 999)
    return f"{prefix}-{num}"

def civ_callsign() -> str:
    return f"Civ-{random.randint(1000,9999)}"

def safr_callsign() -> str:
    return f"FF-{random.randint(100,999)}"

async def give_roles(member: discord.Member, role_ids: List[int], reason: str = None):
    roles = [member.guild.get_role(rid) for rid in role_ids if member.guild.get_role(rid)]
    if roles:
        await member.add_roles(*roles, reason=reason)

async def remove_roles(member: discord.Member, role_ids: List[int], reason: str = None):
    roles = [member.guild.get_role(rid) for rid in role_ids if member.guild.get_role(rid) and (member.guild.get_role(rid) in member.roles)]
    if roles:
        await member.remove_roles(*roles, reason=reason)

async def set_nick_safe(member: discord.Member, nick: str):
    try:
        await member.edit(nick=nick)
    except discord.Forbidden:
        pass

async def log_to_hq(text: str):
    guild = bot.get_guild(CONFIG["HQ_GUILD_ID"])
    if guild:
        ch = guild.get_channel(CONFIG["OAUTH_LOG_CHANNEL_ID"])
        if ch:
            await ch.send(text)

def is_staff(ctx_or_inter: discord.abc.Messageable) -> bool:
    # helper used in some places; for slash check use decorators
    return True

# ─────────────────────────────────────────
# APPLICATION QUESTIONS (first 4 common)
# ─────────────────────────────────────────

Q_COMMON = [
    ("What's your Discord username?", "text"),
    ("How old are you IRL?", "text"),
    ("What's your Date of Birth IRL?", "text"),
    ("How did you find us?", "buttons"),  # Instagram | Tiktok | Partnership | Friend | Other
]

# PSO remaining questions (from your preview)
Q_PSO_EXTRA = [
    ("Explain the \"No Life Rule\" in the best of your ability.", "text"),
    ("What does VDM, RDM and FRP mean? Describe in the best of your ability.", "text"),
    ("Do you have any roleplay experience, if so, please tell us.", "text"),
    ("What time zone are you from? (e.g., GMT, EST, UTC etc.)", "text"),
    ("Describe what a 10-11 means. In your own words.", "text"),
    ("You see a suspect with a knife coming at you. Select one action.", "choice: Taser | Shoot"),
    ("What does a 10-80 mean?", "choice: Vehicle chase"),
    ("How would you handle a 10-11?", "text"),
    ("You arrive at a robbery scene, suspect yells “I have a bomb!!” – what do you do next?", "text"),
    ("What does Code 1, 2, and 3 mean?", "text"),
    ("When you go on duty, what 10 codes do you use?", "text"),
    ("As a cadet, are you eligible to drive on your own?", "choice: Yes | No"),
    ("You see a sniper on a hilltop. You have a pistol and radio. What do you do? (min 20 words)", "text"),
    ("How would you handle a noise complaint? (min 20 words)", "text"),
    ("Choose the correct cadet loadout.", "choice: Pistol, taser, baton, flashlight"),
    ("What is a 10-99?", "text"),
]

Q_CO_EXTRA = [
    ("Explain the \"No Crime Zones\" in the best of your ability.", "text"),
    ("What is \"FailRP\"? Provide an example.", "text"),
    ("Describe your civilian roleplay experience.", "text"),
    ("What time zone are you from?", "text"),
    ("You are in a store and hear gunshots outside. What do you do?", "text"),
    ("You see a police chase passing you. Do you follow them?", "choice: Yes | No"),
    ("How would you report a corrupt cop in roleplay?", "text"),
    ("You are approached by a gang asking you to transport drugs. What do you do?", "text"),
    ("Describe a legal civilian job you would like to roleplay.", "text"),
    ("What does \"FearRP\" mean?", "text"),
    ("Can you rob someone in a green zone?", "choice: Yes | No"),
    ("You crash into another player's vehicle by accident. What do you do?", "text"),
    ("Describe how you would roleplay a court case as a civilian.", "text"),
    ("You want to start a business in roleplay. What's your first step?", "text"),
    ("What is the minimum word count for /me actions in our server? (number)", "text"),
    ("What is the maximum number of firearms a civilian can own? (number)", "text"),
]

Q_SAFR_EXTRA = [
    ("Explain the \"Fire Scene Safety Rule\" in the best of your ability.", "text"),
    ("What does \"IC\" and \"OOC\" mean?", "text"),
    ("Do you have any Fire/EMS roleplay experience?", "text"),
    ("What time zone are you from?", "text"),
    ("You arrive first to a car crash scene. What is your first action?", "text"),
    ("You see a civilian trapped in a burning building. What do you do?", "text"),
    ("How do you handle a chemical spill roleplay?", "text"),
    ("What does \"BLS\" and \"ALS\" stand for?", "text"),
    ("You are called to assist police with a barricaded suspect. How do you help?", "text"),
    ("How do you respond if multiple 911 calls come in at the same time?", "text"),
    ("What should be your radio communication priority during an active fire?", "text"),
    ("How do you ensure your safety at an accident scene?", "text"),
    ("What's the correct way to transport an unconscious patient?", "text"),
    ("You are the only medic available. Three patients need help. What do you do first?", "text"),
    ("What are the colors of a standard fire hydrant cap, and what do they mean?", "text"),
    ("What is the universal emergency number? (number)", "text"),
]

DEPT_QUESTIONS = {
    "PSO": Q_COMMON + Q_PSO_EXTRA,
    "CO":  Q_COMMON + Q_CO_EXTRA,
    "SAFR":Q_COMMON + Q_SAFR_EXTRA,
}

# ─────────────────────────────────────────
# VIEWS: Panel + DM Buttons
# ─────────────────────────────────────────

class HowFoundView(View):
    def __init__(self, user_id: int, question_idx: int):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.question_idx = question_idx

    async def handle(self, interaction: discord.Interaction, choice: str):
        sess = app_sessions.get(self.user_id)
        if not sess or interaction.user.id != self.user_id:
            return await interaction.response.send_message("This isn’t for you.", ephemeral=True)
        # Record answer:
        sess["answers"][self.question_idx] = choice
        await interaction.response.defer()
        await send_next_question(interaction.user)

    @button(label="Instagram", style=discord.ButtonStyle.primary)
    async def ig(self, interaction: discord.Interaction, _btn: Button):
        await self.handle(interaction, "Instagram")

    @button(label="Tiktok", style=discord.ButtonStyle.primary)
    async def tt(self, interaction: discord.Interaction, _btn: Button):
        await self.handle(interaction, "Tiktok")

    @button(label="Partnership", style=discord.ButtonStyle.secondary)
    async def partner(self, interaction: discord.Interaction, _btn: Button):
        await self.handle(interaction, "Partnership")

    @button(label="Friend", style=discord.ButtonStyle.success)
    async def friend(self, interaction: discord.Interaction, _btn: Button):
        await self.handle(interaction, "Friend")

    @button(label="Other", style=discord.ButtonStyle.danger)
    async def other(self, interaction: discord.Interaction, _btn: Button):
        await self.handle(interaction, "Other")

class DepartmentSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select a department to begin…",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Public Safety Office (PSO)", value="PSO", description="Law Enforcement"),
                discord.SelectOption(label="Civilian Operations (CO)", value="CO", description="Civilian Roleplay"),
                discord.SelectOption(label="San Andreas Fire & Rescue (SAFR)", value="SAFR", description="Fire & EMS"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        if user.id in app_sessions and (time.time() - app_sessions[user.id].get("started_at", 0) < CONFIG["APPLICATION_TTL_SECONDS"]):
            return await interaction.response.send_message("⚠️ You already have an application in progress. Please finish it first.", ephemeral=True)

        dept = self.values[0]
        app_sessions[user.id] = {
            "dept": dept,
            "answers": [""] * len(DEPT_QUESTIONS[dept]),
            "started_at": time.time(),
            "platform": "PS4",  # for now
            "review_msg_id": None,
        }

        color = dept_color(dept)
        try:
            dm = await user.create_dm()
            intro = Embed(
                title=f"📋 {dept} Application",
                description=(
                    "I’ll ask you a series of questions here. You have **35 minutes** to complete the application.\n\n"
                    "Please answer each question before the next one appears."
                ),
                color=color
            )
            await dm.send(embed=intro)
            await interaction.response.send_message("📬 I’ve sent you a DM to continue your application.", ephemeral=True)
            await send_next_question(user)
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ I couldn’t DM you. Please open DMs and try again.", ephemeral=True)

class ApplicationPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DepartmentSelect())

# ─────────────────────────────────────────
# APPLICATION FLOW HELPERS
# ─────────────────────────────────────────

async def send_next_question(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess:
        return
    dept = sess["dept"]
    questions = DEPT_QUESTIONS[dept]

    # timeout?
    if time.time() - sess["started_at"] > CONFIG["APPLICATION_TTL_SECONDS"]:
        await fail_timeout(user, dept)
        return

    # find first unanswered
    try:
        idx = sess["answers"].index("")
    except ValueError:
        # done
        await submit_application_for_review(user)
        return

    q_text, q_type = questions[idx]
    color = dept_color(dept)
    dm = await user.create_dm()

    # send question
    if q_type == "text":
        emb = Embed(title=f"Question {idx+1}", description=q_text, color=color)
        await dm.send(embed=emb)

        def check(m: discord.Message):
            return m.author.id == user.id and m.channel == dm

        try:
            msg = await bot.wait_for("message", check=check, timeout=CONFIG["APPLICATION_TTL_SECONDS"])
        except asyncio.TimeoutError:
            await fail_timeout(user, dept)
            return
        sess["answers"][idx] = msg.content.strip()
        await send_next_question(user)

    elif q_type.startswith("choice:"):
        choices_part = q_type.split(":", 1)[1].strip()
        # show as text + they reply; but we’ll accept any text and record it
        emb = Embed(title=f"Question {idx+1}", description=f"{q_text}\n\n**Options:** {choices_part}", color=color)
        await dm.send(embed=emb)

        def check(m: discord.Message):
            return m.author.id == user.id and m.channel == dm

        try:
            msg = await bot.wait_for("message", check=check, timeout=CONFIG["APPLICATION_TTL_SECONDS"])
        except asyncio.TimeoutError:
            await fail_timeout(user, dept)
            return
        sess["answers"][idx] = msg.content.strip()
        await send_next_question(user)

    elif q_type == "buttons":  # How did you find us?
        emb = Embed(title=f"Question {idx+1}", description=q_text, color=color)
        await dm.send(embed=emb, view=HowFoundView(user.id, idx))

async def fail_timeout(user: discord.User, dept: str):
    dm = await user.create_dm()
    await dm.send(embed=Embed(
        title="⏰ Application Timed Out",
        description="You did not complete the application in time. You can start again from the panel.",
        color=discord.Color.orange()
    ))
    await log_to_hq(f"⚠️ Application timed out for <@{user.id}> in **{dept}**.")
    app_sessions.pop(user.id, None)

def chunk_lines(lines: List[str], max_len: int = 4000) -> List[str]:
    # helper for long review descriptions
    chunks, buff = [], ""
    for line in lines:
        if len(buff) + len(line) + 1 > max_len:
            chunks.append(buff)
            buff = ""
        buff += (line + "\n")
    if buff:
        chunks.append(buff)
    return chunks

# ─────────────────────────────────────────
# REVIEW MESSAGE + DECISION BUTTONS
# ─────────────────────────────────────────

class ReviewDecisionView(View):
    def __init__(self, applicant_id: int, dept: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.dept = dept

    @button(label="✅ Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, _btn: Button):
        if not any(r.id == CONFIG["STAFF_CAN_POST_PANEL_ROLE"] for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You lack permission.", ephemeral=True)

        user = interaction.guild.get_member(self.applicant_id)
        # Message staff to run /auth_grant
        await interaction.response.send_message("✅ Application marked **Accepted**.\n**Please run `/auth_grant` to give the user access to the main server.**")
        await log_to_hq(f"🟢 ACCEPT pressed by {interaction.user.mention} for <@{self.applicant_id}> in **{self.dept}**.")

        # DM the applicant with congrats + instructions (code comes from /auth_grant)
        try:
            target = user or await bot.fetch_user(self.applicant_id)
            dm = await target.create_dm()
            e = Embed(
                title="🎉 Application Accepted",
                description=(
                    f"Great news! Your **{self.dept}** application was **Accepted**.\n\n"
                    "A staff member will now generate your one-time verification code. "
                    "Once you receive it, open the verification link and enter the code.\n\n"
                    f"[Main Server Verification Link]({CONFIG['VERIFICATION_LINK']})"
                ),
                color=dept_color(self.dept)
            )
            e.set_image(url=CONFIG["ACCEPT_GIF_URL"])
            view = View()
            view.add_item(discord.ui.Button(label="Open Verification", url=CONFIG["VERIFICATION_LINK"]))
            await dm.send(embed=e, view=view)
        except Exception:
            pass

    @button(label="❌ Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, _btn: Button):
        if not any(r.id == CONFIG["STAFF_CAN_POST_PANEL_ROLE"] for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You lack permission.", ephemeral=True)

        await interaction.response.send_message("❌ Application marked **Denied**.")
        await log_to_hq(f"🔴 DENY pressed by {interaction.user.mention} for <@{self.applicant_id}> in **{self.dept}**.")

        # Add denied cooldown role in HQ
        hq = bot.get_guild(CONFIG["HQ_GUILD_ID"])
        if hq:
            try:
                mem = hq.get_member(self.applicant_id) or await hq.fetch_member(self.applicant_id)
                role = hq.get_role(CONFIG["ROLE_DENIED_ID"])
                if role:
                    await mem.add_roles(role, reason="Application denied (12h cooldown)")
            except Exception:
                pass

        # DM polite denial
        try:
            target = await bot.fetch_user(self.applicant_id)
            dm = await target.create_dm()
            await dm.send(embed=Embed(
                title="Application Result",
                description="We appreciate your interest. Unfortunately, your application was not approved at this time. You may re-apply after the cooldown.",
                color=discord.Color.red()
            ))
        except Exception:
            pass

async def submit_application_for_review(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess:
        return
    dept = sess["dept"]
    questions = DEPT_QUESTIONS[dept]
    answers = sess["answers"]

    # Build lines "Q: ... \n A: ..."
    lines = []
    for i, (q, _qt) in enumerate(questions, start=1):
        a = answers[i-1] if i-1 < len(answers) else ""
        lines.append(f"**Q{i}. {q}**\n{a or '—'}\n")

    review = Embed(
        title=f"📝 New Application: {dept}",
        description="",
        color=dept_color(dept)
    )
    review.set_footer(text=f"Applicant ID: {user.id}")

    chunks = chunk_lines(lines)
    channel = bot.get_guild(CONFIG["HQ_GUILD_ID"]).get_channel(CONFIG["REVIEW_CHANNEL_ID"])
    if not channel:
        await log_to_hq("⚠️ Review channel not found.")
        app_sessions.pop(user.id, None)
        return

    # Send first embed with intro + first chunk
    review.description = chunks[0]
    msg = await channel.send(content=f"Applicant: <@{user.id}>", embed=review, view=ReviewDecisionView(user.id, dept))

    # Send extra chunks as followups
    for extra in chunks[1:]:
        await channel.send(embed=Embed(description=extra, color=dept_color(dept)))

    sess["review_msg_id"] = msg.id
    app_sessions[user.id] = sess
    await log_to_hq(f"📨 Submitted application for <@{user.id}> in **{dept}**.")
    # Final DM
    dm = await user.create_dm()
    await dm.send(embed=Embed(
        title="✅ Application Submitted",
        description="Your answers were sent to staff for review. You’ll receive a DM with the decision.",
        color=discord.Color.blurple()
    ))

# ─────────────────────────────────────────
# PANEL AUTO-POST + MANUAL POST
# ─────────────────────────────────────────

async def auto_post_panel():
    hq = bot.get_guild(CONFIG["HQ_GUILD_ID"])
    if not hq:
        return
    ch = hq.get_channel(CONFIG["PANEL_CHANNEL_ID"])
    if not ch:
        return
    async for msg in ch.history(limit=25):
        if msg.author == bot.user and msg.components:
            return  # already present
    e = Embed(
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
        color=discord.Color.blurple()
    )
    e.set_image(url=CONFIG["PANEL_IMAGE_URL"])
    await ch.send(embed=e, view=ApplicationPanel())
    await log_to_hq(f"✅ Application panel posted in #{ch.name}")

@bot.event
async def on_message(message: discord.Message):
    # Manual panel re-post
    if message.author.bot:
        return
    if message.content.strip().lower() == f"{CONFIG['COMMAND_PREFIX']}post_application_panel":
        # permission check
        if not any(r.id == CONFIG["STAFF_CAN_POST_PANEL_ROLE"] for r in message.author.roles):
            return await message.channel.send("🚫 You don't have permission.", delete_after=6)
        await message.delete()
        await auto_post_panel()
        return
    # Ping immunity (HQ + PS4)
    if message.guild and message.mentions:
        if CONFIG["IMMUNE_USER_ID"] in [m.id for m in message.mentions]:
            exempt_role_id = CONFIG["HQ_IMMUNE_ROLE"] if message.guild.id == CONFIG["HQ_GUILD_ID"] else CONFIG["PS4_IMMUNE_ROLE"]
            if exempt_role_id and any(r.id == exempt_role_id for r in message.author.roles):
                return
            try:
                await message.delete()
            except Exception:
                pass
            warn = (
                f"Naughty Naughty {message.author.mention}, please don't ping <@{CONFIG['IMMUNE_USER_ID']}>, "
                "he is a busy man but his DMs are always open.\n"
                "Pinging him again will result in a written warning. If you request help, please open a support ticket in "
                "https://discord.com/channels/1294319617539575808/1367056555035459606 ."
            )
            try:
                await message.channel.send(warn, delete_after=15)
            except Exception:
                pass

    await bot.process_commands(message)

# ─────────────────────────────────────────
# SLASH COMMANDS
# ─────────────────────────────────────────

@tree.command(name="ping", description="Check if the bot is alive (global).")
async def ping_cmd(interaction: discord.Interaction):
    await interaction.response.send_message("🟢 Pong!", ephemeral=True)

# --- AUTH GRANT ---
@tree.command(name="auth_grant", description="Generate a one-time 6-digit auth code for an accepted applicant (5 min expiry).")
@app_commands.describe(user="Applicant to authorize", department="Department")
@app_commands.choices(department=[
    app_commands.Choice(name="PSO", value="PSO"),
    app_commands.Choice(name="CO", value="CO"),
    app_commands.Choice(name="SAFR", value="SAFR"),
])
async def auth_grant(interaction: discord.Interaction, user: discord.Member, department: app_commands.Choice[str]):
    # Permission: staff role in HQ
    if not any(r.id == CONFIG["STAFF_CAN_POST_PANEL_ROLE"] for r in interaction.user.roles):
        return await interaction.response.send_message("🚫 You don't have permission.", ephemeral=True)

    code = random.randint(100000, 999999)
    pending_codes[user.id] = {
        "code": code,
        "timestamp": time.time(),
        "dept": department.value,
        "platform": "PS4",  # focusing PS4 now
        "granted_by": interaction.user.id,
    }
    await interaction.response.send_message(f"🔐 Generated code for {user.mention}: **{code}** (expires in 5 minutes).", ephemeral=True)

    # Log
    await log_to_hq(f"🔐 Auth code generated for <@{user.id}> | dept `{department.value}` | code `{code}` by {interaction.user.mention}")

    # DM user with code + link (button + markdown)
    try:
        dm = await user.create_dm()
        emb = Embed(
            title="Los Santos Roleplay Network™® — Authorization",
            description=(
                f"**This is your 1 time 6 digit code:** `{code}`\n"
                f"**Once this code is used in the authorization link it will no longer be valid.**\n\n"
                f"[Main Server Verification Link]({CONFIG['VERIFICATION_LINK']})"
            ),
            color=dept_color(department.value)
        )
        view = View()
        view.add_item(discord.ui.Button(label="Open Verification", url=CONFIG["VERIFICATION_LINK"]))
        emb.set_image(url=CONFIG["ACCEPT_GIF_URL"])
        await dm.send(embed=emb, view=view)
    except Exception:
        pass

# --- SESSION COMMANDS ---
@tree.command(name="host_main_session", description="Announce Main Session with RSVP buttons.")
@app_commands.describe(psn="Host PSN", date_time="Start time (e.g. July 26, 20:00 UTC)", session_type="Type (e.g. Patrol)", aop="Area of Play")
async def host_main_session(interaction: discord.Interaction, psn: str, date_time: str, session_type: str, aop: str):
    ping_role = interaction.guild.get_role(CONFIG["SESSION_PING_ROLE_ID"])
    base_desc = f"""**Los Santos Roleplay™ PlayStation |** `Main Session`

**PSN:** {psn}

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
**Session Details.**
**Start Time:** {date_time}
• **Session Type:** {session_type}
• **Area of Play:** {aop}
• [LSRPNetwork Guidelines](https://discord.com/channels/1324117813878718474/1375046710002319460/1395728361371861103) • [Priority Guidelines](https://discord.com/channels/1324117813878718474/1399853866337566881) •
"""
    class RSVPView(View):
        def __init__(self, base_desc, message_id):
            super().__init__(timeout=None)
            self.base_desc = base_desc
            self.message_id = message_id
            self.data = {'attendees': [], 'declines': [], 'late': []}

        async def update(self, inter: discord.Interaction):
            s = (
                f"\n✅ Attending: {', '.join(self.data['attendees']) or '—'}"
                f"\n❌ Not Attending: {', '.join(self.data['declines']) or '—'}"
                f"\n🕰️ Late: {', '.join(self.data['late']) or '—'}"
            )
            await inter.message.edit(embed=Embed(description=self.base_desc + s, color=discord.Color.blurple()), view=self)

        @button(label="✅ Attending", style=discord.ButtonStyle.success)
        async def a(self, inter: discord.Interaction, _btn: Button):
            m = inter.user.mention
            for k in self.data: 
                if m in self.data[k]: self.data[k].remove(m)
            self.data['attendees'].append(m)
            await inter.response.defer()
            await self.update(inter)

        @button(label="❌ Not Attending", style=discord.ButtonStyle.danger)
        async def d(self, inter: discord.Interaction, _btn: Button):
            m = inter.user.mention
            for k in self.data: 
                if m in self.data[k]: self.data[k].remove(m)
            self.data['declines'].append(m)
            await inter.response.defer()
            await self.update(inter)

        @button(label="🕰️ Late", style=discord.ButtonStyle.secondary)
        async def l(self, inter: discord.Interaction, _btn: Button):
            m = inter.user.mention
            for k in self.data: 
                if m in self.data[k]: self.data[k].remove(m)
            self.data['late'].append(m)
            await inter.response.defer()
            await self.update(inter)

    embed = Embed(description=base_desc, color=discord.Color.blurple())
    await interaction.response.send_message(content=ping_role.mention if ping_role else None, embed=embed, view=RSVPView(base_desc, interaction.id))

@tree.command(name="start_session", description="Announce session start.")
@app_commands.describe(psn="PSN", aop="Area of Play")
async def start_session(interaction: discord.Interaction, psn: str, aop: str):
    ping_role = interaction.guild.get_role(CONFIG["SESSION_PING_ROLE_ID"])
    e = Embed(
        title="🟢 SESSION START NOTICE",
        description=(
            f"📍 **Host PSN:** {psn}\n"
            f"📍 **AOP:** {aop}\n"
            f"🕒 **Start Time:** <t:{int(time.time())}:F>\n"
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(content=ping_role.mention if ping_role else None, embed=e)

@tree.command(name="end_session", description="Announce session end.")
async def end_session(interaction: discord.Interaction):
    ping_role = interaction.guild.get_role(CONFIG["SESSION_PING_ROLE_ID"])
    e = Embed(
        title="🔴 SESSION CLOSED",
        description=f"🕒 **End Time:** <t:{int(time.time())}:F>\n\nThanks for attending!",
        color=discord.Color.red()
    )
    await interaction.response.send_message(content=ping_role.mention if ping_role else None, embed=e)

# --- PROMOTE (Admin/Mod only) ---
def has_admin_or_mod():
    async def predicate(inter: discord.Interaction) -> bool:
        return any(r.id in (CONFIG["ADMIN_ROLE_ID"], CONFIG["MOD_ROLE_ID"]) for r in inter.user.roles)
    return app_commands.check(predicate)

@tree.command(name="promote", description="Promote a member within a department (updates role + callsign).")
@app_commands.describe(
    member="Member to promote (PS4 guild)",
    department="Department",
    rank="New rank"
)
@app_commands.choices(department=[
    app_commands.Choice(name="PSO (SASP/BCSO)", value="PSO"),
    app_commands.Choice(name="CO (Civilian)", value="CO"),
    app_commands.Choice(name="SAFR (Fire & Rescue)", value="SAFR"),
])
@has_admin_or_mod()
async def promote(interaction: discord.Interaction, member: discord.Member, department: app_commands.Choice[str], rank: str):
    dept = department.value
    if member.guild.id != CONFIG["PS4_GUILD_ID"]:
        return await interaction.response.send_message("⚠️ Run this in the PS4 guild.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    # Map rank → role id
    role_id = None
    if dept == "PSO":
        # allow both PSO_RANK_ROLES and BCSO_RANK_ROLES names
        role_id = CONFIG["PSO_RANK_ROLES"].get(rank) or CONFIG["BCSO_RANK_ROLES"].get(rank)
        # remove all previous PSO/BCSO rank roles
        await remove_roles(member, list(CONFIG["PSO_RANK_ROLES"].values()) + list(CONFIG["BCSO_RANK_ROLES"].values()), "Promotion cleanup")
        if not role_id:
            return await interaction.followup.send("❌ Unknown PSO/BCSO rank.", ephemeral=True)
        await give_roles(member, [role_id], "Promotion")
        # callsign update
        cs = ps0_callsign_for_rank(rank)
        await set_nick_safe(member, f"{cs} | {member.name}")

    elif dept == "CO":
        role_id = CONFIG["CIV_RANK_ROLES"].get(rank)
        await remove_roles(member, list(CONFIG["CIV_RANK_ROLES"].values()), "Promotion cleanup")
        if not role_id:
            return await interaction.followup.send("❌ Unknown CO rank.", ephemeral=True)
        await give_roles(member, [role_id], "Promotion")
        await set_nick_safe(member, f"{civ_callsign()} | {member.name}")

    else:  # SAFR
        role_id = CONFIG["SAFR_RANK_ROLES"].get(rank)
        await remove_roles(member, list(CONFIG["SAFR_RANK_ROLES"].values()), "Promotion cleanup")
        if not role_id:
            return await interaction.followup.send("❌ Unknown SAFR rank.", ephemeral=True)
        await give_roles(member, [role_id], "Promotion")
        await set_nick_safe(member, f"{safr_callsign()} | {member.name}")

    await log_to_hq(f"⬆️ {interaction.user.mention} promoted {member.mention} in **{dept}** to **{rank}**.")
    await interaction.followup.send(f"✅ Promoted {member.mention} in **{dept}** to **{rank}**.", ephemeral=True)

# ─────────────────────────────────────────
# READY EVENT – Global sync + auto panel
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    # persist views
    try:
        bot.add_view(ApplicationPanel())
    except Exception:
        pass

    # global sync
    try:
        synced = await tree.sync()
        print(f"🌍 Pushed {len(synced)} commands globally")
    except Exception as e:
        print(f"Global sync failed: {e}")

    if not watchdog.is_running():
        watchdog.start()
        print("[watchdog] Started watchdog loop.")

    # auto post panel
    await auto_post_panel()

    print(f"🟢 Bot is online as {bot.user}")

# ─────────────────────────────────────────
# ERROR HANDLER (DM you + log)
# ─────────────────────────────────────────
@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    await log_to_hq(f"❗ Command error by {interaction.user.mention}: `{error}`")
    try:
        await interaction.response.send_message("⚠️ An error occurred while running that command.", ephemeral=True)
    except Exception:
        pass

# ─────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────
if __name__ == "__main__":
    bot.run(CONFIG["BOT_TOKEN"])
