import os
import discord
from discord import app_commands
from discord.ext import commands

# ---------- GUILD ----------
GUILD_ID = 1476921178093387778
GUILD = discord.Object(id=GUILD_ID)

TOKEN = os.getenv("DISCORD_TOKEN")

# ---- CONFIG (EDIT THESE TO MATCH YOUR SERVER ROLE NAMES) ----
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
# ------------------------------------------------------------

INTENTS = discord.Intents.default()
INTENTS.members = True

bot = commands.Bot(command_prefix="!", intents=INTENTS)


def get_role(guild: discord.Guild, role_name: str):
    return discord.utils.get(guild.roles, name=role_name)


async def assign_roles_and_nick(member: discord.Member, legion: str, server: str, rank: str):
    guild = member.guild

    if legion not in LEGIONS:
        raise ValueError("Invalid legion")
    if rank not in RANK_TO_ROLE:
        raise ValueError("Invalid rank")
    if server not in LEGIONS[legion]["servers"]:
        raise ValueError("Invalid server for legion")

    legion_role = get_role(guild, LEGIONS[legion]["role"])
    rank_role = get_role(guild, RANK_TO_ROLE[rank])
    coalition_role = get_role(guild, ROLE_COALITION)
    unverified_role = get_role(guild, ROLE_UNVERIFIED)

    if legion_role is None or rank_role is None:
        raise ValueError("One or more required roles were not found. Check role names in CONFIG.")

    roles_to_add = [legion_role, rank_role]

    if rank in ("R4", "R5") and coalition_role:
        roles_to_add.append(coalition_role)

    if unverified_role and unverified_role in member.roles:
        await member.remove_roles(unverified_role, reason="Verified")

    await member.add_roles(*roles_to_add, reason="Verified")

    new_nick = f"{member.name} [{server}][{rank}]"
    try:
        await member.edit(nick=new_nick, reason="Verified")
    except discord.Forbidden:
        pass


# -------- Interactive Verification UI --------

class RankSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="R3", description="Legion chat only"),
            discord.SelectOption(label="R4", description="Leadership + Coalition"),
            discord.SelectOption(label="R5", description="Leadership + Coalition"),
        ]
        super().__init__(placeholder="Select your rank…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: VerifyView = self.view  # type: ignore
        view.rank = self.values[0]
        await view.refresh(interaction)


class LegionSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Westland"),
            discord.SelectOption(label="Northland"),
            discord.SelectOption(label="Southland"),
            discord.SelectOption(label="Eastland"),
        ]
        super().__init__(placeholder="Select your legion…", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: VerifyView = self.view  # type: ignore
        view.legion = self.values[0]
        view.server = None
        await view.refresh(interaction)


class ServerSelect(discord.ui.Select):
    def __init__(self, legion: str | None):
        options = []
        if legion and legion in LEGIONS:
            options = [discord.SelectOption(label=s) for s in LEGIONS[legion]["servers"]]
        super().__init__(
            placeholder="Select your server…",
            options=options,
            min_values=1,
            max_values=1,
            disabled=not bool(options),
        )

    async def callback(self, interaction: discord.Interaction):
        view: VerifyView = self.view  # type: ignore
        view.server = self.values[0]
        await view.refresh(interaction)


class VerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        self.rank: str | None = None
        self.legion: str | None = None
        self.server: str | None = None

        self.rank_select = RankSelect()
        self.legion_select = LegionSelect()
        self.server_select = ServerSelect(None)

        self.add_item(self.rank_select)
        self.add_item(self.legion_select)
        self.add_item(self.server_select)

    async def refresh(self, interaction: discord.Interaction):
        self.remove_item(self.server_select)
        self.server_select = ServerSelect(self.legion)
        self.add_item(self.server_select)

        content = (
            "**Expedition Verification**\n"
            "Choose your **Rank**, **Legion**, and **Server** using the dropdowns.\n\n"
            f"Selected:\n• Rank: `{self.rank or '—'}`\n• Legion: `{self.legion or '—'}`\n• Server: `{self.server or '—'}`\n\n"
            "When ready, press **Confirm**."
        )
        await interaction.response.edit_message(content=content, view=self)

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.success, custom_id="expedition_verify_confirm")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not (self.rank and self.legion and self.server):
            return await interaction.response.send_message("Please select Rank, Legion, and Server first.", ephemeral=True)

        member = interaction.user
        if not isinstance(member, discord.Member):
            member = interaction.guild.get_member(interaction.user.id)  # type: ignore

        try:
            await assign_roles_and_nick(member, self.legion, self.server, self.rank)  # type: ignore
        except ValueError as e:
            return await interaction.response.send_message(f"Verification error: {e}", ephemeral=True)
        except discord.Forbidden:
            return await interaction.response.send_message(
                "I don't have permission to manage roles/nicknames. Check bot role order & permissions.",
                ephemeral=True,
            )

        await interaction.response.send_message(
            f"✅ Verified: **{member.display_name}** → `{self.server}` `{self.rank}` `{self.legion}`",
            ephemeral=True,
        )


# -------- Slash command to post the Verify panel --------
@bot.tree.command(
    name="setupverify",
    description="Post the Expedition verification panel",
    guild=GUILD,   # ✅ THIS is the key
)
@app_commands.checks.has_permissions(administrator=True)
async def setupverify(interaction: discord.Interaction):
    view = VerifyView()
    content = (
        "**Expedition Verification**\n"
        "Choose your **Rank**, **Legion**, and **Server** using the dropdowns.\n\n"
        "Then press **Confirm**.\n\n"
        "_R4/R5 get Coalition access automatically. R3 stays in legion-only._"
    )
    await interaction.channel.send(content, view=view)  # type: ignore
    await interaction.response.send_message("✅ Verification panel posted.", ephemeral=True)


@bot.event
async def on_ready():
    print("✅ LOADED CORRECT main.py v3")
    bot.add_view(VerifyView())

    try:
        synced = await bot.tree.sync(guild=GUILD)
        print(f"✅ Synced {len(synced)} command(s) to guild {GUILD_ID}")
    except Exception as e:
        print("❌ Command sync failed:", repr(e))

    print(f"🤖 Logged in as {bot.user} (ID: {bot.user.id})")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN is not set.")

bot.run(TOKEN)
