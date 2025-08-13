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
from typing import Dict, List, Tuple

import discord
from discord import app_commands, Embed, Object, ui
from discord.ext import commands, tasks
from discord.ui import View, Button, Select

from flask import Flask, request, redirect, render_template_string

# ─────────────────────────────────────────
# OAUTH2 + WEB (Auth join)
# ─────────────────────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://lsrpnetwork-verification.up.railway.app/auth")

# Guilds
HQ_GUILD_ID       = int(os.getenv("HQ_GUILD_ID", "1294319617539575808"))  # you gave this earlier
PS4_GUILD_ID      = int(os.getenv("PS4_GUILD_ID",  "1324117813878718474"))
PS5_GUILD_ID      = int(os.getenv("PS5_GUILD_ID",  "1401903156274790441"))
XBOX_OG_GUILD_ID  = int(os.getenv("XBOX_OG_GUILD_ID", "1375494043831898334"))

PLATFORM_GUILDS = {
    "PS4":    PS4_GUILD_ID,
    "PS5":    PS5_GUILD_ID,
    "XboxOG": XBOX_OG_GUILD_ID
}

# Logging channel for auth successes (HQ)
AUTH_CODE_LOG_CHANNEL = int(os.getenv("OAUTH_LOG_CHANNEL_ID", "1395135616177668186"))

# Code storage (user_id -> dict)
CODE_TTL_SECONDS = 5 * 60  # per your latest: 5 minutes for auth cooldown
pending_codes: Dict[int, dict] = {}

AUTH_ACCEPT_GIF = "https://cdn.discordapp.com/attachments/1317589676336611381/1402368709783191713/Animated_LSRP.gif?ex=689d8c63&is=689c3ae3&hm=5cd9a2cff01d151238b2fd245a8128ada27122b5f4d7d1d2214332c0324dd3fb&"

# WEB
app = Flask(__name__)

@app.route("/")
def health():
    return "✅ LSRP Network System is running."

@app.route("/healthz")
def healthz():
    return "ok", 200

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

@app.route("/auth", methods=["GET", "POST"])
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

    # Exchange code -> token
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

    # Identify user
    me = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15
    )
    if me.status_code != 200:
        return f"User fetch failed: {me.text}", 400
    user_id = int(me.json()["id"])

    data = pending_codes.get(user_id)
    if not data:
        return "No active authorization found. Ask staff to run /auth_grant again.", 400
    if time.time() - float(data["timestamp"]) > CODE_TTL_SECONDS:
        pending_codes.pop(user_id, None)
        return "Your code expired. Ask staff to generate a new one.", 400
    if pin != str(data["code"]):
        return "Invalid code. Please go back and try again.", 400

    target_guild = PLATFORM_GUILDS.get(data["platform"])
    if not target_guild:
        return "Platform guild not found in configuration.", 500

    put_resp = requests.put(
        f"https://discord.com/api/guilds/{target_guild}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
        json={"access_token": access_token},
        timeout=15
    )
    if put_resp.status_code not in (200, 201, 204):
        if not (put_resp.status_code == 400 and "already" in put_resp.text.lower()):
            return f"Guild join failed: {put_resp.status_code} {put_resp.text}", 400

    # log success
    try:
        guild = bot.get_guild(HQ_GUILD_ID)
        if guild:
            log_ch = guild.get_channel(AUTH_CODE_LOG_CHANNEL)
            if log_ch:
                asyncio.run_coroutine_threadsafe(
                    log_ch.send(
                        f"✅ **Auth success** for <@{user_id}> | Dept `{data['dept']}` | "
                        f"Platform `{data['platform']}` | Code `{data['code']}`"
                    ),
                    bot.loop
                )
    except Exception:
        pass

    pending_codes.pop(user_id, None)
    return "✅ Success! You can close this tab and return to Discord."

def run_web():
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)

threading.Thread(target=run_web, daemon=True).start()

# ─────────────────────────────────────────
# LSRP CONFIG (IDs you gave)
# ─────────────────────────────────────────
# HQ panel channel:
PANEL_CHANNEL_ID = 1324115220725108877

