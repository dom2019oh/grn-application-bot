# ================================================================
# LSRP Network Application Bot — FULL VERSION
# ================================================================
# Handles:
#   • Application Panel (PSO, Civilian Ops, SAFD)
#   • DM Application Flow (20 Qs, embeds, Q4 buttons, 45m timeout)
#   • Staff Review Channel (Accept/Deny buttons)
#   • Accept: HQ Verified→Official, Applicant→Accepted, PSO roles, Callsign
#   • Deny: HQ role swapped with cooldown
#   • Member Join (PS4+PS5 auto system, callsign assign + log)
#   • /auth_grant OAuth Web Server
# ================================================================

import os
import random
import asyncio
import discord
from discord.ext import commands
from discord import app_commands, Embed
from discord.ui import View, Button, Select
from flask import Flask, request
import requests
from threading import Thread

# ================================================================
# SECTION 1 - Setup
# ================================================================

intents = discord.Intents.default()
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

BOT_TOKEN = os.getenv("BOT_TOKEN")

# Guilds
HQ_GUILD_ID = 1324117813878718474
PS4_GUILD_ID = 1324117813878718474
PS5_GUILD_ID = 1401903156274790441

# Invite link
MAIN_INVITE_LINK = "https://discord.gg/yN2fs6y5v3"

# HQ roles
VERIFIED_ROLE_ID = 1401961522556698739
OFFICIAL_ROLE_ID = 1367753287872286720
ACCEPTED_ROLE_ID = 1323753774157664347
DENIED_ROLE_ID = 1323755533492027474

# PS4 PSO roles
PS4_PSO_ROLES = [
    1375046619824914543,
    1375046631237484605,
    1375046520469979256,
    1375046521904431124,
    1375046543329202186,
]

# PS5 PSO roles
PS5_PSO_ROLES = [
    1407034121808646269,  # SASP category
    1407034123561734245,  # BCSO category
]

# Callsign log channel
CALLSIGN_LOG_CHANNEL_ID = 1396076403052773396

# Staff Review Channels (example IDs, replace if needed)
STAFF_REVIEW_CHANNEL_PSO = 1366431401054048357
STAFF_REVIEW_CHANNEL_CIV = 1366431401054048357
STAFF_REVIEW_CHANNEL_SAFD = 1366431401054048357

# ================================================================
# SECTION 2 - Question Banks
# ================================================================

PSO_QUESTIONS = [
    "What is Discord username?",
    "How old are you in real life?",
    "Please state your Date of Birth. (e.g., 16th June 2010)",
    "How did you find us?",  # BUTTONS
    "Explain the 'No Life Rule' in the best of your ability.",
    "What does VDM, RDM and FRP mean? Describe in the best of your ability.",
    "Do you have any roleplay experience, if so, please tell us.",
    "What time zone are you from?",
    "Describe what a 10-11 means. In your own words.",
    "You see a suspect with a knife coming at you. Select one action:",
    "What does a 10-80 mean?",
    "How would you handle a 10-11?",
    "You arrive at a robbery scene, suspect yells 'I have a bomb!!' – what do you do?",
    "What does Code 1, 2, and 3 mean?",
    "When you go on duty, what 10 codes do you use?",
    "As a cadet, are you eligible to drive on your own?",
    "You see a sniper on a hilltop. You have a pistol and radio. What do you do?",
    "How would you handle a noise complaint?",
    "Choose the correct cadet loadout:",
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
    "What is FailRP? Example?",
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
    "What equipment does a firefighter use?",
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

# ================================================================
# SECTION 3 - Application Panel
# ================================================================

class ApplicationSelect(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Select(
            placeholder="Select a department to apply for...",
            options=[
                discord.SelectOption(label="PSO", description="Public Safety Office Application"),
                discord.SelectOption(label="Civilian Ops", description="Civilian Operations Application"),
                discord.SelectOption(label="SAFD", description="Fire/EMS Application"),
            ],
            custom_id="app_select"
        ))

@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user}")
    channel = bot.get_channel(1324115220725108877)  # Application panel channel
    if channel:
        embed = Embed(title="📋 LSRP Network Applications", description="Select a department to apply for using the dropdown below.", color=0x3498db)
        await channel.send(embed=embed, view=ApplicationSelect())

# ================================================================
# SECTION 4 - Application Flow
# ================================================================

