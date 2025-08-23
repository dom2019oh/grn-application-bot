# =====================================================
# LSRP Network Application System (Clean) + Web Auth + /auth_grant
# - Panel + DM application flows (PSO/CO/SAFR) — unchanged
# - Q4 is plain text (no buttons)
# - Staff review embed posting — unchanged
# - Role swap at end, PS5 mirroring — unchanged
# - /auth_grant + mini web server to finish join + role/callsign
# =====================================================


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
from flask import Flask, request, redirect, render_template_string
import urllib.parse

# -------------------------
# Core IDs / Guilds / Channels
# -------------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

# Guilds
HQ_GUILD_ID  = int(os.getenv("HQ_GUILD_ID", "1324117813878718474"))
PS4_GUILD_ID = int(os.getenv("PS4_GUILD_ID", "1324117813878718474"))  # same as HQ if panel + main in same guild
PS5_GUILD_ID = int(os.getenv("PS5_GUILD_ID", "1401903156274790441"))
XBOX_OG_GUILD_ID = int(os.getenv("XBOX_OG_GUILD_ID", "1375494043831898334"))

PLATFORM_GUILDS = {
    "PS4":    PS4_GUILD_ID,
    "PS5":    PS5_GUILD_ID,
    "XboxOG": XBOX_OG_GUILD_ID,
}

# Channels
APP_REVIEW_CHANNEL_ID    = 1366431401054048357
APPLICATION_TIPS_CHANNEL = 1370854351828029470
PANEL_CHANNEL_ID         = 1324115220725108877
AUTH_CODE_LOG_CHANNEL    = 1395135616177668186

# Staff role to operate panel/auth
STAFF_CAN_POST_PANEL_ROLE = 1384558588478886022

# Applicant/Pending/Denied roles (HQ)
ROLE_PENDING    = 1323758692918624366
ROLE_DENIED_12H = 1323755533492027474

# Applicant roles (HQ) — dept + platform
APPLICANT_DEPT_ROLES = {
    "PSO":  1370719624051691580,
    "CO":   1323758149009936424,
    "SAFR": 1370719781488955402,
}
APPLICANT_PLATFORM_ROLES = {
    "PS4":    1401961522556698739,
    "PS5":    1401961758502944900,
    "XboxOG": 1401961991756578817,
}

# Accepted (platform) roles — HQ
ACCEPTED_PLATFORM_ROLES = {
    "PS4":    1367753287872286720,
    "PS5":    1367753535839797278,
    "XboxOG": 1367753756367912960,
}

# PSO subdept roles (PS4 & PS5 mirror)
ROLE_SASP_PS4 = 1401347813958226061
ROLE_BCSO_PS4 = 1401347339796348938
ROLE_SASP_PS5 = 1407034121808646269
ROLE_BCSO_PS5 = 1407034123561734245

# Optional PS4 dept structures (starter/category). If you don’t want these, leave 0.
ROLE_PSO_MAIN_PS4     = 1375046521904431124
ROLE_PSO_CATEGORY_PS4 = 1404575562290434190
ROLE_PSO_STARTER_PS4  = 1375046543329202186

ROLE_CO_MAIN_PS4      = 1375046547678429195
ROLE_CO_CATEGORY_PS4  = 1375046548747980830
ROLE_CO_STARTER_PS4   = 1375046566150406155

ROLE_SAFR_MAIN_PS4    = 1401347818873946133
ROLE_SAFR_CATEGORY_PS4= 1375046571653201961
ROLE_SAFR_STARTER_PS4 = 1375046583153856634

# If you have PS5 equivalents, add here; otherwise they can remain 0 (skipped gracefully).
ROLE_PSO_MAIN_PS5     = int(os.getenv("ROLE_PSO_MAIN_PS5", "0"))
ROLE_PSO_CATEGORY_PS5 = int(os.getenv("ROLE_PSO_CATEGORY_PS5", "0"))
ROLE_PSO_STARTER_PS5  = int(os.getenv("ROLE_PSO_STARTER_PS5", "0"))

