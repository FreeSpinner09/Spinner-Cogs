from .spinnerMod import SpinnerModeration
import logging

log = logging.getLogger("red.spinnerModeration")

async def setup(bot):
    await bot.add_cog(SpinnerModeration(bot))
    log.info("SpinnerModeration loaded (admin_check decorator active)")