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


"""
Author: Routo
NeuraSelf-UwU - https://github.com/routo-loop/neura-self
"""


import asyncio
import aiohttp
import requests


class NopeCaptchaService:
    def __init__(self, bot, api_key, site_key):
        self.bot = bot
        self.api_key = api_key
        self.site_key = site_key
        self.is_paid = bool(api_key and api_key.strip())
        self.base_url = "https://api.nopecha.com/v1"

    async def get_balance(self):
        if not self.is_paid:
            result = await self._request_sync("GET", "/status", auth=False)
            if result and result.get("credit") is not None:
                return result["credit"]
            if result and result.get("error") == 12:  
                self.bot.log("ERROR", "NopeCHA free IP is banned.")
                return 0
            return 0

        # paid mode
        result = await self._request_sync("GET", "/status", auth=True)
        if result and result.get("credit") is not None:
            return result["credit"]
        return 0

    def _get_headers(self, auth=True):
        headers = {"Content-Type": "application/json"}
        if auth and self.api_key:
            headers["Authorization"] = f"Basic {self.api_key}"
        return headers

    async def _request_sync(self, method, endpoint, auth=True, data=None):
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(auth)
        try:
            async with aiohttp.ClientSession() as session:
                if method.upper() == "GET":
                    async with session.get(url, headers=headers, timeout=10) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            try:
                                err = await response.json()
                                self.bot.log("ERROR", f"NopeCHA API error {err.get('error')}: {err.get('message')}")
                                return err
                            except:
                                text = await response.text()
                                self.bot.log("ERROR", f"NopeCHA HTTP {response.status}")
                                return {"error": response.status, "message": text}
                else:
                    async with session.post(url, json=data, headers=headers, timeout=30) as response:
                        if response.status == 200:
                            return await response.json()
                        else:
                            try:
                                err = await response.json()
                                self.bot.log("ERROR", f"NopeCHA API error {err.get('error')}: {err.get('message')}")
                                return err
                            except:
                                text = await response.text()
                                self.bot.log("ERROR", f"NopeCHA HTTP {response.status}")
                                return {"error": response.status, "message": text}
        except Exception as e:
            self.bot.log("ERROR", f"NopeCHA request failed: {e}")
            return {"error": -1, "message": str(e)}

    async def solve_hcaptcha(self, retries=2):
        if self.is_paid:
            return await self._solve_paid(retries)
        else:
            return await self._solve_free(retries)

    async def _solve_paid(self, retries):
        for attempt in range(retries):
            try:
                self.bot.log("SYS", f"Creating NopeCHA paid task (Attempt {attempt+1})...")
                payload = {
                    "type": "hcaptcha",
                    "sitekey": self.site_key,
                    "url": "https://owobot.com"
                }
                result = await self._request_sync("POST", "/token", auth=True, data=payload)
                if result and result.get("data"):
                    token = result["data"]
                    self.bot.log("SUCCESS", "NopeCHA paid solved successfully.")
                    return token
                if result and result.get("error"):
                    if result.get("error") in (13, 14):
                        break
                self.bot.log("ERROR", "NopeCHA paid response missing token.")
            except Exception as e:
                self.bot.log("ERROR", f"NopeCHA paid task failed: {e}")
            await asyncio.sleep(2)
        return None

    async def _solve_free(self, retries):
        for attempt in range(retries):
            try:
                self.bot.log("SYS", f"Creating NopeCHA free task (Attempt {attempt+1})...")
                payload = {
                    "type": "hcaptcha",
                    "sitekey": self.site_key,
                    "url": "https://owobot.com"
                }
                result = await self._request_sync("POST", "/token", auth=False, data=payload)
                if result and result.get("data"):
                    token = result["data"]
                    self.bot.log("SUCCESS", "NopeCHA free solved successfully.")
                    return token
                if result and result.get("error") == 12:
                    self.bot.log("ERROR", "NopeCHA free IP is banned.")
                    break
                if result and result.get("error") == 13:
                    self.bot.log("ERROR", "NopeCHA free quota exceeded (100/day).")
                    break
                self.bot.log("ERROR", "NopeCHA free response missing token.")
            except Exception as e:
                self.bot.log("ERROR", f"NopeCHA free task faileed: {e}")
            await asyncio.sleep(2)
        return None