# ===========================
# Los Santos Network System™® — Full bot.py
# ===========================

# ---------- Imports ----------
import os
import time
import random
import threading
import asyncio
import urllib.parse
from typing import Dict, Optional

import requests
import discord
from discord import app_commands, Embed, Object
from discord.ext import commands, tasks
from discord.ui import View, Button, Select

from flask import Flask, request, redirect, render_template_string

# ---------- Core ENV ----------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://lsrpnetwork-verification.up.railway.app/auth")

# ---------- Guilds ----------
HQ_GUILD_ID       = int(os.getenv("HQ_GUILD_ID", "1294319617539575808"))
PS4_GUILD_ID      = int(os.getenv("PS4_GUILD_ID", "1324117813878718474"))
PS5_GUILD_ID      = int(os.getenv("PS5_GUILD_ID", "1401903156274790441"))
XBOX_OG_GUILD_ID  = int(os.getenv("XBOX_OG_GUILD_ID", "1375494043831898334"))

PLATFORM_GUILDS = {
    "PS4":    PS4_GUILD_ID,
    "PS5":    PS5_GUILD_ID,
    "XboxOG": XBOX_OG_GUILD_ID,
}

# ---------- Channels / Roles (HQ) ----------
PANEL_CHANNEL_ID            = 1324115220725108877
APPLICATION_REVIEW_CHANNEL  = 1366431401054048357
AUTH_CODE_LOG_CHANNEL       = 1395135616177668186

# HQ applicant/accepted/pending/denied roles (in HQ)
APPLICANT_PLATFORM_ROLES = {
    "PS4":    1401961522556698739,
    "PS5":    1401961758502944900,
    "XboxOG": 1401961991756578817,
}
ACCEPTED_PLATFORM_ROLES = {
    "PS4":    1367753287872286720,
    "PS5":    1367753535839797278,
    "XboxOG": 1367753756367912960,
}
APPLICANT_DEPT_ROLES = {
    "PSO":  1370719624051691580,
    "CO":   1323758149009936424,
    "SAFR": 1370719781488955402,
}
PENDING_ROLE_ID = 1323758692918624366
DENIED_ROLE_ID  = 1323755533492027474

# Staff permissions
STAFF_CAN_POST_PANEL_ROLE = 1384558588478886022  # used for /auth_grant, /promote, panel post
MOD_ROLE_ID   = 1375046497590054985
ADMIN_ROLE_ID = 1375046495283318805

# Ping immunity (user + exempt roles)
PROTECTED_USER_ID = 1176071547476262986
HQ_IMMUNE_ROLE    = 1338855588381200426  # HQ Management Team
PS4_IMMUNE_ROLE   = 1375046488194809917  # PS4 Management Team
SUPPORT_TICKET_LINK = "https://discord.com/channels/1294319617539575808/1367056555035459606"

# ---------- Priority / Staff Logs ----------
PROMOTION_LOG_CHANNEL = 1400933920534560989
DEMOTION_LOG_CHANNEL  = 1400934049505349764
PRIORITY_LOG_CHANNEL_ID = 1398746576784068703
PSO_STAFF_ID = 1375046497590054985

# ---------- Session ----------
PING_ROLE_ID = 1375046631237484605  # Session notify role

# ---------- PS4 Dept & Ranks ----------
PS4_DEPT_ROLES = {
    "PSO_MAIN":      1375046521904431124,
    "SASP":          1401347813958226061,
    "BCSO":          1401347339796348938,
    "CO":            1375046547678429195,
    "SAFR":          1401347818873946133,
    "PSO_CATEGORY":  1404575562290434190,   # Public Safety Rank(s)
    "CO_CATEGORY":   1375046548747980830,   # Civilian Operations Rank(s)
    "SAFR_CAT":      1375046571653201961,   # Fire/EMS Rank(s)
    "BCSO_CATEGORY": 1375046520469979256,   # Sheriff's Office Rank(s)
}

# PSO ranks (PS4)
PSO_RANK_ROLES_PS4 = {
    "Cadet":               1375046543329202186,
    "Trooper":             1375046541869584464,
    "Trooper First Class": 1375046540925599815,
    "Sergeant":            1392169682596790395,
    "Master Sergeant":     1375046535410356295,
    "Lieutenant":          1375046533833035778,
    "Captain":             1375046532847501373,
    "Major":               1375046529752105041,
    "Commander":           1375046528963444819,
    "ADOPS":               1375046524567818270,
    "Supervisor":          1375046546554621952,  # added on Sergeant
}

