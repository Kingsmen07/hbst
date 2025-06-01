# ----------------------
# IMPORTS & DEPENDENCIES
# ----------------------
import os
import sys
import discord
from discord.ext import commands
from discord import app_commands
from discord.app_commands import CheckFailure
import asyncio
import yaml
from datetime import datetime, timedelta, timezone
import time
import requests
import re
import math
from queue_commands import register_commands
from discord.utils import get
from remindersystem import load_reminders, delayed_send_reminder, send_reminder, setup as reminders_setup  # Added imports

# ----------------------
# DEPENDENCY CHECKS
# ----------------------
required_modules = [
    "discord",
    "pyyaml",
    "asyncio",
    "requests"
]

for module in required_modules:
    try:
        __import__(module)
    except ImportError:
        os.system(f"{sys.executable} -m pip install {module}")

# ----------------------
# CONFIGURATION LOADING
# ----------------------
try:
    with open("config.yaml", "r") as file:
        config = yaml.safe_load(file)
        # REMINDERS_FILE removed as per changes
except Exception as e:
    print(f"Failed to load config: {e}")
    sys.exit(1)

# ----------------------
# BOT CONFIGURATION
# ----------------------
token = config["token"]
prefix = config["prefix"]
client_role = config["client_role"]
BLUE = 0x0000FF  # Consistent blue color for all embeds
bot_logs = config["bot_logs"]
admin_role = config["admin_role"]
queue_channel = config["queue_channel"]
upi_id = config.get("upi_id", "Not specified")
upi_qr = config.get("upi_qr", "Not specified")
CATEGORY_MESSAGES = config["CATEGORY_MESSAGES"]

# ----------------------
# BOT INITIALIZATION
# ----------------------
start_time = datetime.now()
intents = discord.Intents.all()
bot = commands.Bot(command_prefix=prefix, intents=intents)

# Setup reminder system after bot initialization
reminders_setup(bot)

# Remove conflicting default commands
bot.remove_command('help')
bot.remove_command('info')

# ----------------------
# CONSTANTS - Role emojis for userinfo command
# ----------------------
role_emojis = {
    "・⋈ Owner ！🧋": ("<:hb_owner:1354459569878864062>", "Owner"),
    "୧・ Co-Owner  — ♡゙  ! ⑅": ("<:hb_co_owner:1354459552699125831>", "Co-Owner"),
    "Administrator": ("<:hb_admin:1354459400223592710>", "Admin"),
    "Developer": ("<:hb_dev:1354459387556794572>", "Developer"),
    "≜ Happy Box Staff": ("<:hb_staff2:1354459012745138386>", "Staff"),
    "✧༝ happy booster": ("<:hb_booster:1354460609705677033>", "Booster"),
    "✦༝ unrivaled client": ("<:hb_unrivaledclient:1354458520061218887>", "Unrivaled Client"),
    "✦༝ regular client": ("<:hb_regularclient:1354458362443464945>", "Regular Client"),
    "≜ Retired Mod": ("<:hb_retiredmod:1354460995438776492>", "Retired Staff"),
    "✦༝ Owner's Elites": ("<:hb_ownerelite:1354458450654003282>", "Owner's Elites"),
    "✧༝ vip client": ("<:hb_vipclient:1354458272811454624>", "ViP Client"),
    "✧༝ client": ("<:hb_client:1354457991537233960>", "Client")
}

# ----------------------
# EVENT HANDLERS
# ----------------------
@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    
    try:
        # Load and schedule existing reminders
        reminders = load_reminders()
        current_time = time.time()
        
        for reminder in reminders[:]:  # Iterate over a copy
            remaining_time = reminder['end_time'] - current_time
            if remaining_time > 0:
                bot.loop.create_task(delayed_send_reminder(bot, reminder, remaining_time))
            else:
                # Schedule immediate sending without blocking
                bot.loop.create_task(delayed_send_reminder(bot, reminder, 0))
        
        # Removed save_reminders call as per changes (handled by remindersystem)
        
        # Register commands
        register_commands(bot)
        from cmds import setup
        setup(bot)
        
        synced = await bot.tree.sync()
        print(f'Synced {len(synced)} commands')
    except Exception as e:
        print(f'Error during startup: {e}')

@bot.event
async def on_guild_channel_create(channel):
    if isinstance(channel, discord.TextChannel):
        category = channel.category
        if category and category.id in CATEGORY_MESSAGES:
            await channel.send(CATEGORY_MESSAGES[category.id])

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
    if isinstance(error, discord.app_commands.CheckFailure):
        return
    else:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {error}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

