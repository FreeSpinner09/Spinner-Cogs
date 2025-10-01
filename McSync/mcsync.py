import discord
from redbot.core import commands, Config, checks
import asyncio
from rcon.source import Client as RconClient
import random
import time
import re
import logging
from asyncio import Lock

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("McSync")

class McSync(commands.Cog):
    """Sync Minecraft usernames with Discord and reward players via RCON."""

    # Color scheme for embeds
    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.orange(),
        "info": discord.Color.blue()
    }

    # Config identifier
    MCSYNC_IDENTIFIER = 0xBEEF1234

    def __init__(self, bot):
        try:
            self.bot = bot
            self.config = Config.get_conf(self, identifier=self.MCSYNC_IDENTIFIER)
            self.rcon_lock = Lock()  # Lock for thread-safe RCON access

            default_user = {"mc_username": None, "synced": False}
            default_guild = {
                "roles_allowed": [],
                "reward_cmds": [],
                "rcon_host": None,
                "rcon_port": 25575,
                "rcon_password": None,
            }

            self.config.register_user(**default_user)
            self.config.register_guild(**default_guild)

            # Temporary in-memory store for auth codes
            self.temp_codes = {}
            logger.info("McSync cog initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize McSync cog: {e}")
            raise

    # --------------------------
    # Helpers
    # --------------------------

    async def _test_rcon(self, host: str, port: int, password: str, retries: int = 3, timeout: int = 5):
        """Try connecting to RCON with given details, with retries."""
        async with self.rcon_lock:
            for attempt in range(1, retries + 1):
                try:
                    def run_cmd():
                        with RconClient(host, port, passwd=password, timeout=timeout) as mcr:
                            return mcr.run("list")
                    resp = await asyncio.get_event_loop().run_in_executor(None, run_cmd)
                    logger.info(f"RCON test successful for {host}:{port} on attempt {attempt}")
                    return True if resp is not None else "No response from server."
                except Exception as e:
                    logger.error(f"RCON test failed for {host}:{port} on attempt {attempt}: {e}")
                    if attempt == retries:
                        return f"RCON error: {e} after {retries} attempts"
                    await asyncio.sleep(1)  # Wait before retrying

    async def _send_rcon(self, guild: discord.Guild, command: str, retries: int = 3, timeout: int = 5) -> str:
        """Send a command via RCON with this guild’s config, with retries."""
        settings = await self.config.guild(guild).all()
        host = settings["rcon_host"]
        port = settings["rcon_port"]
        pwd = settings["rcon_password"]

        if not host or not pwd:
            return "⚠️ RCON is not configured. Admins can set it up with `!rcon set <host> <port> <password>`."

        async with self.rcon_lock:
            for attempt in range(1, retries + 1):
                try:
                    def run_cmd():
                        with RconClient(host, port, passwd=pwd, timeout=timeout) as mcr:
                            return mcr.run(command)
                    resp = await asyncio.get_event_loop().run_in_executor(None, run_cmd)
                    logger.info(f"RCON command '{command}' executed for guild {guild.id} on attempt {attempt}")
                    return resp if resp else "No response from server."
                except Exception as exc:
                    logger.error(f"RCON command error for guild {guild.id} on attempt {attempt}: {exc}")
                    if attempt == retries:
                        return f"⚠️ RCON error: {exc} after {retries} attempts"
                    await asyncio.sleep(1)  # Wait before retrying

    async def _allowed_checker(self, ctx: commands.Context) -> bool:
        """Check if user has permission to use restricted commands."""
        if ctx.author.guild_permissions.administrator:
            return True
        allowed_ids = await self.config.guild(ctx.guild).roles_allowed()
        return any(role.id in allowed_ids for role in ctx.author.roles)

    def _embed(self, title: str, desc: str, color_key: str = "info"):
        """Create a Discord embed with consistent colors."""
        return discord.Embed(title=title, description=desc, color=self.COLORS.get(color_key, discord.Color.blue()))

    # --------------------------
    # Sync Command (2-step)
    # --------------------------

    @commands.command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def sync(self, ctx, mc_username: str, code: str = None):
        """
        Two-step Minecraft sync with auth code.
        Step 1: !sync <username> → Sends code via RCON
        Step 2: !sync <username> <code> → Confirms sync and runs reward commands
        Example: `!sync Notch` then `!sync Notch 1234`
        """
        # Validate Minecraft username
        if not re.match(r"^[a-zA-Z0-9_]{3,16}$", mc_username):
            return await ctx.send(embed=self._embed("Error", "❌ Invalid Minecraft username (3-16 characters, alphanumeric or underscore).", "error"))

        user_id = ctx.author.id
        mc_username_lower = mc_username.lower()  # Standardize case

        # Step 1: generate & send code
        if code is None:
            auth_code = f"{random.randint(1000, 9999)}"
            self.temp_codes[user_id] = {"mc_username": mc_username_lower, "code": auth_code, "timestamp": time.time()}

            rcon_msg = f"tell {mc_username} Auth code for {ctx.author.name}: {auth_code}"
            resp = await self._send_rcon(ctx.guild, rcon_msg)

            if "⚠️" in resp:
                return await ctx.send(embed=self._embed("Error", resp, "error"))

            await ctx.send(embed=self._embed(
                "Sync Initiated",
                f"✅ Sent authentication code to **{mc_username}** in-game.\n"
                "Use `!sync <username> <code>` once you receive it.",
                "success"
            ))
            return

        # Step 2: confirm code
        entry = self.temp_codes.get(user_id)
        if not entry or entry["mc_username"] != mc_username_lower:
            return await ctx.send(embed=self._embed("Error", "❌ No pending code for this username. Run `!sync <username>` first.", "error"))

        # Check code expiration (5 minutes)
        if time.time() - entry["timestamp"] > 300:
            self.temp_codes.pop(user_id, None)
            return await ctx.send(embed=self._embed("Error", "❌ Code expired. Run `!sync <username>` again.", "error"))

        if entry["code"] != code:
            return await ctx.send(embed=self._embed("Error", "❌ Incorrect code.", "error"))

        # Remove temporary code
        self.temp_codes.pop(user_id, None)

        # Mark user as synced
        await self.config.user(ctx.author).mc_username.set(mc_username_lower)
        await self.config.user(ctx.author).synced.set(True)
        logger.info(f"User {ctx.author.id} synced with Minecraft username {mc_username_lower}")

        # Run reward commands
        cmds = await self.config.guild(ctx.guild).reward_cmds()
        results = []
        for cmd in cmds:
            full_cmd = cmd.replace("{user}", mc_username)
            resp = await self._send_rcon(ctx.guild, full_cmd)
            results.append(f"`{full_cmd}` → `{resp}`")

        if not cmds:
            results.append("No reward commands configured.")

        await ctx.send(embed=self._embed(
            "Minecraft Sync Complete",
            f"🎉 {ctx.author.mention}, your account has been synced!\n\n" + "\n".join(results),
            "success"
        ))

    # --------------------------
    # Check Link
    # --------------------------

    @commands.command()
    async def checklink(self, ctx, member: discord.Member = None):
        """
        Check a user's link status. (Restricted to allowed roles/admins)
        Example: `!checklink @User`
        """
        target = member or ctx.author
        if target != ctx.author and not await self._allowed_checker(ctx):
            return await ctx.send(embed=self._embed("Error", "❌ You don't have permission to check others.", "error"))

        data = await self.config.user(target).all()
        mc = data.get("mc_username")
        synced = data.get("synced")

        if not mc:
            desc = f"{target.display_name} has no Minecraft username linked."
        else:
            desc = f"**{target.display_name}** → `{mc}` | Synced: **{synced}**"

        await ctx.send(embed=self._embed("Link Status", desc, "info"))

    # --------------------------
    # Admin Commands
    # --------------------------

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsyncmc(self, ctx, member: discord.Member):
        """Admin only: Reset a user's Minecraft link."""
        await self.config.user(member).mc_username.set(None)
        await self.config.user(member).synced.set(False)
        logger.info(f"Admin {ctx.author.id} unsynced user {member.id}")
        await ctx.send(embed=self._embed("Unsync", f"🔄 Reset Minecraft link for {member.display_name}.", "warning"))

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setcheckerroles(self, ctx, *roles: discord.Role):
        """
        Set roles that can use `checklink` (admins always bypass).
        Example: `!setcheckerroles @Moderator @Helper`
        """
        role_ids = [r.id for r in roles]
        await self.config.guild(ctx.guild).roles_allowed.set(role_ids)

        if not roles:
            msg = "No roles specified. Only admins may use `checklink` now."
        else:
            msg = "Allowed roles set: " + ", ".join(r.name for r in roles)
        await ctx.send(embed=self._embed("Checker Roles", msg, "success"))

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setreward(self, ctx):
        """
        Interactive setup for reward commands. Use {user} as placeholder.
        Example: `give {user} minecraft:diamond 5`
        """
        await ctx.send(embed=self._embed(
            "Reward Setup",
            "Type the command to run via RCON when a user confirms sync.\n"
            "Example: `give {user} minecraft:diamond 5`\n\n"
            "Type `done` when finished, or `cancel` to stop.",
            "info"
        ))

        reward_cmds = []
        dangerous_keywords = ["stop", "op ", "deop"]  # Add more as needed
        def check(m): return m.author == ctx.author and m.channel == ctx.channel

        while True:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                await ctx.send(embed=self._embed("Reward Setup", "⚠️ Timed out. No commands saved.", "warning"))
                break

            content = msg.content.strip()
            if content.lower() == "cancel":
                reward_cmds = []
                break
            if content.lower() == "done":
                break

            # Validate command
            if any(dangerous in content.lower() for dangerous in dangerous_keywords):
                await ctx.send(embed=self._embed("Error", "❌ Dangerous command detected.", "error"))
                continue

            reward_cmds.append(content)
            await ctx.send(embed=self._embed("Reward Setup", f"✅ Added: `{content}`", "success"))

        if reward_cmds:
            await self.config.guild(ctx.guild).reward_cmds.set(reward_cmds)
            await ctx.send(embed=self._embed("Reward Setup", f"✅ Saved {len(reward_cmds)} reward command(s).", "success"))
        else:
            await ctx.send(embed=self._embed("Reward Setup", "⚠️ No commands saved.", "warning"))

    # --------------------------
    # RCON Commands
    # --------------------------

    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def rcon(self, ctx):
        """Manage RCON configuration (per guild)."""
        pass

    @rcon.command(name="set")
    async def rcon_set(self, ctx, host: str, port: int, password: str):
        """
        Set RCON connection for this guild (secure).
        Example: `!rcon set example.com 25575 mypassword`
        Note: Password is stored in Redbot's config. Consider securing the config file.
        """
        # Delete original message immediately
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(embed=self._embed("Warning", "⚠️ Could not delete your message. Ensure the bot has 'Manage Messages' permission.", "warning"))

        await ctx.typing()
        result = await self._test_rcon(host, port, password)

        if result is True:
            await self.config.guild(ctx.guild).rcon_host.set(host)
            await self.config.guild(ctx.guild).rcon_port.set(port)
            await self.config.guild(ctx.guild).rcon_password.set(password)
            logger.info(f"RCON configured for guild {ctx.guild.id} at {host}:{port}")
            await ctx.send(embed=self._embed("RCON Config", f"✅ Connected & saved for `{host}:{port}`", "success"))
        else:
            await ctx.send(embed=self._embed("RCON Error", f"❌ Failed to connect: `{result}`\nSettings not saved.", "error"))

    @rcon.command(name="test")
    async def rcon_test(self, ctx):
        """Test current RCON settings."""
        settings = await self.config.guild(ctx.guild).all()
        if not settings["rcon_host"] or not settings["rcon_password"]:
            return await ctx.send(embed=self._embed("RCON Test", "⚠️ No RCON configured. Use `!rcon set <host> <port> <password>` to configure.", "warning"))

        result = await self._test_rcon(settings["rcon_host"], settings["rcon_port"], settings["rcon_password"])
        if result is True:
            await ctx.send(embed=self._embed("RCON Test", f"✅ Connection successful to `{settings['rcon_host']}:{settings['rcon_port']}`", "success"))
        else:
            await ctx.send(embed=self._embed("RCON Test", f"❌ Failed: `{result}`", "error"))

    @rcon.command(name="clear")
    async def rcon_clear(self, ctx):
        """Clear this guild's RCON settings."""
        await self.config.guild(ctx.guild).rcon_host.clear()
        await self.config.guild(ctx.guild).rcon_port.clear()
        await self.config.guild(ctx.guild).rcon_password.clear()
        logger.info(f"RCON settings cleared for guild {ctx.guild.id}")
        await ctx.send(embed=self._embed("RCON Config", "🗑️ Cleared all RCON settings.", "info"))

# Boilerplate
async def setup(bot):
    try:
        await bot.add_cog(McSync(bot))
        logger.info("McSync cog loaded successfully")
    except Exception as e:
        logger.error(f"Failed to load McSync cog: {e}")
        raise