# BCSO ranks (PS4)
BCSO_RANK_START = 1404903885432164362  # Probationary Deputy
BCSO_RANK_ROLES_PS4 = {
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

# CO ranks (PS4)
CO_RANK_ROLES_PS4 = {
    "Probationary Civ":   1375046566150406155,
    "Civilian 1":         1375046564921475102,
    "Civilian 2":         1375046563231174746,
    "Civilian 3":         1375046562182332436,
    "Civilian 4":         1375046561125498921,
    "Civilian 5":         1375046559544119298,
    "Senior Civilian":    1375046558902390876,
    "Gang Manager":       1375046557292036146,
    "Civilian Advisor":   1375046555173785620,
    "Civ Deputy Director":1375046551100985387,
    "Civ Director":       1375046550555988050,
}

# SAFR ranks (PS4)
SAFR_RANK_ROLES_PS4 = {
    "Probationary Firefighter": 1375046583153856634,
    "Firefighter 1":            1375046585150603357,
    "Firefighter Sergeant":     1375046582034235503,
    "Firefighter Lieutenant":   1375046581111361597,
    "Firefighter Captain":      1375046579047632926,
    "Battalion Chief":          1375046577214849075,
    "Deputy Fire Chief":        1375046575499513966,
    "Fire Chief":               1375046574593413151,
}

# ---------- Callsigns ----------
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
CALLSIGN_SCHEMAS = {
    "CO":   {"prefix": "Civ", "range": (1000, 1999)},  # Civ-####
    "SAFR": {"prefix": "FF",  "range": (300,  999)},   # FF-###
}

# ---------- OAuth / Web ----------
CODE_TTL_SECONDS = 5 * 60   # 5 minutes
APP_TIME_LIMIT   = 35 * 60  # 35 minutes to complete DM application

ACCEPT_GIF_URL = "https://cdn.discordapp.com/attachments/1317589676336611381/1402368709783191713/Animated_LSRP.gif?ex=689d8c63&is=689c3ae3&hm=5cd9a2cff01d151238b2fd245a8128ada27122b5f4d7d1d2214332c0324dd3fb&"
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1317589676336611381/1405147584456032276/Sunset_Photography_Tumblr_Banner.png?ex=689dc52a&is=689c73aa&hm=f7fd9a078016e1fc61d54391e5d57bf61f0c1f6b09e82b8163b16eae312c0f1a&"

pending_codes: Dict[int, dict] = {}  # user_id -> {code,timestamp,dept,platform,subdept,granted_by}

# ---------- Bot Setup ----------
intents = discord.Intents.default()
intents.members = True
intents.message_content = True
bot = commands.Bot(command_prefix="?", intents=intents)
tree = bot.tree

# ===========================
# Utilities
# ===========================
def dept_color(dept: str) -> discord.Color:
    return discord.Color.blue() if dept == "PSO" else (discord.Color.green() if dept == "CO" else discord.Color.red())

def has_promote_perms(member: discord.Member) -> bool:
    allowed = {MOD_ROLE_ID, ADMIN_ROLE_ID, STAFF_CAN_POST_PANEL_ROLE}
    return any(r.id in allowed for r in getattr(member, "roles", []))

def generate_callsign_for_dept(dept: str, base_name: str) -> str:
    try:
        if dept == "PSO":
            start, end, prefix = CALLSIGN_RANGES["Cadet"]
            number = random.randint(start, end)
            return f"{prefix}-{number} | {base_name}"
        schema = CALLSIGN_SCHEMAS.get(dept)
        if not schema:
            return base_name
        start, end = schema["range"]
        prefix = schema["prefix"]
        number = random.randint(start, end)
        return f"{prefix}-{number} | {base_name}"
    except Exception:
        return base_name

async def remove_dept_rank_roles(guild: discord.Guild, member: discord.Member, dept: str):
    try:
        ladder = {}
        if guild.id == PS4_GUILD_ID:
            if dept == "PSO":
                ladder = {**PSO_RANK_ROLES_PS4, **BCSO_RANK_ROLES_PS4}
            elif dept == "CO":
                ladder = CO_RANK_ROLES_PS4
            elif dept == "SAFR":
                ladder = SAFR_RANK_ROLES_PS4
        if ladder:
            to_remove = []
            for _, rid in ladder.items():
                r = guild.get_role(rid)
                if r and r in member.roles:
                    to_remove.append(r)
            if to_remove:
                await member.remove_roles(*to_remove, reason=f"{dept} promotion: cleanup previous ranks")
    except Exception as e:
        print(f"⚠️ remove_dept_rank_roles error: {e}")

# ===========================
# Minimal Flask OAuth server (thread)
# ===========================
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
    # 1) redirect to consent if no ?code
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

    # 2) show pin form
    if request.method == "GET":
        return render_template_string(_HTML_FORM)

    pin = (request.form.get("pin") or "").strip()

    # 3) exchange code -> access token
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

    # 4) identify user
    me = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=15
    )
    if me.status_code != 200:
        return f"User fetch failed: {me.text}", 400
    user_id = int(me.json()["id"])

    # 5) check pending code
    data = pending_codes.get(user_id)
    if not data:
        return "No active authorization found. Ask staff to run /auth_grant again.", 400
    if time.time() - float(data["timestamp"]) > CODE_TTL_SECONDS:
        pending_codes.pop(user_id, None)
        return "Your code expired. Ask staff to generate a new one.", 400
    if pin != str(data["code"]):
        return "Invalid code. Please go back and try again.", 400

    # 6) target platform guild
    target_guild = PLATFORM_GUILDS.get(data["platform"])
    if not target_guild:
        return "Platform guild not configured.", 500

    # 7) add to guild with guilds.join
    put_resp = requests.put(
        f"https://discord.com/api/guilds/{target_guild}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
        json={"access_token": access_token},
        timeout=15
    )
    if put_resp.status_code not in (200, 201, 204):
        if not (put_resp.status_code == 400 and "already" in put_resp.text.lower()):
            return f"Guild join failed: {put_resp.status_code} {put_resp.text}", 400

    # 8) Post-join provisioning on platform guild (PS4 fully configured)
    async def provision():
        # Assign platform accepted + dept packages on platform guild (PS4)
        try:
            guild = bot.get_guild(target_guild)
            if not guild:
                return
            member = guild.get_member(user_id) or await guild.fetch_member(user_id)

            add_roles, rem_roles = [], []

            # Platform applicant -> accepted swap (if exist on platform guild)
            plat_applicant_id = APPLICANT_PLATFORM_ROLES.get(data["platform"])
            plat_accepted_id  = ACCEPTED_PLATFORM_ROLES.get(data["platform"])
            if plat_applicant_id:
                rr = guild.get_role(plat_applicant_id)
                if rr and rr in member.roles:
                    rem_roles.append(rr)
            if plat_accepted_id:
                rr = guild.get_role(plat_accepted_id)
                if rr:
                    add_roles.append(rr)

            dept = data["dept"]
            subd = data.get("subdept")

            if guild.id == PS4_GUILD_ID:
                if dept == "PSO":
                    for rid in (PS4_DEPT_ROLES["PSO_MAIN"], PS4_DEPT_ROLES["PSO_CATEGORY"]):
                        r = guild.get_role(rid)
                        if r: add_roles.append(r)
                    if subd == "SASP":
                        r = guild.get_role(PS4_DEPT_ROLES["SASP"])
                        if r: add_roles.append(r)
                        cadet = guild.get_role(PSO_RANK_ROLES_PS4["Cadet"])
                        if cadet: add_roles.append(cadet)
                    elif subd == "BCSO":
                        r = guild.get_role(PS4_DEPT_ROLES["BCSO"])
                        if r: add_roles.append(r)
                        cat = guild.get_role(PS4_DEPT_ROLES["BCSO_CATEGORY"])
                        if cat: add_roles.append(cat)
                        start = guild.get_role(BCSO_RANK_START)
                        if start: add_roles.append(start)
                    else:
                        cadet = guild.get_role(PSO_RANK_ROLES_PS4["Cadet"])
                        if cadet: add_roles.append(cadet)

                elif dept == "CO":
                    for rid in (PS4_DEPT_ROLES["CO_CATEGORY"], PS4_DEPT_ROLES["CO"]):
                        r = guild.get_role(rid)
                        if r: add_roles.append(r)
                    start = guild.get_role(CO_RANK_ROLES_PS4["Probationary Civ"])
                    if start: add_roles.append(start)

                elif dept == "SAFR":
                    for rid in (PS4_DEPT_ROLES["SAFR_CAT"], PS4_DEPT_ROLES["SAFR"]):
                        r = guild.get_role(rid)
                        if r: add_roles.append(r)
                    start = guild.get_role(SAFR_RANK_ROLES_PS4["Probationary Firefighter"])
                    if start: add_roles.append(start)

            if rem_roles:
                try:    await member.remove_roles(*rem_roles, reason="OAuth join: platform applicant -> accepted")
                except Exception as e: print(f"⚠️ platform role remove failed: {e}")
            if add_roles:
                try:    await member.add_roles(*add_roles, reason=f"OAuth join: {dept} onboarding roles")
                except Exception as e: print(f"⚠️ platform role add failed: {e}")

            # Callsign nickname
            try:
                new_nick = generate_callsign_for_dept(dept, member.name)
                if new_nick and new_nick != (member.nick or member.name):
                    await member.edit(nick=new_nick, reason="OAuth join: provisional callsign")
            except discord.Forbidden:
                print("⚠️ Missing permission to change nickname.")

        except Exception as e:
            print(f"⚠️ Post-join provisioning error: {e}")

        # Log success in HQ
        try:
            guild_hq = bot.get_guild(HQ_GUILD_ID)
            if guild_hq:
                log_ch = guild_hq.get_channel(AUTH_CODE_LOG_CHANNEL)
                if log_ch:
                    await log_ch.send(
                        f"✅ **Auth success** for <@{user_id}> | Dept `{data['dept']}`"
                        f"{f' / {data.get('subdept')}' if data.get('subdept') else ''} | "
                        f"Platform `{data['platform']}` | Code `{data['code']}`"
                    )
        except Exception:
            pass

        pending_codes.pop(user_id, None)

    asyncio.run_coroutine_threadsafe(provision(), bot.loop)
    return "✅ Success! You can close this tab and return to Discord."

