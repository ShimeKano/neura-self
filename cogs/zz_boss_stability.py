"""Boss runtime stability guard.

Loaded after cogs.boss so the guard can harden the ticket-check path without
changing the proven Boss detection/join logic from the target-detection branch.
"""

import asyncio

from discord.ext import commands

from cogs.boss import Boss


_original_request_ticket_check = Boss._request_ticket_check


async def _request_ticket_check_ready_guard(self, reason="manual", timeout=12):
    """Do not issue a Boss ticket check until this account is fully ready.

    wait_until_ready() is not sufficient here: discord.py can already have
    completed its READY event while NeuraBot.is_ready is still false because
    NeuraBot.on_ready() is still refreshing cogs. send_message() intentionally
    rejects commands during that short window, which caused the intermittent
    `TICKET CHECK ... failed to send` seen with multiple accounts.
    """
    if not self.enabled:
        return None

    for _ in range(100):
        if getattr(self.bot, "is_ready", False):
            break
        if not getattr(self.bot, "active", True):
            return None
        await asyncio.sleep(0.1)
    else:
        self.bot.log("ERROR", f"TICKET CHECK ({reason}): account readiness timeout")
        return None

    return await _original_request_ticket_check(
        self,
        reason=reason,
        timeout=timeout,
    )


Boss._request_ticket_check = _request_ticket_check_ready_guard


class BossStability(commands.Cog):
    """Marker cog; the class-level guard above is installed once per process."""

    def __init__(self, bot):
        self.bot = bot


async def setup(bot):
    await bot.add_cog(BossStability(bot))
