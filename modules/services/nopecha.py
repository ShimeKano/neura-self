# This file is part of NeuraSelf-UwU.
# Copyright (c) 2025-Present Routo
#
# NeuraSelf-UwU is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# You should have received a copy of the GNU General Public License
# along with NeuraSelf-UwU. If not, see <https://www.gnu.org/licenses/>.


import asyncio
import nopecha

class NopeCaptchaService:
    def __init__(self, bot, api_key, site_key):
        self.bot = bot
        self.api_key = api_key
        self.site_key = site_key
        nopecha.api_key = self.api_key

    async def get_balance(self):
        """Checks free/paid quota balance using the official library."""
        if not self.api_key: return 0
        try:
            status = await asyncio.to_thread(nopecha.Balance.get)

            return int(status.get("credit", 0))
        except Exception as e:
            self.bot.log("ERROR", f"Failed to get NopeCHA balance via library: {e}")
            return 0

    async def solve_hcaptcha(self, retries=2):
        """solves hcaptcha using official nopecha library and returns the token"""
        for attempt in range(retries):
            try:
                self.bot.log("SYS", f"Creating NopeCHA task via library (Attempt {attempt+1})...")

                token = await asyncio.to_thread(
                    nopecha.Token.solve,
                    type="hcaptcha",
                    sitekey=self.site_key,
                    url="https://owobot.com"
                )
                
                if token:
                    self.bot.log("SUCCESS", "NopeCHA solved hCaptcha successfully via library.")
                    return token
                    
            except Exception as e:
                self.bot.log("ERROR", f"NopeCHA library task failed on attempt {attempt+1}: {e}")
                
                err_msg = str(e).lower()
                if "invalid key" in err_msg or "quota" in err_msg:
                    break
                    
                await asyncio.sleep(2) 
                
        return None