def run_web():
    port = int(os.environ.get("PORT", "8080"))
    flask_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# ===========================
# Application Panel + DM Flow
# ===========================
app_sessions: Dict[int, Dict] = {}  # user_id -> {dept, subdept, platform, guild_id, started_at, answers}

QUESTIONS = {
    "PSO": [
        ("What sub-department are you applying for? (SASP / BCSO)", "subdept"),
        ("What timezone are you in?", "tz"),
        ("How old are you?", "age"),
        ("Briefly describe your LEO roleplay experience.", "exp"),
        ("Why should we accept you into PSO?", "motivation"),
        ("Do you agree to follow all PSO & community guidelines? (Yes/No)", "agree"),
    ],
    "CO": [
        ("What timezone are you in?", "tz"),
        ("How old are you?", "age"),
        ("What type of civilian stories do you enjoy roleplaying?", "stories"),
        ("Describe an interesting scenario you’ve done or want to do.", "scenario"),
        ("Do you agree to follow all CO & community guidelines? (Yes/No)", "agree"),
    ],
    "SAFR": [
        ("What timezone are you in?", "tz"),
        ("How old are you?", "age"),
        ("Do you have any Fire/EMS roleplay experience?", "exp"),
        ("How would you handle a multi-patient MVA call?", "mva"),
        ("Do you agree to follow all SAFR & community guidelines? (Yes/No)", "agree"),
    ],
}

