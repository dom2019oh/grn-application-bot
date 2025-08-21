# ================================================================
# LSRP Network — Application Bot (Full)
# ================================================================
# Features
# - Permanent Application Panel (dropdown: PSO / Civilian Ops / SAFD)
# - DM applications (20 Qs/department, Q4 = buttons, 45 min total)
# - Staff review embed (single channel) with Accept / Deny buttons
# - Accept => DM + invite + HQ Verified->Official swap (ENV IDs)
# - Member join:
#     • PS4: keep existing behavior (applicant->accepted + PSO roles + callsign + log)
#     • PS5: mirror PS4 behavior (accepted + category roles + callsign + log)
# - OAuth web server (/auth) to join PS4/PS5 using access_token
#
# Edit hotspots are marked with:  ### EDIT HERE
# ================================================================

import os
import random
import asyncio
from threading import Thread

import requests
from flask import Flask, request

import discord
from discord.ext import commands
from discord import app_commands, Embed
from discord.ui import View, Button, Select
from discord import SelectOption


# ================================================================
# SECTION 1 — Setup & Constants
# ================================================================

intents = discord.Intents.default()
intents.members = True
intents.message_content = False

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# --- Critical ENV (set these in Railway) ------------------------
BOT_TOKEN         = os.getenv("BOT_TOKEN")                          ### EDIT HERE (ENV)
CLIENT_ID         = os.getenv("CLIENT_ID")                          ### EDIT HERE (ENV)
CLIENT_SECRET     = os.getenv("CLIENT_SECRET")                      ### EDIT HERE (ENV)
REDIRECT_URI      = os.getenv("REDIRECT_URI", "https://lsrpnetwork-verification.up.railway.app/auth")
VERIFIED_ROLE_ID  = int(os.getenv("VERIFIED_ROLE_ID", "0"))         ### EDIT HERE (ENV)
OFFICIAL_ROLE_ID  = int(os.getenv("OFFICIAL_ROLE_ID", "0"))         ### EDIT HERE (ENV)

# --- Fixed IDs (from your setup) --------------------------------
HQ_GUILD_ID                = 1324117813878718474
PS4_GUILD_ID               = 1324117813878718474
PS5_GUILD_ID               = 1401903156274790441
PANEL_CHANNEL_ID_HQ        = 1324115220725108877     # Permanent application panel lives here
STAFF_REVIEW_CHANNEL_ID    = 1366431401054048357     # Same channel for all departments

# PS4 applicant/accepted
PS4_APPLICANT_ROLE_ID      = 1401961522556698739
PS4_ACCEPTED_ROLE_ID       = 1367753287872286720

# PS5 applicant/accepted
PS5_APPLICANT_ROLE_ID      = 1401961758502944900
PS5_ACCEPTED_ROLE_ID       = 1367753535839797278

# PS4 PSO roles (keep exact list you provided)
PS4_PSO_ROLES = [
    1375046619824914543,
    1375046631237484605,
    1375046520469979256,
    1375046521904431124,
    1375046543329202186,
]

# PS5 category roles to attach on join (SASP/BCSO)
PS5_PSO_ROLES = [
    1407034121808646269,  # ⦿ San Andreas State Police ⦿
    1407034123561734245,  # ⦿ Blaine County Sheriff's Office ⦿
]

# Callsign log
CALLSIGN_LOG_CHANNEL_ID    = 1396076403052773396

# Invite
MAIN_INVITE_LINK           = "https://discord.gg/yN2fs6y5v3"

# Application timing
APP_TOTAL_TIME_SECONDS     = 45 * 60    # EXACTLY 45 minutes

# Colors
COLOR_PSO  = discord.Color.blue()
COLOR_CIV  = discord.Color.green()
COLOR_SAFD = discord.Color.from_rgb(207, 16, 32)  # lava red-ish
COLOR_PANEL= discord.Color.blurple()

# ================================================================
# SECTION 2 — Department Question Banks (20 each)
# ================================================================

