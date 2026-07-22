import discord
from discord.ext import commands
from discord.ui import View
import os
import asyncio
from datetime import timedelta

TOKEN = os.getenv("DISCORD_TOKEN")

PREFIX = "."

CATEGORY_ID = 1529431738949046312

SUPPORT_ROLES = [
    1523650684132790402,
    1523651007983124652,
    1523651268617175100,
    1523651736701636619,
    1529431155508772874
]

intents = discord.Intents.all()
bot = commands.Bot(command_prefix=PREFIX, intents=intents)

warnings = {}
ticket_counter = 0


def is_support_member(member: discord.Member) -> bool:
    return any(role.id in SUPPORT_ROLES for role in member.roles)


def make_embed(title: str, description: str, color: discord.Color = discord.Color.blue()):
    return discord.Embed(title=title, description=description, color=color)


# =========================
# TICKET FORM (MODAL)
# =========================

class TicketForm(discord.ui.Modal, title="Create Support Ticket"):
    reason = discord.ui.TextInput(
        label="Why are you creating this ticket?",
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        global ticket_counter

        if not interaction.guild:
            await interaction.response.send_message(
                embed=make_embed("Error", "This command can only be used in a server.", discord.Color.red()),
                ephemeral=True
            )
            return

        category = interaction.guild.get_channel(CATEGORY_ID)

        if category is None or not isinstance(category, discord.CategoryChannel):
            await interaction.response.send_message(
                embed=make_embed("Error", "Ticket category not found or invalid.", discord.Color.red()),
                ephemeral=True
            )
            return

        ticket_counter += 1
        channel_name = f"support-ticket-{ticket_counter}"

        guild_me = interaction.guild.me or interaction.guild.get_member(bot.user.id)

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
        }

        if guild_me:
            overwrites[guild_me] = discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            )

        for role_id in SUPPORT_ROLES:
            role = interaction.guild.get_role(role_id)
            if role:
                overwrites[role] = discord.PermissionOverwrite(
                    view_channel=True,
                    send_messages=True,
                    read_message_history=True
                )

        channel = await interaction.guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites
        )

        mentions = " ".join(f"<@&{role_id}>" for role_id in SUPPORT_ROLES)

        embed = make_embed(
            "New Support Ticket",
            f"**User:** {interaction.user.mention}\n"
            f"**Reason:** {self.reason.value}\n\n"
            f"{mentions}",
            discord.Color.green()
        )

        await channel.send(
            content=interaction.user.mention,
            embed=embed,
            view=ClaimCloseView(),
            allowed_mentions=discord.AllowedMentions(roles=True, users=True)
        )

        await interaction.response.send_message(
            embed=make_embed("Ticket Created", f"Your ticket has been created: {channel.mention}", discord.Color.green()),
            ephemeral=True
        )


# =========================
# TICKET BUTTONS
# =========================

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Open Ticket",
        style=discord.ButtonStyle.green,
        custom_id="open_ticket"
    )
    async def open_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(TicketForm())


# =========================
# CLAIM + CLOSE
# =========================

class ClaimCloseView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Claim",
        style=discord.ButtonStyle.blurple,
        custom_id="claim_ticket"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild or not isinstance(interaction.user, discord.Member):
            await interaction.response.send_message(
                embed=make_embed("Error", "This can only be used in a server.", discord.Color.red()),
                ephemeral=True
            )
            return

        if not is_support_member(interaction.user):
            await interaction.response.send_message(
                embed=make_embed("Denied", "Only support staff can claim tickets.", discord.Color.red()),
                ephemeral=True
            )
            return

        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            embed=make_embed(
                "Ticket Claimed",
                f"This ticket was claimed by {interaction.user.mention}.",
                discord.Color.blurple()
            )
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.guild:
            await interaction.response.send_message(
                embed=make_embed("Error", "This can only be used in a server.", discord.Color.red()),
                ephemeral=True
            )
            return

        await interaction.response.send_message(
            embed=make_embed("Closing Ticket", "This ticket will be deleted in 3 seconds.", discord.Color.red())
        )
        await asyncio.sleep(3)
        await interaction.channel.delete(reason=f"Ticket closed by {interaction.user}")


# =========================
# EVENTS
# =========================

@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(ClaimCloseView())
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} app command(s).")
    except Exception as e:
        print(f"Failed to sync app commands: {e}")

    print(f"Logged in as {bot.user}")


# =========================
# MODERATION
# =========================

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int):
    if minutes <= 0:
        await ctx.send(
            embed=make_embed("Error", "Minutes must be greater than 0.", discord.Color.red())
        )
        return

    until = discord.utils.utcnow() + timedelta(minutes=minutes)
    await member.timeout(until, reason=f"Muted by {ctx.author}")

    await ctx.send(
        embed=make_embed(
            "Muted",
            f"{member.mention} has been muted for **{minutes} minute(s)**.",
            discord.Color.orange()
        )
    )


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(
        embed=make_embed(
            "Banned",
            f"**{member}** has been banned.\n**Reason:** {reason}",
            discord.Color.red()
        )
    )


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user, reason=f"Unbanned by {ctx.author}")
    await ctx.send(
        embed=make_embed(
            "Unbanned",
            f"**{user}** has been unbanned.",
            discord.Color.green()
        )
    )


@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    warnings.setdefault(member.id, []).append(reason)
    await ctx.send(
        embed=make_embed(
            "Warned",
            f"{member.mention} has been warned.\n"
            f"**Total Warnings:** {len(warnings[member.id])}\n"
            f"**Reason:** {reason}",
            discord.Color.orange()
        )
    )


@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, member: discord.Member, role: discord.Role):
    if role in member.roles:
        await member.remove_roles(role, reason=f"Role removed by {ctx.author}")
        action = "Removed"
        color = discord.Color.red()
    else:
        await member.add_roles(role, reason=f"Role added by {ctx.author}")
        action = "Added"
        color = discord.Color.green()

    await ctx.send(
        embed=make_embed(
            "Role Updated",
            f"{action} **{role.name}** for {member.mention}.",
            color
        )
    )


# =========================
# TICKET PANEL
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):
    embed = make_embed(
        "Support Tickets",
        "Press the button below to open a ticket.",
        discord.Color.blue()
    )
    await ctx.send(embed=embed, view=TicketView())


# =========================
# ERROR HANDLING
# =========================

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send(
            embed=make_embed("Permission Error", "You do not have permission to use this command.", discord.Color.red())
        )
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            embed=make_embed("Usage Error", f"Missing argument: `{error.param.name}`", discord.Color.red())
        )
    elif isinstance(error, commands.BadArgument):
        await ctx.send(
            embed=make_embed("Argument Error", "Invalid argument provided.", discord.Color.red())
        )
    else:
        await ctx.send(
            embed=make_embed("Error", f"An error occurred: `{error}`", discord.Color.red())
        )


bot.run(TOKEN)
