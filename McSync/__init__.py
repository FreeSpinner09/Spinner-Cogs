from .mc_sync import McSync

async def setup(bot):
    await bot.add_cog(McSync(bot))