# Staff / HR + perms
PSO_STAFF_ID = 1375046497590054985  # (kept for priority commands)
ALLOWED_HR_ROLES = [
    1395743738952941670,  # Head Of Staff
    1375046490564853772,  # PS Manager
    1375046491466371183,  # PS Asst. Manager
]
STAFF_ROLE_ID = 1375046499414704138  # generic staff
STAFF_CAN_POST_PANEL_ROLE = 1384558588478886022  # can post panel, run auth_grant

# Promotions log
PROMOTION_LOG_CHANNEL = 1400933920534560989
DEMOTION_LOG_CHANNEL  = 1400934049505349764

# Priority
PRIORITY_LOG_CHANNEL_ID = 1398746576784068703
active_priority = None

# Session ping role
PING_ROLE_ID = 1375046631237484605

# HQ Applicant category roles (in HQ, where panel is)
APPLICANT_PLATFORM_ROLES = {
    "PS4":   1401961522556698739,
    "PS5":   1401961758502944900,
    "XboxOG":1401961991756578817,
}
ACCEPTED_PLATFORM_ROLES = {
    "PS4":   1367753287872286720,
    "PS5":   1367753535839797278,
    "XboxOG":1367753756367912960,
}
APPLICANT_DEPT_ROLES = {
    "PSO":  1370719624051691580,
    "CO":   1323758149009936424,
    "SAFR": 1370719781488955402,
}
PENDING_ROLE_ID = 1323758692918624366
DENIED_ROLE_ID  = 1323755533492027474

# Main Guild (PS4: 1324117813878718474) department roles:
PS4_PSO_MAIN = 1375046521904431124
PS4_SASP     = 1401347813958226061
PS4_BCSO     = 1401347339796348938
PS4_CO       = 1375046547678429195
PS4_SAFR     = 1401347818873946133

# Category/collection roles:
PS4_PSO_CATEGORY     = 1404575562290434190   # Public Safety Rank(s)
PS4_CO_CATEGORY      = 1375046548747980830   # Civilian Operations Rank(s)
PS4_SAFR_CATEGORY    = 1375046571653201961   # Fire/EMS Rank(s)
PS4_BCSO_CATEGORY    = 1375046520469979256   # Sheriffs Office Rank(s)

# Rank roles in PS4 main (SASP set)
PSO_RANK_ROLES = {
    "Cadet":                 1375046543329202186,
    "Trooper":               1375046541869584464,
    "Trooper First Class":   1375046540925599815,
    "Sergeant":              1392169682596790395,
    "Master Sergeant":       1375046535410356295,
    "Lieutenant":            1375046533833035778,
    "Captain":               1375046532847501373,
    "Major":                 1375046529752105041,
    "Commander":             1375046528963444819,
    "ADOPS":                 1375046524567818270,
    "Supervisor":            1375046546554621952,  # only auto-added when Sergeant
}

# Rank roles in PS4 main (BCSO set)
BCSO_RANK_ROLES = {
    "Probationary Deputy": 1404903885432164362,
    "Deputy":              1401368189543252029,
    "Senior Deputy":       1401368085629370488,
    "Deputy Sergeant":     1401367986614440156,
    "Deputy MSGT":         1401367878770491473,
    "Deputy Lieutenant":   1401347822669922304,
    "Deputy Captain":      1401347820635684994,
    "Undersheriff":        1405177276651278479,
    "Sheriff":             1405178452931379220,
}

# CIV roles (PS4)
CIV_RANK_ROLES = {
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
    "Civ Director":     1375046550555988050,
}

# SAFR roles (PS4)
SAFR_RANK_ROLES = {
    "Probationary Firefighter": 1375046583153856634,
    "Firefighter 1":            1375046585150603357,
    "Firefighter Sergeant":     1375046582034235503,
    "Firefighter Lieutenant":   1375046581111361597,
    "Firefighter Captain":      1375046579047632926,
    "Battalion Chief":          1375046577214849075,
    "Deputy Fire Chief":        1375046575499513966,
    "Fire Chief":               1375046574593413151,
}

# Ping-immunity
IMMUNE_USER_ID = 1176071547476262986
HQ_MANAGEMENT_ROLE = 1338855588381200426
PS4_MANAGEMENT_ROLE = 1375046488194809917
HQ_GUILD_FOR_IMMUNITY = HQ_GUILD_ID
PS4_GUILD_FOR_IMMUNITY = PS4_GUILD_ID
PING_WARNING_CHANNEL_URL = "https://discord.com/channels/1294319617539575808/1367056555035459606"