# ----------------------
# UTILITY FUNCTIONS
# ----------------------
async def log_command_usage(ctx_or_interaction):
    """Handle both Context and Interaction objects for logging"""
    try:
        log_channel = bot.get_channel(bot_logs)
        if not log_channel:
            return

        if isinstance(ctx_or_interaction, commands.Context):
            user = ctx_or_interaction.author
            command = f"{prefix}{ctx_or_interaction.command.name}" if ctx_or_interaction.command else "!"
        else:
            user = ctx_or_interaction.user
            command = f"/{ctx_or_interaction.command.name}" if ctx_or_interaction.command else "!"

        embed = discord.Embed(
            description=f"User: {user.mention}, Command: {command}",
            color=BLUE
        )
        await log_channel.send(embed=embed)
    except Exception as e:
        print(f"Failed to log command: {e}")

# Assign to bot instance
bot.log_command_usage = log_command_usage

class DMPaginator(discord.ui.View):
    def __init__(self, messages, user):
        super().__init__(timeout=300)
        self.messages = messages  # Messages ordered: [newest, ..., oldest]
        self.user = user
        self.current_index = 0
        self.total = len(messages)
        self.update_buttons()

    def update_buttons(self):
        self.first_button.disabled = (self.current_index == 0)
        self.prev_button.disabled = (self.current_index == 0)
        self.next_button.disabled = (self.current_index == self.total - 1)
        self.last_button.disabled = (self.current_index == self.total - 1)

    def format_content(self, message):
        """Format message content with truncation if needed"""
        content = message.clean_content
        
        # Handle empty content
        if not content.strip():
            content = "*[No text content]*"
        
        # Handle long content
        if len(content) > 2000:
            content = content[:1997] + "..."
        
        return content

    def create_embed(self):
        msg = self.messages[self.current_index]
        
        embed = discord.Embed(
            title=f"Message to {self.user.display_name}",
            description=self.format_content(msg),
            color=BLUE,
            timestamp=msg.created_at
        )
        
        # Add metadata fields
        embed.add_field(name="Sent at", value=f"<t:{int(msg.created_at.timestamp())}:F>", inline=False)
        
        # Handle attachments
        if msg.attachments:
            attachments = "\n".join(
                [f"[{a.filename}]({a.url})" for a in msg.attachments[:5]]
            )
            if len(msg.attachments) > 5:
                attachments += f"\n+{len(msg.attachments)-5} more..."
            embed.add_field(name="Attachments", value=attachments, inline=False)
        
        # Add message counter
        embed.set_footer(text=f"Message {self.current_index+1}/{self.total} | ID: {msg.id}")
        
        return embed

    @discord.ui.button(label="<<", style=discord.ButtonStyle.secondary)
    async def first_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index = 0
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index -= 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index += 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label=">>", style=discord.ButtonStyle.secondary)
    async def last_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index = self.total - 1
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)

    @discord.ui.button(label="Exit", style=discord.ButtonStyle.danger)
    async def exit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.delete_original_response()
        self.stop()

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=self)
        except discord.NotFound:
            pass

def admin_only():
    async def predicate(interaction: discord.Interaction):
        admin_role_obj = interaction.guild.get_role(admin_role)
        if not admin_role_obj or admin_role_obj not in interaction.user.roles:
            embed = discord.Embed(description="# Error\nYou must be an admin to use this command.", color=BLUE)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            raise CheckFailure("User does not have the required admin role.")
        return True
    return app_commands.check(predicate)

def get_uptime():
    """Calculate and format the bot's uptime"""
    delta = datetime.now() - start_time
    hours, remainder = divmod(int(delta.total_seconds()), 3600)
    minutes, seconds = divmod(remainder, 60)
    days, hours = divmod(hours, 24)
    return f"{days}d {hours}h {minutes}m {seconds}s"

