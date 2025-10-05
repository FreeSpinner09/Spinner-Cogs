import discord
from discord import ui
from redbot.core import commands, Config, checks
from redbot.core.utils.chat_formatting import humanize_timedelta, pagify, box
from redbot.core.utils.menus import menu, DEFAULT_CONTROLS
import logging
from typing import Optional, List, Dict, Union
import asyncio
import time
import re
from datetime import timedelta

log = logging.getLogger("red.spinnerModeration")

ACTION_COLORS = {
    "warn": discord.Color.yellow(),
    "mute": discord.Color.orange(),
    "kick": discord.Color.red(),
    "ban": discord.Color.dark_red(),
    "unmute": discord.Color.green(),
    "unban": discord.Color.green(),
    "purge": discord.Color.blue(),
}

def is_mod_or_admin():
    async def predicate(ctx):
        if not ctx.guild:
            return False
        guild_conf = await ctx.cog.config.guild(ctx.guild).all()
        if ctx.author.guild_permissions.administrator:
            return True
        if guild_conf["sync_red_perms"]:
            if await checks.mod_or_permissions(manage_messages=True)(ctx):
                return True
        if any(role.id in guild_conf["mod_roles"] for role in ctx.author.roles):
            return True
        if any(role.id in guild_conf["admin_roles"] for role in ctx.author.roles):
            return True
        raise commands.CheckFailure("You do not have sufficient permissions to use this command.")
    return commands.check(predicate)

def admin_check():
    async def predicate(ctx):
        if not ctx.guild:
            return False
        guild_conf = await ctx.cog.config.guild(ctx.guild).all()
        if ctx.author.guild_permissions.administrator:
            return True
        if guild_conf["sync_red_perms"]:
            if await checks.admin_or_permissions(manage_guild=True)(ctx):
                return True
        if any(role.id in guild_conf["admin_roles"] for role in ctx.author.roles):
            return True
        raise commands.CheckFailure("You do not have admin permissions for this command.")
    return commands.check(predicate)