# Permanent panel banner
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1317589676336611381/1405147584456032276/Sunset_Photography_Tumblr_Banner.png?ex=689dc52a&is=689c73aa&hm=f7fd9a078016e1fc61d54391e5d57bf61f0c1f6b09e82b8163b16eae312c0f1a&"

# ─────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)
tree = bot.tree

# ─────────────────────────────────────────
# WATCHDOG
# ─────────────────────────────────────────
FAILED_LIMIT = 3

@tasks.loop(minutes=1)
async def watchdog():
    if not bot.is_ready():
        watchdog.failures = getattr(watchdog, "failures", 0) + 1
    else:
        try:
            await bot.fetch_guild(HQ_GUILD_ID)
            watchdog.failures = 0
        except Exception:
            watchdog.failures = getattr(watchdog, "failures", 0) + 1
    if watchdog.failures >= FAILED_LIMIT:
        print("[watchdog] Discord unreachable. Restarting process...")
        os._exit(1)

@watchdog.before_loop
async def before_watchdog():
    await bot.wait_until_ready()
    print("[watchdog] Started watchdog loop.")

# ─────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────
def dept_color(dept: str) -> discord.Color:
    return discord.Color.blue() if dept == "PSO" else (discord.Color.green() if dept == "CO" else discord.Color.red())

def callsign_for_pso(rank: str, subdept: str, username: str) -> str:
    # PSO system (kept your old ranges; adjust as needed)
    ranges = {
        "Cadet": (1000, 1999, "C"),
        "Officer I": (800, 899, "B"),
        "Officer II": (700, 799, "B"),
        "Sergeant": (600, 699, "B"),
        "Master Sergeant": (500, 599, "B"),
        "Lieutenant": (400, 499, "B"),
        "Captain": (300, 399, "B"),
        "Major": (200, 299, "L"),
        "Commander": (100, 199, "L"),
        "ADOPS": (102, 102, "L"),
        # BCSO ladder uses its own wording but we’ll still use C/B/L prefixes by level
        "Probationary Deputy": (1000, 1999, "C"),
        "Deputy": (800, 899, "B"),
        "Senior Deputy": (700, 799, "B"),
        "Deputy Sergeant": (600, 699, "B"),
        "Deputy MSGT": (500, 599, "B"),
        "Deputy Lieutenant": (400, 499, "B"),
        "Deputy Captain": (300, 399, "B"),
        "Undersheriff": (200, 299, "L"),
        "Sheriff": (100, 199, "L"),
    }
    if rank == "ADOPS":
        return f"L-102 | {username} | ADOPS"
    if rank in ranges:
        s, e, p = ranges[rank]
        return f"{p}-{random.randint(s,e)} | {username}"
    # default
    return f"C-{random.randint(1000,1999)} | {username}"

def callsign_for_co(rank: str, username: str) -> str:
    # Simple CIV-XXXX (you can refine ranges per rank later)
    return f"CIV-{random.randint(1000,9999)} | {username}"

def callsign_for_safr(rank: str, username: str) -> str:
    # Simple FF-XXX
    return f"FF-{random.randint(100,999)} | {username}"

# ─────────────────────────────────────────
# APPLICATION QUESTIONS (FULL SETS)
# ─────────────────────────────────────────
PSO_QUESTIONS = [
    ("Which PSO sub-department are you applying for?", "Select one: **SASP** or **BCSO**."),
    ("What is your PSN or Gamertag?", "Enter your exact platform username."),
    ("How old are you?", "Numeric age."),
    ("What region/timezone are you in?", "e.g., EU/Romania (EET)."),
    ("Do you have prior RP experience? If yes, where and how long?", "A few sentences."),
    ("Why should we accept you into PSO? (Minimum 4–6 sentences)", "Be specific."),
    ("List your top 3 strengths as an officer.", "Short bullets are fine."),
    ("List 2 weaknesses and how you’re improving them.", "Be honest."),
    ("Describe a professional traffic stop from start to finish.", "Detail your steps."),
    ("How do you de-escalate a situation that’s getting heated?", "Your approach."),
]