PSO_QUESTIONS = [
    "What is Discord username?",
    "How old are you in real life?",
    "Please state your Date of Birth. (e.g., 16th June 2010)",
    "How did you find us?",  # BUTTONS
    "Explain the \"No Life Rule\" in the best of your ability.",
    "What does VDM, RDM and FRP mean? Describe in the best of your ability.",
    "Do you have any roleplay experience, if so, please tell us.",
    "What time zone are you from? (e.g., GMT, EST, UTC etc.)",
    "Describe what a 10-11 means. In your own words.",
    "You see a suspect with a knife coming at you. Select one action:\n• Ask him to stop.\n• Taser him. ✅\n• Run away.\n• Shoot him. ✅",
    "What does a 10-80 mean? (Foot pursuit / Officer down / Vehicle chase ✅)",
    "How would you handle a 10-11? (User explains)",
    "You arrive at a robbery scene, suspect yells “I have a bomb!!” – what do you do next?",
    "What does Code 1, 2, and 3 mean?",
    "When you go on duty, what 10 codes do you use?\n• 10-8, 10-41 ✅\n• 10-7, 10-42\n• 10-70, 10-80",
    "As a cadet, are you eligible to drive on your own?\n• Yes\n• No ✅",
    "You see a sniper on a hilltop. You have a pistol and radio. What do you do? (Min 20 words)",
    "How would you handle a noise complaint? (Min 20 words)",
    "Choose the correct cadet loadout:\n• Pistol, taser, baton, flashlight ✅\n• Assault rifle, pistol, shotgun, baton, flashbang\n• RPG, baton, pistol, flashlight",
    "What is a 10-99?",
]

CIVILIAN_QUESTIONS = [
    "What is Discord username?",
    "How old are you in real life?",
    "Please state your Date of Birth.",
    "How did you find us?",  # BUTTONS
    "Explain FearRP in your own words.",
    "What is Powergaming? Give an example.",
    "What is Metagaming? Give an example.",
    "Do you have previous civilian roleplay experience?",
    "Describe how you would roleplay a traffic stop as a civilian.",
    "If police chase you for speeding, how do you react?",
    "What do you do if you crash during an RP scene?",
    "Explain how to roleplay injuries properly.",
    "How would you roleplay a robbery realistically?",
    "What is FailRP? Provide an example.",
    "How do you roleplay owning a business?",
    "How would you roleplay being arrested?",
    "What is Cop Baiting and why is it not allowed?",
    "Describe how you would roleplay a car accident.",
    "What do you do if staff interrupts your RP?",
    "Why do you want to join Civilian Operations?",
]

SAFD_QUESTIONS = [
    "What is Discord username?",
    "How old are you in real life?",
    "Please state your Date of Birth.",
    "How did you find us?",  # BUTTONS
    "What does EMT stand for?",
    "Explain how you would roleplay a fire scene.",
    "How do you roleplay CPR?",
    "What’s the difference between ALS and BLS?",
    "List key firefighter equipment used in scenes.",
    "How would you treat a gunshot wound?",
    "How do you roleplay transporting a patient?",
    "What do you do if PD calls you to a crash?",
    "How do you roleplay being overrun in a fire?",
    "What’s the chain of command in SAFD?",
    "How do you roleplay a hazmat scene?",
    "What’s the correct SAFD radio code for en route?",
    "How do you roleplay backup arriving?",
    "What’s the SAFD loadout?",
    "How would you roleplay heat exhaustion?",
    "Why do you want to join SAFD?",
]

# Department map
DEPTS = {
    "PSO":      {"color": COLOR_PSO,  "questions": PSO_QUESTIONS},
    "Civilian": {"color": COLOR_CIV,  "questions": CIVILIAN_QUESTIONS},
    "SAFD":     {"color": COLOR_SAFD, "questions": SAFD_QUESTIONS},
}

# ================================================================
# SECTION 3 — Panel (Permanent)
# ================================================================

class DepartmentSelect(Select):
    def __init__(self):
        options = [
            SelectOption(label="PSO", description="Public Safety Office Application", emoji="🛡️"),
            SelectOption(label="Civilian", description="Civilian Operations Application", emoji="🧍"),
            SelectOption(label="SAFD", description="Fire/EMS Application", emoji="🚑"),
        ]
        super().__init__(
            placeholder="Select your department to start the application…",
            min_values=1, max_values=1, options=options, custom_id="lsrp_panel_select"
        )

    async def callback(self, interaction: discord.Interaction):
        dept = self.values[0]
        await interaction.response.send_message(
            f"✅ Check your DMs to start the **{dept}** application. You have **45 minutes**.",
            ephemeral=True
        )
        try:
            await start_application_dm(interaction.user, dept)
        except discord.Forbidden:
            await interaction.followup.send(
                "⚠️ I couldn't DM you. Enable DMs and try again.",
                ephemeral=True
            )

class ApplicationPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DepartmentSelect())

async def post_permanent_panel():
    """Posts the permanent panel in the configured channel (HQ)."""
    guild = bot.get_guild(HQ_GUILD_ID)
    if not guild:
        return
    ch = guild.get_channel(PANEL_CHANNEL_ID_HQ)
    if not ch:
        return

    desc = (
        "**Welcome to Los Santos Roleplay Network™® Applications**\n\n"
        "Use the dropdown below to select your department and begin your application.\n"
        "Applications are conducted via **DM**. You have **45 minutes** to complete all questions.\n"
        "Staff will review your application and notify you of the result."
    )
    emb = Embed(title="📋 LSRP Network — Membership Applications", description=desc, color=COLOR_PANEL)
    await ch.send(embed=emb, view=ApplicationPanel())

# ================================================================
# SECTION 4 — DM Application Flow
# ================================================================

class HowFoundButtons(View):
    """Button set for Q4: How did you find us?"""
    def __init__(self):
        super().__init__(timeout=APP_TOTAL_TIME_SECONDS)
        self.value = None

    @discord.ui.button(label="Friend", style=discord.ButtonStyle.primary)
    async def friend(self, interaction: discord.Interaction, button: Button):
        self.value = "Friend"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Instagram", style=discord.ButtonStyle.primary)
    async def instagram(self, interaction: discord.Interaction, button: Button):
        self.value = "Instagram"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Partnership", style=discord.ButtonStyle.primary)
    async def partnership(self, interaction: discord.Interaction, button: Button):
        self.value = "Partnership"
        await interaction.response.defer()
        self.stop()

    @discord.ui.button(label="Other", style=discord.ButtonStyle.secondary)
    async def other(self, interaction: discord.Interaction, button: Button):
        self.value = "Other"
        await interaction.response.defer()
        self.stop()

async def _ask_text(dm: discord.DMChannel, color: discord.Color, q: str) -> str | None:
    emb = Embed(title="Application Question", description=q, color=color)
    await dm.send(embed=emb)

    def check(m: discord.Message):
        return isinstance(m.channel, discord.DMChannel) and m.author == dm.recipient

    try:
        msg = await bot.wait_for("message", timeout=APP_TOTAL_TIME_SECONDS, check=check)
        return msg.content.strip()
    except asyncio.TimeoutError:
        await dm.send("⏰ Time limit exceeded (45 minutes). Please reapply from the panel.")
        return None

async def _ask_buttons(dm: discord.DMChannel, color: discord.Color, q: str) -> str | None:
    emb = Embed(title="Application Question", description=q, color=color)
    view = HowFoundButtons()
    sent = await dm.send(embed=emb, view=view)
    try:
        timeout = await view.wait()
        if timeout or not view.value:
            await dm.send("⏰ Time limit exceeded (45 minutes). Please reapply from the panel.")
            return None
        return view.value
    finally:
        # remove buttons
        try:
            await sent.edit(view=None)
        except Exception:
            pass

async def start_application_dm(user: discord.User, dept_key: str):
    dept = DEPTS.get(dept_key)
    if not dept:
        return
    color = dept["color"]
    questions = dept["questions"]

    dm = await user.create_dm()
    intro = (
        f"**{dept_key} Application**\n"
        "Answer each question. Use the buttons when provided.\n"
        "You have **45 minutes** in total to complete this application."
    )
    await dm.send(embed=Embed(title="Starting Application", description=intro, color=color))

    answers: list[str] = []
    for idx, q in enumerate(questions, start=1):
        if idx == 4:
            ans = await _ask_buttons(dm, color, q)
        else:
            ans = await _ask_text(dm, color, q)
        if ans is None:
            return  # user timed out
        answers.append(ans)

    await _post_for_review(user, dept_key, questions, answers, color)

