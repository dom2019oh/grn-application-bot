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
from typing import Dict

import discord
from discord import app_commands, Embed
from discord.ext import commands, tasks
from discord.ui import View, Button, Select

from flask import Flask, request, redirect, render_template_string

# ─────────────────────────────────────────
# OAUTH2 AUTHORIZATION WEB SERVER
# ─────────────────────────────────────────
import os, time, random, threading, requests, urllib.parse, asyncio
from typing import Dict
from flask import Flask, request, redirect, render_template_string

# ── ENV CONFIG ───────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN")
CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://lsrpnetwork-verification.up.railway.app/auth")

# Guild IDs
HQ_GUILD_ID       = int(os.getenv("HQ_GUILD_ID", "1324117813878718474"))
PS4_GUILD_ID      = int(os.getenv("PS4_GUILD_ID",  "0"))
PS5_GUILD_ID      = int(os.getenv("PS5_GUILD_ID",  "0"))
XBOX_OG_GUILD_ID  = int(os.getenv("XBOX_OG_GUILD_ID", "0"))

PLATFORM_GUILDS = {
    "PS4":    PS4_GUILD_ID,
    "PS5":    PS5_GUILD_ID,
    "XboxOG": XBOX_OG_GUILD_ID
}

# Log channel for successful auth
AUTH_CODE_LOG_CHANNEL = int(os.getenv("OAUTH_LOG_CHANNEL_ID", "0"))

# Code storage
CODE_TTL_SECONDS = 10 * 60  # 10 minutes
pending_codes: Dict[int, dict] = {}

# ── WEB APP ──────────────────────────────
app = Flask(__name__)

@app.route("/")
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

@app.route("/auth", methods=["GET", "POST"])
def oauth_handler():
    # 1) No ?code → redirect to Discord authorize page
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

    # 2) Show HTML form on GET
    if request.method == "GET":
        return render_template_string(_HTML_FORM)

    # 3) Get entered pin
    pin = (request.form.get("pin") or "").strip()

    # 4) Exchange code → access_token
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

    # 5) Identify user
    me = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15
    )
    if me.status_code != 200:
        return f"User fetch failed: {me.text}", 400
    user_id = int(me.json()["id"])

    # 6) Validate pending code
    data = pending_codes.get(user_id)
    if not data:
        return "No active authorization found. Ask staff to run /auth_grant again.", 400
    if time.time() - float(data["timestamp"]) > CODE_TTL_SECONDS:
        pending_codes.pop(user_id, None)
        return "Your code expired. Ask staff to generate a new one.", 400
    if pin != str(data["code"]):
        return "Invalid code. Please go back and try again.", 400

    # 7) Get guild from platform
    target_guild = PLATFORM_GUILDS.get(data["platform"])
    if not target_guild:
        return "Platform guild not found in configuration.", 500

    # 8) Add user to guild
    put_resp = requests.put(
        f"https://discord.com/api/guilds/{target_guild}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
        json={"access_token": access_token},
        timeout=15
    )
    if put_resp.status_code not in (200, 201, 204):
        if not (put_resp.status_code == 400 and "already" in put_resp.text.lower()):
            return f"Guild join failed: {put_resp.status_code} {put_resp.text}", 400

    # 9) Log success in HQ server
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

    # 10) Cleanup
    pending_codes.pop(user_id, None)
    return "✅ Success! You can close this tab and return to Discord."

# ── Start web server in thread ────────────
def run_web():
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()


# ─────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────
GUILD_ID = 1324117813878718474
BOT_TOKEN = os.environ.get("BOT_TOKEN")

# Staff / HR
PSO_STAFF_ID = 1375046497590054985
PROMOTION_LOG_CHANNEL = 1400933920534560989
DEMOTION_LOG_CHANNEL = 1400934049505349764
ALLOWED_HR_ROLES = [
    1395743738952941670,  # Head Of Staff
    1375046490564853772,  # PS Manager
    1375046491466371183,  # PS Asst. Manager
]
STAFF_ROLE_ID = 1375046499414704138
STAFF_ROLES = [
    1380937336094982154,
    1375046500098506844,
    1375046499414704138,
]