CO_QUESTIONS = [
    ("What is your PSN or Gamertag?", "Enter your exact platform username."),
    ("How old are you?", "Numeric age."),
    ("What region/timezone are you in?", "e.g., EU/Romania (EET)."),
    ("Do you have prior RP experience? If yes, where and how long?", "A few sentences."),
    ("Why do you want to join Civilian Operations? (4–6 sentences)", "Be specific."),
    ("Pitch one civilian scenario you’d run in LSRP.", "Outline the idea."),
    ("How will you avoid Fail RP and keep scenes fun for others?", "Explain."),
    ("What is Meta-gaming? Give an example.", "Define + example."),
]

SAFR_QUESTIONS = [
    ("What is your PSN or Gamertag?", "Enter your exact platform username."),
    ("How old are you?", "Numeric age."),
    ("What region/timezone are you in?", "e.g., EU/Romania (EET)."),
    ("Do you have prior RP experience? If yes, where and how long?", "A few sentences."),
    ("Why do you want to join SAFR? (4–6 sentences)", "Be specific."),
    ("Describe your steps on a structure fire page-out.", "From dispatch to clear."),
    ("How would you triage a multi-casualty incident?", "Your process."),
    ("When do you call for additional resources / mutual aid?", "Explain."),
]

# ─────────────────────────────────────────
# APPLICATION PANEL & DM FLOW
# ─────────────────────────────────────────
app_sessions: Dict[int, Dict] = {}  # ephemeral per-user

class DepartmentSelect(Select):
    def __init__(self):
        super().__init__(
            placeholder="Select a department to begin…",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="Public Safety Office (PSO)", value="PSO", description="SASP or BCSO"),
                discord.SelectOption(label="Civilian Operations (CO)", value="CO", description="Civilian Roleplay"),
                discord.SelectOption(label="San Andreas Fire & Rescue (SAFR)", value="SAFR", description="Fire & EMS"),
            ],
        )

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        app_sessions[user.id] = {
            "dept": self.values[0],
            "guild_id": interaction.guild.id,
            "start_ts": time.time(),
            "answers": [],
            "step": 0,
            "platform": None,
            "subdept": None,
            "timer_task": None,
            "review_message_id": None,
        }
        color = dept_color(self.values[0])
        try:
            dm = await user.create_dm()
            banner = Embed(color=color).set_image(url=PANEL_IMAGE_URL)
            await dm.send(embed=banner)
            await dm.send(embed=Embed(
                title="📋 Los Santos Roleplay Network™® | Application",
                description=(
                    f"Department selected: **{self.values[0]}**\n"
                    "You have **35 minutes** to complete this application.\n\n"
                    "I’ll guide you through the steps here in DMs.\n"
                    "If your DMs are closed, please enable them and select again."
                ),
                color=color
            ))
            # PSO needs subdept first; SAFR skips subdept and goes platform; CO goes straight to questions after platform
            if self.values[0] == "PSO":
                await dm.send(
                    embed=Embed(title="Sub-Department", description="Choose your **PSO** sub-department:", color=color),
                    view=SubDeptView(user.id)
                )
            else:
                await dm.send(
                    embed=Embed(title="Platform Selection", description="Choose your platform:", color=color),
                    view=PlatformView(user.id)
                )
            # start 35 min timer
            loop = asyncio.get_running_loop()
            app_sessions[user.id]["timer_task"] = loop.create_task(application_timer(user.id, 35*60))
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
            placeholder="Select PSO sub-department…",
            min_values=1, max_values=1,
            options=[
                discord.SelectOption(label="San Andreas State Police (SASP)", value="SASP"),
                discord.SelectOption(label="Blaine County Sheriff's Office (BCSO)", value="BCSO"),
            ],
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("This menu isn’t for you.", ephemeral=True)
        sess = app_sessions.get(self.user_id, {})
        sess["subdept"] = self.values[0]
        dept = sess.get("dept", "PSO")
        await interaction.response.edit_message(
            embed=Embed(title="Platform Selection", description="Choose your platform:", color=dept_color(dept)),
            view=PlatformView(self.user_id)
        )

