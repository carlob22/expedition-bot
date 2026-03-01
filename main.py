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
intents.members = True  # enable SERVER MEMBERS INTENT in Dev Portal too

bot = commands.Bot(command_prefix="!", intents=intents)


def get_role(guild: discord.Guild, name: str):
    return discord.utils.get(guild.roles, name=name)


async def assign_roles(member: discord.Member, legion: str, server: str, rank: str):
    guild = member.guild

    legion_role = get_role(guild, LEGIONS[legion]["role"])
    rank_role = get_role(guild, RANK_TO_ROLE[rank])
    coalition_role = get_role(guild, ROLE_COALITION)
    unverified_role = get_role(guild, ROLE_UNVERIFIED)

    if not legion_role or not rank_role:
        raise ValueError("Role names do not match server. Check spelling/case.")

    # remove unverified if present
    if unverified_role and unverified_role in member.roles:
        await member.remove_roles(unverified_role)

    # remove old legion/rank roles (clean re-verify)
    all_legion_role_names = [cfg["role"] for cfg in LEGIONS.values()]
    all_rank_role_names = list(RANK_TO_ROLE.values())

    roles_to_remove = [r for r in member.roles if r.name in all_legion_role_names or r.name in all_rank_role_names]
    if roles_to_remove:
        await member.remove_roles(*roles_to_remove)

    roles_to_add = [legion_role, rank_role]
    if rank in ("R4", "R5") and coalition_role:
        roles_to_add.append(coalition_role)

    await member.add_roles(*roles_to_add)

    # nickname format
    await member.edit(nick=f"{member.name} [{server}][{rank}]")


# ---------------- PRIVATE VERIFY FLOW (EPHEMERAL) ---------------- #

class PrivateVerifyView(discord.ui.View):
    def __init__(self, user_id: int):
        super().__init__(timeout=300)
        self.user_id = user_id

        self.rank: str | None = None
        self.legion: str | None = None
        self.server: str | None = None

        # we keep references so we can update/enable server select
        self.rank_select = RankSelect()
        self.legion_select = LegionSelect()
        self.server_select = ServerSelect()

        self.add_item(self.rank_select)
        self.add_item(self.legion_select)
        self.add_item(self.server_select)
        self.add_item(ConfirmButton())

    def _guard(self, interaction: discord.Interaction) -> bool:
        return interaction.user.id == self.user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if not self._guard(interaction):
            await interaction.response.send_message("This verification menu isn't for you.", ephemeral=True)
            return False
        return True


class RankSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=r) for r in ("R3", "R4", "R5")]
        super().__init__(placeholder="Select Rank", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: PrivateVerifyView = self.view  # type: ignore
        view.rank = self.values[0]

        # show choice by changing placeholder (simple + reliable)
        self.placeholder = f"Rank: {view.rank}"
        await interaction.response.edit_message(view=view)


class LegionSelect(discord.ui.Select):
    def __init__(self):
        options = [discord.SelectOption(label=l) for l in ("Westland", "Northland", "Southland", "Eastland")]
        super().__init__(placeholder="Select Legion", options=options, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        view: PrivateVerifyView = self.view  # type: ignore
        view.legion = self.values[0]
        view.server = None

        # show choice
        self.placeholder = f"Legion: {view.legion}"

        # populate + enable server select
        view.server_select.options = [discord.SelectOption(label=s) for s in LEGIONS[view.legion]["servers"]]
        view.server_select.placeholder = "Select Server"
        view.server_select.disabled = False

        await interaction.response.edit_message(view=view)


class ServerSelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="Select legion first",
            options=[discord.SelectOption(label="—")],
            min_values=1,
            max_values=1,
            disabled=True,
        )

    async def callback(self, interaction: discord.Interaction):
        view: PrivateVerifyView = self.view  # type: ignore
        view.server = self.values[0]

        self.placeholder = f"Server: {view.server}"
        await interaction.response.edit_message(view=view)


class ConfirmButton(discord.ui.Button):
    def __init__(self):
        super().__init__(label="Confirm", style=discord.ButtonStyle.success)

    async def callback(self, interaction: discord.Interaction):
        view: PrivateVerifyView = self.view  # type: ignore

        if not (view.rank and view.legion and view.server):
            await interaction.response.send_message("Complete Rank, Legion, and Server first.", ephemeral=True)
            return

        try:
            await assign_roles(interaction.user, view.legion, view.server, view.rank)
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ Missing permissions.\n"
                "Give the bot **Manage Roles** + **Change Nickname** and move the bot role ABOVE the roles it assigns.",
                ephemeral=True,
            )
            return
        except Exception as e:
            await interaction.response.send_message(f"❌ Error: {e}", ephemeral=True)
            return

        await interaction.response.send_message("✅ Verified!", ephemeral=True)


# ---------------- PUBLIC PANEL (ONE BUTTON) ---------------- #

class StartVerifyView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)  # persistent

    @discord.ui.button(label="Start Verification", style=discord.ButtonStyle.primary)
    async def start(self, interaction: discord.Interaction, button: discord.ui.Button):
        # send a private (ephemeral) UI just for the clicker
        await interaction.response.send_message(
            "**Expedition Verification**\nSelect your Rank, Legion, and Server:",
            ephemeral=True,
            view=PrivateVerifyView(interaction.user.id),
        )


# ---------------- COMMAND ---------------- #

@bot.tree.command(name="setupverify", description="Post verification panel")
@app_commands.guilds(discord.Object(id=GUILD_ID))
async def setupverify(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)

    await interaction.channel.send(
        "**Expedition Verification**\nClick the button below to verify.",
        view=StartVerifyView()
    )

    await interaction.followup.send("✅ Verification panel posted.", ephemeral=True)


@bot.event
async def on_ready():
    # register persistent view so the button still works after restart
    bot.add_view(StartVerifyView())

    guild = discord.Object(id=GUILD_ID)
    await bot.tree.sync(guild=guild)
    print(f"Bot ready as {bot.user}")


if not TOKEN:
    raise RuntimeError("DISCORD_TOKEN missing")

bot.run(TOKEN)