# ================================================================
# SECTION 5 — Staff Review & Accept/Deny
# ================================================================

class ReviewButtons(View):
    def __init__(self, applicant_id: int, dept: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.dept = dept

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        # Disable both buttons
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)

        # DM the applicant with invite
        try:
            user = await bot.fetch_user(self.applicant_id)
            dm = await user.create_dm()
            desc = (
                f"You've been **ACCEPTED** to **{self.dept}**!\n\n"
                f"Join here: {MAIN_INVITE_LINK}\n\n"
                "Once you join the platform server, your roles and callsign will be handled automatically."
            )
            await dm.send(embed=Embed(title="✅ Application Accepted", description=desc, color=discord.Color.green()))
        except Exception:
            pass

        # HQ role swap: Verified -> Official (ENV-based)
        hq = bot.get_guild(HQ_GUILD_ID)
        if hq and VERIFIED_ROLE_ID and OFFICIAL_ROLE_ID:
            member = hq.get_member(self.applicant_id)
            if member:
                vrole = hq.get_role(VERIFIED_ROLE_ID)
                orole = hq.get_role(OFFICIAL_ROLE_ID)
                try:
                    if vrole and vrole in member.roles:
                        await member.remove_roles(vrole, reason="Accepted: Verified->Official")
                except Exception:
                    pass
                try:
                    if orole and orole not in member.roles:
                        await member.add_roles(orole, reason="Accepted: add Official")
                except Exception:
                    pass

        await interaction.followup.send("✅ Accepted. Invite sent; HQ roles updated.", ephemeral=True)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.danger)
    async def deny(self, interaction: discord.Interaction, button: Button):
        for item in self.children:
            if isinstance(item, Button):
                item.disabled = True
        await interaction.response.edit_message(view=self)

        # DM denial
        try:
            user = await bot.fetch_user(self.applicant_id)
            dm = await user.create_dm()
            await dm.send(embed=Embed(
                title="❌ Application Denied",
                description="Thank you for applying. You may reapply after the cooldown.",
                color=discord.Color.red()
            ))
        except Exception:
            pass

        await interaction.followup.send("❌ Applicant denied.", ephemeral=True)

async def _post_for_review(user: discord.User, dept_key: str, questions: list[str], answers: list[str], color: discord.Color):
    guild = bot.get_guild(HQ_GUILD_ID)
    if not guild:
        return
    ch = guild.get_channel(STAFF_REVIEW_CHANNEL_ID)
    if not ch:
        return

    emb = Embed(title=f"{dept_key} Membership Application", color=color)
    emb.set_author(name=f"{user} • {user.id}")
    for i, q in enumerate(questions, start=1):
        val = answers[i - 1]
        if len(val) > 1024:
            val = val[:1020] + " ..."
        emb.add_field(name=f"Q{i}. {q}", value=val or "*No answer*", inline=False)

    view = ReviewButtons(applicant_id=user.id, dept=dept_key)
    await ch.send(embed=emb, view=view)

# ================================================================
# SECTION 6 — Member Join (PS4 kept, PS5 mirrored)
# ================================================================

def _gen_callsign(username: str) -> str:
    return f"C-{random.randint(1000, 1999)} | {username}"

async def _log_callsign(guild: discord.Guild, member: discord.Member, callsign: str, tag: str):
    ch = guild.get_channel(CALLSIGN_LOG_CHANNEL_ID)
    if ch:
        try:
            await ch.send(f"✅ {member.mention} assigned callsign **{callsign}** ({tag}).")
        except Exception:
            pass