# ----------------------
# BOT COMMANDS
# ----------------------
@bot.command(name='help')
async def custom_help(ctx):
    """Show help information with all available commands"""
    # Get all commands from the bot
    all_commands = bot.commands
    
    # Organize commands by category
    command_categories = {
        "General": [],
        "Channel Management": [],
        "Admin": [],
        "Reminders": [],
        "Transactions": []
    }
    
    # Categorize commands
    for cmd in all_commands:
        if cmd.name in ['ping', 'info', 'help']:
            command_categories["General"].append(cmd)
        elif cmd.name in ['add', 'remove']:
            command_categories["Channel Management"].append(cmd)
        elif cmd.name in ['nuke', 'clone', 'rename', 'delete', 'purge']:
            command_categories["Admin"].append(cmd)
        elif cmd.name == 'remind':
            command_categories["Reminders"].append(cmd)
        elif cmd.name == 'txid':
            command_categories["Transactions"].append(cmd)
        else:
            command_categories["General"].append(cmd)
    
    # Build the embed
    embed = discord.Embed(
        title="Happy Box Bot Help",
        color=BLUE
    )
    
    # Add fields for each category
    for category, cmds in command_categories.items():
        if cmds:  # Only add category if it has commands
            # Sort commands alphabetically
            cmds_sorted = sorted(cmds, key=lambda x: x.name)
            command_list = "\n".join(
                f"`{prefix}{cmd.name}` - {cmd.help or 'No description available'}"
                for cmd in cmds_sorted
            )
            embed.add_field(
                name=f"**{category} Commands**",
                value=command_list,
                inline=False
            )
    
    # Add slash commands section
    slash_commands = [
        "`/client` - Manage client role",
        "`/vouch` - Give a vouch for a user",
        "`/role` - Manage roles for users",
        "`/purge` - Delete messages",
        "`/qr` - Show payment QR code",
        "`/mail` - Send a DM to a user",
        "`/userinfo` - Show user information",
        "`/records` - List all records",
        "`/queue-add` - Add to queue",
        "`/clear-records` - Clear records",
        "`/play` - Set playing status",
        "`/stream` - Set streaming status",
        "`/listen` - Set listening status",
        "`/watch` - Set watching status",
        "`/clear_status` - Clear bot status"
    ]
    
    embed.add_field(
        name="**Slash Commands**",
        value="\n".join(slash_commands),
        inline=False
    )
    
    embed.set_footer(text="Made with 💙 by Happy Box")
    await log_command_usage(ctx)
    await ctx.send(embed=embed)

@bot.command(name='info')
async def custom_info(ctx):
    """Show bot information"""
    uptime = get_uptime()
    latency = round(bot.latency * 1000)
    
    embed = discord.Embed(
        title="Happy Box Bot Information",
        description=(
            f"**Uptime:** {uptime}\n"
            f"**Server's:** {len(bot.guilds)}\n"
            f"**Latency:** {latency}ms\n"
            f"**Commands Processed:** {len(bot.commands)}\n"
            f"**Creator:** HBST Developers\n"
            "\n**Available Commands:**\n"
            "=info - Shows this information\n"
            "=ping - Checks bot latency\n"
            "=txid - Checks LTC transaction\n"
            "=nuke - Nukes a specific channel\n"
            "=clone - Clones a channel with same permissions\n"
            "=add - Adds a user to the channel\n"
            "=remove - Remove a user from a channel with\n"                
            "=rename - Renames a channel\n"
            "=delete - Deletes the current channel\n"
            "\n**Slash Commands:**\n"
            "/client - Manages client role\n"
            "/vouch - Gives a vouch for a user\n"
            "/role - Manages roles for users\n"
            "/purge - Deletes messages\n"
            "/qr - Shows payment QR code\n"
        ),
        color=BLUE
    )
    embed.set_footer(text="Made with 💙 by Happy Box")
    await log_command_usage(ctx)
    await ctx.send(embed=embed)

@bot.command(name='ping')
async def ping(ctx):
    """Check bot latency"""
    latency = round(bot.latency * 1000)  # Convert to ms
    embed = discord.Embed(
        description=f"🏓 Pong! Latency: {latency}ms",
        color=BLUE
    )
    await log_command_usage(ctx)
    await ctx.send(embed=embed)

# ----------------------
# USER INFO COMMAND
# ----------------------

@bot.tree.command(name="userinfo", description="Shows information about a user")
async def userinfo(interaction: discord.Interaction, member: discord.Member = None):
    try:
        if member is None:
            member = interaction.user

        # Fetch user with banner
        try:
            user = await bot.fetch_user(member.id)
        except:
            user = member

        sorted_roles = sorted(member.roles[1:], key=lambda r: r.position, reverse=True)
        highest_role = sorted_roles[0] if sorted_roles else None

        roles_display = "\n".join(f'> - {role.mention}' for role in sorted_roles) or "> - No roles"
        badges = sorted([role for role in sorted_roles if role.name in role_emojis], key=lambda r: r.position, reverse=True)
        badges_display = "\n".join(f'> - {role_emojis[role.name][0]} {role_emojis[role.name][1]}' for role in badges) or "> - No badges"

        embed = discord.Embed(
            title=f"__***{member.global_name or member.display_name}'s Profile***__",
            color=member.accent_color or (highest_role.color if highest_role else BLUE)
        )

        embed.set_thumbnail(url=member.display_avatar.url)

        # Add banner if available
        if hasattr(user, 'banner') and user.banner:
            embed.set_image(url=user.banner.url)

        embed.add_field(name="__User Info:__", value=(
            f"Username: `{member.name}`\n"
            f"User iD: `{member.id}`\n"
            f"Display Name: {member.global_name or member.display_name}\n"
            f"Mention: {member.mention}\n"
            f"Created: <t:{int(member.created_at.timestamp())}:R>\n"
            f"Banner color: `{str(highest_role.color) if highest_role else 'Default'}`"
        ), inline=False)

        embed.add_field(name="__Server Info:__", value=(
            f"Joined: <t:{int(member.joined_at.timestamp())}:R>"
        ), inline=False)

        embed.add_field(name="__Badges:__", value=badges_display, inline=False)
        embed.add_field(name="__Roles:__", value=roles_display, inline=False)

        embed.set_footer(text=f"Requested by {interaction.user.name}")

        await log_command_usage(interaction)
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)
        