async def ask_questions_dm(user: discord.User, dept: str, platform: str) -> Optional[Dict]:
    channel = await user.create_dm()
    color = dept_color(dept)
    start_ts = time.time()

    await channel.send(embed=Embed(
        title=f"{dept} Application — Questions",
        description=f"You have **35 minutes** to complete your application.\nAnswer each question in one message.",
        color=color
    ))

    answers = {}
    qlist = QUESTIONS[dept]

    for idx, (question, key) in enumerate(qlist, start=1):
        remaining = APP_TIME_LIMIT - (time.time() - start_ts)
        if remaining <= 0:
            await channel.send("⏰ Time limit reached. Please start a new application.")
            return None

        embed = Embed(title=f"Q{idx}", description=question, color=color)
        await channel.send(embed=embed)

        try:
            msg = await bot.wait_for(
                "message",
                timeout=remaining,
                check=lambda m: m.author.id == user.id and m.channel.id == channel.id
            )
        except asyncio.TimeoutError:
            await channel.send("⏰ Time limit reached. Please start a new application.")
            return None

        content = msg.content.strip()
        # Normalize PSO subdept
        if dept == "PSO" and key == "subdept":
            val = content.upper().replace(" ", "")
            if "SASP" in val:
                content = "SASP"
            elif "BCSO" in val:
                content = "BCSO"
            else:
                await channel.send("Please answer **SASP** or **BCSO**.")
                # repeat same question
                return await ask_questions_dm(user, dept, platform)
            app_sessions[user.id]["subdept"] = content

        answers[key] = content

    app_sessions[user.id]["answers"] = answers
    return answers

async def post_review_embed(guild: discord.Guild, applicant: discord.Member, dept: str, platform: str, subdept: Optional[str], answers: Dict):
    ch = guild.get_channel(APPLICATION_REVIEW_CHANNEL)
    if not ch:
        return
    color = dept_color(dept)

    qa_lines = []
    for idx, (q, key) in enumerate(QUESTIONS[dept], start=1):
        qa_lines.append(f"**Q{idx}: {q}**\n{answers.get(key, '—')}\n")

    desc = (
        f"**Applicant:** {applicant.mention} (`{applicant.id}`)\n"
        f"**Department:** {dept}{f' / {subdept}' if subdept else ''}\n"
        f"**Platform:** {platform}\n\n" +
        "\n".join(qa_lines)
    )
    embed = Embed(title="📥 New Application Submitted", description=desc, color=color)
    await ch.send(embed=embed)

# ---------- Public panel components ----------
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
        subdept = sess.get("subdept")
        platform = sess["platform"]
        guild_id = sess.get("guild_id")

        # Give HQ applicant roles (platform + department)
        if guild_id == HQ_GUILD_ID:
            guild = bot.get_guild(HQ_GUILD_ID)
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
                    print(f"⚠️ Missing permissions to assign HQ applicant roles for user {self.user_id}")
                except Exception as e:
                    print(f"⚠️ HQ applicant role error: {e}")

        # Confirm + start questions
        emb = Embed(
            title="Application Details Confirmed",
            description=(
                f"**Department:** {dept}\n"
                f"**Sub-Department:** {subdept or 'N/A'}\n"
                f"**Platform:** {platform}\n\n"
                "✅ Selections saved. I’ll now begin your application questions."
            ),
            color=dept_color(dept)
        )
        await interaction.response.edit_message(embed=emb, view=None)

        # Begin Q/A with 35‑minute timer
        user = interaction.user
        app_sessions[user.id]["started_at"] = time.time()
        answers = await ask_questions_dm(user, dept, platform)
        if not answers:
            try:
                await user.send("❌ Your application was not completed in time. Please start again from the panel.")
            except Exception:
                pass
            return

        # Post review in HQ and give Pending role
        try:
            guild_hq = bot.get_guild(HQ_GUILD_ID)
            if guild_hq:
                member_hq = guild_hq.get_member(user.id) or await guild_hq.fetch_member(user.id)
                if PENDING_ROLE_ID:
                    pr = guild_hq.get_role(PENDING_ROLE_ID)
                    if pr:
                        try:
                            await member_hq.add_roles(pr, reason="Application submitted: Pending review")
                        except Exception as e:
                            print(f"⚠️ Pending role add failed: {e}")
                await post_review_embed(guild_hq, member_hq, dept, platform, subdept, answers)
        except Exception as e:
            print(f"⚠️ Review post error: {e}")

        # DM confirmation to applicant
        try:
            await user.send(embed=Embed(
                title="📨 Application Submitted",
                description="Your application has been sent to staff for review. You’ll be notified once a decision has been made.",
                color=discord.Color.blurple()
            ))
        except Exception:
            pass

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
                discord.SelectOption(label="Public Safety Office (PSO)", value="PSO", description="SASP / BCSO"),
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
        super().__init__(timeout=None)
        self.add_item(DepartmentSelect())