class SubDeptView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(SubDeptSelect(user_id))

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
        sess = app_sessions.get(self.user_id)
        if not sess:
            return await interaction.response.send_message("Session not found. Please use the panel again.", ephemeral=True)
        sess["platform"] = self.values[0]

        # Assign HQ Applicant roles (dept + platform + pending)
        guild_id = sess.get("guild_id")
        if guild_id:
            guild = bot.get_guild(guild_id)
            if guild:
                try:
                    member = guild.get_member(self.user_id) or await guild.fetch_member(self.user_id)
                    roles = []
                    plat_role = guild.get_role(APPLICANT_PLATFORM_ROLES.get(sess["platform"]))
                    dept_role = guild.get_role(APPLICANT_DEPT_ROLES.get(sess["dept"]))
                    pending = guild.get_role(PENDING_ROLE_ID)
                    for r in (plat_role, dept_role, pending):
                        if r: roles.append(r)
                    if roles:
                        await member.add_roles(*roles, reason="Application started (platform chosen)")
                except Exception as e:
                    print(f"[role-assign] Error: {e}")

        # Start questions
        dept = sess["dept"]
        if dept == "PSO":
            qset = PSO_QUESTIONS
        elif dept == "CO":
            qset = CO_QUESTIONS
        else:
            qset = SAFR_QUESTIONS

        sess["qset"] = qset
        sess["answers"] = []
        sess["step"] = 0

        first_q, helptext = qset[0]
        embed = Embed(
            title=f"{dept} Application – Question 1/{len(qset)}",
            description=f"**{first_q}**\n*{helptext}*",
            color=dept_color(dept)
        )
        await interaction.response.edit_message(embed=embed, view=None)

class PlatformView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(PlatformSelect(user_id))

# 35-minute timer
async def application_timer(user_id: int, seconds: int):
    await asyncio.sleep(seconds)
    sess = app_sessions.get(user_id)
    if not sess:
        return
    # if not finished -> timeout
    if "finished" not in sess:
        try:
            user = await bot.fetch_user(user_id)
            await user.send(embed=Embed(
                title="⏰ Application Timed Out",
                description="You ran out of time (35 minutes). Please start again from the application panel.",
                color=discord.Color.red()
            ))
        except Exception:
            pass
        # optionally strip pending role in HQ
        guild = bot.get_guild(HQ_GUILD_ID)
        if guild:
            try:
                member = guild.get_member(user_id) or await guild.fetch_member(user_id)
                pending = guild.get_role(PENDING_ROLE_ID)
                if pending and pending in member.roles:
                    await member.remove_roles(pending, reason="Application timed out")
            except Exception:
                pass
        app_sessions.pop(user_id, None)

# Collect DM answers
@bot.event
async def on_message(message: discord.Message):
    # ignore bot
    if message.author.bot:
        return
    # ping immunity (HQ + PS4) for a specific user ID
    if message.guild and message.mentions and any(m.id == IMMUNE_USER_ID for m in message.mentions):
        allowed = False
        if message.guild.id == HQ_GUILD_FOR_IMMUNITY:
            allowed = any(getattr(message.author, "roles", []) and r.id == HQ_MANAGEMENT_ROLE for r in message.author.roles)
        elif message.guild.id == PS4_GUILD_FOR_IMMUNITY:
            allowed = any(getattr(message.author, "roles", []) and r.id == PS4_MANAGEMENT_ROLE for r in message.author.roles)
        if not allowed:
            try:
                await message.delete()
            except Exception:
                pass
            try:
                warn = (
                    f"Naughty Naughty {message.author.mention}, please don't ping <@{IMMUNE_USER_ID}>, he is a busy man but his DMs are always open.\n"
                    f"Pinging him again will result in a written warning. If you request help, please open a support ticket: {PING_WARNING_CHANNEL_URL}"
                )
                await message.channel.send(warn, delete_after=10)
            except Exception:
                pass

    # handle DM Q&A
    if message.guild is None:
        user_id = message.author.id
        sess = app_sessions.get(user_id)
        if not sess or "qset" not in sess:
            return
        # If they haven't chosen PSO subdept at Q0, ensure the first PSO qs already done
        qset: List[Tuple[str,str]] = sess["qset"]
        step = sess.get("step", 0)
        dept = sess.get("dept", "CO")

        # Record the answer to previous prompt
        content = message.content.strip()
        sess["answers"].append(content)

        step += 1
        if step >= len(qset):
            # finished
            sess["finished"] = True
            # cancel timer
            t = sess.get("timer_task")
            if t and not t.done():
                t.cancel()
            # send summary and push to review
            await finalize_application(message.author, sess)
            app_sessions.pop(user_id, None)
            return
        # ask next
        next_q, helptext = qset[step]
        sess["step"] = step
        embed = Embed(
            title=f"{dept} Application – Question {step+1}/{len(qset)}",
            description=f"**{next_q}**\n*{helptext}*",
            color=dept_color(dept)
        )
        await message.channel.send(embed=embed)

    await bot.process_commands(message)

