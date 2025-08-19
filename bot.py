# =======================================================
# LSRP Network System™® — Unified Bot (Full Raw Version)
# Focus build: Application System (PSO/CO/SAFR) + Auth + /ping + /version + Auto-callsigns
# =======================================================

import os
import time
import random
import asyncio
import threading
from typing import Dict, List

import discord
from discord import app_commands, Embed, Object
from discord.ext import commands
from discord.ui import View, Button, Select

from flask import Flask, request, redirect

# =======================================================
# ENVIRONMENT + CONFIG
# =======================================================

BOT_TOKEN = os.getenv("BOT_TOKEN")

CLIENT_ID = os.getenv("CLIENT_ID") or "1397974568706117774"
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or "YOUR_CLIENT_SECRET"
REDIRECT_URI = os.getenv("REDIRECT_URI", "https://auth.lsrpnetwork.com/auth")

HQ_GUILD_ID = 1324117813878718474   # PS4 HQ (Main server)
PS5_GUILD_ID = 1401903156274790441  # PS5 guild
XBOX_GUILD_ID = 1375494043831898334 # Xbox OG guild

# Roles
ROLE_VERIFIED = 1294322438733168723
ROLE_MEMBER = 1323753774157664347
ROLE_DENIED = 1323755533492027474

# Applicant roles
PS4_APPLICANT = 1401961522556698739
PS4_ACCEPTED = 1367753287872286720

PS5_APPLICANT = 1401961758502944900
PS5_ACCEPTED = 1367753535839797278

XBOX_APPLICANT = 1401961991756578817
XBOX_ACCEPTED = 1367753756367912960

# Department roles
PSO_MAIN = 1407034126510325907
SASP_ROLE = 1407034121808646269
BCSO_ROLE = 1407034123561734245
CO_ROLE = 1407034124648317079
SAFR_ROLE = 1407034125713408053

# Logging channels
REVIEW_CHANNEL_ID = 1366431401054048357
AUTH_LOG_CHANNEL_ID = 1395135616177668186
PANEL_CHANNEL_ID = 1324115220725108877

# =======================================================
# DISCORD CLIENT
# =======================================================

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)

# =======================================================
# GLOBALS
# =======================================================

active_apps: Dict[int, Dict] = {}
application_timeout = 3600  # 1 hour

# =======================================================
# QUESTIONS
# =======================================================

COMMON_QUESTIONS = [
    "What is your Discord username?",
    "How old are you in real life?",
    "Your Date of Birth (e.g., 16th June 2010).",
    "How did you find us? (Friend / Instagram / Partnership / Other)"
]

PSO_QUESTIONS = [
    "Explain the No Life Rule.",
    "What does VDM, RDM and FRP mean?",
    "Do you have any roleplay experience? If yes, describe.",
    "What time zone are you from? (GMT, EST, UTC etc.)",
    "Describe what a 10-11 means.",
    "You see a suspect with a knife. What do you do?",
    "What does a 10-80 mean?",
    "How would you handle a 10-11?",
    "You arrive at robbery scene, suspect says 'I have a bomb'—what next?",
    "What do Code 1, 2, and 3 mean?",
    "Which 10 codes do you use when on duty?",
    "As a cadet, can you drive solo? Yes or No.",
    "You see a sniper with only pistol & radio. What do you do?",
    "How would you handle a noise complaint? (min 20 words)",
    "Choose correct cadet loadout from options.",
    "What is a 10-99?",
    "Explain difference between code 4 and 10-15.",
    "How respond to officer down call?",
    "How to handle chain-of-command conflicts in RP.",
    "Why do you want to join PSO long-term?"
]

CO_QUESTIONS = [
    "Explain what FearRP means.",
    "How would you roleplay a store robbery as a civilian?",
    "How to handle a traffic stop as a civ?",
    "What is Powergaming? Give example.",
    "What is Metagaming? Give example.",
    "You crash your car. Roleplay your action.",
    "A fight breaks out at club. How do you respond?",
    "How to roleplay owning a business?",
    "How to roleplay losing a gunfight?",
    "Your long-term goal as a civilian roleplayer?",
    "Explain your character background plan.",
    "How to avoid chaotic civilian RP?",
    "Ideal civilian scene you’d run?",
    "How would you signal for EMS as a civilian?",
    "Difference between legal and illegal RP?",
    "How do you RP being drunk/high?",
    "Explain realism importance in civilian RP.",
    "How to step back and let others lead?",
    "How will you use public locations to spark RP?",
    "Why do you want to join Civilian Ops?"
]

FIRE_QUESTIONS = [
    "What does EMS stand for?",
    "Your priorities at a fire scene?",
    "How to treat gunshot wound?",
    "What equipment do firefighters carry?",
    "If civilian is trapped in burning house, what next?",
    "Explain 'triage' in EMS.",
    "How to handle mass casualty scene?",
    "What does Code Red mean in Fire/EMS?",
    "Roleplay providing CPR.",
    "Explain chain of command in Fire/EMS.",
    "How do you assist police at accident scene?",
    "Differences between EMT and Paramedic?",
    "Roleplay patient transport.",
    "How to handle hazmat situation?",
    "Responding to plane crash RP?",
    "How to roleplay fatigue on long scene?",
    "Handling conflicting commands situation?",
    "What tools would you carry into a fire?",
    "Approach to patient consent refusal?",
    "Why do you want to join SAFR?"
]

# =======================================================
# APPLICATION PANEL
# =======================================================

class DepartmentSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="PSO", description="Public Safety Office (SASP/BCSO)"),
            discord.SelectOption(label="CO", description="Civilian Operations"),
            discord.SelectOption(label="SAFR", description="San Andreas Fire & Rescue")
        ]
        super().__init__(placeholder="Select department...", options=options)

    async def callback(self, interaction: discord.Interaction):
        user = interaction.user
        dept = self.values[0]
        await interaction.response.send_message(f"{user.mention}, please check your DMs to start the {dept} application.", ephemeral=True)

        questions = COMMON_QUESTIONS.copy()
        if dept == "PSO":
            questions += PSO_QUESTIONS
        elif dept == "CO":
            questions += CO_QUESTIONS
        else:
            questions += FIRE_QUESTIONS

        try:
            dm = await user.create_dm()
            await dm.send(embed=Embed(title=f"{dept} Application", description="Please answer all questions. You have one hour.", color=discord.Color.blue()))
        except:
            return

        active_apps[user.id] = {"dept": dept, "answers": []}

        for q in questions:
            await dm.send(embed=Embed(title="Question", description=q, color=discord.Color.blue()))
            try:
                msg = await bot.wait_for("message", check=lambda m: m.author == user and isinstance(m.channel, discord.DMChannel), timeout=application_timeout)
                active_apps[user.id]["answers"].append((q, msg.content))
            except asyncio.TimeoutError:
                await dm.send("Application timed out. Please reapply via the panel.")
                del active_apps[user.id]
                return

        # Submit to review
        review_channel = bot.get_channel(REVIEW_CHANNEL_ID)
        if review_channel:
            embed = Embed(title=f"{dept} Application Submitted", color=discord.Color.blue())
            for q, a in active_apps[user.id]["answers"]:
                embed.add_field(name=q, value=a or "No answer", inline=False)
            view = ReviewButtons(user.id, dept)
            await review_channel.send(embed=embed, view=view)

        await dm.send("Application submitted! Staff will review shortly.")
        del active_apps[user.id]

class ApplicationPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(DepartmentSelect())

# =======================================================
# REVIEW BUTTONS WITH CALLSIGN
# =======================================================

class ReviewButtons(View):
    def __init__(self, applicant_id: int, dept: str):
        super().__init__(timeout=None)
        self.applicant_id = applicant_id
        self.dept = dept

    @discord.ui.button(label="Accept", style=discord.ButtonStyle.green)
    async def accept(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        applicant = guild.get_member(self.applicant_id)
        if not applicant:
            await interaction.response.send_message("Applicant not found.", ephemeral=True)
            return

        await applicant.remove_roles(discord.Object(ROLE_VERIFIED))
        await applicant.add_roles(discord.Object(ROLE_MEMBER))

        # Callsign formatting
        if self.dept == "PSO":
            cs = f"C-{random.randint(1000,1999)} | {applicant.name}"
        elif self.dept == "CO":
            cs = f"CIV-{random.randint(1000,1999)} | {applicant.name}"
        else:
            cs = f"FF-{random.randint(100,999)} | {applicant.name}"

        try:
            await applicant.edit(nick=cs, reason="Assigned callsign")
        except:
            pass

        embed = Embed(title="Application Accepted", color=discord.Color.green())
        embed.add_field(name="Accepted By", value=interaction.user.mention, inline=False)
        embed.add_field(name="Applicant", value=applicant.mention, inline=False)
        embed.add_field(name="Department", value=self.dept, inline=False)
        embed.add_field(name="Assigned Callsign", value=cs, inline=False)
        embed.add_field(name="Time", value=f"<t:{int(time.time())}:F>", inline=False)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Deny", style=discord.ButtonStyle.red)
    async def deny(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        applicant = guild.get_member(self.applicant_id)
        if applicant:
            await applicant.add_roles(discord.Object(ROLE_DENIED))
        embed = Embed(title="Application Denied", color=discord.Color.red())
        embed.add_field(name="Denied By", value=interaction.user.mention, inline=False)
        embed.add_field(name="Applicant", value=f"<@{self.applicant_id}>", inline=False)
        embed.add_field(name="Time", value=f"<t:{int(time.time())}:F>", inline=False)

        for child in self.children:
            child.disabled = True
        await interaction.response.edit_message(embed=embed, view=self)

# =======================================================
# SLASH COMMANDS
# =======================================================

@bot.tree.command(name="ping", description="Check if bot is online")
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong!")

@bot.tree.command(name="version", description="Check bot version")
async def version(interaction: discord.Interaction):
    await interaction.response.send_message("LSRP Bot v1.0 — Full unified build")

@bot.tree.command(name="auth_grant", description="Grant authorization after OAuth")
async def auth_grant(interaction: discord.Interaction, user: discord.Member):
    await interaction.response.send_message(f"✅ Authorization granted for {user.mention}", ephemeral=True)
    log = bot.get_channel(AUTH_LOG_CHANNEL_ID)
    if log:
        await log.send(f"✅ {user.mention} authorized at <t:{int(time.time())}:F>")

# =======================================================
# STARTUP
# =======================================================

@bot.event
async def on_ready():
    print(f"Bot online as {bot.user}")
    await bot.tree.sync()
    channel = bot.get_channel(PANEL_CHANNEL_ID)
    if channel:
        await channel.send(embed=Embed(title="LSRP Application Panel", description="Select a department below to begin.", color=discord.Color.blue()), view=ApplicationPanel())

# =======================================================
# WEB SERVER (OAuth placeholder)
# =======================================================

app = Flask("auth")

@app.route("/auth")
def auth():
    return redirect("https://discord.gg")

def run_web():
    app.run(host="0.0.0.0", port=8080)

threading.Thread(target=run_web, daemon=True).start()

# =======================================================
# RUN BOT
# =======================================================

bot.run(BOT_TOKEN)
