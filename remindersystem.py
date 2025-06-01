# remindersystem.py
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import time
import math
import re
from datetime import datetime, timedelta

# ----------------------
# CONSTANTS & CONFIG
# ----------------------
BLUE = 0x0000FF
REMINDERS_FILE = "reminders.yaml"
reminders_lock = asyncio.Lock()

# ----------------------
# REMINDER UTILITIES
# ----------------------
def save_reminders(reminders):
    """Save reminders to YAML file"""
    try:
        import yaml
        with open(REMINDERS_FILE, "w") as f:
            yaml.dump(reminders, f)
    except Exception as e:
        print(f"Failed to save reminders: {e}")

def load_reminders():
    """Load reminders from YAML file"""
    try:
        import yaml
        with open(REMINDERS_FILE, "r") as f:
            return yaml.safe_load(f) or []
    except FileNotFoundError:
        return []
    except Exception as e:
        print(f"Failed to load reminders: {e}")
        return []

async def delayed_send_reminder(bot, reminder, delay):
    """Wait for remaining time before sending reminder"""
    await asyncio.sleep(delay)
    await send_reminder(bot, reminder)
    
    # Remove the reminder from storage with thread safety
    async with reminders_lock:
        reminders = load_reminders()
        try:
            reminders.remove(reminder)
            save_reminders(reminders)
        except ValueError:
            pass  # Already removed

async def send_reminder(bot, reminder):
    """Send reminder to user"""
    user = bot.get_user(reminder['user_id'])
    channel = bot.get_channel(reminder['channel_id'])
    
    if user:
        try:
            await user.send(f"## <a:hb_timer:1356310162616356945> Reminder! \n- **Reason:** {reminder['message']} `[after {reminder['duration']}]`")
        except discord.Forbidden:
            if channel:
                await channel.send(f"{user.mention}, I couldn't DM your reminder!", delete_after=10)
    elif channel:
        await channel.send(f"## <a:hb_timer:1356310162616356945> Reminder! \n- **Reason:** {reminder['message']} `[after {reminder['duration']}]`")

def has_remind_permission(ctx=None, interaction=None):
    """Check if user has permission to use reminder commands"""
    if ctx:
        return ctx.author.guild_permissions.mute_members or any(role.id == 1288455526124097537 for role in ctx.author.roles)
    if interaction:
        return interaction.user.guild_permissions.mute_members or any(role.id == 1288455526124097537 for role in interaction.user.roles)
    return False