# ----------------------
# ADMIN COMMANDS
# ----------------------

@bot.tree.command(name="say", description="Make the bot send a message in a channel.")
@admin_only()
@app_commands.describe(
    msg="The message you want the bot to send.",
    channel="The channel where the message should be sent. (Optional)",
    attachment="An optional file to attach to the message."
)
async def say_command(interaction: discord.Interaction, msg: str, channel: discord.TextChannel = None, attachment: discord.Attachment = None):
    try:
        await log_command_usage(interaction)
        await interaction.response.defer()
        target_channel = channel if channel else interaction.channel  

        if attachment:
            await target_channel.send(msg, file=await attachment.to_file())
        else:
            await target_channel.send(msg)
        await interaction.followup.send("Message sent!", ephemeral=True)
    except Exception as e:
        await interaction.followup.send(f"Failed to send message: {str(e)}", ephemeral=True)

@bot.tree.command(name="client", description="Gives or removes the client role from a user.")
async def client_command(interaction: discord.Interaction, user: discord.Member):
    try:
        # Check if user has manage_roles permission
        if not interaction.user.guild_permissions.manage_roles:
            embed = discord.Embed(description="# __Error__\nYou don't have permission to manage roles.", color=BLUE)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        await log_command_usage(interaction)
        role = interaction.guild.get_role(client_role)
        if not role:
            embed = discord.Embed(description="# __Error__\nClient role not found.", color=BLUE)
            await interaction.response.send_message(embed=embed)
            return
            
        # Check if bot has permission to manage this role
        if role.position >= interaction.guild.me.top_role.position:
            embed = discord.Embed(description="# __Error__\nI don't have permission to manage this role.", color=BLUE)
            await interaction.response.send_message(embed=embed)
            return
            
        if role in user.roles:
            await user.remove_roles(role)
            embed = discord.Embed(description=f"## __Client Role Removed:__\n***Successfully removed {role.mention} from {user.mention}.***", color=BLUE)
        else:
            await user.add_roles(role)
            embed = discord.Embed(description=f"## __Client Role Assigned:__\n***Successfully gave {role.mention} to {user.mention}.***", color=BLUE)
            
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        error_embed = discord.Embed(description=f"## __Error__\nAn error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed)

@bot.tree.command(name="vouch", description="Give a vouch for a user.")
@admin_only()
@app_commands.describe(
    user="The user who gets the vouch.",
    product_amt="The amount of the product.",
    product="The product being vouched for.",
    for_text="The price and payment method for the product."
)
async def vouch_command(interaction: discord.Interaction, user: discord.Member, product_amt: int, product: str, for_text: str):
    try:
        await log_command_usage(interaction)
        embed = discord.Embed(
            description=f"# __Vouch__\n```+rep {user.id} got {product_amt}x {product} for {for_text}, Legit!!```",
            color=BLUE
        )
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="role", description="Add or remove a role from a user.")
@app_commands.describe(
    user="The user to give/remove the role.",
    role="The role to be added or removed."
)
async def role_command(interaction: discord.Interaction, user: discord.Member, role: discord.Role):
    try:
        await log_command_usage(interaction)
        if not interaction.user.guild_permissions.manage_roles:
            embed = discord.Embed(description="You do not have permission to manage roles.", color=BLUE)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        if role in user.roles:
            await user.remove_roles(role)
            action = f"removed {role.mention} from"
        else:
            await user.add_roles(role)
            action = f"issued {role.mention} to"
            
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        embed = discord.Embed(
            description=f"## __Roles Assignment:__\n***{action} {user.mention} successfully!***",
            color=BLUE
        )
        embed.set_footer(text=f"Today at {current_time}")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="purge", description="Delete a specific number of messages from the channel.")
@admin_only()
@app_commands.describe(amt="The number of messages to delete.")
async def purge_command(interaction: discord.Interaction, amt: int):
    try:
        await log_command_usage(interaction)
        if amt <= 0:
            embed = discord.Embed(description="Please specify a valid number of messages to delete.", color=BLUE)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        await interaction.response.defer(ephemeral=True)
        deleted = await interaction.channel.purge(limit=amt)
        embed = discord.Embed(description=f"Successfully Deleted {len(deleted)} messages.", color=BLUE)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.followup.send(embed=error_embed, ephemeral=True)

