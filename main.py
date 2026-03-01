import os
import discord
from discord import app_commands
from discord.ext import commands

TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = 1476921178093387778  # Your server ID

# ---- ROLE CONFIG ----
ROLE_UNVERIFIED = "Unverified"
ROLE_COALITION = "Coalition command"

ROLE_R3 = "R3"
ROLE_R4 = "R4"
ROLE_R5 = "R5"

ROLE_WESTLAND = "Westland legion"
ROLE_NORTHLAND = "Northland legion"
ROLE_SOUTHLAND = "Southland legion"
ROLE_EASTLAND = "Eastland legion"

LEGIONS = {
    "Westland": {"role": ROLE_WESTLAND, "servers": ["M30", "M70", "M108"]},
    "Northland": {"role": ROLE_NORTHLAND, "servers": ["M31", "M51", "M161"]},
    "Southland": {"role": ROLE_SOUTHLAND, "servers": ["M19", "M121", "M130"]},
    "Eastland": {"role": ROLE_EASTLAND, "servers": ["M34", "M157", "M159"]},
}

RANK_TO_ROLE = {"R3": ROLE_R3, "R4": ROLE_R4, "R5": ROLE_R5}

# ---- BOT SETUP ----
intents = discord.Intents.default()
intents.members = True

bot = commands.Bot(command_prefix="!", intents=intents)


def get_role(guild, name):
    return discord.utils.get(guild.roles, name=name)


async def assign_roles(member, legion, server, rank):
    guild = member.guild

    legion_role = get_role(guild, LEGIONS[legion]["role"])
    rank_role = get_role(guild, RANK_TO_ROLE[rank])
    coalition_role = get_role(guild, ROLE_COALITION)
    unverified_role = get_role(guild, ROLE_UNVERIFIED)

    if not legion_role or not rank_role:
        raise ValueError("Role names do not match server.")

    if unverified_role and unverified_role in member.roles:
        await member.remove_roles(unverified_role)

    roles = [legion_role, rank_role]

    if rank in ("R4", "R5") and coalition_role:
        roles.append(coalition_role)

    await member.add_roles(*roles)

    await member.edit(nick=f"{member.name} [{server}][{rank}]")


# ---------------- VIEW ---------------- #

class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.rank = None
        self.legion = None
        self.server = None

    @discord.ui.select(
        placeholder="Select Rank",
        options=[
            discord.SelectOption(label="R3"),
            discord.SelectOption(label="R4"),
            discord.SelectOption(label="R5"),
        ],
    )
    async def select_rank(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.rank = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(
        placeholder="Select Legion",
        options=[
            discord.SelectOption(label="Westland"),
            discord.SelectOption(label="Northland"),
            discord.SelectOption(label="Southland"),
            discord.SelectOption(label="Eastland"),
        ],
    )
    async def select_legion(self, interaction: discord.Interaction, select: discord.ui.Select):
        self.legion = select.values[0]
        await interaction.response.defer()

    @discord.ui.select(placeholder="Select Server")
    async def select_server(self, interaction: discord.Interaction, select: discord.ui.Select):
        if not self.legion:
            await interaction.response.send_message("Select legion first.", ephemeral=True)
            return

        select.options = [
            discord.SelectOption(label=s)
            for s in LEGIONS[self.legion]["servers"]
        ]
        self.server = select.values[0]
        await interaction.response.defer()

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (self.rank and self.legion and self.server):
            await interaction.response.send_message("Complete all selections first.", ephemeral=True)
            return

        await assign_roles(interaction.user, self.legion, self.server, self.rank)
        await interaction.response.send_message("✅ Verified!", ephemeral=True)


# ---------------- COMMAND ---------------- #

@bot.tree.command(name="setupverify", description="Post verification panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def setupverify(interaction: discord.Interaction):

    await interaction.response.defer(ephemeral=True)

    view = VerifyView()

    await interaction.channel.send(
        "**Expedition Verification**\nSelect your Rank, Legion and Server.",
        view=view
    )

    await interaction.followup.send("✅ Verification panel posted.", ephemeral=True)
    


@bot.event
async def on_ready():
    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print(f"Bot ready as {bot.user}")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing")

bot.run(TOKEN)
