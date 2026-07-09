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
import aiohttp
import time
import json
import re
import webbrowser
import sys
import os
import subprocess
from urllib.parse import quote

from modules.services.yescaptcha import YesCaptchaService
from modules.services.nopecha import NopeCaptchaService
from modules.services.anticaptcha import AntiCaptchaService
from modules.services.captchaly import CaptchalyService


class WebSolver:
    _manual_lock = asyncio.Lock()
    _solve_queue = asyncio.Queue()
    _processor_task = None
    _verification_futures = {}

    def __init__(self, bot):
        self.bot = bot
        cfg = self.bot.config.get('security', {}).get('captcha_solver', {})
        self.api_key = cfg.get('api_key', '')
        self.active_service_name = cfg.get('service', 'yescaptcha').lower()
        self.enabled = cfg.get('enabled', True)
        self.browser_cfg = cfg.get('browser_config', {})
        self.site_key = "a6a1d5ce-612d-472d-8e37-7601408fbc09"
        self.auth_url = "https://discord.com/api/v9/oauth2/authorize?client_id=408785106942164992&response_type=code&redirect_uri=https://owobot.com/api/auth/discord/redirect&scope=identify guilds"

        if self.active_service_name == 'nopecha':
            self.active_key = cfg.get('nopecha_api_key', self.api_key)
            self.service = NopeCaptchaService(bot, self.active_key, self.site_key)
        elif self.active_service_name == 'anticaptcha':
            self.active_key = cfg.get('anticaptcha_api_key', self.api_key)
            self.service = AntiCaptchaService(bot, self.active_key, self.site_key)
        elif self.active_service_name == 'captchaly':
            self.active_key = cfg.get('captchaly_api_key', self.api_key)
            self.service = CaptchalyService(bot, self.active_key, self.site_key)
        else:
            self.active_key = cfg.get('yescaptcha_api_key', self.api_key)
            self.service = YesCaptchaService(bot, self.active_key, self.site_key)

    async def get_balance(self):
        return await self.service.get_balance()

    async def solve_hcaptcha(self, retries=3):
        return await self.service.solve_hcaptcha(retries)

    async def verify_token(self, token):
        import socket
        import requests

        _original_getaddrinfo = socket.getaddrinfo

        def patched_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
            if host == 'owobot.com':
                return [(socket.AF_INET, socket.SOCK_STREAM, 6, '', ('104.21.35.189', port))]
            return _original_getaddrinfo(host, port, family, type, proto, flags)

        socket.getaddrinfo = patched_getaddrinfo

        headers = {
            "Authorization": self.bot.token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        payload = {"token": token}

        try:
            verify_url = "https://owobot.com/api/captcha/verify"
            response = await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: requests.post(verify_url, json=payload, headers=headers, verify=False, timeout=10)
            )
            return response.status_code == 200
        finally:
            socket.getaddrinfo = _original_getaddrinfo

    async def auto_verify(self, tries=3):
        if not self.active_key and self.active_service_name != 'nopecha':
            self.bot.log("ERROR", f"{self.active_service_name.capitalize()} API key missing in settings.")
            return False

        balance = await self.get_balance()
        if self.active_service_name == 'yescaptcha' and balance < 30:
            self.bot.log("ERROR", f"YesCaptcha balance too low: {balance}")
            return False
        elif self.active_service_name == 'nopecha' and balance < 1:
            self.bot.log("ERROR", f"NopeCHA balance too low: {balance}")
            return False
        elif self.active_service_name == 'anticaptcha' and balance < 0.5:
            self.bot.log("ERROR", f"AntiCaptcha balance too low: {balance}")
            return False
        elif self.active_service_name == 'captchaly' and balance < 0.005:
            self.bot.log("ERROR", f"Captchaly balance too low: {balance}")
            return False

        headers = {
            "Authorization": self.bot.token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                auth_payload = {
                    "authorize": True,
                    "permissions": "0",
                    "integration_type": 0,
                    "location_context": {"guild_id": "10000", "channel_id": "10000", "channel_type": 10000}
                }
                async with session.post(self.auth_url, json=auth_payload) as resp:
                    if resp.status != 200:
                        return False
                    auth_data = await resp.json()
                    redirect_url = auth_data.get("location")

                if redirect_url:
                    async with session.get(redirect_url) as r:
                        pass

                solution = await self.solve_hcaptcha(tries)
                if not solution:
                    return False

                return await self.verify_token(solution)
            except Exception as e:
                self.bot.log("ERROR", f"Auto-verification failed: {e}")
                return False

    @classmethod
    def enqueue_manual_solve(cls, bot_id, captcha_url=None):
        cls._solve_queue.put_nowait((bot_id, captcha_url or "https://owobot.com/captcha"))
        if cls._processor_task is None or cls._processor_task.done():
            cls._processor_task = asyncio.create_task(cls._manual_processor())

    @classmethod
    async def _manual_processor(cls):
        while True:
            try:
                bot_id, captcha_url = await cls._solve_queue.get()

                async with cls._manual_lock:
                    future = asyncio.get_event_loop().create_future()
                    cls._verification_futures[bot_id] = future

                    bot = cls._get_bot_by_user_id(bot_id)
                    if not bot:
                        cls._verification_futures.pop(bot_id, None)
                        cls._solve_queue.task_done()
                        continue

                    username = getattr(bot, 'username', bot_id)
                    bot.log("SECURITY", f"[QUEUE] Manual solve started for {username} - {captcha_url}")

                    try:
                        from dashboard.app import register_captcha_challenge
                        register_captcha_challenge(bot_id, {"account_name": username, "captcha_url": captcha_url})
                    except Exception as e:
                        bot.log("ERROR", f"[QUEUE] Failed to register captcha for dashboard: {e}")

                    async def alert_loop():
                        start = time.time()
                        last_alert = 0
                        while not future.done():
                            elapsed = int(time.time() - start)
                            if elapsed > 0 and elapsed % 60 == 0 and elapsed != last_alert:
                                mins = elapsed // 60
                                secs = elapsed % 60
                                if mins == 0:
                                    bot.log("SECURITY", f"[QUEUE] {username}: {secs}s elapsed – captcha still pending")
                                elif mins < 10:
                                    bot.log("SECURITY", f"[QUEUE] {username}: {mins}m {secs}s elapsed – captcha still pending")
                                else:
                                    bot.log("SECURITY", f"[QUEUE] {username}: {mins}m {secs}s elapsed – OVER 10 MINUTES! Solve now to avoid strike!")
                                last_alert = elapsed
                            await asyncio.sleep(1)

                    alert_task = asyncio.create_task(alert_loop())

                    sec_cfg = bot.config.get("security", {})
                    if sys.platform == "win32":
                        auto_open = sec_cfg.get("open_captcha_url_on_pc", False)
                    else:
                        auto_open = sec_cfg.get("open_captcha_url_on_mobile", False)

                    if auto_open:
                        bot.log("SYS", f"[QUEUE] Opening captcha for {username}...")
                        success = await cls.open_in_browser(captcha_url, bot=bot)
                        if not success:
                            bot.log("ERROR", f"[QUEUE] Failed to open browser for {username}")

                    await future 

                    bot.log("SUCCESS", f"[QUEUE] {username}: Manual captcha VERIFIED!")

                    alert_task.cancel()
                    try:
                        await alert_task
                    except asyncio.CancelledError:
                        pass

                    cls._verification_futures.pop(bot_id, None)
                    cls._solve_queue.task_done()

            except Exception as e:
                import traceback
                print(f"[QUEUE ERROR] Manual processor crashed: {e}")
                traceback.print_exc()

    @classmethod
    def _get_bot_by_user_id(cls, user_id):
        try:
            for bot in getattr(state, 'bot_instances', []):
                if hasattr(bot, 'user') and bot.user and str(bot.user.id) == str(user_id):
                    return bot
            return None
        except Exception:
            return None

    @classmethod
    def mark_verification_done(cls, bot_id):
        future = cls._verification_futures.get(bot_id)
        if future and not future.done():
            future.set_result(True)

        try:
            from dashboard.app import clear_captcha_challenge
            clear_captcha_challenge(bot_id)
        except Exception as e:
            bot = cls._get_bot_by_user_id(bot_id)
            if bot:
                bot.log("ERROR", f"Failed to clear captcha challenge: {e}")

    @staticmethod
    async def open_in_browser(captcha_url=None, bot=None):
        if not bot:
            return False

        auth_url = "https://discord.com/api/v9/oauth2/authorize?client_id=408785106942164992&response_type=code&redirect_uri=https://owobot.com/api/auth/discord/redirect&scope=identify guilds"

        headers = {
            "Authorization": bot.token,
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                auth_payload = {
                    "authorize": True,
                    "permissions": "0",
                    "integration_type": 0,
                    "location_context": {"guild_id": "10000", "channel_id": "10000", "channel_type": 10000}
                }

                full_auth_url = auth_url
                if captcha_url:
                    full_auth_url += f"&state={quote(captcha_url)}"

                async with session.post(full_auth_url, json=auth_payload) as resp:
                    if resp.status != 200:
                        bot.log("ERROR", f"Browser Solver: OAuth failed (Status {resp.status})")
                        if captcha_url:
                            bot.log("SYS", "OAuth failed. Opening raw captcha URL as fallback.")
                            _open_url(captcha_url, bot)
                        return False

                    auth_data = await resp.json()
                    redirect_url = auth_data.get("location")

                if redirect_url:
                    bot.log("SYS", f"Opening Auth Login for {bot.username}...")
                    _open_url(redirect_url, bot)
                    return True
                return False
            except Exception as e:
                bot.log("ERROR", f"Browser solver start failed: {e}")
                return False


def _open_url(url, bot):
    """Open a URL in the system browser, with mobile support."""
    if sys.platform == "win32":
        webbrowser.open_new_tab(url)
        return

    if sys.platform == "darwin":
        webbrowser.open_new_tab(url)
        return

    if "ANDROID_ROOT" in os.environ or "TERMUX_VERSION" in os.environ:
        try:
            subprocess.Popen(["termux-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            bot.log("SYS", "Opened URL using termux-open")
            return
        except FileNotFoundError:
            try:
                subprocess.Popen(["am", "start", "-a", "android.intent.action.VIEW", "-d", url],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                bot.log("SYS", "Opened URL using am start")
                return
            except FileNotFoundError:
                bot.log("WARN", "Failed to open URL on mobile. Install termux-open or use dashboard.")
                return

    try:
        subprocess.Popen(["xdg-open", url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        bot.log("SYS", "Opened URL using xdg-open")
    except FileNotFoundError:
        bot.log("WARN", "No browser opener found. Use dashboard to open captcha manually.")


import core.state as state

def setup_web_solver(bot):
    return WebSolver(bot)