@bot.tree.command(name="qr", description="Send UPI payment details")
@app_commands.checks.has_permissions(mute_members=True)
async def qr_command(interaction: discord.Interaction):
    try:
        await log_command_usage(interaction)
        embed = discord.Embed(
            title="**<:hb_UPI:1333397769343209483> KINDLY PAY ON THE GIVEN QR**",
            description=f"UPI ID: {upi_id}",
            color=BLUE
        )
        embed.set_image(url=upi_qr)
        embed.set_footer(text="PLEASE SEND SCREENSHOT ONCE DONE!")
        await interaction.response.send_message(embed=embed)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="mail", description="Send a direct message to a user.")
@admin_only()
@app_commands.describe(
    user="The user to send a direct message to.",
    message="The message to send to the user.",
    attachment="An optional file to attach to the message."
)
async def dm_command(interaction: discord.Interaction, user: discord.Member, message: str, attachment: discord.Attachment = None):
    try:
        await log_command_usage(interaction)
        await interaction.response.defer()
        if attachment:
            await user.send(message, file=await attachment.to_file())
        else:
            await user.send(message)
        embed = discord.Embed(description=f"***Delivered successfully!*** {user.mention}!", color=BLUE)
        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        embed = discord.Embed(description=f"Failed to send message to {user.mention}: {str(e)}", color=BLUE)
        await interaction.followup.send(embed=embed, ephemeral=True)

