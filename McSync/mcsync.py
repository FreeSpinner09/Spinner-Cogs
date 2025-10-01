import discord
from redbot.core import commands, Config, checks
import asyncio
from rcon.source import Client as RconClient, RconError
import random
import time
import re
import logging
import socket
from asyncio import Lock

# ----------------------------------------------------------------------
# Logging
# ----------------------------------------------------------------------
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("McSync")

# ----------------------------------------------------------------------
# Cog definition
# ----------------------------------------------------------------------
class McSync(commands.Cog):
    """Sync Minecraft usernames with Discord and reward players via RCON."""

    COLORS = {
        "success": discord.Color.green(),
        "error": discord.Color.red(),
        "warning": discord.Color.orange(),
        "info": discord.Color.blue(),
    }

    MCSYNC_IDENTIFIER = 0xBEEF1234

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=self.MCSYNC_IDENTIFIER)
        self.rcon_lock = Lock()

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

        self.temp_codes = {}
        logger.info("McSync cog initialized")

    # ------------------------------------------------------------------
    # RCON helpers
    # ------------------------------------------------------------------
    async def _test_rcon(
        self,
        host: str,
        port: int,
        password: str,
        retries: int = 3,
        timeout: int = 10,
    ) -> object:
        """Test RCON connectivity – returns True on success, error string otherwise."""
        async with self.rcon_lock:
            for attempt in range(1, retries + 1):
                try:
                    def _run():
                        with RconClient(host, port, passwd=password, timeout=timeout) as client:
                            return client.run("list")

                    resp = await asyncio.get_event_loop().run_in_executor(None, _run)
                    logger.info(f"RCON test OK {host}:{port} (attempt {attempt})")
                    return True if resp is not None else "No response from server."

                except RconError as e:
                    logger.error(f"RCON auth/protocol error (attempt {attempt}): {e}")
                except (ConnectionResetError, BrokenPipeError) as e:
                    logger.error(f"RCON connection reset (attempt {attempt}): {e}")
                except socket.timeout as e:
                    logger.error(f"RCON timeout (attempt {attempt}): {e}")
                except Exception as e:
                    logger.error(f"Unexpected RCON error (attempt {attempt}): {e}")

                if attempt < retries:
                    await asyncio.sleep(2)  # short pause before retry
            return "RCON error after retries"

    async def _send_rcon(
        self,
        guild: discord.Guild,
        command: str,
        retries: int = 3,
        timeout: int = 10,
    ) -> str:
        """Send a single command – returns the server response string."""
        settings = await self.config.guild(guild).all()
        host = settings["rcon_host"]
        port = settings["rcon_port"]
        pwd = settings["rcon_password"]

        if not host or not pwd:
            return "RCON not configured – use `!rcon set <host> <port> <password>`."

        async with self.rcon_lock:
            for attempt in range(1, retries + 1):
                try:
                    def _run():
                        with RconClient(host, port, passwd=pwd, timeout=timeout) as client:
                            return client.run(command)

                    resp = await asyncio.get_event_loop().run_in_executor(None, _run)
                    logger.info(f"RCON command executed (attempt {attempt}): {command!r}")
                    return resp if resp else "No response from server."

                except RconError as e:
                    logger.error(f"RCON auth error on command (attempt {attempt}): {e}")
                except (ConnectionResetError, BrokenPipeError) as e:
                    logger.error(f"RCON connection reset (attempt {attempt}): {e}")
                except socket.timeout as e:
                    logger.error(f"RCON timeout (attempt {attempt}): {e}")
                except Exception as e:
                    logger.error(f"Unexpected RCON error (attempt {attempt}): {e}")

                if attempt < retries:
                    await asyncio.sleep(2)

            return f"RCON error after {retries} attempts"

    # ------------------------------------------------------------------
    # Permission helpers
    # ------------------------------------------------------------------
    async def _allowed_checker(self, ctx: commands.Context) -> bool:
        if ctx.author.guild_permissions.administrator:
            return True
        allowed = await self.config.guild(ctx.guild).roles_allowed()
        return any(r.id in allowed for r in ctx.author.roles)

    def _embed(self, title: str, desc: str, color_key: str = "info"):
        return discord.Embed(title=title, description=desc, color=self.COLORS.get(color_key))

    # ------------------------------------------------------------------
    # User commands
    # ------------------------------------------------------------------
    @commands.command()
    @commands.cooldown(1, 60, commands.BucketType.user)
    async def sync(self, ctx, mc_username: str, code: str = None):
        """Two-step Minecraft sync."""
        if not re.match(r"^[a-zA-Z0-9_]{3,16}$", mc_username):
            return await ctx.send(embed=self._embed("Error", "Invalid Minecraft username.", "error"))

        uid = ctx.author.id
        mc_username = mc_username.lower()

        # ---- Step 1: generate & send code ---------------------------------
        if code is None:
            auth_code = f"{random.randint(1000, 9999)}"
            self.temp_codes[uid] = {
                "mc_username": mc_username,
                "code": auth_code,
                "timestamp": time.time(),
            }

            rcon_cmd = f"tell {mc_username} Auth code for {ctx.author.name}: {auth_code}"
            resp = await self._send_rcon(ctx.guild, rcon_cmd)

            if "RCON error" in resp:
                return await ctx.send(embed=self._embed("Error", resp, "error"))

            await ctx.send(
                embed=self._embed(
                    "Sync started",
                    f"Sent code to **{mc_username}**. Use `!sync {mc_username} <code>` to finish.",
                    "success",
                )
            )
            return

        # ---- Step 2: verify code -----------------------------------------
        entry = self.temp_codes.get(uid)
        if not entry or entry["mc_username"] != mc_username:
            return await ctx.send(embed=self._embed("Error", "No pending code for that username.", "error"))

        if time.time() - entry["timestamp"] > 300:
            self.temp_codes.pop(uid, None)
            return await ctx.send(embed=self._embed("Error", "Code expired – start over.", "error"))

        if entry["code"] != code:
            return await ctx.send(embed=self._embed("Error", "Wrong code.", "error"))

        # success – store link
        del self.temp_codes[uid]
        await self.config.user(ctx.author).mc_username.set(mc_username)
        await self.config.user(ctx.author).synced.set(True)
        logger.info(f"User {uid} synced to Minecraft name {mc_username}")

        # run reward commands
        rewards = await self.config.guild(ctx.guild).reward_cmds()
        results = []
        for cmd in rewards:
            full = cmd.replace("{user}", mc_username)
            out = await self._send_rcon(ctx.guild, full)
            results.append(f"`{full}` → `{out}`")
        if not rewards:
            results.append("No reward commands configured.")

        await ctx.send(
            embed=self._embed(
                "Sync complete",
                f"{ctx.author.mention} is now linked!\n\n" + "\n".join(results),
                "success",
            )
        )

    @commands.command()
    async def checklink(self, ctx, member: discord.Member = None):
        target = member or ctx.author
        if target != ctx.author and not await self._allowed_checker(ctx):
            return await ctx.send(embed=self._embed("Error", "You cannot check other users.", "error"))

        data = await self.config.user(target).all()
        mc = data.get("mc_username")
        synced = data.get("synced")
        if not mc:
            desc = f"{target.display_name} has no linked Minecraft name."
        else:
            desc = f"**{target.display_name}** → `{mc}` | Synced: **{synced}**"
        await ctx.send(embed=self._embed("Link status", desc, "info"))

    # ------------------------------------------------------------------
    # Admin commands
    # ------------------------------------------------------------------
    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsyncmc(self, ctx, member: discord.Member):
        await self.config.user(member).clear()
        await ctx.send(embed=self._embed("Unsync", f"Cleared link for {member.display_name}.", "warning"))

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setcheckerroles(self, ctx, *roles: discord.Role):
        await self.config.guild(ctx.guild).roles_allowed.set([r.id for r in roles])
        await ctx.send(
            embed=self._embed(
                "Roles updated",
                "Allowed roles: " + ", ".join(r.name for r in roles) if roles else "None (admin only)",
                "success",
            )
        )

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setreward(self, ctx):
        await ctx.send(
            embed=self._embed(
                "Reward setup",
                "Enter RCON commands (use `{user}` placeholder). Type `done` when finished, `cancel` to abort.",
                "info",
            )
        )

        cmds = []
        dangerous = ["stop", "op ", "deop"]
        def check(m):
            return m.author == ctx.author and m.channel == ctx.channel

        while True:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                await ctx.send(embed=self._embed("Reward setup", "Timed out – nothing saved.", "warning"))
                break

            txt = msg.content.strip().lower()
            if txt == "cancel":
                cmds = []
                break
            if txt == "done":
                break
            if any(k in txt for k in dangerous):
                await ctx.send(embed=self._embed("Error", "Dangerous command blocked.", "error"))
                continue

            cmds.append(msg.content.strip())
            await ctx.send(embed=self._embed("Added", f"`{msg.content.strip()}`", "success"))

        if cmds:
            await self.config.guild(ctx.guild).reward_cmds.set(cmds)
            await ctx.send(embed=self._embed("Saved", f"{len(cmds)} reward command(s) saved.", "success"))
        else:
            await ctx.send(embed=self._embed("Cancelled", "No changes made.", "warning"))

    # ------------------------------------------------------------------
    # RCON admin commands
    # ------------------------------------------------------------------
    @commands.group()
    @checks.admin_or_permissions(manage_guild=True)
    async def rcon(self, ctx):
        """RCON management."""
        pass

    @rcon.command(name="set")
    async def rcon_set(self, ctx, host: str, port: int, password: str):
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            await ctx.send(embed=self._embed("Warning", "Could not delete message (missing Manage Messages).", "warning"))

        result = await self._test_rcon(host, port, password)
        if result is True:
            await self.config.guild(ctx.guild).rcon_host.set(host)
            await self.config.guild(ctx.guild).rcon_port.set(port)
            await self.config.guild(ctx.guild).rcon_password.set(password)
            await ctx.send(embed=self._embed("RCON set", f"Saved `{host}:{port}`", "success"))
        else:
            await ctx.send(embed=self._embed("RCON error", f"Failed: `{result}`", "error"))

    @rcon.command(name="test")
    async def rcon_test(self, ctx):
        settings = await self.config.guild(ctx.guild).all()
        if not settings["rcon_host"] or not settings["rcon_password"]:
            return await ctx.send(embed=self._embed("RCON missing", "Run `!rcon set` first.", "warning"))

        ok = await self._test_rcon(
            settings["rcon_host"], settings["rcon_port"], settings["rcon_password"]
        )
        if ok is True:
            await ctx.send(embed=self._embed("RCON OK", "Connection works!", "success"))
        else:
            await ctx.send(embed=self._embed("RCON failed", str(ok), "error"))

    @rcon.command(name="clear")
    async def rcon_clear(self, ctx):
        await self.config.guild(ctx.guild).rcon_host.clear()
        await self.config.guild(ctx.guild).rcon_port.clear()
        await self.config.guild(ctx.guild).rcon_password.clear()
        await ctx.send(embed=self._embed("RCON cleared", "Settings removed.", "info"))


# ----------------------------------------------------------------------
# Cog loader
# ----------------------------------------------------------------------
async def setup(bot):
    await bot.add_cog(McSync(bot))
    logger.info("McSync cog loaded")