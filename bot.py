# =========================
# LSRP Network System™®  — Application Core + Auth (PS4 + PS5)
# Focus: Original permanent panel layout + Dropdown flow + 20 Q per dept
# Review: Accept/Deny buttons (disable after click) + logs
# Auth: /auth_grant (UNCHANGED) + Flask OAuth on https://auth.lsrpnetwork.com/auth
# Commands kept: /auth_grant, /ping, /version   (nothing else)
# =========================

# ---- Imports ----
import os
import sys
import time
import random
import threading
import asyncio
from typing import Dict, List, Tuple

import logging
import urllib.parse
import traceback
import requests

import discord
from discord import app_commands, Embed, Object
from discord.ext import commands, tasks
from discord.ui import View, Button, Select

from flask import Flask, request, redirect, render_template_string

# =========================
# LOGGING
# =========================
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

# =========================
# ENV / CONSTANTS
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is not set")

OWNER_ID = 1176071547476262986

# ---- OAuth (UNCHANGED flow; custom domain) ----
CLIENT_ID = os.getenv("CLIENT_ID") or "1397974568706117774"
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or "KcaapGwCEsH_JDlIbrAX3lghSC-tDREN"
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://auth.lsrpnetwork.com/auth")  # << custom domain

# ---- Guilds ----
HQ_GUILD_ID      = int(os.getenv("HQ_GUILD_ID", "1294319617539575808"))  # HQ where panel & review live
PS4_GUILD_ID     = int(os.getenv("PS4_GUILD_ID", "1324117813878718474"))
PS5_GUILD_ID     = int(os.getenv("PS5_GUILD_ID", "1401903156274790441"))
# Only PS4 + PS5 active now
PLATFORM_GUILDS = {
    "PS4": PS4_GUILD_ID,
    "PS5": PS5_GUILD_ID,
}

# ---- Channels / Review / Panel ----
PANEL_CHANNEL_ID         = 1324115220725108877   # permanent panel (autopost on ready)
APP_REVIEW_CHANNEL_ID    = 1366431401054048357   # review channel
AUTH_CODE_LOG_CHANNEL    = 1395135616177668186   # auth logs
APPLICATION_TIPS_CHANNEL = 1370854351828029470   # used in the panel copy

# ---- Staff role to accept/deny/post panel/etc ----
STAFF_CAN_POST_PANEL_ROLE = 1384558588478886022

# ---- Status roles in HQ ----
ROLE_DENIED_12H = 1323755533492027474
ROLE_PENDING    = 1323758692918624366

# ---- HQ applicant roles (upon starting app in HQ) ----
APPLICANT_PLATFORM_ROLES = {
    "PS4": 1401961522556698739,
    "PS5": 1401961758502944900,
}
APPLICANT_DEPT_ROLES = {
    "PSO":  1370719624051691580,
    "CO":   1323758149009936424,
    "SAFR": 1370719781488955402,
}

# ---- Accepted roles (HQ) by platform ----
ACCEPTED_PLATFORM_ROLES = {
    "PS4": 1367753287872286720,
    "PS5": 1367753535839797278,
}

# ---- Global membership swap (HQ + platform guilds) ----
OFFICIAL_MEMBER_ROLE = 1323753774157664347
VERIFIED_MEMBER_ROLE = 1294322438733168723

# ---- Platform applicant/accepted (platform guild swaps) ----
PLATFORM_APPLICANT_ROLES = {
    "PS4": 1401961522556698739,
    "PS5": 1401961758502944900,
}
PLATFORM_ACCEPTED_ROLES = {
    "PS4": 1367753287872286720,
    "PS5": 1367753535839797278,
}

# ---- PS4 department starter roles (auto-assign on OAuth) ----
ROLE_PSO_MAIN_PS4      = 1375046521904431124
ROLE_SASP_PS4          = 1401347813958226061
ROLE_BCSO_PS4          = 1401347339796348938
ROLE_PSO_CATEGORY_PS4  = 1404575562290434190
ROLE_BCSO_CATEGORY_PS4 = 1375046520469979256
ROLE_PSO_STARTER_PS4   = 1375046543329202186
ROLE_CO_MAIN_PS4       = 1375046547678429195
ROLE_CO_CATEGORY_PS4   = 1375046548747980830
ROLE_CO_STARTER_PS4    = 1375046566150406155
ROLE_SAFR_MAIN_PS4     = 1401347818873946133
ROLE_SAFR_CATEGORY_PS4 = 1375046571653201961
ROLE_SAFR_STARTER_PS4  = 1375046583153856634