@bot.command(name='txid')
async def ltc_tx(ctx, tx_id: str):
    from datetime import datetime, timezone, timedelta
    
    # Permission check
    allowed_roles = ["≜ Happy Box Staff", "Administrator"]
    if not any(role.name in allowed_roles for role in ctx.author.roles):
        embed = discord.Embed(
            description=f"**DENIED!** {ctx.author.mention}, You're not allowed to use this command!",
            color=BLUE
        )
        await ctx.send(embed=embed)
        return

    try:
        await log_command_usage(ctx)
        
        if not tx_id:
            embed = discord.Embed(description="Please provide a transaction ID", color=BLUE)
            await ctx.send(embed=embed)
            return

        url = f'https://api.blockcypher.com/v1/ltc/main/txs/{tx_id}'
        try:
            response = requests.get(url)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            embed = discord.Embed(description=f'Error fetching transaction details: {e}', color=BLUE)
            await ctx.send(embed=embed)
            return

        data = response.json()
        try:
            # Get multiple currency rates
            price_response = requests.get('https://api.coingecko.com/api/v3/simple/price?ids=litecoin&vs_currencies=usd,inr,eur', timeout=10)
            price_response.raise_for_status()
            price_data = price_response.json()
            ltc_to_usd = price_data['litecoin']['usd']
            ltc_to_inr = price_data['litecoin']['inr']
            ltc_to_eur = price_data['litecoin']['eur']
        except requests.exceptions.RequestException as e:
            embed = discord.Embed(description=f'Error fetching exchange rates: {e}', color=BLUE)
            await ctx.send(embed=embed)
            return

        embed = discord.Embed(title='LTC Transaction Details', color=BLUE)
        
        # Calculate receiver amount (excluding change)
        outputs = data.get('outputs', [])
        inputs = data.get('inputs', [])
        
        input_addresses = set()
        for tx_input in inputs:
            input_addresses.update(tx_input.get('addresses', []))
        
        receiver_amount = 0
        receiver_outputs = []
        for output in outputs:
            addresses = output.get('addresses', [])
            if not any(addr in input_addresses for addr in addresses):
                receiver_amount += output.get('value', 0)
                receiver_outputs.append(output)
        
        receiver_amount_ltc = receiver_amount / 1e8
        
        # Confirmation status (moved to top)
        confirmations = data.get('confirmations', 0)
        
        # Format confirmation count display
        if confirmations >= 6:
            count_display = f"6+ | {confirmations}"
        else:
            count_display = f"{confirmations}/6"
        
        # Determine status and emoji
        if confirmations >= 6:
            status_emoji = "<a:hb_greentick:1356310199207723028>"
            status_text = "**Confirmed**"
        else:
            status_emoji = "<a:red_redtick:1356310209638699149>"
            status_text = "**Pending**"

        # Create confirmation status string
        confirmation_status = f"{status_emoji} {status_text} ( **{count_display}** )"
        embed.add_field(name='Confirmation Status:', value=confirmation_status, inline=False)
        
        # Receiver Amount
        embed.add_field(name='Receiver Amount:', value=f"{receiver_amount_ltc:.8f} LTC", inline=False)
        
        # Get and format transaction time in IST
        if data.get('confirmed'):
            tx_time_str = data['confirmed']
        elif data.get('received'):
            tx_time_str = data['received']
        else:
            tx_time_str = None

        if tx_time_str:
            try:
                # Handle both formats: with and without milliseconds
                if '.' in tx_time_str:
                    tx_time_utc = datetime.strptime(tx_time_str, '%Y-%m-%dT%H:%M:%S.%fZ').replace(tzinfo=timezone.utc)
                else:
                    tx_time_utc = datetime.strptime(tx_time_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
                
                # Convert to IST (UTC+5:30)
                ist_tz = timezone(timedelta(hours=5, minutes=30))
                tx_time_ist = tx_time_utc.astimezone(ist_tz)
                
                # Format IST time
                ist_time_str = tx_time_ist.strftime('%Y-%m-%d %H:%M:%S IST')
                
                # Format UTC time for Discord
                unix_timestamp = int(tx_time_utc.timestamp())
                discord_timestamp = f"<t:{unix_timestamp}:F> (<t:{unix_timestamp}:R>)"
                
                # Combine both time formats
                time_value = f"{discord_timestamp}"
                
            except ValueError:
                time_value = 'N/A'
        else:
            time_value = 'N/A'

        embed.add_field(name='Transaction Time:', value=time_value, inline=False)
        
        # Show only receiver outputs with USD, INR, and EURO values
        output_details = []
        for output in receiver_outputs:
            addresses = output.get("addresses", [])
            value = output.get("value", 0) / 1e8
            value_usd = value * ltc_to_usd
            value_inr = value * ltc_to_inr
            value_eur = value * ltc_to_eur
            
            # Only show the first address for each output
            if addresses:
                address = addresses[0]
                output_details.append(
                    f"- **Receiver Address:** {address}\n"
                    f"  - **Value Received:** {value:.8f} LTC ≈ ${value_usd:.2f} USD / ₹{value_inr:.2f} INR / €{value_eur:.2f} EUR\n"
                )
        
        if output_details:
            embed.add_field(name=f'Receiver Outputs: [{len(receiver_outputs)}]', 
                          value='\n'.join(output_details), 
                          inline=False)
        else:
            embed.add_field(name='Receiver Outputs:', 
                          value='No receiver outputs found', 
                          inline=False)

        await ctx.send(embed=embed)
    except Exception as e:
        embed = discord.Embed(description=f"An error occurred: {e}", color=BLUE)
        await ctx.send(embed=embed)
        
# ----------------------
# STATUS COMMANDS
# ----------------------

@bot.tree.command(name="play", description="Sets bot activity to `Playing`")
@admin_only()
async def play(interaction: discord.Interaction, game: str):
    try:
        await bot.change_presence(activity=discord.Game(name=game))
        embed = discord.Embed(description=f"Now Playing: {game}", color=BLUE)
        await log_command_usage(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="stream", description="Sets bot activity to `Streaming`")
@admin_only()
async def stream(interaction: discord.Interaction, title: str):
    try:
        activity = discord.Streaming(name=title, url="https://www.twitch.tv/wallibear")
        await bot.change_presence(activity=activity)
        embed = discord.Embed(description=f"Now Streaming: {title}", color=BLUE)
        await log_command_usage(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="listen", description="Sets bot activity to `Listening`")
@admin_only()
async def listen(interaction: discord.Interaction, title: str):
    try:
        activity = discord.Activity(type=discord.ActivityType.listening, name=title)
        await bot.change_presence(activity=activity)
        embed = discord.Embed(description=f"Now Listening to: {title}", color=BLUE)
        await log_command_usage(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="watch", description="Sets bot activity to `Watching`")
@admin_only()
async def watch(interaction: discord.Interaction, title: str):
    try:
        activity = discord.Activity(type=discord.ActivityType.watching, name=title)
        await bot.change_presence(activity=activity)
        embed = discord.Embed(description=f"Now Watching: {title}", color=BLUE)
        await log_command_usage(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

@bot.tree.command(name="clear_status", description="Clears bot activity")
@admin_only()
async def clear_status(interaction: discord.Interaction):
    try:
        await bot.change_presence(activity=None)
        embed = discord.Embed(description="Bot activity has been cleared!", color=BLUE)
        await log_command_usage(interaction)
        await interaction.response.send_message(embed=embed, ephemeral=True)
    except Exception as e:
        error_embed = discord.Embed(title="Error", description=f"An error occurred: {e}", color=BLUE)
        await interaction.response.send_message(embed=error_embed, ephemeral=True)

# ----------------------
# CHANNEL MANAGEMENT
# ----------------------

@bot.command(name="nuke")
@commands.has_permissions(administrator=True)
async def nuke_command(ctx):
    """Nuke the current channel: deletes and recreates the channel."""
    try:
        await log_command_usage(ctx)
        
        # Create the confirmation embed (BLUE color)
        confirm_embed = discord.Embed(
            title="<a:hb_alert:1356310188004606072> Nuke Confirmation",
            description=f"Are you sure you want to nuke {ctx.channel.mention}?\nThis action cannot be undone!",
            color=BLUE
        )
        confirm_embed.set_footer(text="You have 10 seconds to decide")

        # Custom View with Red "Yes" and Green "No" buttons
        class NukeConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=10.0)  # 10-second timeout
                self.value = None

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.red, emoji="<a:red_redtick:1356310209638699149>")
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You didn't initiate this nuke!", ephemeral=True)
                    return
                self.value = True
                self.stop()
                await interaction.message.delete()

            @discord.ui.button(label="No", style=discord.ButtonStyle.green, emoji="<a:hb_greentick:1356310199207723028>")
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You didn't initiate this nuke!", ephemeral=True)
                    return
                self.value = False
                self.stop()
                await interaction.message.delete()
                await ctx.send("Nuke cancelled.", delete_after=5)

            async def on_timeout(self):
                try:
                    await self.message.delete()
                    await ctx.send("**Timed out!** - Cancelled.", delete_after=5)
                except:
                    pass

        view = NukeConfirmView()
        view.message = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()

        if not view.value:
            return

        # Backup channel details
        channel = ctx.channel
        guild = ctx.guild
        channel_name = channel.name
        channel_category = channel.category
        channel_position = channel.position
        overwrites = channel.overwrites

        # Delete original channel
        await channel.delete(reason=f"Nuked by {ctx.author}")

        # Recreate channel
        new_channel = await guild.create_text_channel(
            name=channel_name,
            category=channel_category,
            position=channel_position,
            overwrites=overwrites,
            reason=f"Nuked by {ctx.author}"
        )

        # Send confirmation embed in new channel
        nuke_embed = discord.Embed(
            description=f"**Nuked By** `{ctx.author.name}`",
            color=BLUE
        )
        await new_channel.send(embed=nuke_embed)

    except Exception as e:
        embed = discord.Embed(description=f"Error during nuke: {str(e)}", color=BLUE)
        await ctx.send(embed=embed)