@bot.event
async def on_member_join(member: discord.Member):
    try:
        # ---------------- PS4 (AS-IS BEHAVIOR) ----------------
        if member.guild.id == PS4_GUILD_ID:
            # Remove Applicant, add Accepted
            app_role = member.guild.get_role(PS4_APPLICANT_ROLE_ID)
            if app_role and app_role in member.roles:
                try:
                    await member.remove_roles(app_role, reason="Accepted: remove PS4 Applicant")
                except Exception:
                    pass

            acc_role = member.guild.get_role(PS4_ACCEPTED_ROLE_ID)
            if acc_role and acc_role not in member.roles:
                try:
                    await member.add_roles(acc_role, reason="Accepted: add PS4 Accepted")
                except Exception:
                    pass

            # Add PSO roles list
            for rid in PS4_PSO_ROLES:
                r = member.guild.get_role(rid)
                if r and r not in member.roles:
                    try:
                        await member.add_roles(r, reason="PS4: add PSO base roles")
                    except Exception:
                        pass

            # Callsign + log
            callsign = _gen_callsign(member.name)
            try:
                await member.edit(nick=callsign, reason="PS4: cadet callsign")
            except Exception:
                pass
            await _log_callsign(member.guild, member, callsign, "PS4")

            return  # done

        # ---------------- PS5 (MIRROR PS4) ----------------
        if member.guild.id == PS5_GUILD_ID:
            # Remove Applicant, add Accepted
            app_role = member.guild.get_role(PS5_APPLICANT_ROLE_ID)
            if app_role and app_role in member.roles:
                try:
                    await member.remove_roles(app_role, reason="Accepted: remove PS5 Applicant")
                except Exception:
                    pass

            acc_role = member.guild.get_role(PS5_ACCEPTED_ROLE_ID)
            if acc_role and acc_role not in member.roles:
                try:
                    await member.add_roles(acc_role, reason="Accepted: add PS5 Accepted")
                except Exception:
                    pass

            # Add PS5 base category roles (SASP/BCSO)
            for rid in PS5_PSO_ROLES:
                r = member.guild.get_role(rid)
                if r and r not in member.roles:
                    try:
                        await member.add_roles(r, reason="PS5: add PSO category roles")
                    except Exception:
                        pass

            # Callsign + log
            callsign = _gen_callsign(member.name)
            try:
                await member.edit(nick=callsign, reason="PS5: cadet callsign")
            except Exception:
                pass
            await _log_callsign(member.guild, member, callsign, "PS5")

    except Exception:
        # Quiet fail to avoid breaking join flow
        pass

# ================================================================
# SECTION 7 — OAuth Web Server (/auth) (UNCHANGED BEHAVIOR)
# ================================================================

app = Flask(__name__)

@app.route("/auth")
def auth_grant():
    code = request.args.get("code")
    if not code:
        return "No code provided", 400

    # Exchange code for token
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    if r.status_code != 200:
        return f"Token exchange failed: {r.text}", 400

    access_token = r.json().get("access_token")
    if not access_token:
        return "Failed to get access token", 400

    # Get user info
    user = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    ).json()
    user_id = int(user["id"])

    # Add to PS4 + PS5 (HQ already handled separately by you)
    for gid in (PS4_GUILD_ID, PS5_GUILD_ID):
        try:
            url = f"https://discord.com/api/guilds/{gid}/members/{user_id}"
            requests.put(url, json={"access_token": access_token},
                         headers={"Authorization": f"Bot {BOT_TOKEN}"}, timeout=10)
        except Exception:
            pass

    return f"<h2>✅ Welcome {user.get('username','User')}!</h2><p>You’ve been added to the servers. You can return to Discord now.</p>"

# ================================================================
# SECTION 8 — Panel Bootstrap & Startup
# ================================================================

@bot.event
async def on_ready():
    print(f"✅ Application Bot ready as {bot.user} (ID: {bot.user.id})")

    try:
        # Permanent Application Panel Channel (HQ)
        channel = bot.get_channel(1324115220725108877)  # <-- your permanent panel channel ID

        if channel:
            embed = Embed(
                title="📋 LSRP Network Applications",
                description=(
                    "Welcome to the Los Santos Roleplay Network™ Application Center.\n\n"
                    "Please select the department you wish to apply for using the dropdown menu below.\n\n"
                    "Once selected, you will be guided through the application process in your DMs."
                ),
                color=0x2F3136
            )

            # Attach dropdown view
            view = DepartmentDropdownView()  # Make sure this matches your dropdown class name
            await channel.send(embed=embed, view=view)

    except Exception as e:
        print(f"⚠️ Failed to spawn panel: {e}")


# ================================================================
# RUN
# ================================================================

def _run_web():
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "8080")))

if __name__ == "__main__":
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN is missing.")
    Thread(target=_run_web, daemon=True).start()
    bot.run(BOT_TOKEN)
