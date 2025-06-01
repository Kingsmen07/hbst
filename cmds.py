import discord
from discord.ext import commands
from discord import app_commands

BLUE = 0x0000FF

def setup(bot):
    """
    Registers prefix commands with the bot
    """
    @bot.command(name="add", aliases=['+'])
    async def add_access(ctx, *, target: str):
        """Adds a user or role to the current channel
        *Usage: =add <user or role mention/id>*
        """
        try:
            # Log command usage
            await ctx.bot.log_command_usage(ctx)

            # Check permissions and context
            if not ctx.guild:
                return await ctx.send("This command only works in servers!")
            
            if not ctx.author.guild_permissions.manage_channels:
                embed = discord.Embed(
                    title="**DENIED!**",
                    description="You need `Manage Channels` permission to use this command.",
                    color=BLUE
                )
                return await ctx.send(embed=embed)
            
            # Try to convert to Member or Role
            try:
                # Try member first
                target_obj = await commands.MemberConverter().convert(ctx, target)
                target_type = "member"
            except commands.MemberNotFound:
                try:
                    # Try role if member not found
                    target_obj = await commands.RoleConverter().convert(ctx, target)
                    target_type = "role"
                except commands.RoleNotFound:
                    embed = discord.Embed(
                        description=f"❌ User or Role `{discord.utils.escape_markdown(target)}` not found.",
                        color=BLUE
                    )
                    return await ctx.send(embed=embed)
            
            # Check permissions for target
            if target_type == "member":
                permissions = ctx.channel.permissions_for(target_obj)
                if permissions.read_messages:
                    embed = discord.Embed(
                        description=f"***<a:hb_blue_alert:1378437322756067478> {target_obj.mention} already has access to {ctx.channel.mention}***",
                        color=BLUE
                    )
                    return await ctx.send(embed=embed)
            else:  # role
                overwrites = ctx.channel.overwrites_for(target_obj)
                if overwrites.read_messages:
                    embed = discord.Embed(
                        description=f"***<a:hb_blue_alert:1378437322756067478> Role {target_obj.mention} already has access to {ctx.channel.mention}***",
                        color=BLUE
                    )
                    return await ctx.send(embed=embed)
            
            # Grant access
            await ctx.channel.set_permissions(target_obj, read_messages=True, send_messages=True)
            
            # Success message
            if target_type == "member":
                embed = discord.Embed(
                    description=f"***<a:hb_greentick:1356310199207723028> {target_obj.mention} added to {ctx.channel.mention}***",
                    color=BLUE
                )
            else:
                embed = discord.Embed(
                    description=f"***<a:hb_greentick:1356310199207723028> Role {target_obj.mention} added to {ctx.channel.mention}***",
                    color=BLUE
                )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ I don't have permission to modify channel permissions!",
                color=BLUE
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"❌ Error: {str(e)}",
                color=BLUE
            )
            await ctx.send(embed=embed)

    @bot.command(name="remove", aliases=['-'])
    async def remove_access(ctx, *, target: str):
        """Removes a user or role from the current channel
        *Usage: =remove <user or role mention/id>*
        """
        try:
            # Log command usage
            await ctx.bot.log_command_usage(ctx)

            # Check permissions and context
            if not ctx.guild:
                return await ctx.send("This command only works in servers!")
            
            if not ctx.author.guild_permissions.manage_channels:
                embed = discord.Embed(
                    title="**DENIED!**",
                    description="You need `Manage Channels` permission to use this command.",
                    color=BLUE
                )
                return await ctx.send(embed=embed)
            
            # Try to convert to Member or Role
            try:
                # Try member first
                target_obj = await commands.MemberConverter().convert(ctx, target)
                target_type = "member"
            except commands.MemberNotFound:
                try:
                    # Try role if member not found
                    target_obj = await commands.RoleConverter().convert(ctx, target)
                    target_type = "role"
                except commands.RoleNotFound:
                    embed = discord.Embed(
                        description=f"❌ User or Role `{discord.utils.escape_markdown(target)}` not found.",
                        color=BLUE
                    )
                    return await ctx.send(embed=embed)
            
            # Check permissions for target
            if target_type == "member":
                permissions = ctx.channel.permissions_for(target_obj)
                if not permissions.read_messages:
                    embed = discord.Embed(
                        description=f"***<a:hb_blue_alert:1378437322756067478> {target_obj.mention} already doesn't have access to {ctx.channel.mention}***",
                        color=BLUE
                    )
                    return await ctx.send(embed=embed)
            else:  # role
                overwrites = ctx.channel.overwrites_for(target_obj)
                if not overwrites.read_messages:
                    embed = discord.Embed(
                        description=f"***<a:hb_blue_alert:1378437322756067478> Role {target_obj.mention} already doesn't have access to {ctx.channel.mention}***",
                        color=BLUE
                    )
                    return await ctx.send(embed=embed)
            
            # Remove access
            await ctx.channel.set_permissions(target_obj, overwrite=None)
            
            # Success message
            if target_type == "member":
                embed = discord.Embed(
                    description=f"***<a:hb_redtick:1356310209638699149> {target_obj.mention} removed from {ctx.channel.mention}***",
                    color=BLUE
                )
            else:
                embed = discord.Embed(
                    description=f"***<a:hb_redtick:1356310209638699149> Role {target_obj.mention} removed from {ctx.channel.mention}***",
                    color=BLUE
                )
            await ctx.send(embed=embed)

        except discord.Forbidden:
            embed = discord.Embed(
                description="❌ I don't have permission to modify channel permissions!",
                color=BLUE
            )
            await ctx.send(embed=embed)
        except Exception as e:
            embed = discord.Embed(
                description=f"❌ Error: {str(e)}",
                color=BLUE
            )
            await ctx.send(embed=embed)

    print(f"Channel access commands registered: add, remove")