# ===========================
# /auth_grant — Accept applicant (code + button + link + GIF)
# ===========================
@tree.command(name="auth_grant", description="Approve an applicant and DM a one-time 6-digit authorization code (expires in 5 min).")
@app_commands.describe(
    user="The applicant",
    department="Department (PSO / CO / SAFR)",
    platform="Platform (PS4 / PS5 / XboxOG)",
    subdept="If PSO: SASP or BCSO (otherwise leave blank)"
)
@app_commands.choices(department=[
    app_commands.Choice(name="PSO", value="PSO"),
    app_commands.Choice(name="CO",  value="CO"),
    app_commands.Choice(name="SAFR",value="SAFR"),
])
@app_commands.choices(platform=[
    app_commands.Choice(name="PS4",    value="PS4"),
    app_commands.Choice(name="PS5",    value="PS5"),
    app_commands.Choice(name="XboxOG", value="XboxOG"),
])
async def auth_grant(
    interaction: discord.Interaction,
    user: discord.Member,
    department: app_commands.Choice[str],
    platform: app_commands.Choice[str],
    subdept: Optional[str] = None
):
    # Permissions
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in interaction.user.roles):
        return await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)

    dept = department.value
    plat = platform.value
    if dept == "PSO":
        # validate subdept
        if not subdept or subdept.upper() not in ("SASP", "BCSO"):
            return await interaction.response.send_message("For **PSO**, please provide `subdept` as **SASP** or **BCSO**.", ephemeral=True)
        subdept = subdept.upper()
    else:
        subdept = None

    await interaction.response.defer(ephemeral=True)

    # issue code
    code = random.randint(100000, 999999)
    pending_codes[user.id] = {
        "code": code,
        "timestamp": time.time(),
        "dept": dept,
        "platform": plat,
        "subdept": subdept,
        "granted_by": interaction.user.id,
    }

    # Log for staff
    try:
        log_ch = interaction.guild.get_channel(AUTH_CODE_LOG_CHANNEL) if interaction.guild else None
        if log_ch:
            await log_ch.send(
                f"🔐 **Auth Code Generated**\n"
                f"User: {user.mention} (`{user.id}`)\n"
                f"Department: `{dept}`{f' / {subdept}' if subdept else ''}  |  Platform: `{plat}`\n"
                f"Code: **{code}** (expires in 5 minutes)\n"
                f"Granted by: {interaction.user.mention}"
            )
    except Exception:
        pass

    # DM applicant: code + button + link and GIF
    try:
        btn = Button(label="Open Verification", url=REDIRECT_URI)
        view = View()
        view.add_item(btn)

        dm = await user.create_dm()
        e = Embed(
            title="✅ Application Approved",
            description=(
                f"Welcome to **Los Santos Roleplay Network™®**!\n\n"
                f"**This is your 1 time 6 digit code:** `{code}`\n"
                f"**Once this code is used in the authorization link it will no longer be valid.**\n\n"
                f"[Main Server Verification Link]({REDIRECT_URI})"
            ),
            color=dept_color(dept)
        )
        e.set_image(url=ACCEPT_GIF_URL)
        await dm.send(embed=e, view=view)
        await interaction.followup.send(f"✅ Code sent to {user.mention}'s DMs.", ephemeral=True)
    except discord.Forbidden:
        await interaction.followup.send(f"⚠️ I couldn’t DM {user.mention}. Ask them to enable DMs and re-run.", ephemeral=True)

# ===========================
# Staff / HR commands
# ===========================
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

async def is_hr(interaction: discord.Interaction) -> bool:
    if isinstance(interaction.user, discord.Member):
        if any(r.id in ALLOWED_HR_ROLES for r in interaction.user.roles):
            return True
    await interaction.response.send_message("🚫 You’re not authorized to run this.", ephemeral=True)
    return False

