import discord
from discord import app_commands
from discord.app_commands import CheckFailure
import yaml
import json
import os

# Load configuration
with open("config.yaml", "r") as file:
    config = yaml.safe_load(file)

queue_channel_id = config.get("queue_channel", None)
records_file = "records.json"
admin_role = config["admin_role"]
BLUE = 0x0000FF
bot_logs = config["bot_logs"]

async def log_command_usage(interaction: discord.Interaction):
    log_channel = interaction.guild.get_channel(bot_logs)
    if log_channel:
        embed = discord.Embed(description=f":User    {interaction.user.mention}, Command: /{interaction.command.name}", color=BLUE)
        await log_channel.send(embed=embed)

def admin_only():
    async def predicate(interaction: discord.Interaction):
        admin_role_obj = interaction.guild.get_role(admin_role)
        if not admin_role_obj or admin_role_obj not in interaction.user.roles:
            embed = discord.Embed(description="# Error\nYou must be an admin to use this command.", color=BLUE)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            raise CheckFailure("User  does not have the required admin role.")
        return True
    return app_commands.check(predicate)

def load_records():
    if os.path.exists(records_file):
        with open(records_file, "r") as file:
            try:
                data = json.load(file)
                if isinstance(data, list): 
                    return data
            except json.JSONDecodeError:
                print("⚠️ records.json is corrupted! Resetting file.")
        return [] 
    return []

def save_records(records_list):
    with open(records_file, "w") as file:
        json.dump(records_list, file, indent=4)

def register_commands(bot):
    @bot.tree.command(name="records", description="Lists all records in records.json")
    @admin_only()
    async def show_records(interaction: discord.Interaction):
        await log_command_usage(interaction)
        records_list = load_records()

        if not records_list:
            await interaction.response.send_message("The records are currently empty.", ephemeral=True)
            return

        records_text = "\n".join([f"{record['user']} | {record['product']} | {record['quantity']} | {record['mop']} - {record['additional_text']} - Handled by: {record['handled_by']}" for record in records_list])
        embed = discord.Embed(color=0x0000FF, description=f"# __Records__\n**{records_text}**")
        await interaction.response.send_message(embed=embed)

    @bot.tree.command(name="queue-add", description="Adds a new entry to records")
    @admin_only()
    async def add_to_records(
        interaction: discord.Interaction, 
        user: discord.Member, 
        product: str, 
        mop: str,  # Payment method
        quantity: int, 
        additional_text: str, 
        handled_by: discord.Member,
        dm: bool = False,  # Optional parameter for DM
        channel: discord.TextChannel = None  # Optional parameter for channel mentions
    ):
        await log_command_usage(interaction)
        records_list = load_records()

        # Create the record entry
        record_entry = {
            "user": user.mention,
            "product": product,
            "mop": mop,  # Store the payment method
            "quantity": quantity,
            "additional_text": additional_text,
            "handled_by": handled_by.mention
        }
        records_list.append(record_entry)
        save_records(records_list)

        # Format the message as plain text
        message = (
            f"_ _ \n             —  𝘊𝘢𝘳𝘵 𝘘𝘶𝘦𝘶𝘦\n"
            f"          <:hb_bag:1314601083854655488> {user.mention} : {channel.mention if channel else'No channel mentioned'}\n\n"
            f"          <:hb_replya:1354443545905205319> ( {quantity} ) ◟ __{product}__\n"
            f"          <:hb_replyb:1354443566876856320> mop: __{mop}__\n"
            f"          <:hb_replyc:1354443589501063229> {additional_text}\n\n"
            f"-# _ _           <:hb_staff:1354443521892941936> assisted by : {handled_by.mention}"
        )

        # Send the message to the configured queue channel
        target_channel = interaction.client.get_channel(queue_channel_id)
        
        if target_channel:
            await interaction.response.send_message("Successfully Added!")
            await target_channel.send(message)  # Send as plain text
            
            # Send DM if the parameter is True
            if dm:
                await user.send(f"*Your order is confirmed!*:\n{message}")
        else:
            await interaction.response.send_message("⚠️ Queue channel not found!", ephemeral=True)

    @bot.tree.command(name="clear-records", description="Clears all records from records.json")
    @admin_only()
    async def clear_records(interaction: discord.Interaction):
        await log_command_usage(interaction)
        save_records([])  # Clear the records by saving an empty list
        await interaction.response.send_message("✅ All records have been cleared.", ephemeral=True)