class SpinnerModeration(commands.Cog):
    """Advanced modular moderation system with point-based warns, logging, and GUI config."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xDEAD2025)
        default_global = {"version": "1.0"}
        self.config.register_global(**default_global)
        default_guild = {
            "mod_roles": [],
            "admin_roles": [],
            "modlog_channel": None,
            "dm_notify": False,
            "dm_message_template": "You have received a {action} in {guild}.\nReason: {reason}\nDuration: {duration}\nTotal Points: {points}",
            "warn_reasons": {},
            "punishments": [],
            "mute_role": None,
            "sync_red_perms": False,
        }
        self.config.register_guild(**default_guild)
        default_member = {"warnings": []}
        self.config.register_member(**default_member)

    async def cog_load(self):
        log.info("SpinnerModeration cog loaded.")

    async def cog_unload(self):
        log.info("SpinnerModeration cog unloaded.")

    # Helper Functions

    async def is_mod(self, ctx: commands.Context) -> bool:
        if ctx.author.guild_permissions.administrator:
            return True
        guild_conf = await self.config.guild(ctx.guild).all()
        if guild_conf["sync_red_perms"]:
            if await checks.mod_or_permissions(manage_messages=True)(ctx):
                return True
        return any(role.id in guild_conf["mod_roles"] for role in ctx.author.roles)

    async def is_admin(self, ctx: commands.Context) -> bool:
        if ctx.author.guild_permissions.administrator:
            return True
        guild_conf = await self.config.guild(ctx.guild).all()
        if guild_conf["sync_red_perms"]:
            if await checks.admin_or_permissions(manage_guild=True)(ctx):
                return True
        return any(role.id in guild_conf["admin_roles"] for role in ctx.author.roles)

    async def get_points(self, member: discord.Member) -> int:
        await self.check_expired_warnings(member)
        warnings = await self.config.member(member).warnings()
        return sum(w["points"] for w in warnings if w["permanent"] or w["expires"] > time.time())

    async def check_expired_warnings(self, member: discord.Member):
        current_time = time.time()
        async with self.config.member(member).warnings() as warnings:
            warnings[:] = [w for w in warnings if w["permanent"] or w["expires"] > current_time]

    async def apply_auto_punishment(self, ctx: commands.Context, member: discord.Member):
        points = await self.get_points(member)
        punishments = await self.config.guild(ctx.guild).punishments()
        if not punishments:
            return
        punishments = sorted(punishments, key=lambda p: p["points"], reverse=True)
        for p in punishments:
            if points >= p["points"]:
                action = p["action"]
                duration = p.get("duration")
                reason = f"Auto-punishment for reaching {points} points."
                if action == "mute":
                    await self.mute_member(ctx.guild, member, duration, reason)
                elif action == "kick":
                    await member.kick(reason=reason)
                    await self.log_action(ctx.guild, "kick", member, self.bot.user, reason)
                elif action == "ban":
                    await member.ban(reason=reason)
                    await self.log_action(ctx.guild, "ban", member, self.bot.user, reason)
                break

    async def log_action(self, guild: discord.Guild, action: str, user: Union[discord.Member, discord.User], moderator: Union[discord.Member, discord.User], reason: str, points: Optional[int] = None, duration: Optional[str] = None):
        channel_id = await self.config.guild(guild).modlog_channel()
        if not channel_id:
            return
        channel = guild.get_channel(channel_id)
        if not channel:
            return
        embed = discord.Embed(title=f"🔨 {action.capitalize()}ed", color=ACTION_COLORS.get(action.lower(), discord.Color.blurple()))
        embed.add_field(name="User", value=user.mention, inline=False)
        embed.add_field(name="Moderator", value=moderator.mention, inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        if points is not None:
            embed.add_field(name="Points", value=str(points), inline=False)
        if duration:
            embed.add_field(name="Duration", value=duration, inline=False)
        embed.timestamp = discord.utils.utcnow()
        embed.set_footer(text=f"User ID: {user.id}")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning(f"Missing permissions to send in modlog channel {channel_id}.")
        except discord.HTTPException as e:
            log.error(f"Failed to send log: {e}")

    async def send_dm_notification(self, user: discord.User, guild: discord.Guild, action: str, reason: str, points: int, duration: Optional[str] = "Permanent"):
        dm_notify = await self.config.guild(guild).dm_notify()
        if not dm_notify:
            return
        template = await self.config.guild(guild).dm_message_template()
        msg = template.format(user=user.name, action=action, reason=reason, points=points, duration=duration, guild=guild.name)
        try:
            await user.send(msg)
        except discord.Forbidden:
            pass
        except discord.HTTPException as e:
            log.error(f"Failed to DM user {user.id}: {e}")

    def parse_duration(self, duration_str: str) -> Optional[int]:
        if not duration_str:
            return None
        total_seconds = 0
        matches = re.findall(r"(\\d+)([smhdw])", duration_str.lower())
        for value, unit in matches:
            value = int(value)
            if unit == "s":
                total_seconds += value
            elif unit == "m":
                total_seconds += value * 60
            elif unit == "h":
                total_seconds += value * 3600
            elif unit == "d":
                total_seconds += value * 86400
            elif unit == "w":
                total_seconds += value * 604800
        return total_seconds if total_seconds > 0 else None

    async def mute_member(self, guild: discord.Guild, member: discord.Member, duration_seconds: Optional[int], reason: str):
        mute_role_id = await self.config.guild(guild).mute_role()
        if mute_role_id:
            mute_role = guild.get_role(mute_role_id)
            if mute_role:
                try:
                    await member.add_roles(mute_role, reason=reason)
                except discord.Forbidden:
                    log.warning(f"Missing permissions to add mute role to {member.id}.")
        if duration_seconds:
            timeout_until = discord.utils.utcnow() + timedelta(seconds=duration_seconds)
            try:
                await member.timeout(until=timeout_until, reason=reason)
            except discord.Forbidden:
                log.warning(f"Missing permissions to timeout {member.id}.")
        await self.log_action(guild, "mute", member, self.bot.user if not hasattr(self, 'ctx') else self.ctx.author, reason, duration=humanize_timedelta(timedelta=timedelta(seconds=duration_seconds)) if duration_seconds else None)

    async def unmute_member(self, guild: discord.Guild, member: discord.Member, reason: str = "Unmuted"):
        mute_role_id = await self.config.guild(guild).mute_role()
        if mute_role_id:
            mute_role = guild.get_role(mute_role_id)
            if mute_role:
                try:
                    await member.remove_roles(mute_role, reason=reason)
                except discord.Forbidden:
                    log.warning(f"Missing permissions to remove mute role from {member.id}.")
        try:
            await member.timeout(until=None, reason=reason)
        except discord.Forbidden:
            log.warning(f"Missing permissions to remove timeout from {member.id}.")
        await self.log_action(guild, "unmute", member, self.bot.user if not hasattr(self, 'ctx') else self.ctx.author, reason)

    # Commands

    @commands.hybrid_command(name="warn")
    @commands.guild_only()
    @is_mod_or_admin()
    async def warn(self, ctx: commands.Context, member: discord.Member, *, reason: str):
        """Issues a warning to a member and checks for auto-punishments.

        This adds points based on the reason and may trigger punishments.
        """
        if member.top_role >= ctx.author.top_role:
            return await ctx.send("You cannot warn a member with equal or higher role.")
        if member == ctx.author:
            return await ctx.send("You cannot warn yourself.")
        guild_conf = await self.config.guild(ctx.guild).all()
        warn_reasons = guild_conf["warn_reasons"]
        points = 1
        duration_seconds = None
        permanent = True
        if reason in warn_reasons:
            r = warn_reasons[reason]
            points = r["points"]
            permanent = r.get("permanent", True)
            duration_seconds = r.get("duration")
        expires = int(time.time() + duration_seconds) if duration_seconds else None
        warning = {
            "reason": reason,
            "points": points,
            "permanent": permanent,
            "expires": expires,
            "moderator": ctx.author.id,
            "date": int(time.time())
        }
        async with self.config.member(member).warnings() as warnings:
            warnings.append(warning)
        total_points = await self.get_points(member)
        duration_str = humanize_timedelta(timedelta=timedelta(seconds=duration_seconds)) if duration_seconds else "Permanent"
        await self.send_dm_notification(member, ctx.guild, "warning", reason, total_points, duration_str)
        await self.log_action(ctx.guild, "warn", member, ctx.author, reason, total_points, duration_str)
        await ctx.send(f"{member.mention} has been warned for: {reason}. Total points: {total_points}.")
        await self.apply_auto_punishment(ctx, member)

    @commands.hybrid_command(name="warnings")
    @commands.guild_only()
    @is_mod_or_admin()
    async def warnings(self, ctx: commands.Context, member: discord.Member):
        """Displays all warnings for a member."""
        await self.check_expired_warnings(member)
        warnings = await self.config.member(member).warnings()
        if not warnings:
            return await ctx.send(f"{member} has no warnings.")
        active = [w for w in warnings if w["permanent"] or w["expires"] > time.time()]
        expired = [w for w in warnings if not w["permanent"] and w["expires"] <= time.time()]
        embed = discord.Embed(title=f"Warnings for {member}", color=discord.Color.yellow())
        if active:
            active_str = "\n".join(f"**Reason:** {w['reason']} | **Points:** {w['points']} | **Date:** {discord.utils.format_dt(discord.utils.utcnow().replace(timestamp=w['date']))} | **Expires:** {'Permanent' if w['permanent'] else discord.utils.format_dt(discord.utils.utcnow().replace(timestamp=w['expires']))}" for w in active)
            for page in pagify(active_str, page_length=1024):
                embed.add_field(name="Active Warnings", value=page, inline=False)
        if expired:
            expired_str = "\n".join(f"**Reason:** {w['reason']} | **Points:** {w['points']} | **Expired:** {discord.utils.format_dt(discord.utils.utcnow().replace(timestamp=w['expires']))}" for w in expired)
            for page in pagify(expired_str, page_length=1024):
                embed.add_field(name="Expired Warnings", value=page, inline=False)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="clearwarns")
    @commands.guild_only()
    @is_mod_or_admin()
    async def clearwarns(self, ctx: commands.Context, member: discord.Member):
        """Clears all warnings for a member (with confirmation)."""
        view = ui.View(timeout=30)
        confirm_btn = ui.Button(label="Confirm", style=discord.ButtonStyle.danger)
        cancel_btn = ui.Button(label="Cancel", style=discord.ButtonStyle.secondary)
        async def confirm_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return
            await self.config.member(member).warnings.set([])
            await interaction.response.edit_message(content=f"Warnings cleared for {member}.", view=None)
            await self.log_action(ctx.guild, "clearwarns", member, ctx.author, "All warnings cleared")
        async def cancel_callback(interaction: discord.Interaction):
            if interaction.user != ctx.author:
                return
            await interaction.response.edit_message(content="Operation cancelled.", view=None)
        confirm_btn.callback = confirm_callback
        cancel_btn.callback = cancel_callback
        view.add_item(confirm_btn)
        view.add_item(cancel_btn)
        await ctx.send(f"Are you sure you want to clear all warnings for {member}?", view=view, ephemeral=True)

    @commands.hybrid_group(name="reason")
    @commands.guild_only()
    @is_mod_or_admin()
    async def reason_group(self, ctx: commands.Context):
        """Manage warn reasons."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @reason_group.command(name="add")
    async def reason_add(self, ctx: commands.Context, name: str, points: int, *, args: str):
        """Add or edit a warn reason.

        Usage: [p]reason add <name> <points> [duration] [--perm]
        """
        args_list = args.split()
        permanent = False
        duration_str = None
        if args_list and args_list[-1] == "--perm":
            permanent = True
            args_list.pop()
        if args_list:
            duration_str = " ".join(args_list)
        duration_seconds = self.parse_duration(duration_str)
        permanent = permanent or duration_seconds is None
        async with self.config.guild(ctx.guild).warn_reasons() as reasons:
            reasons[name] = {
                "points": points,
                "permanent": permanent,
                "duration": duration_seconds
            }
        await ctx.send(f"Reason '{name}' added/updated.")

    @reason_group.command(name="remove")
    async def reason_remove(self, ctx: commands.Context, name: str):
        """Remove a warn reason."""
        async with self.config.guild(ctx.guild).warn_reasons() as reasons:
            if name in reasons:
                del reasons[name]
                await ctx.send(f"Reason '{name}' removed.")
            else:
                await ctx.send(f"Reason '{name}' not found.")

    @reason_group.command(name="list")
    async def reason_list(self, ctx: commands.Context):
        """List all warn reasons."""
        reasons = await self.config.guild(ctx.guild).warn_reasons()
        if not reasons:
            return await ctx.send("No warn reasons configured.")
        desc = "\n".join(f"**{name}**: Points: {r['points']}, Permanent: {r['permanent']}, Duration: {humanize_timedelta(timedelta=timedelta(seconds=r['duration'])) if r.get('duration') else 'N/A'}" for name, r in reasons.items())
        embed = discord.Embed(title="Warn Reasons", description=desc)
        await ctx.send(embed=embed)

    @commands.hybrid_group(name="punishments")
    @commands.guild_only()
    @is_mod_or_admin()
    async def punishments_group(self, ctx: commands.Context):
        """Manage auto-punishments."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @punishments_group.command(name="list")
    async def punishments_list(self, ctx: commands.Context):
        """List configured punishments."""
        punishments = await self.config.guild(ctx.guild).punishments()
        if not punishments:
            return await ctx.send("No punishments configured.")
        desc = "\n".join(f"**{p['points']} points**: {p['action'].capitalize()} (Duration: {humanize_timedelta(timedelta=timedelta(seconds=p.get('duration', 0))) if p.get('duration') else 'Permanent'})" for p in sorted(punishments, key=lambda p: p["points"]))
        embed = discord.Embed(title="Auto-Punishments", description=desc)
        await ctx.send(embed=embed)

    @punishments_group.command(name="add")
    async def punishments_add(self, ctx: commands.Context, points: int, action: str, duration: Optional[str] = None):
        """Add or update a punishment threshold."""
        action = action.lower()
        if action not in ["mute", "kick", "ban", "warn"]:
            return await ctx.send("Invalid action. Must be mute, kick, ban, or warn.")
        duration_seconds = self.parse_duration(duration)
        async with self.config.guild(ctx.guild).punishments() as pun:
            for p in pun:
                if p["points"] == points:
                    p["action"] = action
                    p["duration"] = duration_seconds
                    break
            else:
                pun.append({"points": points, "action": action, "duration": duration_seconds})
        await ctx.send(f"Punishment for {points} points added/updated.")

    @punishments_group.command(name="remove")
    async def punishments_remove(self, ctx: commands.Context, points: int):
        """Remove a punishment threshold."""
        async with self.config.guild(ctx.guild).punishments() as pun:
            pun[:] = [p for p in pun if p["points"] != points]
        await ctx.send(f"Punishment for {points} points removed.")

    @punishments_group.command(name="gui")
    async def punishments_gui(self, ctx: commands.Context):
        """Opens an interactive GUI for managing punishments."""
        view = PunishmentSetupView(self, ctx.guild)
        embed = await view.get_embed()
        await ctx.send(embed=embed, view=view, ephemeral=True)

    @commands.hybrid_command(name="mute")
    @commands.guild_only()
    @is_mod_or_admin()
    async def mute(self, ctx: commands.Context, member: discord.Member, duration: Optional[str] = None, *, reason: str = "No reason provided"):
        """Mutes a member with optional duration."""
        duration_seconds = self.parse_duration(duration)
        duration_str = humanize_timedelta(timedelta=timedelta(seconds=duration_seconds)) if duration_seconds else "Permanent"
        await self.mute_member(ctx.guild, member, duration_seconds, reason)
        total_points = await self.get_points(member)
        await self.send_dm_notification(member, ctx.guild, "mute", reason, total_points, duration_str)
        await ctx.send(f"{member.mention} has been muted. Duration: {duration_str}.")
        await self.log_action(ctx.guild, "mute", member, ctx.author, reason, duration=duration_str)

    @commands.hybrid_command(name="unmute")
    @commands.guild_only()
    @is_mod_or_admin()
    async def unmute(self, ctx: commands.Context, member: discord.Member):
        """Unmutes a member."""
        await self.unmute_member(ctx.guild, member, "Unmuted by moderator.")
        await ctx.send(f"{member.mention} has been unmuted.")
        await self.log_action(ctx.guild, "unmute", member, ctx.author, "Unmuted")

    @commands.hybrid_command(name="kick")
    @commands.guild_only()
    @is_mod_or_admin()
    async def kick(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Kicks a member."""
        total_points = await self.get_points(member)
        await self.send_dm_notification(member, ctx.guild, "kick", reason, total_points)
        try:
            await member.kick(reason=reason)
            await ctx.send(f"{member} has been kicked.")
            await self.log_action(ctx.guild, "kick", member, ctx.author, reason)
        except discord.Forbidden:
            await ctx.send("Missing permissions to kick.")

    @commands.hybrid_command(name="ban")
    @commands.guild_only()
    @is_mod_or_admin()
    async def ban(self, ctx: commands.Context, member: discord.Member, *, reason: str = "No reason provided"):
        """Bans a member."""
        total_points = await self.get_points(member)
        await self.send_dm_notification(member, ctx.guild, "ban", reason, total_points)
        try:
            await member.ban(reason=reason)
            await ctx.send(f"{member} has been banned.")
            await self.log_action(ctx.guild, "ban", member, ctx.author, reason)
        except discord.Forbidden:
            await ctx.send("Missing permissions to ban.")

    @commands.hybrid_command(name="unban")
    @commands.guild_only()
    @is_mod_or_admin()
    async def unban(self, ctx: commands.Context, *, user_input: str):
        """Unbans a user by ID or name#discrim."""
        user = None
        try:
            user_id = int(user_input)
            user = discord.Object(id=user_id)
            await ctx.guild.unban(user)
        except ValueError:
            async for ban in ctx.guild.bans(limit=2000):
                if f"{ban.user.name}#{ban.user.discriminator}" == user_input:
                    user = ban.user
                    await ctx.guild.unban(user)
                    break
        if user:
            await ctx.send(f"{user} has been unbanned.")
            await self.log_action(ctx.guild, "unban", user, ctx.author, "Unbanned")
        else:
            await ctx.send("User not found in bans.")

    @commands.hybrid_command(name="purge")
    @commands.guild_only()
    @is_mod_or_admin()
    async def purge(self, ctx: commands.Context, amount: int):
        """Purges messages in the channel."""
        try:
            await ctx.channel.purge(limit=amount)
            await ctx.send(f"Purged {amount} messages.", delete_after=5)
            await self.log_action(ctx.guild, "purge", ctx.author, ctx.author, f"Purged {amount} messages in {ctx.channel.mention}")
        except discord.Forbidden:
            await ctx.send("Missing permissions to purge.")

    @commands.hybrid_group(name="modset")
    @commands.guild_only()
    @admin_check()
    async def modset_group(self, ctx: commands.Context):
        """Moderation setup commands."""
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @modset_group.command(name="addmodrole")
    async def modset_addmodrole(self, ctx: commands.Context, role: discord.Role):
        """Add a moderator role."""
        async with self.config.guild(ctx.guild).mod_roles() as roles:
            if role.id not in roles:
                roles.append(role.id)
        await ctx.send(f"Added {role.name} as mod role.")

    @modset_group.command(name="removemodrole")
    async def modset_removemodrole(self, ctx: commands.Context, role: discord.Role):
        """Remove a moderator role."""
        async with self.config.guild(ctx.guild).mod_roles() as roles:
            if role.id in roles:
                roles.remove(role.id)
        await ctx.send(f"Removed {role.name} as mod role.")

    @modset_group.command(name="addadminrole")
    async def modset_addadminrole(self, ctx: commands.Context, role: discord.Role):
        """Add an admin role."""
        async with self.config.guild(ctx.guild).admin_roles() as roles:
            if role.id not in roles:
                roles.append(role.id)
        await ctx.send(f"Added {role.name} as admin role.")

    @modset_group.command(name="removeadminrole")
    async def modset_removeadminrole(self, ctx: commands.Context, role: discord.Role):
        """Remove an admin role."""
        async with self.config.guild(ctx.guild).admin_roles() as roles:
            if role.id in roles:
                roles.remove(role.id)
        await ctx.send(f"Removed {role.name} as admin role.")

    @modset_group.command(name="setlogchannel")
    async def modset_setlogchannel(self, ctx: commands.Context, channel: discord.TextChannel):
        """Set the mod log channel."""
        await self.config.guild(ctx.guild).modlog_channel.set(channel.id)
        await ctx.send(f"Mod log channel set to {channel.mention}.")

    @modset_group.command(name="toggledm")
    async def modset_toggledm(self, ctx: commands.Context):
        """Toggle DM notifications."""
        current = await self.config.guild(ctx.guild).dm_notify()
        await self.config.guild(ctx.guild).dm_notify.set(not current)
        await ctx.send(f"DM notifications {'enabled' if not current else 'disabled'}.")

    @modset_group.command(name="setdmtemplate")
    async def modset_setdmtemplate(self, ctx: commands.Context):
        """Edit DM template via modal."""
        modal = DMTemplateModal(self, ctx.guild)
        await ctx.interaction.response.send_modal(modal) if ctx.interaction else await ctx.send("This command requires interaction support.")

    @modset_group.command(name="muterole")
    async def modset_muterole(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Set or change mute role. If none, prompt to create."""
        if not role:
            view = ui.View()
            create_btn = ui.Button(label="Create Mute Role", style=discord.ButtonStyle.primary)
            async def create_callback(interaction: discord.Interaction):
                if interaction.user != ctx.author:
                    return
                try:
                    mute_role = await ctx.guild.create_role(name="Muted", reason="Created by SpinnerModeration")
                    for channel in ctx.guild.channels:
                        await channel.set_permissions(mute_role, send_messages=False, speak=False)
                    await self.config.guild(ctx.guild).mute_role.set(mute_role.id)
                    await interaction.response.edit_message(content=f"Created and set {mute_role.name} as mute role.", view=None)
                except discord.Forbidden:
                    await interaction.response.edit_message(content="Missing permissions to create role.", view=None)
            create_btn.callback = create_callback
            view.add_item(create_btn)
            await ctx.send("No role provided. Create one?", view=view, ephemeral=True)
        else:
            await self.config.guild(ctx.guild).mute_role.set(role.id)
            await ctx.send(f"Set {role.name} as mute role.")

    @modset_group.command(name="syncperms")
    async def modset_syncperms(self, ctx: commands.Context):
        """Toggle sync with Redbot permissions."""
        current = await self.config.guild(ctx.guild).sync_red_perms()
        await self.config.guild(ctx.guild).sync_red_perms.set(not current)
        await ctx.send(f"Red perms sync {'enabled' if not current else 'disabled'}.")

    async def cog_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CheckFailure):
            await ctx.send("You lack the required permissions for this command.", ephemeral=True)
        elif isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Missing argument: {error.param.name}", ephemeral=True)
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Invalid argument provided.", ephemeral=True)
        else:
            log.error(f"Unexpected error in command {ctx.command}: {error}", exc_info=True)
            await ctx.send("An unexpected error occurred. Please check the logs.", ephemeral=True)

class PunishmentAddModal(ui.Modal, title="Add/Edit Punishment"):
    points = ui.TextInput(label="Points Threshold", style=discord.TextStyle.short)
    action = ui.TextInput(label="Action (mute/kick/ban/warn)", style=discord.TextStyle.short)
    duration = ui.TextInput(label="Duration (e.g., 1d2h)", style=discord.TextStyle.short, required=False)

    def __init__(self, cog, guild, view):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            points_val = int(self.points.value)
            action_val = self.action.value.lower()
            if action_val not in ["mute", "kick", "ban", "warn"]:
                return await interaction.response.send_message("Invalid action.", ephemeral=True)
            duration_val = self.cog.parse_duration(self.duration.value)
            async with self.cog.config.guild(self.guild).punishments() as pun:
                for p in pun:
                    if p["points"] == points_val:
                        p["action"] = action_val
                        p["duration"] = duration_val
                        break
                else:
                    pun.append({"points": points_val, "action": action_val, "duration": duration_val})
            new_embed = await self.view.get_embed()
            await interaction.response.edit_message(embed=new_embed, view=self.view)
        except ValueError:
            await interaction.response.send_message("Invalid points value.", ephemeral=True)

class PunishmentRemoveModal(ui.Modal, title="Remove Punishment"):
    points = ui.TextInput(label="Points Threshold", style=discord.TextStyle.short)

    def __init__(self, cog, guild, view):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.view = view

    async def on_submit(self, interaction: discord.Interaction):
        try:
            points_val = int(self.points.value)
            async with self.cog.config.guild(self.guild).punishments() as pun:
                pun[:] = [p for p in pun if p["points"] != points_val]
            new_embed = await self.view.get_embed()
            await interaction.response.edit_message(embed=new_embed, view=self.view)
        except ValueError:
            await interaction.response.send_message("Invalid points value.", ephemeral=True)

class PunishmentSetupView(ui.View):
    def __init__(self, cog, guild):
        super().__init__(timeout=None)
        self.cog = cog
        self.guild = guild

    async def get_embed(self):
        punishments = await self.cog.config.guild(self.guild).punishments()
        desc = "No punishments configured." if not punishments else "\n".join(f"**{p['points']}**: {p['action']} ({humanize_timedelta(timedelta=timedelta(seconds=p.get('duration', 0))) if p.get('duration') else 'Permanent'})" for p in sorted(punishments, key=lambda p: p["points"]))
        return discord.Embed(title="Punishment Setup", description=desc)

    @ui.button(label="Add/Edit", style=discord.ButtonStyle.primary)
    async def add_edit(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.guild_permissions.administrator or await self.cog.is_mod(interaction) or await self.cog.is_admin(interaction):
            modal = PunishmentAddModal(self.cog, self.guild, self)
            await interaction.response.send_modal(modal)

    @ui.button(label="Remove", style=discord.ButtonStyle.danger)
    async def remove(self, interaction: discord.Interaction, button: ui.Button):
        if interaction.user.guild_permissions.administrator or await self.cog.is_mod(interaction) or await self.cog.is_admin(interaction):
            modal = PunishmentRemoveModal(self.cog, self.guild, self)
            await interaction.response.send_modal(modal)

    @ui.button(label="Close", style=discord.ButtonStyle.secondary)
    async def close(self, interaction: discord.Interaction, button: ui.Button):
        await interaction.response.edit_message(content="Setup closed.", embed=None, view=None)

class DMTemplateModal(ui.Modal, title="Edit DM Template"):
    template = ui.TextInput(
        label="DM Template",
        style=discord.TextStyle.paragraph,
        default="You have received a {action} in {guild}.\nReason: {reason}\nDuration: {duration}\nTotal Points: {points}"
    )

    def __init__(self, cog, guild):
        super().__init__()
        self.cog = cog
        self.guild = guild
        self.template.default = self.cog.config.guild(self.guild).dm_message_template()

    async def on_submit(self, interaction: discord.Interaction):
        await self.cog.config.guild(self.guild).dm_message_template.set(self.template.value)
        await interaction.response.send_message("DM template updated.", ephemeral=True)