@tree.command(name="ping", description="Check slash command availability")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🟢 Pong!")

@tree.command(name="staff_hire", description="Hire a new staff member")
@app_commands.describe(user="The user to hire")
async def staff_hire(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.defer(ephemeral=True)
    staff_role = interaction.guild.get_role(STAFF_ROLE_ID)
    if staff_role:
        await user.add_roles(staff_role)
    await interaction.followup.send(f"✅ {user.mention} has been hired as Staff.", ephemeral=True)

@tree.command(name="staff_promote", description="Promote a staff member")
@app_commands.describe(user="User to promote", new_role="New staff role")
async def staff_promote(interaction: discord.Interaction, user: discord.Member, new_role: discord.Role):
    if not await is_hr(interaction): return
    for r_id in STAFF_ROLES:
        r = interaction.guild.get_role(r_id)
        if r in user.roles:
            await user.remove_roles(r)
    await user.add_roles(new_role)
    await interaction.response.send_message(f"✅ {user.mention} has been promoted to {new_role.mention}.")
    ch = interaction.guild.get_channel(PROMOTION_LOG_CHANNEL)
    if ch: await ch.send(f"⬆️ {user.mention} was promoted to {new_role.mention} by {interaction.user.mention}.")

@tree.command(name="staff_demote", description="Demote a staff member")
@app_commands.describe(user="User to demote", new_role="New staff role")
async def staff_demote(interaction: discord.Interaction, user: discord.Member, new_role: discord.Role):
    if not await is_hr(interaction): return
    for r_id in STAFF_ROLES:
        r = interaction.guild.get_role(r_id)
        if r in user.roles:
            await user.remove_roles(r)
    await user.add_roles(new_role)
    await interaction.response.send_message(f"❌ {user.mention} has been demoted to {new_role.mention}.")
    ch = interaction.guild.get_channel(DEMOTION_LOG_CHANNEL)
    if ch: await ch.send(f"🔇 {user.mention} was demoted to {new_role.mention} by {interaction.user.mention}.")

@tree.command(name="staff_fire", description="Fire a staff member completely")
@app_commands.describe(user="User to fire")
async def staff_fire(interaction: discord.Interaction, user: discord.Member):
    if not await is_hr(interaction): return
    removed = []
    for r_id in STAFF_ROLES:
        r = interaction.guild.get_role(r_id)
        if r in user.roles:
            await user.remove_roles(r); removed.append(r.name)
    await interaction.response.send_message(f"⛔️ {user.mention} fired. Removed roles: {', '.join(removed) or '—'}")

# ===========================
# Priority
# ===========================
active_priority = None

@tree.command(name="priority_start", description="Start a priority scene")
@app_commands.describe(user="User to start priority on", type="Type of priority")
@app_commands.checks.has_role(PSO_STAFF_ID)
@app_commands.choices(type=[
    app_commands.Choice(name="Shooting", value="Shooting"),
    app_commands.Choice(name="Robbery", value="Robbery"),
    app_commands.Choice(name="Pursuit", value="Pursuit"),
    app_commands.Choice(name="Other", value="Other"),
])
async def priority_start(interaction: discord.Interaction, user: discord.Member, type: app_commands.Choice[str]):
    global active_priority
    if active_priority:
        return await interaction.response.send_message("⚠️ Priority already active. End it first.", ephemeral=True)
    active_priority = {"user": user, "type": type.value, "started_by": interaction.user, "time": time.time()}
    ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
    e = Embed(title="🚨 Priority Started", description=f"**User:** {user.mention}\n**Type:** {type.value}", color=discord.Color.red())
    if ch: await ch.send(embed=e)
    await interaction.response.send_message(f"✅ Priority started for {user.mention}.", ephemeral=True)

@tree.command(name="priority_end", description="End the current priority")
@app_commands.checks.has_role(PSO_STAFF_ID)
async def priority_end(interaction: discord.Interaction):
    global active_priority
    if not active_priority:
        return await interaction.response.send_message("❌ No active priority.", ephemeral=True)
    ch = interaction.guild.get_channel(PRIORITY_LOG_CHANNEL_ID)
    e = Embed(title="✅ Priority Ended", description=f"**User:** {active_priority['user'].mention}", color=discord.Color.green())
    if ch: await ch.send(embed=e)
    active_priority = None
    await interaction.response.send_message("✅ Priority ended.", ephemeral=True)

# ===========================
# Session (RSVP buttons)
# ===========================
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
    async def attending(self, interaction: discord.Interaction, _: Button):
        data = rsvp_data[self.message_id]; m = interaction.user.mention
        for lst in ('attendees','declines','late'):
            if m in data[lst]: data[lst].remove(m)
        data['attendees'].append(m)
        await self.update_embed(interaction); await interaction.response.defer()

    @discord.ui.button(label="❌ Not Attending", style=discord.ButtonStyle.danger)
    async def not_attending(self, interaction: discord.Interaction, _: Button):
        data = rsvp_data[self.message_id]; m = interaction.user.mention
        for lst in ('attendees','declines','late'):
            if m in data[lst]: data[lst].remove(m)
        data['declines'].append(m)
        await self.update_embed(interaction); await interaction.response.defer()

    @discord.ui.button(label="🕰️ Late", style=discord.ButtonStyle.secondary)
    async def late(self, interaction: discord.Interaction, _: Button):
        data = rsvp_data[self.message_id]; m = interaction.user.mention
        for lst in ('attendees','declines','late'):
            if m in data[lst]: data[lst].remove(m)
        data['late'].append(m)
        await self.update_embed(interaction); await interaction.response.defer()

@tree.command(name="host_main_session", description="Announce Main Session with RSVP buttons")
@app_commands.describe(psn="PSN", date_time="Date & time", session_type="Type", aop="Area of Play")
async def host_main_session(interaction: discord.Interaction, psn: str, date_time: str, session_type: str, aop: str):
    ping_role = interaction.guild.get_role(PING_ROLE_ID)
    base_desc = f"""**Los Santos Roleplay™ PlayStation |** `Main Session`

**PSN:** {psn}

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
**Commencement Process.**
> *At the below time invites will begin being disputed. Connect to Session Queue voice channel.*

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
**Session Orientation**
> *Orientation will happen after invites are dispersed and you will be briefed.*

▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬
**Session Details.**
**Start Time:** {date_time}
• **Session Type:** {session_type}
• **Area of Play:** {aop}
• [LSRPNetwork Guidelines](https://discord.com/channels/1324117813878718474/1375046710002319460/1395728361371861103) • [Priority Guidelines](https://discord.com/channels/1324117813878718474/1399853866337566881) •
"""
    embed = Embed(description=base_desc, color=discord.Color.blurple())
    await interaction.response.send_message(content=ping_role.mention if ping_role else None, embed=embed, view=RSVPView(base_desc, interaction.id))

@tree.command(name="start_session", description="Announce that the roleplay session is starting now")
@app_commands.describe(psn="Host PSN", aop="Area of Play")
async def start_session(interaction: discord.Interaction, psn: str, aop: str):
    session_role = interaction.guild.get_role(PING_ROLE_ID)
    e = Embed(
        title="🟢 SESSION START NOTICE",
        description=(
            "**The session is now officially starting!**\n\n"
            f"📍 **Host PSN:** {psn}\n"
            f"📍 **AOP:** {aop}\n"
            f"🕒 **Start Time:** <t:{int(time.time())}:F>\n\n"
            "🔊 **Please Ensure:**\n"
            "• Correct RP attire\n• Mic working\n• Follow guidelines\n• Join promptly"
        ),
        color=discord.Color.green()
    )
    await interaction.response.send_message(content=session_role.mention if session_role else None, embed=e)

@tree.command(name="end_session", description="Announce that the roleplay session has ended")
async def end_session(interaction: discord.Interaction):
    session_role = interaction.guild.get_role(PING_ROLE_ID)
    e = Embed(
        title="🔴 SESSION CLOSED",
        description=(
            "**This session has now concluded.**\n\n"
            f"🕒 **End Time:** <t:{int(time.time())}:F>\n\n"
            "🙏 Thank you for maintaining professionalism."
        ),
        color=discord.Color.red()
    )
    await interaction.response.send_message(content=session_role.mention if session_role else None, embed=e)

# ===========================
# Universal /promote (PS4 guild)
# ===========================
PROMOTE_RANKS = {
    "PSO":  list(PSO_RANK_ROLES_PS4.keys()),
    "BCSO": list(BCSO_RANK_ROLES_PS4.keys()),
    "CO":   list(CO_RANK_ROLES_PS4.keys()),
    "SAFR": list(SAFR_RANK_ROLES_PS4.keys()),
}

@tree.command(name="promote", description="Promote a member in PS4 guild (updates roles and callsign).")
@app_commands.describe(
    user="Member to promote (PS4 Guild)",
    department="Department ladder",
    rank="New rank"
)
@app_commands.choices(department=[
    app_commands.Choice(name="PSO", value="PSO"),
    app_commands.Choice(name="BCSO", value="BCSO"),
    app_commands.Choice(name="CO", value="CO"),
    app_commands.Choice(name="SAFR", value="SAFR"),
])
async def promote(interaction: discord.Interaction, user: discord.Member, department: app_commands.Choice[str], rank: str):
    if not has_promote_perms(interaction.user):
        return await interaction.response.send_message("🚫 You don’t have permission to use this.", ephemeral=True)
    if interaction.guild.id != PS4_GUILD_ID:
        return await interaction.response.send_message("This command operates only in the **PS4** guild.", ephemeral=True)

    dept = department.value
    ladder_map = {
        "PSO":  PSO_RANK_ROLES_PS4,
        "BCSO": BCSO_RANK_ROLES_PS4,
        "CO":   CO_RANK_ROLES_PS4,
        "SAFR": SAFR_RANK_ROLES_PS4,
    }
    if rank not in ladder_map[dept]:
        return await interaction.response.send_message(f"Rank `{rank}` not found in {dept}.", ephemeral=True)

    await interaction.response.defer(ephemeral=True)

    # Remove all prior ranks in that ladder
    await remove_dept_rank_roles(interaction.guild, user, dept)

    # Add new rank
    new_role = interaction.guild.get_role(ladder_map[dept][rank])
    if new_role:
        await user.add_roles(new_role, reason=f"{dept} promotion to {rank}")

    # PSO Sergeant → add Supervisor
    if dept == "PSO" and rank == "Sergeant":
        sup = interaction.guild.get_role(PSO_RANK_ROLES_PS4["Supervisor"])
        if sup: await user.add_roles(sup, reason="PSO Sergeant auto Supervisor")

    # Nickname / callsign
    try:
        cs = generate_callsign_for_dept("PSO" if dept in ("PSO","BCSO") else dept, user.name)
        await user.edit(nick=cs, reason=f"{dept} promotion: callsign update")
    except discord.Forbidden:
        pass

    await interaction.followup.send(f"✅ Promoted {user.mention} to **{rank}** in **{dept}**.", ephemeral=True)

# Autocomplete for /promote rank
@promote.autocomplete("rank")
async def rank_autocomplete(interaction: discord.Interaction, current: str):
    dept_choice = interaction.namespace.department
    if not dept_choice:
        return []
    dept = dept_choice.value
    ranks = PROMOTE_RANKS.get(dept, [])
    current_low = (current or "").lower()
    return [app_commands.Choice(name=r, value=r) for r in ranks if current_low in r.lower()][:25]

# ===========================
# Ping immunity (HQ + PS4)
# ===========================
@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    gid = message.guild.id
    if gid not in {HQ_GUILD_ID, PS4_GUILD_ID}:
        return
    if message.mentions and any(u.id == PROTECTED_USER_ID for u in message.mentions):
        # exempt roles
        immune_role_id = HQ_IMMUNE_ROLE if gid == HQ_GUILD_ID else PS4_IMMUNE_ROLE
        if any(r.id == immune_role_id for r in getattr(message.author, "roles", [])):
            return
        try:
            await message.delete()
        except Exception:
            pass
        try:
            warn = await message.channel.send(
                f"Naughty Naughty {message.author.mention}, please don't ping <@{PROTECTED_USER_ID}>, "
                f"he is a busy man but his DMs are always open.\n"
                f"Pinging him again will result in a written warning. "
                f"If you request help, please open a support ticket in {SUPPORT_TICKET_LINK}."
            )
            # auto-delete warning after 8 seconds to keep channel clean
            await asyncio.sleep(8)
            await warn.delete()
        except Exception:
            pass

    await bot.process_commands(message)

# ===========================
# Watchdog
# ===========================
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
        print("[watchdog] Discord unreachable. Restarting process…")
        os._exit(1)

@watchdog.before_loop
async def _before_watchdog():
    await bot.wait_until_ready()

# ===========================
# Post Application Panel (manual + auto)
# ===========================
def panel_embed() -> Embed:
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
    try:
        e.set_image(url=PANEL_IMAGE_URL)
    except Exception:
        pass
    return e

@bot.command(name="post_application_panel")
@commands.has_permissions(manage_guild=True)
async def post_application_panel(ctx: commands.Context):
    # allow only staff role explicitly too
    if not any(r.id == STAFF_CAN_POST_PANEL_ROLE for r in getattr(ctx.author, "roles", [])):
        return await ctx.reply("🚫 You don’t have permission to post the panel.")
    await ctx.message.delete(delay=0)
    try:
        await ctx.channel.send(embed=panel_embed(), view=ApplicationPanel())
    except Exception as e:
        await ctx.send(f"⚠️ Failed to post panel: {e}", delete_after=10)

# ===========================
# Ready: global sync + auto panel + watchdog
# ===========================
@bot.event
async def on_ready():
    try:
        bot.add_view(ApplicationPanel())  # keep persistent view alive
    except Exception:
        pass

    # Global sync (so commands show in all your servers)
    try:
        synced = await tree.sync()
        print(f"🌍 Pushed {len(synced)} commands globally")
    except Exception as e:
        print(f"⚠️ Global sync failed: {e}")

    # Start watchdog once
    if not watchdog.is_running():
        watchdog.start()
        print("[watchdog] Started watchdog loop.")

    # Auto-post panel in HQ if not present in recent history
    try:
        hq = bot.get_guild(HQ_GUILD_ID)
        channel = hq.get_channel(PANEL_CHANNEL_ID) if hq else None
        if channel:
            async for msg in channel.history(limit=20):
                if msg.author == bot.user and msg.components:
                    break
            else:
                await channel.send(embed=panel_embed(), view=ApplicationPanel())
                print(f"✅ Application panel posted in #{channel.name}")
    except Exception as e:
        print(f"⚠️ Could not auto-post panel: {e}")

    print(f"🟢 Bot is online as {bot.user}")

# ===========================
# Run
# ===========================
if __name__ == "__main__":
    bot.run(BOT_TOKEN)