@bot.command(name='clone')
@commands.has_permissions(manage_channels=True)
async def clone_channel(ctx):
    """Clone the current channel with same permissions"""
    try:
        await log_command_usage(ctx)
        original_channel = ctx.channel
        
        # Create new channel with same properties
        new_channel = await original_channel.clone(reason=f"Channel cloned by {ctx.author}")
        
        # Send confirmation in original channel
        embed = discord.Embed(
            description=f"Successfully cloned channel {original_channel.mention} to {new_channel.mention}",
            color=BLUE
        )
        await ctx.send(embed=embed)
        
        # Send message in new channel
        cloned_embed = discord.Embed(
            description=f"Cloned {original_channel.mention}",
            color=BLUE
        )
        await new_channel.send(embed=cloned_embed)
        
    except Exception as e:
        embed = discord.Embed(
            description=f"Error cloning channel: {str(e)}",
            color=BLUE
        )
        await ctx.send(embed=embed)

@bot.command(name='rename')
@commands.has_permissions(manage_channels=True)
async def rename_channel(ctx, *, new_name: str):
    """Rename the current channel"""
    try:
        await log_command_usage(ctx)
        original_name = ctx.channel.name
        await ctx.channel.edit(name=new_name)
        
        embed = discord.Embed(
            description=f"Renamed from `{original_name}` to `{new_name}`",
            color=BLUE
        )
        await ctx.send(embed=embed)
        
    except Exception as e:
        embed = discord.Embed(
            description=f"Error renaming channel: {str(e)}",
            color=BLUE
        )
        await ctx.send(embed=embed)

@bot.command(name='delete')
@commands.has_permissions(manage_channels=True)
async def delete_channel(ctx):
    """Delete the current channel with confirmation"""
    try:
        await log_command_usage(ctx)
        # Create the confirmation embed
        confirm_embed = discord.Embed(
            title="<a:hb_alert:1356310188004606072> Delete Channel Confirmation",
            description=f"Are you sure you want to delete {ctx.channel.mention}?\nThis action cannot be undone!",
            color=BLUE
        )
        confirm_embed.set_footer(text="You have 10 seconds to decide")

        class DeleteConfirmView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=10.0)
                self.value = None

            @discord.ui.button(label="Yes", style=discord.ButtonStyle.red, emoji="<a:red_redtick:1356310209638699149>")
            async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You didn't initiate this deletion!", ephemeral=True)
                    return
                self.value = True
                self.stop()
                await interaction.message.delete()

            @discord.ui.button(label="No", style=discord.ButtonStyle.green, emoji="<a:hb_greentick:1356310199207723028>")
            async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
                if interaction.user != ctx.author:
                    await interaction.response.send_message("You didn't initiate this deletion!", ephemeral=True)
                    return
                self.value = False
                self.stop()
                await interaction.message.delete()
                await ctx.send("Channel deletion cancelled.", delete_after=5)

            async def on_timeout(self):
                try:
                    await self.message.delete()
                    await ctx.send("**Timed out!** - Cancelled.", delete_after=5)
                except:
                    pass

        view = DeleteConfirmView()
        view.message = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()

        if not view.value:
            return

        # Proceed with deletion
        channel_name = ctx.channel.name
        await ctx.channel.delete(reason=f"Channel deleted by {ctx.author}")
        
        # Log the deletion
        log_channel = bot.get_channel(bot_logs)
        if log_channel:
            embed = discord.Embed(
                description=f"Deleted channel `{channel_name}` by {ctx.author.mention}",
                color=BLUE
            )
            await log_channel.send(embed=embed)
            
    except Exception as e:
        embed = discord.Embed(
            description=f"Error deleting channel: {str(e)}",
            color=BLUE
        )
        await ctx.send(embed=embed)