ROLE_CO_MAIN_PS5      = int(os.getenv("ROLE_CO_MAIN_PS5", "0"))
ROLE_CO_CATEGORY_PS5  = int(os.getenv("ROLE_CO_CATEGORY_PS5", "0"))
ROLE_CO_STARTER_PS5   = int(os.getenv("ROLE_CO_STARTER_PS5", "0"))

ROLE_SAFR_MAIN_PS5    = int(os.getenv("ROLE_SAFR_MAIN_PS5", "0"))
ROLE_SAFR_CATEGORY_PS5= int(os.getenv("ROLE_SAFR_CATEGORY_PS5", "0"))
ROLE_SAFR_STARTER_PS5 = int(os.getenv("ROLE_SAFR_STARTER_PS5", "0"))

# Visuals
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1317589676336611381/1405147584456032276/Sunset_Photography_Tumblr_Banner.png"
ACCEPT_GIF_URL  = "https://cdn.discordapp.com/attachments/1317589676336611381/1402368709783191713/Animated_LSRP.gif"

# OAuth app (use your real app creds)
CLIENT_ID     = os.getenv("CLIENT_ID") or "1397974568706117774"
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or "KcaapGwCEsH_JDlIbrAX3lghSC-tDREN"
REDIRECT_URI  = "https://auth.lsrpnetwork.com/auth"  # fixed

# Timing
APP_TOTAL_TIME_SECONDS = 35 * 60  # 35 minutes
CODE_TTL_SECONDS       = 5 * 60   # 5 minutes

# -------------------------
# Bot
# -------------------------
intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# -------------------------
# In-memory stores
# -------------------------
app_sessions: Dict[int, dict]  = {}  # application progress
pending_codes: Dict[int, dict] = {}  # /auth_grant pending codes

# -------------------------
# Helpers
# -------------------------
def dept_color(dept: str) -> discord.Color:
    if dept == "PSO": return discord.Color.blue()
    if dept == "CO":  return discord.Color.green()
    return discord.Color.red()  # SAFR

def readable_remaining(deadline: float) -> str:
    left = max(0, int(deadline - time.time()))
    m, s = divmod(left, 60)
    return f"{m}m {s}s"

async def report_interaction_error(interaction: discord.Interaction | None, err: Exception, prefix: str):
    print(prefix, "".join(traceback.format_exception(type(err), err, err.__traceback__)))
    try:
        if interaction:
            if interaction.response.is_done():
                await interaction.followup.send("❌ An error occurred. Staff has been notified.", ephemeral=True)
            else:
                await interaction.response.send_message("❌ An error occurred. Staff has been notified.", ephemeral=True)
    except Exception:
        pass
    try:
        ch = bot.get_channel(AUTH_CODE_LOG_CHANNEL)
        if ch:
            await ch.send(f"**{prefix}**\n```\n{repr(err)}\n```")
    except Exception:
        pass

