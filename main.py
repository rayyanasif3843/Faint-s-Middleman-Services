import discord
from discord.ext import commands
from discord.ui import View
import os
import asyncio

TOKEN = os.getenv("DISCORD_TOKEN")

PREFIX = "w!"

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

ticket_counter = 0


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

        category = interaction.guild.get_channel(CATEGORY_ID)

        if category is None:
            await interaction.response.send_message(
                "Ticket category not found.",
                ephemeral=True
            )
            return

        ticket_counter += 1
        channel_name = f"support-ticket-{ticket_counter}"

        overwrites = {
            interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
            interaction.user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True
            ),
            interaction.guild.me: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True
            )
        }

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

        await channel.send(
            content=f"{interaction.user.mention} {mentions}\n\n"
                    f"📩 **Reason:** {self.reason.value}",
            view=ClaimCloseView(),
            allowed_mentions=discord.AllowedMentions(roles=True, users=True)
        )

        await interaction.response.send_message(
            f"Ticket created: {channel.mention}",
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

        support = any(
            interaction.guild.get_role(role_id) in interaction.user.roles
            for role_id in SUPPORT_ROLES
        )

        if not support:
            await interaction.response.send_message(
                "Only support staff can claim tickets.",
                ephemeral=True
            )
            return

        button.disabled = True
        button.label = f"Claimed by {interaction.user.display_name}"
        await interaction.message.edit(view=self)

        await interaction.response.send_message(
            f"Ticket claimed by {interaction.user.mention}"
        )

    @discord.ui.button(
        label="Close",
        style=discord.ButtonStyle.red,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):

        await interaction.response.send_message("Closing ticket in 3 seconds...")
        await asyncio.sleep(3)
        await interaction.channel.delete()


# =========================
# EVENTS
# =========================

@bot.event
async def on_ready():
    bot.add_view(TicketView())
    bot.add_view(ClaimCloseView())
    print(f"Logged in as {bot.user}")


# =========================
# MODERATION
# =========================

@bot.command()
@commands.has_permissions(moderate_members=True)
async def mute(ctx, member: discord.Member, minutes: int):
    await member.timeout(discord.utils.utcnow() + discord.timedelta(minutes=minutes))
    await ctx.send(f"{member.mention} muted for {minutes} minute(s).")


@bot.command()
@commands.has_permissions(ban_members=True)
async def ban(ctx, member: discord.Member, *, reason="No reason"):
    await member.ban(reason=reason)
    await ctx.send(f"{member} banned.\nReason: {reason}")


@bot.command()
@commands.has_permissions(ban_members=True)
async def unban(ctx, user_id: int):
    user = await bot.fetch_user(user_id)
    await ctx.guild.unban(user)
    await ctx.send(f"Unbanned {user}")


warnings = {}

@bot.command()
@commands.has_permissions(manage_messages=True)
async def warn(ctx, member: discord.Member, *, reason="No reason"):
    warnings.setdefault(member.id, []).append(reason)
    await ctx.send(f"{member.mention} warned.\nTotal warnings: {len(warnings[member.id])}")


@bot.command()
@commands.has_permissions(manage_roles=True)
async def role(ctx, member: discord.Member, role: discord.Role):
    if role in member.roles:
        await member.remove_roles(role)
        await ctx.send(f"Removed {role.name} from {member.mention}")
    else:
        await member.add_roles(role)
        await ctx.send(f"Added {role.name} to {member.mention}")


# =========================
# TICKET PANEL
# =========================

@bot.command()
@commands.has_permissions(administrator=True)
async def ticketpanel(ctx):
    embed = discord.Embed(
        title="Support Tickets",
        description="Press the button below to open a ticket.",
        color=discord.Color.blue()
    )

    await ctx.send(embed=embed, view=TicketView())


bot.run(TOKEN)