# Build review embed
async def finalize_application(user: discord.User, sess: dict):
    dept = sess["dept"]
    subdept = sess.get("subdept") if dept == "PSO" else "N/A"
    platform = sess.get("platform")
    qset: List[Tuple[str,str]] = sess["qset"]
    answers: List[str] = sess["answers"]

    # Ensure same length (in case user skipped — should not happen here)
    qa_lines = []
    for idx, (q, _hint) in enumerate(qset, start=1):
        ans = answers[idx-1] if idx-1 < len(answers) else "*No answer*"
        qa_lines.append(f"**Q{idx}. {q}**\n{ans}")

    review_embed = Embed(
        title=f"📝 Application Review — {dept}",
        description=(
            f"**Applicant:** {user.mention} (`{user.id}`)\n"
            f"**Department:** {dept}\n"
            f"**Sub-Department:** {subdept}\n"
            f"**Platform:** {platform}\n\n" +
            "\n\n".join(qa_lines)
        ),
        color=dept_color(dept)
    )

    guild = bot.get_guild(HQ_GUILD_ID)
    review_ch = guild.get_channel(1366431401054048357) if guild else None
    if not review_ch:
        try:
            await user.send("⚠️ Application submitted, but I couldn't locate the review channel.")
        except Exception:
            pass
        return

    view = ReviewButtons(user.id, dept, subdept, platform)
    msg = await review_ch.send(embed=review_embed, view=view)
    # store review message id if needed later
    sess["review_message_id"] = msg.id

class ReviewButtons(View):
    def __init__(self, user_id: int, dept: str, subdept: str, platform: str):
        super().__init__(timeout=None)
        self.user_id = user_id
        self.dept = dept
        self.subdept = subdept
        self.platform = platform

    @discord.ui.button(label="✅ Approve", style=discord.ButtonStyle.success)
    async def approve(self, interaction: discord.Interaction, button: Button):
        # restrict to staff
        if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You can’t approve this.", ephemeral=True)

        # generate 6-digit code, store
        code = random.randint(100000, 999999)
        pending_codes[self.user_id] = {
            "code": code,
            "timestamp": time.time(),
            "dept": self.dept,
            "platform": self.platform,
            "granted_by": interaction.user.id,
        }

        # DM applicant (code + link + button + GIF)
        try:
            u = await bot.fetch_user(self.user_id)
            dm = await u.create_dm()
            e = Embed(
                title="🎉 Application Accepted",
                description=(
                    f"Welcome to **{self.dept}**!\n\n"
                    f"**This is your 1 time 6-digit code:** `{code}`\n"
                    f"**Once this code is used in the authorization link it will no longer be valid.**\n\n"
                    f"[Main Server Verification Link]({REDIRECT_URI})"
                ),
                color=dept_color(self.dept)
            )
            e.set_image(url=AUTH_ACCEPT_GIF)
            view = View()
            view.add_item(discord.ui.Button(label="Open Verification", url=REDIRECT_URI, style=discord.ButtonStyle.link))
            await dm.send(embed=e, view=view)
        except Exception as ex:
            print(f"[approve DM] {ex}")

        # Update HQ roles (remove pending, keep applicant roles or you can swap to accepted)
        try:
            guild = bot.get_guild(HQ_GUILD_ID)
            member = guild.get_member(self.user_id) or await guild.fetch_member(self.user_id)
            pending = guild.get_role(PENDING_ROLE_ID)
            if pending and pending in member.roles:
                await member.remove_roles(pending, reason="Accepted (pending auth)")
        except Exception:
            pass

        await interaction.response.send_message(f"✅ Code sent to <@{self.user_id}>. Code expires in 5 minutes.", ephemeral=True)

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: Button):
        if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
            return await interaction.response.send_message("🚫 You can’t deny this.", ephemeral=True)

        # DM denial
        try:
            u = await bot.fetch_user(self.user_id)
            e = Embed(
                title="❌ Application Denied",
                description=(
                    "Thank you for applying. After review, we’re unable to accept your application at this time.\n"
                    "You may re-apply in **12 hours**.\n"
                    "If you have questions, open a ticket in HQ."
                ),
                color=discord.Color.red()
            )
            await u.send(embed=e)
        except Exception:
            pass

        # HQ roles: swap pending->denied
        try:
            guild = bot.get_guild(HQ_GUILD_ID)
            member = guild.get_member(self.user_id) or await guild.fetch_member(self.user_id)
            pending = guild.get_role(PENDING_ROLE_ID)
            denied = guild.get_role(DENIED_ROLE_ID)
            to_add = []
            if pending and pending in member.roles:
                await member.remove_roles(pending, reason="Denied")
            if denied:
                to_add.append(denied)
            if to_add:
                await member.add_roles(*to_add, reason="Application denied (12h cooldown)")
        except Exception:
            pass

        await interaction.response.send_message("❌ Applicant denied.", ephemeral=True)