# -------------------------
# Questions (20 each)
# -------------------------
COMMON_4 = [
    ("Q1",  "What's your Discord username?"),
    ("Q2",  "How old are you IRL?"),
    ("Q3",  "What's your Date of Birth IRL?"),
    ("Q4",  "How did you find us? (Instagram / Tiktok / Partnership / Friend / Other)"),
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
# Panel UI
# -------------------------
class SafeView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
    async def on_error(self, error: Exception, item: discord.ui.Item, interaction: discord.Interaction) -> None:
        await report_interaction_error(interaction, error, f"View error in '{getattr(item, 'custom_id', getattr(item, 'label', '?'))}'")

class DepartmentSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Choose your department...",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="Public Safety Office (PSO)", value="PSO", emoji="🚓"),
                discord.SelectOption(label="Civilian Operations (CO)", value="CO", emoji="🧑"),
                discord.SelectOption(label="San Andreas Fire & Rescue (SAFR)", value="SAFR", emoji="🚒"),
            ],
            custom_id="lsrp_app_panel_dept_select"  # persistent
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
            }
            color = dept_color(dept)

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

            # Start questions
            await run_questions(user)
            await interaction.followup.send("📬 I’ve sent you a DM to continue your application.", ephemeral=True)

            # Add pending + applicant dept role in HQ
            if interaction.guild and interaction.guild.id == HQ_GUILD_ID:
                roles_to_add = []
                dept_role_id = APPLICANT_DEPT_ROLES.get(dept)
                if dept_role_id:
                    r = interaction.guild.get_role(dept_role_id)
                    if r:
                        roles_to_add.append(r)
                pending_role = interaction.guild.get_role(ROLE_PENDING)
                if pending_role:
                    roles_to_add.append(pending_role)
                member = interaction.guild.get_member(user.id) or await interaction.guild.fetch_member(user.id)
                if roles_to_add:
                    try:
                        await member.add_roles(*roles_to_add, reason="Application started")
                    except Exception:
                        pass

        except discord.Forbidden:
            if not interaction.response.is_done():
                await interaction.response.send_message("⚠️ I couldn’t DM you. Please enable DMs and select again.", ephemeral=True)
            else:
                await interaction.followup.send("⚠️ I couldn’t DM you. Please enable DMs and select again.", ephemeral=True)
        except Exception as e:
            await report_interaction_error(interaction, e, "DepartmentSelect callback failed")


class ApplicationPanel(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DepartmentSelect())

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
        "> New to RP? That’s fine. Tell us how you plan to grow — everyone starts somewhere and we’re here to support you."
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