# ----------------------
# REMINDER PAGINATOR
# ----------------------
class RemindersPaginator(discord.ui.View):
    def __init__(self, reminders, user):
        super().__init__(timeout=300)
        self.reminders = reminders
        self.user = user
        self.current_index = 0
        self.total = len(reminders)
        self.update_buttons()

    def create_embed(self):
        """Create embed for current reminder"""
        reminder = self.reminders[self.current_index]
        end_time = reminder['end_time']
        time_left = end_time - time.time()
        
        # Format time left
        if time_left < 0:
            time_str = "Overdue!"
        else:
            days = time_left // 86400
            hours = (time_left % 86400) // 3600
            minutes = (time_left % 3600) // 60
            seconds = time_left % 60
            time_str = f"{int(days)}d {int(hours)}h {int(minutes)}m {int(seconds)}s"
        
        embed = discord.Embed(
            title=f"Reminder {self.current_index+1}/{self.total}",
            color=BLUE
        )
        embed.add_field(name="Message", value=reminder['message'], inline=False)
        embed.add_field(name="Duration", value=reminder['duration'], inline=False)
        embed.add_field(name="Time Left", value=time_str, inline=False)
        embed.add_field(name="Ends", value=f"<t:{end_time}:R>", inline=False)
        return embed
    
    def update_buttons(self):
        """Update button states based on current index"""
        self.prev_button.disabled = self.current_index <= 0
        self.next_button.disabled = self.current_index >= self.total - 1
    
    @discord.ui.button(label="<", style=discord.ButtonStyle.primary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index = max(0, self.current_index - 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    @discord.ui.button(label=">", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.current_index = min(self.total - 1, self.current_index + 1)
        self.update_buttons()
        await interaction.response.edit_message(embed=self.create_embed(), view=self)
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the command user can interact with the buttons"""
        return interaction.user.id == self.user.id

# ----------------------
# REMINDER COMMANDS
# ----------------------
def setup(bot):
    # Access bot's config
    global REMINDERS_FILE
    REMINDERS_FILE = bot.config.get("reminders_file", "reminders.yaml")
    
    @bot.command(name='remind')
    async def remind_command(ctx, duration: str, *, message: str = None):
        """Set a reminder (format: =remind 1d2h30m message)"""
        if not has_remind_permission(ctx=ctx):
            embed = discord.Embed(
                description=f"**DENIED!** {ctx.author.mention}, You're not allowed to use this command!",
                color=BLUE
            )
            await ctx.send(embed=embed)
            return

        try:
            if not message:
                embed = discord.Embed(description="Please provide a message for the timer.", color=BLUE)
                await ctx.send(embed=embed)
                return

            # Parse duration
            total_seconds = 0
            pattern = r"(\d+\.?\d*)([dDhHmMsS])"
            matches = re.findall(pattern, duration)
            
            if not matches:
                embed = discord.Embed(
                    description="Invalid duration format! Use combinations like 1d2h30m",
                    color=BLUE
                )
                await ctx.send(embed=embed)
                return

            for value, unit in matches:
                num = float(value)
                unit = unit.lower()
                if unit == 'd':
                    total_seconds += num * 86400
                elif unit == 'h':
                    total_seconds += num * 3600
                elif unit == 'm':
                    total_seconds += num * 60
                elif unit == 's':
                    total_seconds += num

            total_seconds = math.ceil(total_seconds)
            end_time = int(time.time()) + total_seconds

            # Save reminder
            reminder = {
                'user_id': ctx.author.id,
                'channel_id': ctx.channel.id,
                'end_time': end_time,
                'message': message,
                'duration': duration
            }
            
            async with reminders_lock:
                reminders = load_reminders()
                reminders.append(reminder)
                save_reminders(reminders)

            # Schedule reminder
            delay = end_time - time.time()
            if delay > 0:
                bot.loop.create_task(delayed_send_reminder(bot, reminder, delay))

            embed = discord.Embed(
                description=f"## <a:hb_timer:1356310162616356945> Reminder Successfully Set \n- **ends** <t:{end_time}:R>",
                color=BLUE
            )
            await ctx.send(embed=embed)

        except Exception as e:
            embed = discord.Embed(description=f"An error occurred: {e}", color=BLUE)
            await ctx.send(embed=embed)
    
    # ----------------------
    # REMINDERS SLASH COMMAND
    # ----------------------
    class RemoveReminderDropdown(discord.ui.Select):
        def __init__(self, reminders):
            self.reminders = reminders
            options = [
                discord.SelectOption(
                    label=f"Reminder {idx+1}",
                    description=f"{rem['message'][:50]}{'...' if len(rem['message']) > 50 else ''}",
                    value=str(idx)
                ) for idx, rem in enumerate(reminders)
            ]
            super().__init__(
                placeholder="Select a reminder to remove",
                min_values=1,
                max_values=1,
                options=options
            )
        
        async def callback(self, interaction: discord.Interaction):
            idx = int(self.values[0])
            reminder = self.reminders.pop(idx)
            
            # Update stored reminders
            async with reminders_lock:
                all_reminders = load_reminders()
                try:
                    all_reminders.remove(reminder)
                    save_reminders(all_reminders)
                except ValueError:
                    pass
            
            # Update message
            if not self.reminders:
                await interaction.response.edit_message(
                    content="All your reminders have been removed",
                    embed=None,
                    view=None
                )
            else:
                embed = discord.Embed(
                    title="Your Active Reminders",
                    description="Reminder removed successfully!",
                    color=BLUE
                )
                await interaction.response.edit_message(embed=embed, view=RemindersView(self.reminders))

    class RemindersView(discord.ui.View):
        def __init__(self, reminders):
            super().__init__()
            self.reminders = reminders
            self.add_item(RemoveReminderDropdown(reminders))
        
        @discord.ui.button(label="Done", style=discord.ButtonStyle.green)
        async def done(self, interaction: discord.Interaction, button: discord.ui.Button):
            await interaction.response.defer()
            await interaction.delete_original_response()

    @bot.tree.command(name="reminders", description="View and manage your reminders")
    async def reminders_command(interaction: discord.Interaction):
        """List and manage reminders"""
        if not has_remind_permission(interaction=interaction):
            embed = discord.Embed(
                description="You don't have permission to use this command!",
                color=BLUE
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Get user's reminders
        async with reminders_lock:
            reminders = load_reminders()
            user_reminders = [r for r in reminders if r['user_id'] == interaction.user.id]
        
        if not user_reminders:
            embed = discord.Embed(
                description="You have no active reminders!",
                color=BLUE
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Send reminders list
        if len(user_reminders) == 1:
            # Single reminder - show details directly
            paginator = RemindersPaginator(user_reminders, interaction.user)
            await interaction.response.send_message(embed=paginator.create_embed(), view=paginator, ephemeral=True)
        else:
            # Multiple reminders - show management view
            embed = discord.Embed(
                title="Your Active Reminders",
                description="Select a reminder to remove or use arrows to navigate",
                color=BLUE
            )
            await interaction.response.send_message(embed=embed, view=RemindersView(user_reminders), ephemeral=True)