# ─────────────────────────────────────────
# PANEL POST COMMAND (message command)
# ─────────────────────────────────────────
@bot.command(name="post_application_panel")
@commands.has_any_role(STAFF_CAN_POST_PANEL_ROLE)
async def post_application_panel(ctx: commands.Context):
    # delete the invoking message
    try:
        await ctx.message.delete()
    except Exception:
        pass

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
    await ctx.send(embed=embed, view=ApplicationPanel())
    await ctx.send("✅ Panel posted.", delete_after=5)

# ─────────────────────────────────────────
# GLOBAL / GUILD SYNC + AUTO PANEL
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    # Persist views
    try:
        bot.add_view(ApplicationPanel())
    except Exception:
        pass

    # Global sync (so commands appear everywhere)
    try:
        global_commands = await tree.sync()
        print(f"🌍 Pushed {len(global_commands)} commands globally")
    except Exception as e:
        print(f"[global sync] {e}")

    # Optional: also ensure HQ has them immediately
    try:
        guild_commands = await tree.sync(guild=Object(id=HQ_GUILD_ID))
        print(f"✅ Synced {len(guild_commands)} commands to HQ guild {HQ_GUILD_ID}")
        print(f"🛠 Commands: {[c.name for c in guild_commands]}")
    except Exception as e:
        print(f"[guild sync] {e}")

    # Start watchdog once
    if not watchdog.is_running():
        watchdog.start()
        print("[watchdog] Started watchdog loop.")

    # Auto-post panel if not present in the last 20 messages (HQ channel)
    try:
        channel = bot.get_channel(PANEL_CHANNEL_ID)
        if channel:
            async for msg in channel.history(limit=20):
                if msg.author == bot.user and msg.components:
                    break
            else:
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
                print(f"✅ Application panel posted in #application-system")
    except Exception as e:
        print(f"⚠️ Could not post application panel: {e}")

    print(f"🟢 Bot is online as {bot.user}")

# ─────────────────────────────────────────
# AUTH GRANT (manual, if you still want it)
# ─────────────────────────────────────────
@tree.command(name="auth_grant", description="Generate a one-time 6-digit auth code (expires in 5 minutes).")
async def auth_grant(
    interaction: discord.Interaction,
    user: discord.Member,
    department: app_commands.Choice[str],
    platform: app_commands.Choice[str]
):
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
        return await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)
    await interaction.response.defer(ephemeral=True)
    code = random.randint(100000, 999999)
    pending_codes[user.id] = {
        "code": code,
        "timestamp": time.time(),
        "dept": department.value,
        "platform": platform.value,
        "granted_by": interaction.user.id,
    }
    log_ch = interaction.guild.get_channel(AUTH_CODE_LOG_CHANNEL)
    if log_ch:
        await log_ch.send(
            f"🔐 **Auth Code Generated**\n"
            f"User: {user.mention} (`{user.id}`)\n"
            f"Department: `{department.value}`  |  Platform: `{platform.value}`\n"
            f"Code: **{code}** (expires in 5 minutes)\n"
            f"Granted by: {interaction.user.mention}"
        )
    try:
        dm_embed = Embed(
            title="🔐 Los Santos Roleplay Network™® — Authorization",
            description=(
                f"**Your one-time 6-digit code:** `{code}`\n"
                f"[Main Server Verification Link]({REDIRECT_URI})"
            ),
            color=dept_color(department.value),
        )
        view = View()
        view.add_item(discord.ui.Button(label="Open Verification", url=REDIRECT_URI, style=discord.ButtonStyle.link))
        await user.send(embed=dm_embed, view=view)
    except discord.Forbidden:
        pass
    await interaction.followup.send(f"✅ Code sent to {user.mention}'s DMs.", ephemeral=True)