# -------------------------
# DM flow (plain text Q4)
# -------------------------
async def run_questions(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess: return
    dept     = sess["dept"]
    questions= DEPT_QUESTIONS[dept]
    deadline = sess["deadline"]
    color    = dept_color(dept)

    dm = await user.create_dm()
    for qkey, qtext in questions:
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

        await dm.send(embed=Embed(title=qkey, description=qtext + f"\n\n_Time remaining: **{readable_remaining(deadline)}**_", color=color))

        def check(m: discord.Message):
            return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

        try:
            remaining = max(1, int(deadline - time.time()))
            timeout = min(remaining, 300)  # max 5 minutes per question
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

    await post_review(user)

# -------------------------
# Application Review System (Accept/Deny with logging)
# -------------------------
DECISION_LOG_CHANNEL = 1408751099581829130  # application-commands channel

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
        )
        await ch.send(embed=embed)

    @discord.ui.button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id="review_accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            # disable buttons
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

            # DM applicant
            try:
                e = Embed(
                    title="🎉 Application Accepted",
                    description=(
                        f"Congratulations! You’ve been **accepted** into {self.dept}.\n\n"
                        "A staff member will issue you a **one-time 6-digit verification code** soon.\n\n"
                        "⚠️ Keep your DMs **open** — the code expires in **5 minutes** once sent."
                    ),
                    color=discord.Color.green()
                )
                e.add_field(
                    name="Next steps",
                    value="• Wait for staff to issue your code.\n• Do not share it.\n• Complete verification for main server access.",
                    inline=False
                )
                e.add_field(
                    name="Expectations",
                    value="• Follow all community regulations and SOPs.\n"
                          "• Be respectful and professional.\n"
                          "• You’ll receive full access after verification.",
                    inline=False
                )
                await self.applicant.send(embed=e)
            except Exception:
                await interaction.followup.send("⚠️ Could not DM the applicant (they may have DMs closed).", ephemeral=True)

            await self._log_decision(interaction.user, "Accepted", discord.Color.green())
            await interaction.followup.send(f"✅ Accepted {self.applicant.mention}", ephemeral=True)

        except Exception as e:
            await report_interaction_error(interaction, e, "Accept button failed")

    @discord.ui.button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="review_deny")
    async def deny(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            await interaction.response.defer(ephemeral=True)

            # disable buttons
            for child in self.children:
                child.disabled = True
            await interaction.message.edit(view=self)

            # DM applicant
            try:
                e = Embed(
                    title="❌ Application Denied",
                    description=(
                        "Unfortunately, your application was **denied**.\n\n"
                        "You may reapply after **12 hours**.\n\n"
                        "Please take time to review the rules before submitting again."
                    ),
                    color=discord.Color.red()
                )
                await self.applicant.send(embed=e)
            except Exception:
                await interaction.followup.send("⚠️ Could not DM the applicant (they may have DMs closed).", ephemeral=True)

            await self._log_decision(interaction.user, "Denied", discord.Color.red())
            await interaction.followup.send(f"❌ Denied {self.applicant.mention}", ephemeral=True)

        except Exception as e:
            await report_interaction_error(interaction, e, "Deny button failed")


# -------------------------
# Review post (embed + buttons)
# -------------------------
async def post_review(user: discord.User):
    sess = app_sessions.get(user.id)
    if not sess:
        return

    dept  = sess.get("dept", "N/A")
    color = dept_color(dept)

    review = Embed(
        title="📂 New Application Submitted",
        color=color,
        description=f"**Applicant:** {user.mention} (`{user.id}`)\n**Department:** {dept}\n"
    )
    for idx, (q, a) in enumerate(sess.get("answers", []), start=1):
        name = f"Q{idx}: {q}"
        if len(name) > 256:
            name = name[:253] + "…"
        review.add_field(name=name, value=a[:1000] if a else "—", inline=False)

    ch = bot.get_channel(APP_REVIEW_CHANNEL_ID)
    if ch:
        await ch.send(embed=review, view=ReviewButtons(user, dept))

    try:
        # Applicant only gets submission notice here
        e = Embed(
            title="📋 Application Status",
            description="✅ Application Submitted\n\nYour application has been delivered to staff for review.\nYou’ll receive a DM once a decision is made.",
            color=color
        )
        await user.send(embed=e)
    except Exception:
        pass

    # clear session
    app_sessions.pop(user.id, None)

# -------------------------
# Role Swap + PS5 mirroring (called after OAuth success)
# -------------------------
async def assign_ps_roles_ps4(member: discord.Member, dept: str, subdept: str | None):
    to_add = []

    if dept == "PSO":
        for rid in (ROLE_PSO_MAIN_PS4, ROLE_PSO_CATEGORY_PS4, ROLE_PSO_STARTER_PS4):
            r = member.guild.get_role(rid)
            if r: to_add.append(r)
        if (subdept or "").upper() == "SASP":
            r = member.guild.get_role(ROLE_SASP_PS4)
            if r: to_add.append(r)
        elif (subdept or "").upper() == "BCSO":
            r = member.guild.get_role(ROLE_BCSO_PS4)
            if r: to_add.append(r)

        # starter callsign
        try:
            cs = f"C-{random.randint(1000,1999)} | {member.name}"
            await member.edit(nick=cs, reason="Initial PSO callsign")
        except Exception:
            pass

    elif dept == "CO":
        for rid in (ROLE_CO_MAIN_PS4, ROLE_CO_CATEGORY_PS4, ROLE_CO_STARTER_PS4):
            r = member.guild.get_role(rid)
            if r: to_add.append(r)
        try:
            cs = f"CIV-{random.randint(1000,1999)} | {member.name}"
            await member.edit(nick=cs, reason="Initial CO callsign")
        except Exception:
            pass

    elif dept == "SAFR":
        for rid in (ROLE_SAFR_MAIN_PS4, ROLE_SAFR_CATEGORY_PS4, ROLE_SAFR_STARTER_PS4):
            r = member.guild.get_role(rid)
            if r: to_add.append(r)
        try:
            cs = f"FF-{random.randint(100,999)} | {member.name}"
            await member.edit(nick=cs, reason="Initial SAFR callsign")
        except Exception:
            pass

    if to_add:
        try: await member.add_roles(*to_add, reason="Initial dept roles (PS4)")
        except Exception: pass

async def assign_ps_roles_ps5(member: discord.Member, dept: str, subdept: str | None):
    to_add = []

    if dept == "PSO":
        for rid in (ROLE_PSO_MAIN_PS5, ROLE_PSO_CATEGORY_PS5, ROLE_PSO_STARTER_PS5):
            if rid:
                r = member.guild.get_role(rid)
                if r: to_add.append(r)
        if (subdept or "").upper() == "SASP":
            r = member.guild.get_role(ROLE_SASP_PS5)
            if r: to_add.append(r)
        elif (subdept or "").upper() == "BCSO":
            r = member.guild.get_role(ROLE_BCSO_PS5)
            if r: to_add.append(r)
        try:
            cs = f"C-{random.randint(1000,1999)} | {member.name}"
            await member.edit(nick=cs, reason="Initial PSO callsign (PS5)")
        except Exception:
            pass

    elif dept == "CO":
        for rid in (ROLE_CO_MAIN_PS5, ROLE_CO_CATEGORY_PS5, ROLE_CO_STARTER_PS5):
            if rid:
                r = member.guild.get_role(rid)
                if r: to_add.append(r)
        try:
            cs = f"CIV-{random.randint(1000,1999)} | {member.name}"
            await member.edit(nick=cs, reason="Initial CO callsign (PS5)")
        except Exception:
            pass

    elif dept == "SAFR":
        for rid in (ROLE_SAFR_MAIN_PS5, ROLE_SAFR_CATEGORY_PS5, ROLE_SAFR_STARTER_PS5):
            if rid:
                r = member.guild.get_role(rid)
                if r: to_add.append(r)
        try:
            cs = f"FF-{random.randint(100,999)} | {member.name}"
            await member.edit(nick=cs, reason="Initial SAFR callsign (PS5)")
        except Exception:
            pass

    if to_add:
        try: await member.add_roles(*to_add, reason="Initial dept roles (PS5)")
        except Exception: pass

# -------------------------
# /auth_grant — generate 6-digit + DM link
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

        # Log to HQ
        hq = bot.get_guild(HQ_GUILD_ID)
        log_ch = hq.get_channel(AUTH_CODE_LOG_CHANNEL) if hq else None
        if log_ch:
            await log_ch.send(
                f"🔐 **Auth Code Generated**\n"
                f"User: {user.mention} (`{user.id}`)\n"
                f"Department: `{department.value}` | Platform: `{platform.value}` | Subdept: `{pending_codes[user.id]['subdept']}`\n"
                f"Code: **{code}** (expires in 5 minutes)\n"
                f"Granted by: {interaction.user.mention}"
            )

        # DM applicant (code + link button)
        try:
            e = Embed(
                title="🔐 Los Santos Roleplay Network™® — Authorization",
                description=(
                    f"**Your one-time 6-digit code:** `{code}`\n"
                    f"**Once used in the authorization link, it will no longer be valid.**\n\n"
                    f"[Main Server Verification Link]({REDIRECT_URI})"
                ),
                color=dept_color(department.value),
            )
            e.set_image(url=ACCEPT_GIF_URL)
            v = SafeView()
            v.add_item(discord.ui.Button(label="Open Verification", url=REDIRECT_URI, style=discord.ButtonStyle.link))
            await user.send(embed=e, view=v)
        except Exception:
            pass

        await interaction.followup.send(f"✅ Code sent to {user.mention}'s DMs.", ephemeral=True)
    except Exception as e:
        await report_interaction_error(interaction, e, "auth_grant failed")

# -------------------------
# Web server (OAuth + code pin)
# -------------------------
flask_app = Flask(__name__)

@flask_app.route("/")
def health():
    return "✅ LSRP Application/Auth service running."

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

    # Exchange token
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

    pdata = pending_codes.get(user_id)
    if not pdata:
        return "No active authorization found. Ask staff to run /auth_grant again.", 400

    if time.time() - float(pdata["timestamp"]) > CODE_TTL_SECONDS:
        pending_codes.pop(user_id, None)
        return "Your code expired. Ask staff to generate a new one.", 400
    if pin != str(pdata["code"]):
        return "Invalid code. Please go back and try again.", 400

    # Join target guild
    platform = pdata["platform"]
    target_guild_id = PLATFORM_GUILDS.get(platform)
    if not target_guild_id:
        return "Platform guild not configured.", 500

    put_resp = requests.put(
        f"https://discord.com/api/guilds/{target_guild_id}/members/{user_id}",
        headers={"Authorization": f"Bot {BOT_TOKEN}", "Content-Type": "application/json"},
        json={"access_token": access_token},
        timeout=15
    )
    if put_resp.status_code not in (200, 201, 204):
        # ignore 400 already a member
        if not (put_resp.status_code == 400 and "already" in put_resp.text.lower()):
            return f"Guild join failed: {put_resp.status_code} {put_resp.text}", 400

    # Post-join role/callsign (PS4/PS5 mirrored), remove pending, grant accepted, etc.
    try:
        loop = bot.loop

        async def _apply():
            # find guild & member
            g = bot.get_guild(target_guild_id)
            if not g:
                return
            try:
                m = g.get_member(user_id) or await g.fetch_member(user_id)
            except Exception:
                m = g.get_member(user_id)
            if not m:
                return

            dept    = pdata["dept"]
            subdept = pdata.get("subdept", "N/A")

            # Remove pending in HQ (if present) and add accepted platform role there
            hq = bot.get_guild(HQ_GUILD_ID)
            if hq:
                try:
                    hm = hq.get_member(user_id) or await hq.fetch_member(user_id)
                except Exception:
                    hm = hq.get_member(user_id)
                if hm:
                    # remove pending
                    pending = hq.get_role(ROLE_PENDING)
                    if pending and pending in hm.roles:
                        try: await hm.remove_roles(pending, reason="Application resolved")
                        except Exception: pass
                    # add accepted platform role (HQ)
                    acc = hq.get_role(ACCEPTED_PLATFORM_ROLES.get(platform))
                    if acc and acc not in hm.roles:
                        try: await hm.add_roles(acc, reason="Accepted")
                        except Exception: pass

            # PS subdept + starter roles
            if target_guild_id == PS4_GUILD_ID:
                await assign_ps_roles_ps4(m, dept, subdept)
            elif target_guild_id == PS5_GUILD_ID:
                await assign_ps_roles_ps5(m, dept, subdept)

        fut = asyncio.run_coroutine_threadsafe(_apply(), loop)
        fut.result(timeout=15)

    except Exception as e:
        print("apply roles error:", e)

    # Log success
    try:
        hq = bot.get_guild(HQ_GUILD_ID)
        log_ch = hq.get_channel(AUTH_CODE_LOG_CHANNEL) if hq else None
        if log_ch:
            log_ch.send(f"✅ **Auth success** for <@{user_id}> | Dept `{pdata['dept']}` | Subdept `{pdata.get('subdept','N/A')}` | Platform `{pdata['platform']}` | Code `{pdata['code']}`")
    except Exception:
        pass

    pending_codes.pop(user_id, None)
    return "✅ Success! You can close this tab and return to Discord."

def run_web():
    port = int(os.environ.get("PORT", "8080"))
    flask_app.run(host="0.0.0.0", port=port)

# -------------------------
# Startup
# -------------------------
@bot.event
async def on_ready():
    try:
        # Register the persistent view so the dropdown works after restart
        bot.add_view(ApplicationPanel())

        # Small delay to let cache warm up
        await asyncio.sleep(2)

        # Always try to post a fresh panel
        hq = bot.get_guild(HQ_GUILD_ID)
        if not hq:
            print(f"[panel] HQ guild {HQ_GUILD_ID} not found or bot not in it.")
            return

        ch = hq.get_channel(PANEL_CHANNEL_ID)
        if not isinstance(ch, discord.TextChannel):
            print(f"[panel] Channel {PANEL_CHANNEL_ID} not found or not a text channel.")
            return

        await post_panel(ch)
        print(f"✅ Posted application panel in #{ch.name}")

    except Exception as e:
        print(f"[panel] Failed to post: {e}")

    print(f"🟢 Bot ready as {bot.user}")

# -------------------------
# Run
# -------------------------
if __name__ == "__main__":
    threading.Thread(target=run_web, daemon=True).start()
    bot.run(BOT_TOKEN)
