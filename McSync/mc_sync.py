import discord
from redbot.core import commands, Config, checks
import asyncio
import mcrcon
import random
import time

class mc_sync(commands.Cog):
    """Sync Minecraft usernames with Discord and reward players via RCON."""

    def __init__(self, bot):
        self.bot = bot
        self.config = Config.get_conf(self, identifier=0xBEEF1234)

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

        # Temporary in-memory store for auth codes: {discord_id: {"mc_username": str, "code": str, "timestamp": float}}
        self.temp_codes = {}

    # --------------------------
    # Helpers
    # --------------------------

    async def _test_rcon(self, host: str, port: int, password: str):
        """Try connecting to RCON with given details."""
        try:
            with mcrcon.MCRcon(host, password, port=port) as mcr:
                resp = mcr.command("list")
                return True if resp is not None else "No response from server."
        except Exception as e:
            return str(e)

    async def _send_rcon(self, guild: discord.Guild, command: str) -> str:
        """Send a command via RCON with this guild’s config."""
        settings = await self.config.guild(guild).all()
        host = settings["rcon_host"]
        port = settings["rcon_port"]
        pwd = settings["rcon_password"]

        if not host or not pwd:
            return "⚠️ RCON is not configured for this server."

        try:
            def run_cmd():
                with mcrcon.MCRcon(host, pwd, port=port) as mcr:
                    return mcr.command(command)

            return await asyncio.get_event_loop().run_in_executor(None, run_cmd)
        except Exception as exc:
            return f"⚠️ RCON error: {exc}"

    async def _allowed_checker(self, ctx: commands.Context) -> bool:
        if ctx.author.guild_permissions.administrator:
            return True
        allowed_ids = await self.config.guild(ctx.guild).roles_allowed()
        return any(role.id in allowed_ids for role in ctx.author.roles)

    def _embed(self, title: str, desc: str, color=discord.Color.blurple()):
        return discord.Embed(title=title, description=desc, color=color)

    # --------------------------
    # Sync Command (2-step)
    # --------------------------

    @commands.command()
    async def sync(self, ctx, mc_username: str, code: str = None):
        """
        Two-step Minecraft sync with auth code.
        Step 1: !sync <username> → Sends code via RCON
        Step 2: !sync <username> <code> → Confirms sync and runs reward commands
        """
        user_id = ctx.author.id

        # Step 1: generate & send code
        if code is None:
            auth_code = f"{random.randint(1000, 9999)}"
            self.temp_codes[user_id] = {"mc_username": mc_username, "code": auth_code, "timestamp": time.time()}

            rcon_msg = f"Auth code for {ctx.author.name}: {auth_code}"
            resp = await self._send_rcon(ctx.guild, f"tell {mc_username} {rcon_msg}")

            await ctx.send(embed=self._embed(
                "Sync Initiated",
                f"✅ Sent authentication code to **{mc_username}** in-game.\n"
                "Use `!sync <username> <code>` once you receive it."
            ))
            return

        # Step 2: confirm code
        entry = self.temp_codes.get(user_id)
        if not entry or entry["mc_username"].lower() != mc_username.lower():
            return await ctx.send(embed=self._embed("Error", "❌ No pending code for this username. Run `!sync <username>` first."))

        if entry["code"] != code:
            return await ctx.send(embed=self._embed("Error", "❌ Incorrect code."))

        # Remove temporary code
        self.temp_codes.pop(user_id, None)

        # Mark user as synced
        await self.config.user(ctx.author).mc_username.set(mc_username)
        await self.config.user(ctx.author).synced.set(True)

        # Run reward commands
        cmds = await self.config.guild(ctx.guild).reward_cmds()
        results = []
        for cmd in cmds:
            full_cmd = cmd.replace("{user}", mc_username)
            resp = await self._send_rcon(ctx.guild, full_cmd)
            results.append(f"`{full_cmd}` → `{resp}`")

        await ctx.send(embed=self._embed(
            "Minecraft Sync Complete",
            f"🎉 {ctx.author.mention}, your account has been synced!\n\n" + "\n".join(results),
            discord.Color.green()
        ))

    # --------------------------
    # Check Link
    # --------------------------

    @commands.command()
    async def checklink(self, ctx, member: discord.Member = None):
        """Check a user's link status. (Restricted to allowed roles/admins)"""
        target = member or ctx.author
        if target != ctx.author and not await self._allowed_checker(ctx):
            return await ctx.send(embed=self._embed("Error", "❌ You don't have permission to check others."))

        data = await self.config.user(target).all()
        mc = data.get("mc_username")
        synced = data.get("synced")

        if not mc:
            desc = f"{target.display_name} has no Minecraft username linked."
        else:
            desc = f"**{target.display_name}** → `{mc}` | Synced: **{synced}**"

        await ctx.send(embed=self._embed("Link Status", desc))

    # --------------------------
    # Admin Commands
    # --------------------------

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def unsyncmc(self, ctx, member: discord.Member):
        """Admin only: Reset a user's Minecraft link."""
        await self.config.user(member).mc_username.set(None)
        await self.config.user(member).synced.set(False)
        await ctx.send(embed=self._embed("Unsync", f"🔄 Reset Minecraft link for {member.display_name}.", discord.Color.orange()))

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setcheckerroles(self, ctx, *roles: discord.Role):
        """Set roles that can use `checklink` (admins always bypass)."""
        role_ids = [r.id for r in roles]
        await self.config.guild(ctx.guild).roles_allowed.set(role_ids)

        if not roles:
            msg = "Only admins may check links now."
        else:
            msg = "Allowed roles set: " + ", ".join(r.name for r in roles)
        await ctx.send(embed=self._embed("Checker Roles", msg))

    @commands.command()
    @checks.admin_or_permissions(manage_guild=True)
    async def setreward(self, ctx):
        """Interactive setup for reward commands. Use {user} as placeholder."""
        await ctx.send(embed=self._embed(
            "Reward Setup",
            "Type the command to run via RCON when a user confirms sync.\n"
            "Example: `give {user} minecraft:diamond 5`\n\n"
            "Type `done` when finished, or `cancel` to stop."
        ))

        reward_cmds = []
        def check(m): return m.author == ctx.author and m.channel == ctx.channel

        while True:
            try:
                msg = await self.bot.wait_for("message", check=check, timeout=60)
            except asyncio.TimeoutError:
                break

            content = msg.content.strip()
            if content.lower() == "cancel":
                reward_cmds = []
                break
            if content.lower() == "done":
                break

            reward_cmds.append(content)
            await ctx.send(embed=self._embed("Reward Setup", f"✅ Added: `{content}`"))

        if reward_cmds:
            await self.config.guild(ctx.guild).reward_cmds.set(reward_cmds)
            await ctx.send(embed=self._embed("Reward Setup", f"✅ Saved {len(reward_cmds)} reward command(s)."))
        else:
            await ctx.send(embed=self._embed("Reward Setup", "⚠️ No commands saved."))

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
        """Set RCON connection for this guild (secure)."""
        # Delete original message immediately
        try:
            await ctx.message.delete()
        except (discord.Forbidden, discord.HTTPException):
            pass

        await ctx.typing()
        result = await self._test_rcon(host, port, password)

        if result is True:
            await self.config.guild(ctx.guild).rcon_host.set(host)
            await self.config.guild(ctx.guild).rcon_port.set(port)
            await self.config.guild(ctx.guild).rcon_password.set(password)
            await ctx.send(embed=self._embed("RCON Config", f"✅ Connected & saved for `{host}:{port}`", discord.Color.green()))
        else:
            await ctx.send(embed=self._embed("RCON Error", f"❌ Failed to connect: `{result}`\nSettings not saved.", discord.Color.red()))

    @rcon.command(name="test")
    async def rcon_test(self, ctx):
        """Test current RCON settings."""
        settings = await self.config.guild(ctx.guild).all()
        if not settings["rcon_host"] or not settings["rcon_password"]:
            return await ctx.send(embed=self._embed("RCON Test", "⚠️ No RCON configured.", discord.Color.orange()))

        result = await self._test_rcon(settings["rcon_host"], settings["rcon_port"], settings["rcon_password"])
        if result is True:
            await ctx.send(embed=self._embed("RCON Test", f"✅ Connection successful to `{settings['rcon_host']}:{settings['rcon_port']}`", discord.Color.green()))
        else:
            await ctx.send(embed=self._embed("RCON Test", f"❌ Failed: `{result}`", discord.Color.red()))

    @rcon.command(name="clear")
    async def rcon_clear(self, ctx):
        """Clear this guild's RCON settings."""
        await self.config.guild(ctx.guild).rcon_host.clear()
        await self.config.guild(ctx.guild).rcon_port.clear()
        await self.config.guild(ctx.guild).rcon_password.clear()
        await ctx.send(embed=self._embed("RCON Config", "🗑️ Cleared all RCON settings.", discord.Color.blue()))


# Boilerplate
async def setup(bot):
    await bot.add_cog(mc_sync(bot))