# Priority
PRIORITY_LOG_CHANNEL_ID = 1398746576784068703
active_priority = None

# Session
PING_ROLE_ID = 1375046631237484605  # Session notify role

# PSO Ranks & Roles (your latest names)
CALLSIGN_RANGES = {
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
}
PSO_ROLES = {
    "Cadet": 1375046543329202186,
    "Trooper": 1375046541869584464,
    "Trooper First Class": 1375046540925599815,
    "Sergeant": 1392169682596790395,
    "Master Sergeant": 1375046535410356295,
    "Lieutenant": 1375046533833035778,
    "Captain": 1375046532847501373,
    "Major": 1375046529752105041,
    "Commander": 1375046528963444819,
    "ADOPS": 1375046524567818270,
    "PSO_Main": 1375046521904431124,
    "Supervisor": 1375046546554621952,
}

# ── Applicant role IDs by platform
APPLICANT_PLATFORM_ROLES = {
    "PS4":   1401961522556698739,  # PS4 Applicant
    "PS5":   1401961758502944900,  # PS5 Applicant
    "XboxOG":1401961991756578817,  # Xbox OG Applicant
}

# (Accepted roles – reserved for future use)
ACCEPTED_PLATFORM_ROLES = {
    "PS4":   1367753287872286720,
    "PS5":   1367753535839797278,
    "XboxOG":1367753756367912960,
}

# ── Applicant role IDs by department
APPLICANT_DEPT_ROLES = {
    "PSO":  1370719624051691580,  # Public Safety Applicant
    "CO":   1323758149009936424,  # Civilian Operations Applicant
    "SAFR": 1370719781488955402,  # Fire & Rescue Applicant
}

# Application Panel
PANEL_CHANNEL_ID = 1324115220725108877
STAFF_CAN_POST_PANEL_ROLE = 1384558588478886022  # also used for /auth_grant permission

# Auth grant
AUTH_CODE_LOG_CHANNEL = 1395135616177668186
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://your-railway-domain/auth")  # set in Railway
CODE_TTL_SECONDS = 10 * 60  # 10 minutes

# ─────────────────────────────────────────
# BOT SETUP
# ─────────────────────────────────────────
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# ─────────────────────────────────────────
# WATCHDOG: Restart if Discord unreachable
# ─────────────────────────────────────────
FAILED_LIMIT = 3

@tasks.loop(minutes=1)
async def watchdog():
    if not bot.is_ready():
        watchdog.failures = getattr(watchdog, "failures", 0) + 1
    else:
        try:
            await bot.fetch_guild(GUILD_ID)
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
# APPLICATION PANEL + DM FLOW
# ─────────────────────────────────────────
app_sessions: Dict[int, Dict] = {}  # per-user ephemeral state

def dept_color(dept: str) -> discord.Color:
    if dept == "PSO":
        return discord.Color.blue()
    if dept == "CO":
        return discord.Color.green()
    return discord.Color.red()  # SAFR

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
        app_sessions.setdefault(self.user_id, {})["subdept"] = self.values[0]
        dept = app_sessions[self.user_id]["dept"]
        emb = Embed(title="Platform Selection", description="Choose your platform:", color=dept_color(dept))
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

        # Save platform
        app_sessions.setdefault(self.user_id, {})["platform"] = self.values[0]
        sess = app_sessions[self.user_id]
        dept = sess.get("dept", "CO")
        subdept = sess.get("subdept", "N/A")
        platform = sess["platform"]
        guild_id = sess.get("guild_id")  # set when dept selected in panel

        # Assign applicant roles in the source guild
        if guild_id:
            guild = bot.get_guild(guild_id)
            if guild:
                try:
                    member = guild.get_member(self.user_id) or await guild.fetch_member(self.user_id)
                    roles_to_add = []

                    plat_role_id = APPLICANT_PLATFORM_ROLES.get(platform)
                    if plat_role_id:
                        r = guild.get_role(plat_role_id)
                        if r: roles_to_add.append(r)

                    dept_role_id = APPLICANT_DEPT_ROLES.get(dept)
                    if dept_role_id:
                        r = guild.get_role(dept_role_id)
                        if r: roles_to_add.append(r)

                    if roles_to_add:
                        await member.add_roles(*roles_to_add, reason="Application started (platform selected in DM)")
                except discord.Forbidden:
                    print(f"⚠️ Missing permissions to assign roles for {interaction.user}")
                except Exception as e:
                    print(f"⚠️ Error assigning applicant roles: {e}")

        # Confirm + move to question flow (hook point)
        summary = (
            f"**Department:** {dept}\n"
            f"**Sub-Department:** {subdept}\n"
            f"**Platform:** {platform}\n\n"
            "✅ Selections saved. I’ll now begin your application questions."
        )
        emb = Embed(title="Application Details Confirmed", description=summary, color=dept_color(dept))
        await interaction.response.edit_message(embed=emb, view=None)

        # TODO: start your department-specific DM questions here
        # await start_application_questions(interaction.user, dept, subdept, platform)