@auth_grant.describe
def _desc():
    return {
        "user": "The applicant to authorize",
        "department": "Department",
        "platform": "Platform"
    }

@auth_grant.choices
async def _choices(interaction: discord.Interaction):
    pass

# Manually attach choices (discord.py 2.3 doesn't support multiple decorators together cleanly)
auth_grant._params["department"].choices = [
    app_commands.Choice(name="PSO", value="PSO"),
    app_commands.Choice(name="CO", value="CO"),
    app_commands.Choice(name="SAFR", value="SAFR"),
]
auth_grant._params["platform"].choices = [
    app_commands.Choice(name="PS4", value="PS4"),
    app_commands.Choice(name="PS5", value="PS5"),
    app_commands.Choice(name="Xbox Old Gen", value="XboxOG"),
]

# ─────────────────────────────────────────
# STAFF / PRIORITY / SESSION (kept minimal)
# ─────────────────────────────────────────
@tree.command(name="ping", description="Check slash command.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🟢 Pong!")

@tree.command(name="priority_start", description="Start a priority scene")
@app_commands.describe(user="User to start priority on", type="Type of priority")
@app_commands.choices(type=[
    app_commands.Choice(name="Shooting", value="Shooting"),
    app_commands.Choice(name="Robbery", value="Robbery"),
    app_commands.Choice(name="Pursuit", value="Pursuit"),
    app_commands.Choice(name="Other",    value="Other"),
])
async def priority_start(interaction: discord.Interaction, user: discord.Member, type: app_commands.Choice[str]):
    global active_priority
    if active_priority:
        return await interaction.response.send_message("⚠️ Priority already active. End it first.", ephemeral=True)
    active_priority = {"user": user, "type": type.value, "started_by": interaction.user, "time": time.time()}
    ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
    if ch:
        await ch.send(embed=Embed(title="🚨 Priority Started", description=f"**User:** {user.mention}\n**Type:** {type.value}", color=discord.Color.red()))
    await interaction.response.send_message(f"✅ Priority started for {user.mention}.", ephemeral=True)

@tree.command(name="priority_end", description="End the current priority")
async def priority_end(interaction: discord.Interaction):
    global active_priority
    if not active_priority:
        return await interaction.response.send_message("❌ No active priority.", ephemeral=True)
    ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
    if ch:
        await ch.send(embed=Embed(title="✅ Priority Ended", description=f"**User:** {active_priority['user'].mention}", color=discord.Color.green()))
    active_priority = None
    await interaction.response.send_message("✅ Priority ended.", ephemeral=True)

@tree.command(name="start_session", description="Announce session start")
async def start_session(interaction: discord.Interaction, psn: str, aop: str):
    role = interaction.guild.get_role(PING_ROLE_ID)
    e = Embed(
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
    await interaction.response.send_message(content=role.mention if role else None, embed=e)

@tree.command(name="end_session", description="Announce session end")
async def end_session(interaction: discord.Interaction):
    role = interaction.guild.get_role(PING_ROLE_ID)
    e = Embed(
        title="🔴 SESSION CLOSED",
        description=(
            "**This session has now concluded.**\n\n"
            f"🕒 **End Time:** <t:{int(time.time())}:F>\n\n"
            "🙏 **Thank you to everyone who attended and maintained professionalism throughout the session.**"
        ),
        color=discord.Color.red()
    )
    await interaction.response.send_message(content=role.mention if role else None, embed=e)

# ─────────────────────────────────────────
# RUN
# ─────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    bot.run(BOT_TOKEN)