# ---- PS5 department starter packages (per your mapping) ----
PS5_ROLE_PACKAGES = {
    # PSO → SASP
    ("PSO", "SASP"): [
        1407034074190708816,  # Cadet
        1407034121808646269,  # SASP
        1407034126510325907,  # PSO Main
        1407034075532886172,  # ▬ State Police Rank(s) ▬
    ],
    # PSO → BCSO
    ("PSO", "BCSO"): [
        1407034085917986999,  # Cadet
        1407034123561734245,  # BCSO
        1407034126510325907,  # PSO Main
        1407034075532886172,  # Public Safety Rank(s)
    ],
    # CO
    ("CO", "N/A"): [
        1407034103978655757,  # Probationary Civilian
        1407034124648317079,  # CO
        1407034105345872023,  # ▬ Civilian Operations Rank(s) ▬
    ],
    # SAFR
    ("SAFR", "N/A"): [
        1407034114082738178,  # Probationary Firefighter
        1407034125713408053,  # SAFR
        1407034115311669409,  # ▬ Fire/EMS Rank(s) ▬
    ],
}

# ---- Timing ----
APP_TOTAL_TIME_SECONDS = 35 * 60
CODE_TTL_SECONDS       = 5 * 60

# ---- Panel imagery (matches your screenshot layout copy) ----
PANEL_IMAGE_URL = "https://cdn.discordapp.com/attachments/1317589676336611381/1405147584456032276/Sunset_Photography_Tumblr_Banner.png"
ACCEPT_GIF_URL  = "https://cdn.discordapp.com/attachments/1317589676336611381/1402368709783191713/Animated_LSRP.gif"

# =========================
# DISCORD BOT SETUP
# =========================
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# =========================
# IN-MEMORY STORES
# =========================
app_sessions: Dict[int, dict] = {}   # user_id -> {dept, subdept, platform, started_at, deadline, answers: [(q,a),...] }
pending_codes: Dict[int, dict] = {}  # user_id -> {code, timestamp, dept, platform, subdept}

# =========================
# HELPERS
# =========================
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
    logging.error("%s:\n%s", prefix, "".join(traceback.format_exception(type(err), err, err.__traceback__)))
    try:
        if interaction.response.is_done():
            await interaction.followup.send("❌ An error occurred. Staff has been notified.", ephemeral=True)
        else:
            await interaction.response.send_message("❌ An error occurred. Staff has been notified.", ephemeral=True)
    except Exception:
        pass
    try:
        owner = bot.get_user(OWNER_ID) or await bot.fetch_user(OWNER_ID)
        await owner.send(f"**{prefix}** in **{getattr(interaction.guild, 'name', 'DM')}**\n```\n{repr(err)}\n```")
    except Exception:
        pass
    try:
        ch = bot.get_channel(AUTH_CODE_LOG_CHANNEL)
        if ch:
            await ch.send(f"**{prefix}**\n```\n{''.join(traceback.format_exception(type(err), err, err.__traceback__))[:1900]}\n```")
    except Exception:
        pass

async def _try_swap_roles(member: discord.Member, remove_ids: List[int], add_ids: List[int], reason: str):
    if not member or not member.guild:
        return
    to_remove = [member.guild.get_role(rid) for rid in remove_ids if rid]
    to_add    = [member.guild.get_role(rid) for rid in add_ids if rid]
    to_remove = [r for r in to_remove if r]
    to_add    = [r for r in to_add if r]
    try:
        if to_remove:
            await member.remove_roles(*to_remove, reason=reason)
        if to_add:
            await member.add_roles(*to_add, reason=reason)
    except Exception:
        pass