@bot.tree.command(name="get_dms", description="Get what the bot has sent to a user's DMs (Admin only)")
@admin_only()
@app_commands.describe(
    user="The user whose DMs to check",
    limit="Number of messages to retrieve (default: 100)"
)
async def get_dms(interaction: discord.Interaction, user: discord.User, limit: int = 100):
    try:
        await log_command_usage(interaction)
        await interaction.response.defer(ephemeral=True)
        
        # Check DM access
        try:
            channel = user.dm_channel or await user.create_dm()
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"<a:hb_redtick:1356310209638699149> Cannot access DMs with {user.mention}. They may have DMs disabled.",
                color=BLUE
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get messages
        try:
            messages = []
            async for message in channel.history(limit=limit):
                if message.author == bot.user:
                    messages.append(message)
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"<a:hb_redtick:1356310209638699149> No permission to read message history in {user.mention}'s DMs.",
                color=BLUE
            )
            await interaction.followup.send(embed=embed)
            return
        
        if not messages:
            embed = discord.Embed(
                description=f"<a:hb_blue_alert:1378437322756067478> No messages from the bot found in {user.mention}'s DMs.",
                color=BLUE
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Create and send paginator
        paginator = DMPaginator(messages, user)
        paginator.message = await interaction.followup.send(
            embed=paginator.create_embed(),
            view=paginator,
            ephemeral=True
        )
        
    except Exception as e:
        error_embed = discord.Embed(
            title="⚠️ Error",
            description=f"```{e}```",
            color=BLUE
        )
        await interaction.followup.send(embed=error_embed)

@bot.tree.command(name="clear_dms", description="Delete bot's messages in a user's DMs")
@admin_only()
@app_commands.describe(
    user="The user whose DMs to clean",
    limit="Number of messages to check (default: 100)"
)
async def clear_dms(interaction: discord.Interaction, user: discord.User, limit: int = 100):
    try:
        await log_command_usage(interaction)
        await interaction.response.defer(ephemeral=True)
        
        # Check if we have DM channel with this user
        try:
            channel = user.dm_channel or await user.create_dm()
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"Cannot access DMs with {user.mention}. They may have DMs disabled.",
                color=BLUE
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Get messages
        try:
            messages = []
            async for message in channel.history(limit=limit):
                if message.author == bot.user:
                    messages.append(message)
        except discord.Forbidden:
            embed = discord.Embed(
                description=f"No permission to read message history in {user.mention}'s DMs.",
                color=BLUE
            )
            await interaction.followup.send(embed=embed)
            return
        
        if not messages:
            embed = discord.Embed(
                description=f"No messages from the bot found in {user.mention}'s DMs.",
                color=BLUE
            )
            await interaction.followup.send(embed=embed)
            return
        
        # Delete messages
        deleted = 0
        for message in messages:
            try:
                await message.delete()
                deleted += 1
                await asyncio.sleep(0.5)  # Rate limit prevention
            except discord.NotFound:
                continue
            except discord.Forbidden:
                continue
            except Exception as e:
                print(f"Error deleting message: {e}")
                continue
        
        embed = discord.Embed(
            description=f"Deleted {deleted} messages in {user.mention}'s DMs.",
            color=BLUE
        )
        await interaction.followup.send(embed=embed)
        
    except Exception as e:
        error_embed = discord.Embed(
            title="Error",
            description=f"An error occurred: {e}",
            color=BLUE
        )
        await interaction.followup.send(embed=error_embed)

# ----------------------
# BOT STARTUP
# ----------------------
if __name__ == "__main__":
    try:
        bot.run(token)
    except discord.LoginError:
        print("Invalid bot token - please check your config.yaml")
    except Exception as e:
        print(f"An error occurred while starting the bot: {e}")