class PlatformView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(PlatformSelect(user_id))

class SubDeptView(View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.add_item(SubDeptSelect(user_id))

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
        user = interaction.user
        app_sessions[user.id] = {"dept": self.values[0], "guild_id": interaction.guild.id}
        dept = app_sessions[user.id]["dept"]
        color = dept_color(dept)
        try:
            dm = await user.create_dm()
            intro = Embed(
                title="📋 Los Santos Roleplay Network™® | Application",
                description=(
                    f"Department selected: **{dept}**\n\n"
                    "I’ll guide you through the next steps here in DMs.\n"
                    "If your DMs are closed, please enable them and select again."
                ),
                color=color,
            )
            await dm.send(embed=intro)
            if dept == "PSO":
                await dm.send(
                    embed=Embed(title="Sub-Department Selection", description="Choose your **PSO** sub-department:", color=color),
                    view=SubDeptView(user.id)
                )
            else:
                await dm.send(
                    embed=Embed(title="Platform Selection", description="Choose your platform:", color=color),
                    view=PlatformView(user.id)
                )
            await interaction.response.send_message("📬 I’ve sent you a DM to continue your application.", ephemeral=True)
        except discord.Forbidden:
            await interaction.response.send_message("⚠️ I couldn’t DM you. Please enable DMs and select again.", ephemeral=True)

class ApplicationPanel(View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent view
        self.add_item(DepartmentSelect())

# ─────────────────────────────────────────
# AUTH GRANT (6-digit codes with expiry)
# ─────────────────────────────────────────
pending_codes: Dict[int, Dict] = {}  # user_id -> {code,timestamp,dept,platform,granted_by}

@tree.command(
    name="auth_grant",
    description="Generate a one-time 6-digit auth code for an accepted applicant (expires in 10 minutes).",
    guilds=[Object(id=GUILD_ID)]
)
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
    app_commands.Choice(name="Xbox Old Gen", value="XboxOG"),
])
async def auth_grant(
    interaction: discord.Interaction,
    user: discord.Member,
    department: app_commands.Choice[str],
    platform: app_commands.Choice[str]
):
    # Permission: only specific staff role
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
        return await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    # Issue code
    code = random.randint(100000, 999999)
    pending_codes[user.id] = {
        "code": code,
        "timestamp": time.time(),
        "dept": department.value,
        "platform": platform.value,
        "granted_by": interaction.user.id,
    }

    # Log to staff code channel
    log_ch = interaction.guild.get_channel(AUTH_CODE_LOG_CHANNEL)
    if log_ch:
        await log_ch.send(
            f"🔐 **Auth Code Generated**\n"
            f"User: {user.mention} (`{user.id}`)\n"
            f"Department: `{department.value}`  |  Platform: `{platform.value}`\n"
            f"Code: **{code}** (expires in 10 minutes)\n"
            f"Granted by: {interaction.user.mention}"
        )

    # DM applicant
    try:
        dm_embed = Embed(
            title="🔐 Los Santos Roleplay Network™® — Authorization",
            description=(
                f"Congratulations! Your application for **{department.value}** has been **approved**.\n\n"
                f"**Your one-time 6-digit code:** `{code}`\n"
                f"**Authorization link:** {REDIRECT_URI}\n\n"
                "Open the link, complete the authorization, and enter the code when prompted.\n"
                "This code expires in **10 minutes** and can only be used once."
            ),
            color=dept_color(department.value),
        )
        await user.send(embed=dm_embed)
        await interaction.followup.send(f"✅ Code sent to {user.mention}'s DMs.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(f"⚠️ I couldn’t DM {user.mention}. Ask them to enable DMs and re-run.", ephemeral=True)

def is_code_valid(user_id: int, code: int) -> bool:
    data = pending_codes.get(user_id)
    if not data:
        return False
    if int(data["code"]) != int(code):
        return False
    if time.time() - float(data["timestamp"]) > CODE_TTL_SECONDS:
        # expired
        pending_codes.pop(user_id, None)
        return False
    return True

def consume_code(user_id: int):
    pending_codes.pop(user_id, None)

# ─────────────────────────────────────────
# STAFF / HR COMMANDS
# ─────────────────────────────────────────
async def is_hr(interaction: discord.Interaction) -> bool:
    if isinstance(interaction.user, discord.Member):
        if any(r.id in ALLOWED_HR_ROLES for r in interaction.user.roles):
            return True
    await interaction.response.send_message(
        "**Oops, looks like you're not staff. Do not attempt to run the command again.**",
        ephemeral=True
    )
    return False

def staff_only():
    async def predicate(interaction: discord.Interaction) -> bool:
        if any(r.id == STAFF_ROLE_ID for r in interaction.user.roles):
            return True
        await interaction.response.send_message(
            "🚫 Oops, looks like you're not staff. Do not attempt to run the command again.",
            ephemeral=True
        )
        return False
    return app_commands.check(predicate)

@tree.command(name="ping", description="Check slash command sync", guilds=[Object(id=GUILD_ID)])
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🟢 Pong!")

@tree.command(name="staff_hire", description="Hire a new staff member", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(user="The user to hire")
async def staff_hire(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer()
    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    await user.add_roles(staff_role)
    await interaction.followup.send(f"✅ {user.mention} has been hired as Staff.")

@tree.command(name="staff_promote", description="Promote a staff member", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(user="User to promote", new_role="New staff role")
async def staff_promote(interaction: discord.Interaction, user: discord.Member, new_role: discord.Role):
    if not await is_hr(interaction): return
    for r_id in STAFF_ROLES:
        r = interaction.guild.get_role(r_id)
        if r in user.roles:
            await user.remove_roles(r)
    await user.add_roles(new_role)
    await interaction.response.send_message(f"✅ {user.mention} has been promoted to {new_role.mention}.")
    log_channel = interaction.guild.get_channel(PROMOTION_LOG_CHANNEL)
    if log_channel:
        await log_channel.send(f"⬆️ {user.mention} was promoted to {new_role.mention} by {interaction.user.mention}.")

@tree.command(name="staff_demote", description="Demote a staff member", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(user="User to demote", new_role="New staff role")
async def staff_demote(interaction: discord.Interaction, user: discord.Member, new_role: discord.Role):
    if not await is_hr(interaction): return
    for r_id in STAFF_ROLES:
        r = interaction.guild.get_role(r_id)
        if r in user.roles:
            await user.remove_roles(r)
    await user.add_roles(new_role)
    await interaction.response.send_message(f"❌ {user.mention} has been demoted to {new_role.mention}.")
    log_channel = interaction.guild.get_channel(DEMOTION_LOG_CHANNEL)
    if log_channel:
        await log_channel.send(f"🔇 {user.mention} was demoted to {new_role.mention} by {interaction.user.mention}.")

@tree.command(name="staff_fire", description="Fire a staff member completely", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(user="User to fire")
async def staff_fire(interaction: discord.Interaction, user: discord.Member):
    if not await is_hr(interaction): return
    removed = []
    for r_id in STAFF_ROLES:
        r = interaction.guild.get_role(r_id)
        if r in user.roles:
            await user.remove_roles(r)
            removed.append(r.name)
    await interaction.response.send_message(f"⛔️ {user.mention} has been fired. Removed roles: {', '.join(removed)}")

# ─────────────────────────────────────────
# PRIORITY COMMANDS
# ─────────────────────────────────────────
@tree.command(name="priority_start", description="Start a priority scene", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(user="User to start priority on", type="Type of priority")
@app_commands.checks.has_role(PSO_STAFF_ID)
@app_commands.choices(type=[
    app_commands.Choice(name="Shooting", value="Shooting"),
    app_commands.Choice(name="Robbery", value="Robbery"),
    app_commands.Choice(name="Pursuit", value="Pursuit"),
    app_commands.Choice(name="Other", value="Other")
])
async def priority_start(interaction: discord.Interaction, user: discord.Member, type: app_commands.Choice[str]):
    global active_priority
    if active_priority:
        return await interaction.response.send_message("⚠️ Priority already active. End it first.", ephemeral=True)
    active_priority = {"user": user, "type": type.value, "started_by": interaction.user, "time": datetime.datetime.now()}
    log_ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
    embed = Embed(title="🚨 Priority Started", description=f"**User:** {user.mention}\n**Type:** {type.value}", color=discord.Color.red())
    if log_ch:
        await log_ch.send(embed=embed)
    await interaction.response.send_message(f"✅ Priority started for {user.mention}.", ephemeral=True)

@tree.command(name="priority_end", description="End the current priority", guilds=[Object(id=GUILD_ID)])
@app_commands.checks.has_role(PSO_STAFF_ID)
async def priority_end(interaction: discord.Interaction):
    global active_priority
    if not active_priority:
        return await interaction.response.send_message("❌ No active priority.", ephemeral=True)
    log_ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
    embed = Embed(title="✅ Priority Ended", description=f"**User:** {active_priority['user'].mention}", color=discord.Color.green())
    if log_ch:
        await log_ch.send(embed=embed)
    active_priority = None
    await interaction.response.send_message("✅ Priority ended.", ephemeral=True)

# ─────────────────────────────────────────
# SESSION COMMANDS (Buttons RSVP)
# ─────────────────────────────────────────
rsvp_data: Dict[int, Dict] = {}

class RSVPView(View):
    def __init__(self, base_desc, message_id):
        super().__init__(timeout=None)
        self.base_desc = base_desc
        self.message_id = message_id
        rsvp_data[self.message_id] = {'base': base_desc, 'attendees': [], 'declines': [], 'late': []}

    async def update_embed(self, interaction: discord.Interaction):
        data = rsvp_data[self.message_id]
        summary = (
            f"\n✅ Attending: {', '.join(data['attendees']) or '—'}"
            f"\n❌ Not Attending: {', '.join(data['declines']) or '—'}"
            f"\n🕰️ Late: {', '.join(data['late']) or '—'}"
        )
        embed = Embed(description=data['base'] + summary, color=discord.Color.blurple())
        await interaction.message.edit(embed=embed, view=self)

    @discord.ui.button(label="✅ Attending", style=discord.ButtonStyle.success)
    async def attending(self, interaction: discord.Interaction, button: Button):
        data = rsvp_data[self.message_id]
        mention = interaction.user.mention
        for lst in ('attendees', 'declines', 'late'):
            if mention in data[lst]:
                data[lst].remove(mention)
        data['attendees'].append(mention)
        await self.update_embed(interaction)
        await interaction.response.defer()

    @discord.ui.button(label="❌ Not Attending", style=discord.ButtonStyle.danger)
    async def not_attending(self, interaction: discord.Interaction, button: Button):
        data = rsvp_data[self.message_id]
        mention = interaction.user.mention
        for lst in ('attendees', 'declines', 'late'):
            if mention in data[lst]:
                data[lst].remove(mention)
        data['declines'].append(mention)
        await self.update_embed(interaction)
        await interaction.response.defer()

    @discord.ui.button(label="🕰️ Late", style=discord.ButtonStyle.secondary)
    async def late(self, interaction: discord.Interaction, button: Button):
        data = rsvp_data[self.message_id]
        mention = interaction.user.mention
        for lst in ('attendees', 'declines', 'late'):
            if mention in data[lst]:
                data[lst].remove(mention)
        data['late'].append(mention)
        await self.update_embed(interaction)
        await interaction.response.defer()

@tree.command(
    name="host_main_session",
    description="Announce Main Session with RSVP buttons",
    guilds=[Object(id=GUILD_ID)]
)
@app_commands.describe(
    psn="Your PlayStation Network ID",
    date_time="Date & time of the session (e.g. July 26, 20:00 UTC)",
    session_type="Type of session (e.g. Patrol, Heist)",
    aop="Area of Play"
)
async def host_main_session(
    interaction: discord.Interaction,
    psn: str,
    date_time: str,
    session_type: str,
    aop: str
):
    ping_role = interaction.guild.get_role(PING_ROLE_ID)  # Session notify role

    base_desc = f"""**Los Santos Roleplay™ PlayStation |** `Main Session`

> *This message upholds all information regarding the upcoming roleplay session hosted by Los Santos Roleplay. Please take your time to review the details below and if any questions arise, please ask the host of the session.*

**PSN:** {psn}

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
**Commencement Process.**
> *At the below time invites will begin being disputed. You will then be directed to your proper briefing channels. We ask that you're to ensure you are connected to the Session Queue voice channel.*

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
**Session Orientation**
> *Before the session must begin, all individuals must be orientated accordingly. The orientation will happen after the invites are dispersed and you will be briefed by the highest-ranking official in terms of your department.*

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
**Session Details.**
**Start Time:** {date_time}
• **Session Type:** {session_type}
• **Area of Play:** {aop}
• [LSRPNetwork Guidelines](https://discord.com/channels/1324117813878718474/1375046710002319460/1395728361371861103) • [Priority Guidelines](https://discord.com/channels/1324117813878718474/1399853866337566881) •
"""
    embed = Embed(description=base_desc, color=discord.Color.blurple())
    await interaction.response.send_message(content=ping_role.mention if ping_role else None, embed=embed, view=RSVPView(base_desc, interaction.id))

@tree.command(name="start_session", description="Announce that the roleplay session is starting now", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(psn="Your PlayStation Network username", aop="Area of Play for the session")
async def start_session(interaction: discord.Interaction, psn: str, aop: str):
    session_role = interaction.guild.get_role(PING_ROLE_ID)
    embed = Embed(
        title="🟢 SESSION START NOTICE",
        description=(
            "**The session is now officially starting!**\n\n"
            f"📍 **Host PSN:** {psn}\n"
            f"📍 **AOP:** {aop}\n"
            f"🕒 **Start Time:** <t:{int(datetime.datetime.now().timestamp())}:F>\n\n"
            "🔊 **Please Ensure:**\n"
            "• You are in correct RP attire.\n"
            "• Your mic is working.\n"
            "• You follow all RP & community guidelines.\n"
            "• You join promptly to avoid being marked absent."
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(content=session_role.mention if session_role else None, embed=embed)

@tree.command(name="end_session", description="Announce that the roleplay session has ended", guilds=[Object(id=GUILD_ID)])
async def end_session(interaction: discord.Interaction):
    session_role = interaction.guild.get_role(PING_ROLE_ID)
    embed = Embed(
        title="🔴 SESSION CLOSED",
        description=(
            "**This session has now concluded.**\n\n"
            f"🕒 **End Time:** <t:{int(datetime.datetime.now().timestamp())}:F>\n\n"
            "🙏 **Thank you to everyone who attended and maintained professionalism throughout the session.**"
        ),
        color=discord.Color.red()
    )
    await interaction.response.send_message(content=session_role.mention if session_role else None, embed=embed)

# ─────────────────────────────────────────
# READY: Sync, Watchdog, Auto-post Panel
# ─────────────────────────────────────────
@bot.event
async def on_ready():
    # Keep panel view alive across restarts
    try:
        bot.add_view(ApplicationPanel())
    except Exception:
        pass

    # Sync commands to your guild
    guild = Object(id=GUILD_ID)
    synced = await tree.sync(guild=guild)
    print(f"✅ Synced {len(synced)} commands to guild ID {GUILD_ID}")
    print(f"🛠 Commands available: {[cmd.name for cmd in synced]}")

    # Start watchdog once
    if not watchdog.is_running():
        watchdog.start()
        print("[watchdog] Started watchdog loop.")

    # Auto-post panel if not present recently
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
                await channel.send(embed=embed, view=ApplicationPanel())
                print(f"✅ Application panel posted in #{channel.name}")
    except Exception as e:
        print(f"⚠️ Could not post application panel: {e}")

    print(f"✅ Bot is online as {bot.user}")

# ─────────────────────────────────────────
# PSO COMMANDS
# ─────────────────────────────────────────
async def remove_old_pso_roles(member: discord.Member):
    for role_id in PSO_ROLES.values():
        role = member.guild.get_role(role_id)
        if role and role in member.roles:
            await member.remove_roles(role)

@tree.command(name="pso_hire", description="Hire a user into PSO as Cadet", guilds=[Object(id=GUILD_ID)])
@staff_only()
@app_commands.describe(user="User to hire")
async def pso_hire(interaction: discord.Interaction, user: discord.Member):
    await remove_old_pso_roles(user)
    cadet_role = interaction.guild.get_role(PSO_ROLES["Cadet"])
    pso_main_role = interaction.guild.get_role(PSO_ROLES["PSO_Main"])
    callsign = f"C-{random.randint(*CALLSIGN_RANGES['Cadet'][:2])} | {user.name}"
    try:
        await user.edit(nick=callsign)
    except discord.Forbidden:
        pass
    await user.add_roles(cadet_role, pso_main_role)
    await interaction.response.send_message(f"{user.mention} hired as **Cadet** with callsign `{callsign}`")

@tree.command(name="pso_promote", description="Promote a PSO member", guilds=[Object(id=GUILD_ID)])
@staff_only()
@app_commands.describe(user="User to promote", rank="New PSO rank")
@app_commands.choices(rank=[
    app_commands.Choice(name="Officer I", value="Officer I"),
    app_commands.Choice(name="Officer II", value="Officer II"),
    app_commands.Choice(name="Sergeant", value="Sergeant"),
    app_commands.Choice(name="Master Sergeant", value="Master Sergeant"),
    app_commands.Choice(name="Lieutenant", value="Lieutenant"),
    app_commands.Choice(name="Captain", value="Captain"),
    app_commands.Choice(name="Major", value="Major"),
    app_commands.Choice(name="Commander", value="Commander"),
    app_commands.Choice(name="ADOPS", value="ADOPS"),
])
async def pso_promote(interaction: discord.Interaction, user: discord.Member, rank: app_commands.Choice[str]):
    rank_name = rank.value
    await remove_old_pso_roles(user)
    role = interaction.guild.get_role(PSO_ROLES[rank_name])
    if not role:
        return await interaction.response.send_message("❌ Role not found.", ephemeral=True)
    if rank_name == "ADOPS":
        callsign = f"L-102 | {user.name} | ADOPS"
    else:
        start, end, prefix = CALLSIGN_RANGES[rank_name]
        callsign = f"{prefix}-{random.randint(start, end)} | {user.name}"
    try:
        await user.edit(nick=callsign)
    except discord.Forbidden:
        pass
    await user.add_roles(role)
    if rank_name == "Sergeant":
        supervisor_role = interaction.guild.get_role(PSO_ROLES["Supervisor"])
        await user.add_roles(supervisor_role)
        try:
            await user.send(
                "**Congratulations!**\n\n"
                "You have been promoted to a Sergeant.\n\n"
                "> *That means you are now a supervisor...*"
            )
        except discord.Forbidden:
            pass
    await interaction.response.send_message(f"{user.mention} promoted to **{rank_name}** with callsign `{callsign}`.")

# ─────────────────────────────────────────
# RUN BOT
# ─────────────────────────────────────────
if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is not set")
    bot.run(BOT_TOKEN)
