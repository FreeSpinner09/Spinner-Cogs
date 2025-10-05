from .spinnerMod import SpinnerModeration

def setup(bot):
    bot.add_cog(SpinnerModeration(bot))
    log.info("SpinnerModeration loaded (admin_check decorator active)")