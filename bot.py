import os
import random
import datetime
import discord
from discord import app_commands, Embed, Object
from discord.ext import commands, tasks

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
rsvp_data: dict[int, dict] = {}

# PSO Ranks & Roles
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
    "Officer I": 1375046541869584464,
    "Officer II": 1375046540925599815,
    "Sergeant": 1392169682596790395,
    "Master Sergeant": 1375046535410356295,
    "Lieutenant": 1375046533833035778,
    "Captain": 1375046532847501373,
    "Major": 1375046529752105041,
    "Commander": 1375046528963444819,
    "ADOPS": 1375046524567818270,
    "PSO_Main": 1375046521904431124,
    "Supervisor": 1375046546554621952
}

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

@bot.event
async def on_ready():
    synced = await tree.sync(guild=Object(id=GUILD_ID))
    print(f"✅ Synced {len(synced)} commands")
    print(f"✅ Bot is online as {bot.user}")
    if not watchdog.is_running():
        watchdog.start()

# ─────────────────────────────────────────
# PERMISSIONS
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

# ─────────────────────────────────────────
# STAFF COMMANDS
# ─────────────────────────────────────────
@tree.command(name="ping", description="Check slash command sync", guilds=[Object(id=GUILD_ID)])
async def ping(interaction: discord.Interaction):
    await interaction.response.send_message("🟢 Pong!")

@tree.command(name="staff_hire", description="Hire a user into the staff team", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(user="User to hire")
async def staff_hire(interaction: discord.Interaction, user: discord.Member):
    if not await is_hr(interaction): return
    role = interaction.guild.get_role(STAFF_ROLE_ID)
    await user.add_roles(role, reason="Staff hire")
    try:
        await user.send(
            "**📋 Staff Hire Confirmation**\n\n"
            f"Welcome aboard, {user.mention}!\n\n"
            "You have officially been hired as part of the **Los Santos Roleplay Staff Team**..."
        )
    except discord.Forbidden:
        pass
    await interaction.response.send_message(f"✅ {user.mention} has been hired as Staff.")

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
    await log_ch.send(embed=embed)
    active_priority = None
    await interaction.response.send_message("✅ Priority ended.", ephemeral=True)

# ─────────────────────────────────────────
# SESSION COMMANDS
# ─────────────────────────────────────────
@tree.command(name="host_main_session", description="Announce Main Session", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(psn="PSN ID", date_time="Date & Time", session_type="Type", aop="Area of Play")
async def host_main_session(interaction: discord.Interaction, psn: str, date_time: str, session_type: str, aop: str):
    base_desc = f"""**Los Santos Roleplay™ PlayStation |** Main Session

**PSN:** {psn}

**Start Time:** {date_time}
• **Type:** {session_type}
• **AOP:** {aop}
"""
    embed = Embed(description=base_desc, color=discord.Color.blurple())
    await interaction.response.send_message(embed=embed)
    message = await interaction.original_response()
    for emoji in ("✅", "❌", "🕰️"):
        await message.add_reaction(emoji)
    rsvp_data[message.id] = {'base': base_desc, 'attendees': [], 'declines': [], 'late': []}

@bot.event
async def on_raw_reaction_add(payload: discord.RawReactionActionEvent):
    if payload.message_id not in rsvp_data or payload.user_id == bot.user.id:
        return
    data = rsvp_data[payload.message_id]
    user_mention = f"<@{payload.user_id}>"
    emoji = str(payload.emoji)
    for lst in ('attendees','declines','late'):
        if user_mention in data[lst]:
            data[lst].remove(user_mention)
    if emoji == "✅":
        data['attendees'].append(user_mention)
    elif emoji == "❌":
        data['declines'].append(user_mention)
    elif emoji == "🕰️":
        data['late'].append(user_mention)
    summary = f"\n✅ Attending: {', '.join(data['attendees']) or '—'}\n❌ Not Attending: {', '.join(data['declines']) or '—'}\n🕰️ Late: {', '.join(data['late']) or '—'}"
    channel = bot.get_channel(payload.channel_id)
    msg = await channel.fetch_message(payload.message_id)
    new_embed = Embed(description=data['base'] + summary, color=discord.Color.blurple())
    await msg.edit(embed=new_embed)

@tree.command(name="start_session", description="Announce session start", guilds=[Object(id=GUILD_ID)])
@app_commands.describe(psn="PSN Username", aop="Area of Play")
async def start_session(interaction: discord.Interaction, psn: str, aop: str):
    session_role = interaction.guild.get_role(PING_ROLE_ID)
    embed = Embed(title="🟢 SESSION START", description=f"**Host PSN:** {psn}\n**AOP:** {aop}", color=discord.Color.green())
    await interaction.response.send_message(content=session_role.mention, embed=embed)

@tree.command(name="end_session", description="Announce session end", guilds=[Object(id=GUILD_ID)])
async def end_session(interaction: discord.Interaction):
    session_role = interaction.guild.get_role(PING_ROLE_ID)
    embed = Embed(title="🔴 SESSION CLOSED", description="**This session has now concluded.**", color=discord.Color.red())
    await interaction.response.send_message(content=session_role.mention, embed=embed)

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
bot.run(BOT_TOKEN)