async def apply_accept_swaps_and_packages(user_id: int, platform: str, dept: str, subdept: str):
    """
    Perform:
      - HQ: Verified->Official, remove Pending, HQ Applicant->Accepted.
      - Platform guild: Verified->Official, Platform Applicant->Accepted.
      - PS5: add starter package roles for dept/subdept (per mapping).
    """
    # HQ
    try:
        hq = bot.get_guild(HQ_GUILD_ID)
        if hq:
            m = hq.get_member(user_id) or await hq.fetch_member(user_id)
            if m:
                await _try_swap_roles(
                    m,
                    remove_ids=[VERIFIED_MEMBER_ROLE, ROLE_PENDING, PLATFORM_APPLICANT_ROLES.get(platform, 0)],
                    add_ids=[OFFICIAL_MEMBER_ROLE, PLATFORM_ACCEPTED_ROLES.get(platform, 0)],
                    reason=f"Application accepted ({platform}) [HQ]"
                )
    except Exception:
        pass

    # Platform guild
    try:
        pgid = PLATFORM_GUILDS.get(platform)
        if pgid:
            g = bot.get_guild(pgid)
            if g:
                m = g.get_member(user_id) or await g.fetch_member(user_id)
                if m:
                    await _try_swap_roles(
                        m,
                        remove_ids=[VERIFIED_MEMBER_ROLE, PLATFORM_APPLICANT_ROLES.get(platform, 0)],
                        add_ids=[OFFICIAL_MEMBER_ROLE, PLATFORM_ACCEPTED_ROLES.get(platform, 0)],
                        reason=f"Application accepted ({platform}) [Platform]"
                    )
                    # PS5 starter package assignment
                    if g.id == PS5_GUILD_ID:
                        package = None
                        if dept == "PSO" and subdept in ("SASP", "BCSO"):
                            package = PS5_ROLE_PACKAGES.get(("PSO", subdept))
                        elif dept in ("CO", "SAFR"):
                            package = PS5_ROLE_PACKAGES.get((dept, "N/A"))
                        if package:
                            roles = [g.get_role(rid) for rid in package]
                            roles = [r for r in roles if r]
                            try:
                                await m.add_roles(*roles, reason=f"Initial {dept} package ({subdept})")
                            except Exception:
                                pass
    except Exception:
        pass

def acceptance_embed(staffer: discord.Member, platform: str, user: discord.User, dept: str, subdept: str) -> Embed:
    ts = int(time.time())
    ht_link = f"https://hammertime.cyou/en?date={ts}"
    desc = (
        f"**Application Accepted by {staffer.mention}.**\n"
        f"**Date and Time:** <t:{ts}:F>  |  [Hammertime]({ht_link})\n"
        f"**Platform:** {platform}\n"
        f"**Applicant User ID:** `{user.id}`\n"
        f"**Applicant Username:** `{user.name}#{user.discriminator}`\n"
        f"**Department:** {dept}\n"
        f"**Sub Department:** {('N/A' if dept in ('CO','SAFR') else subdept)}"
    )
    e = Embed(title="✅ Application Accepted", description=desc, color=discord.Color.green())
    e.set_footer(text="Los Santos Roleplay Network™®")
    return e