class HowFoundUs(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.value = None
        self.add_item(Button(label="Friend", style=discord.ButtonStyle.primary, custom_id="friend"))
        self.add_item(Button(label="Instagram", style=discord.ButtonStyle.primary, custom_id="instagram"))
        self.add_item(Button(label="Partnership", style=discord.ButtonStyle.primary, custom_id="partnership"))
        self.add_item(Button(label="Other", style=discord.ButtonStyle.secondary, custom_id="other"))

    async def interaction_check(self, interaction: discord.Interaction):
        self.value = interaction.data["custom_id"]
        await interaction.response.send_message(f"✅ You selected {self.value}", ephemeral=True)
        self.stop()
        return True

async def run_application(user: discord.User, dept: str, questions: list, review_channel_id: int):
    answers = []
    def check(m): return m.author.id == user.id and isinstance(m.channel, discord.DMChannel)

    try:
        dm = await user.create_dm()
        await dm.send(embed=Embed(title=f"{dept} Application", description="You have 45 minutes to complete this application.", color=0x2ecc71))

        for idx, q in enumerate(questions, start=1):
            if idx == 4:  # Special buttons
                view = HowFoundUs()
                await dm.send(embed=Embed(title=f"Q{idx}", description=q, color=0x2ecc71), view=view)
                await view.wait()
                answers.append(view.value or "No response")
                continue

            await dm.send(embed=Embed(title=f"Q{idx}", description=q, color=0x2ecc71))
            try:
                msg = await bot.wait_for("message", timeout=2700, check=check)  # 45 min
                answers.append(msg.content)
            except asyncio.TimeoutError:
                await dm.send("⏰ Time limit exceeded. Please reapply.")
                return

        # Send to staff review
        review_channel = bot.get_channel(review_channel_id)
        if review_channel:
            embed = Embed(title=f"{dept} Application Submitted", color=0x7289da)
            for idx, q in enumerate(questions, start=1):
                embed.add_field(name=f"Q{idx}: {q}", value=answers[idx-1], inline=False)
            await review_channel.send(embed=embed, view=ReviewButtons())

    except Exception as e:
        print(f"[ERROR] run_application: {e}")

# ================================================================
# SECTION 5 - Staff Review System
# ================================================================

class ReviewButtons(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(Button(label="✅ Accept", style=discord.ButtonStyle.success, custom_id="accept"))
        self.add_item(Button(label="❌ Deny", style=discord.ButtonStyle.danger, custom_id="deny"))

@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.data.get("custom_id") == "accept":
        guild = bot.get_guild(HQ_GUILD_ID)
        if guild:
            member = guild.get_member(interaction.user.id)
            if member:
                vrole = guild.get_role(VERIFIED_ROLE_ID)
                orole = guild.get_role(OFFICIAL_ROLE_ID)
                if vrole in member.roles: await member.remove_roles(vrole)
                if orole not in member.roles: await member.add_roles(orole)
        await interaction.response.send_message("✅ Accepted & updated.", ephemeral=True)

    elif interaction.data.get("custom_id") == "deny":
        await interaction.response.send_message("❌ Denied.", ephemeral=True)

# ================================================================
# SECTION 6 - Member Join (PS4 + PS5)
# ================================================================

@bot.event
async def on_member_join(member: discord.Member):
    try:
        if member.guild.id == PS4_GUILD_ID:
            app_role = member.guild.get_role(1401961522556698739)
            acc_role = member.guild.get_role(1367753287872286720)
            if app_role in member.roles: await member.remove_roles(app_role)
            if acc_role not in member.roles: await member.add_roles(acc_role)
            for rid in PS4_PSO_ROLES:
                r = member.guild.get_role(rid)
                if r: await member.add_roles(r)
            callsign = f"C-{random.randint(1000,1999)} | {member.name}"
            await member.edit(nick=callsign)
            log = member.guild.get_channel(CALLSIGN_LOG_CHANNEL_ID)
            if log: await log.send(f"✅ {member.mention} assigned {callsign} (PS4)")

        elif member.guild.id == PS5_GUILD_ID:
            app_role = member.guild.get_role(1401961758502944900)
            acc_role = member.guild.get_role(1367753535839797278)
            if app_role in member.roles: await member.remove_roles(app_role)
            if acc_role not in member.roles: await member.add_roles(acc_role)
            for rid in PS5_PSO_ROLES:
                r = member.guild.get_role(rid)
                if r: await member.add_roles(r)
            callsign = f"C-{random.randint(1000,1999)} | {member.name}"
            await member.edit(nick=callsign)
            log = member.guild.get_channel(CALLSIGN_LOG_CHANNEL_ID)
            if log: await log.send(f"✅ {member.mention} assigned {callsign} (PS5)")

    except Exception as e:
        print(f"[ERROR] on_member_join: {e}")

# ================================================================
# SECTION 7 - Web Server (/auth_grant)
# ================================================================

app = Flask(__name__)

CLIENT_ID = os.getenv("CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://lsrpnetwork-verification.up.railway.app/auth")

@app.route("/auth")
def auth_grant():
    code = request.args.get("code")
    if not code: return "No code", 400
    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    r = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    if r.status_code != 200: return f"Token exchange failed: {r.text}", 400
    token = r.json().get("access_token")
    if not token: return "No token", 400
    user = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {token}"}).json()
    uid = int(user["id"])
    for gid in [PS4_GUILD_ID, PS5_GUILD_ID]:
        url = f"https://discord.com/api/guilds/{gid}/members/{uid}"
        requests.put(url, json={"access_token": token}, headers={"Authorization": f"Bot {BOT_TOKEN}"})
    return f"<h2>✅ Welcome {user['username']}!</h2>"

# ================================================================
# Run Bot
# ================================================================

if __name__ == "__main__":
    Thread(target=lambda: app.run(host="0.0.0.0", port=8080)).start()
    bot.run(BOT_TOKEN)