# =========================
# QUESTIONS (4 common are inside each department's 20)
# =========================
PSO_20 = [
    ("Q1",  "What's your Discord username?"),
    ("Q2",  "How old are you IRL?"),
    ("Q3",  "What's your Date of Birth IRL?"),
    ("Q4",  "How did you find us? (Instagram / Tiktok / Partnership / Friend / Other)"),
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
CO_20 = [
    ("Q1",  "What's your Discord username?"),
    ("Q2",  "How old are you IRL?"),
    ("Q3",  "What's your Date of Birth IRL?"),
    ("Q4",  "How did you find us? (Instagram / Tiktok / Partnership / Friend / Other)"),
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
SAFR_20 = [
    ("Q1",  "What's your Discord username?"),
    ("Q2",  "How old are you IRL?"),
    ("Q3",  "What's your Date of Birth IRL?"),
    ("Q4",  "How did you find us? (Instagram / Tiktok / Partnership / Friend / Other)"),
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
DEPT_QUESTIONS = {"PSO": PSO_20, "CO": CO_20, "SAFR": SAFR_20}

# =========================
# PANEL & DM APPLICATION FLOW (continued)
# =========================

class SafeView(View):
    def __init__(self, *args, **kwargs):
        super().__init__(timeout=None)

# ---- Permanent Panel ----
async def post_permanent_panel():
    ch = bot.get_channel(PANEL_CHANNEL_ID)
    if not ch:
        return

    embed = Embed(
        title="📋 Los Santos Roleplay™® — Department Applications",
        description=(
            "Welcome to the official **Application Panel** for joining departments within **Los Santos Roleplay Network™®**.\n\n"
            "Please select your department from the dropdown menu below to begin your application. "
            "Once selected, you’ll receive the application in **your DMs**. You have **35 minutes** to complete it.\n\n"
            f"For more information, visit <#{APPLICATION_TIPS_CHANNEL}>."
        ),
        color=discord.Color.blurple()
    )
    embed.set_image(url=PANEL_IMAGE_URL)
    embed.set_footer(text="Los Santos Roleplay Network™® • Applications System")

    view = SafeView()
    select = Select(
        placeholder="Select a Department to Apply...",
        options=[
            discord.SelectOption(label="Public Safety Office (PSO)", value="PSO", description="Police - BCSO or SASP"),
            discord.SelectOption(label="Civilian Operations (CO)", value="CO", description="Civilian roleplay department"),
            discord.SelectOption(label="San Andreas Fire Rescue (SAFR)", value="SAFR", description="Fire/EMS department"),
        ]
    )

    async def select_callback(interaction: discord.Interaction):
        dept = select.values[0]
        app_sessions[interaction.user.id] = {
            "dept": dept,
            "subdept": None,
            "platform": None,
            "answers": [],
            "started_at": time.time(),
            "deadline": time.time() + APP_TOTAL_TIME_SECONDS,
        }
        await interaction.response.send_message(
            f"📩 Please check your DMs — your **{dept} application** has begun.",
            ephemeral=True
        )
        try:
            dm = await interaction.user.create_dm()
            if dept == "PSO":
                await dm.send(embed=Embed(
                    title="🚔 Public Safety Office Application",
                    description="Please select your sub-department:\n• SASP\n• BCSO",
                    color=dept_color(dept)
                ))
            else:
                await dm.send(embed=Embed(
                    title=f"{dept} Application Started",
                    description="Your application will now begin. Please answer the questions one by one.",
                    color=dept_color(dept)
                ))
            await start_application(interaction.user, dept)
        except Exception:
            pass

    select.callback = select_callback
    view.add_item(select)

    # Prevent duplicate panel posting
    async for msg in ch.history(limit=20):
        if msg.author == bot.user and msg.embeds and "Department Applications" in msg.embeds[0].title:
            return
    await ch.send(embed=embed, view=view)

# ---- Application Logic ----
async def start_application(user: discord.User, dept: str):
    qs = DEPT_QUESTIONS[dept]
    dm = await user.create_dm()

    for qid, qtext in qs:
        if user.id not in app_sessions:
            break
        s = app_sessions[user.id]
        if time.time() > s["deadline"]:
            await dm.send("⏰ Time expired. Please reapply through the panel.")
            del app_sessions[user.id]
            return
        await dm.send(embed=Embed(
            title=f"{dept} Application — {qid}",
            description=qtext,
            color=dept_color(dept)
        ))

        try:
            msg = await bot.wait_for(
                "message",
                timeout=APP_TOTAL_TIME_SECONDS,
                check=lambda m: m.author.id == user.id and isinstance(m.channel, discord.DMChannel)
            )
        except asyncio.TimeoutError:
            await dm.send("⏰ Time expired. Please reapply through the panel.")
            del app_sessions[user.id]
            return
        s["answers"].append((qid, msg.content))

    await dm.send("✅ Your application has been submitted! Staff will review it shortly.")
    await forward_application_to_staff(user, dept, s["answers"])

async def forward_application_to_staff(user: discord.User, dept: str, answers: List[Tuple[str, str]]):
    ch = bot.get_channel(APP_REVIEW_CHANNEL_ID)
    if not ch:
        return
    desc = "\n".join([f"**{qid}**: {ans}" for qid, ans in answers])
    e = Embed(
        title=f"📥 {dept} Application — {user.name}#{user.discriminator}",
        description=desc,
        color=dept_color(dept)
    )
    e.set_footer(text=f"User ID: {user.id}")

    view = SafeView()
    accept = Button(label="Accept", style=discord.ButtonStyle.success)
    deny = Button(label="Deny", style=discord.ButtonStyle.danger)

    async def accept_cb(inter: discord.Interaction):
        if inter.user.guild_permissions.manage_roles:
            await inter.response.send_message("✅ Accepted.", ephemeral=True)
            for item in view.children: item.disabled = True
            await inter.message.edit(view=view)
            await handle_accept(user, dept, inter.user)
        else:
            await inter.response.send_message("❌ You cannot accept applications.", ephemeral=True)

    async def deny_cb(inter: discord.Interaction):
        if inter.user.guild_permissions.manage_roles:
            await inter.response.send_message("❌ Denied.", ephemeral=True)
            for item in view.children: item.disabled = True
            await inter.message.edit(view=view)
            await handle_deny(user, dept, inter.user)
        else:
            await inter.response.send_message("❌ You cannot deny applications.", ephemeral=True)

    accept.callback = accept_cb
    deny.callback = deny_cb
    view.add_item(accept)
    view.add_item(deny)

    await ch.send(embed=e, view=view)

async def handle_accept(user: discord.User, dept: str, staffer: discord.Member):
    embed = acceptance_embed(staffer, "PS4/PS5", user, dept, "Auto")
    ch = bot.get_channel(APP_REVIEW_CHANNEL_ID)
    if ch:
        await ch.send(embed=embed)

    try:
        dm = await user.create_dm()
        e = Embed(
            title="🎉 Congratulations!",
            description="You have been **ACCEPTED** into Los Santos Roleplay Network™®.\n\n"
                        "Join the main server with the invite link below to finalize your membership.",
            color=discord.Color.green()
        )
        e.set_image(url=ACCEPT_GIF_URL)
        await dm.send(embed=e)
    except Exception:
        pass

    await apply_accept_swaps_and_packages(user.id, "PS4", dept, "N/A")

async def handle_deny(user: discord.User, dept: str, staffer: discord.Member):
    ch = bot.get_channel(APP_REVIEW_CHANNEL_ID)
    if ch:
        e = Embed(
            title="❌ Application Denied",
            description=f"{user.mention} denied by {staffer.mention}.",
            color=discord.Color.red()
        )
        await ch.send(embed=e)
    try:
        dm = await user.create_dm()
        await dm.send("Unfortunately your application was **denied**. You may reapply in 12 hours.")
    except Exception:
        pass

# =========================
# /auth_grant COMMAND
# =========================
@tree.command(name="auth_grant", description="Generate OAuth link for applicant.")
async def auth_grant(interaction: discord.Interaction, user: discord.Member):
    code = random.randint(100000, 999999)
    pending_codes[user.id] = {
        "code": code,
        "timestamp": time.time(),
        "dept": "PSO",
        "platform": "PS4",
        "subdept": "N/A",
    }
    oauth_url = (
        f"https://discord.com/api/oauth2/authorize?"
        f"client_id={CLIENT_ID}&redirect_uri={urllib.parse.quote_plus(REDIRECT_URI)}&"
        f"response_type=code&scope=identify%20guilds.join"
    )
    await interaction.response.send_message(
        f"✅ Auth link for {user.mention}:\n{oauth_url}\n\n6-digit code: **{code}**",
        ephemeral=True
    )
    ch = bot.get_channel(AUTH_CODE_LOG_CHANNEL)
    if ch:
        await ch.send(f"Auth code `{code}` generated for {user.mention} ({user.id})")

# =========================
# /ping + /version
# =========================
@tree.command(name="ping", description="Check bot latency.")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message(f"Pong! {round(bot.latency*1000)}ms")

@tree.command(name="version", description="Show bot version.")
async def version(interaction: discord.Interaction):
    await interaction.response.send_message("LSRP Network System™® v1.0 — Auth + Applications")

# =========================
# FLASK WEB SERVER (OAuth)
# =========================
app = Flask(__name__)

@app.route("/auth")
def auth():
    code = request.args.get("code")
    if not code:
        return "Missing code", 400
    return "✅ Auth success. You may close this tab."

def run_flask():
    app.run(host="0.0.0.0", port=8080)

# =========================
# BOT EVENTS
# =========================
@bot.event
async def on_ready():
    await tree.sync()
    await post_permanent_panel()
    print(f"✅ Bot is online as {bot.user} and panel ensured in {PANEL_CHANNEL_ID}")

# =========================
# MAIN START
# =========================
if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    bot.run(BOT_TOKEN)

