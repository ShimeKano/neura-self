# This file is part of NeuraSelf-UwU.
# Copyright (c) 2025-Present Routo
#
# NeuraSelf-UwU is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

"""
Author: Routo
NeuraSelf-UwU - https://github.com/routo-loop/neura-self
"""

import discord
from discord.ext import commands
import asyncio
import time
import random

from component_v2_neura import parse_v2_message, get_boss_battle_id
import json
import os
import re


class Boss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # State is rebound to the authenticated account in register_actions().
        # This prevents multiple accounts in one process from sharing Boss tickets.
        self.state_file = None
        self._load_state()
        self.enabled = self.bot.config.get("boss", {}).get("enabled", True)
        self.join_chance = self.bot.config.get("boss", {}).get("join_chance", 100)
        self.target_guilds = self._normalize_ids(self.bot.config.get("boss", {}).get("target_guilds", []))
        self.ignore_guilds = self._normalize_ids(self.bot.config.get("boss", {}).get("ignore_guilds", []))
        self.playing_guild_ids = set()
        self.processing_ids = set()
        self.ticket_check_lock = asyncio.Lock()
        self.ticket_check_event = asyncio.Event()
        self._update_playing_guilds()

    @staticmethod
    def _normalize_ids(values):
        if values is None:
            return []
        if isinstance(values, (str, int)):
            values = [values]
        result = []
        for value in values:
            value = str(value).strip()
            if value and value not in result:
                result.append(value)
        return result

    def _update_playing_guilds(self):
        self.playing_guild_ids.clear()
        for c_id in self.bot.channels:
            try:
                ch = self.bot.get_channel(int(c_id))
            except (TypeError, ValueError):
                ch = None
            if ch and ch.guild:
                self.playing_guild_ids.add(str(ch.guild.id))

        if hasattr(self.bot, "guild_id") and self.bot.guild_id:
            self.playing_guild_ids.add(str(self.bot.guild_id))

    async def register_actions(self):
        cfg = self.bot.config.get("boss", {})
        self.enabled = bool(cfg.get("enabled", True))
        self.join_chance = max(0, min(100, int(cfg.get("join_chance", 100))))
        self.target_guilds = self._normalize_ids(cfg.get("target_guilds", []))
        self.ignore_guilds = self._normalize_ids(cfg.get("ignore_guilds", []))
        self._update_playing_guilds()

        # Each NeuraBot instance gets an isolated Boss state file based on the
        # authenticated Discord user ID. This is essential for multi-account mode.
        account_id = str(getattr(self.bot, "user_id", "") or "").strip()
        if account_id:
            new_state_file = os.path.join("data", "boss", f"{account_id}.json")
            if new_state_file != self.state_file:
                self.state_file = new_state_file
                self._load_state()

        self.bot.log(
            "SYS",
            f"Boss settings refreshed: enabled={self.enabled}, targets={len(self.target_guilds)}, "
            f"ignored={len(self.ignore_guilds)}, chance={self.join_chance}%"
        )

        # Always synchronize the real ticket count before Boss hunting starts.
        if self.enabled and getattr(self.bot, "is_ready", False):
            await self._request_ticket_check("startup")

    def _load_state(self):
        self.tickets = 3
        self.last_reset = 0
        self.joined_ids = set()
        if not self.state_file or not os.path.exists(self.state_file):
            return
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
                self.tickets = int(data.get("tickets", 3))
                self.last_reset = data.get("last_reset", 0)
                self.joined_ids = set(str(x) for x in data.get("joined_ids", []))
        except Exception as e:
            self.bot.log("ERROR", f"Boss state load failed: {e}")

    def _save_state(self):
        if not self.state_file:
            return
        try:
            os.makedirs(os.path.dirname(self.state_file), exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump({
                    "tickets": self.tickets,
                    "last_reset": self.last_reset,
                    "joined_ids": list(self.joined_ids)
                }, f)
        except Exception as e:
            self.bot.log("ERROR", f"Boss state save failed: {e}")

    def _check_reset(self):
        # The real ticket count comes from oboss t. This only clears stale
        # local battle IDs after the normal ticket period has elapsed.
        now = time.time()
        if now - self.last_reset > 72000:
            self.joined_ids.clear()
            self._save_state()

    def _is_target_guild(self, guild_id):
        """Apply blacklist-first, explicit-target-only guild routing."""
        guild_id = str(guild_id or "").strip()
        if not guild_id:
            return False
        if guild_id in self.ignore_guilds:
            return False
        return guild_id in self.target_guilds

    @staticmethod
    def _find_fight_button(components):
        """Find the Boss fight button without depending on one exact Discord custom_id."""
        buttons = [
            c for c in components
            if c.name == "button" and c.custom_id and not c.disabled
        ]

        exact = next((c for c in buttons if c.custom_id == "guildboss_fight"), None)
        if exact:
            return exact

        for component in buttons:
            custom_id = str(component.custom_id).lower()
            label = str(component.label or "").lower()
            if "guildboss" in custom_id and "fight" in custom_id:
                return component
            if "boss" in custom_id and "fight" in label:
                return component

        return None

    @staticmethod
    def _parse_ticket_count(text):
        """Parse the real X/3 Boss ticket count from an oboss t response."""
        text = str(text or "").lower()
        patterns = [
            r"(\d+)\s*/\s*3\s+boss\s+tickets?",
            r"(\d+)\s*/\s*3\s+boss\s+ticket",
            r"boss\s+tickets?.{0,80}?(\d+)\s*/\s*3",
            r"(\d+)\s+boss\s+tickets?\s+(?:left|remaining)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                return max(0, min(3, int(match.group(1))))
        if "ran out of boss tickets" in text or "no boss tickets" in text:
            return 0
        return None

    async def _request_ticket_check(self, reason="manual", timeout=12):
        """Ask THIS account to run `oboss t` and wait for THIS account's response."""
        if not self.enabled or not getattr(self.bot, "is_ready", False):
            return None

        async with self.ticket_check_lock:
            self.ticket_check_event.clear()
            self.bot.log("BOSS", f"TICKET CHECK ({reason}): sending `oboss t`")
            sent = await self.bot.send_message("oboss t", priority=True)
            if not sent:
                self.bot.log("ERROR", f"TICKET CHECK ({reason}): failed to send `oboss t`")
                return None

            try:
                await asyncio.wait_for(self.ticket_check_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                self.bot.log("ERROR", f"TICKET CHECK ({reason}): timed out waiting for OwO response")
                return None

            self.bot.log("BOSS", f"TICKET CHECK ({reason}): confirmed {self.tickets}/3")
            return self.tickets

    @commands.Cog.listener()
    async def on_message(self, message):
        if str(message.author.id) != self.bot.owo_bot_id:
            return
        if message.channel.id != self.bot.channel_id:
            return

        if not self.bot.is_message_for_me(message):
            return

        full_content = self.bot.get_full_content(message)
        ticket_count = self._parse_ticket_count(full_content)
        if ticket_count is not None:
            self.tickets = ticket_count
            self.last_reset = time.time()
            self._save_state()
            self.ticket_check_event.set()
            self.bot.log("BOSS", f"Synced tickets with OwO: {self.tickets}/3")

    @commands.Cog.listener()
    async def on_socket_raw_receive(self, msg):
        if not self.enabled or self.bot.paused:
            return
        if isinstance(msg, bytes):
            return

        try:
            raw_data = json.loads(msg)
        except Exception:
            return

        if raw_data.get("t") != "MESSAGE_CREATE":
            return

        data = raw_data.get("d", {})
        author_id = str(data.get("author", {}).get("id") or "")
        if author_id != str(self.bot.owo_bot_id):
            return

        message_id = str(data.get("id") or "")
        channel_id_raw = data.get("channel_id")
        guild_id = str(data.get("guild_id") or "").strip()
        if not message_id:
            self.bot.log("BOSS", "SKIP message: MESSAGE_CREATE has no message id")
            return
        if not channel_id_raw:
            self.bot.log("BOSS", f"SKIP message={message_id}: missing channel_id")
            return

        try:
            channel_id = int(channel_id_raw)
        except (TypeError, ValueError):
            self.bot.log("BOSS", f"SKIP message={message_id}: invalid channel_id={channel_id_raw!r}")
            return

        components = parse_v2_message(data)
        content = (data.get("content") or "").lower()
        v2_text = " ".join(
            c.content for c in components if c.name == "text_display" and c.content
        ).lower()
        labels = " ".join(
            str(c.label) for c in components if c.name == "button" and c.label
        ).lower()
        full_text = f"{content} {v2_text} {labels}"
        is_spawn = "runs away" in full_text or "guild boss" in full_text or "boss battle" in full_text
        fight_btn = self._find_fight_button(components)
        fight_buttons = [
            c for c in components
            if c.name == "button" and c.custom_id
        ]

        if is_spawn or fight_btn:
            button_ids = [str(c.custom_id) for c in fight_buttons]
            self.bot.log(
                "BOSS",
                f"DETECT message={message_id} guild={guild_id or '-'} channel={channel_id} "
                f"components={len(components)} buttons={button_ids} "
                f"spawn={is_spawn} fight_button={'YES' if fight_btn else 'NO'}"
            )

        if not components:
            if is_spawn:
                self.bot.log("BOSS", f"SKIP message={message_id}: Boss-like message has no parseable components")
            return

        if not is_spawn and not fight_btn:
            return

        # Blacklist always wins, then explicit target matching is required.
        if guild_id in self.ignore_guilds:
            self.bot.log("BOSS", f"SKIP message={message_id}: guild {guild_id} is ignored")
            return

        if not self._is_target_guild(guild_id):
            self.bot.log(
                "BOSS",
                f"SKIP message={message_id}: guild {guild_id or '-'} is not targeted "
                f"(targets={','.join(self.target_guilds) or 'none'})"
            )
            return

        if not fight_btn:
            self.bot.log(
                "BOSS",
                f"SKIP message={message_id}: Boss detected in targeted guild but no usable fight button was found"
            )
            return

        battle_id = get_boss_battle_id(components)
        if battle_id and battle_id in self.joined_ids:
            self.bot.log("BOSS", f"SKIP message={message_id}: battle {battle_id} already processed")
            return

        tracking_id = str(battle_id or f"msg_{message_id}")
        if tracking_id in self.processing_ids:
            self.bot.log("BOSS", f"SKIP message={message_id}: battle {tracking_id} is already being processed")
            return

        self._check_reset()
        # If the local state says zero, perform one authoritative check before
        # deciding to stop. We never invent a ticket decrement locally.
        if self.tickets <= 0:
            checked = await self._request_ticket_check("before-join")
            if checked is None or checked <= 0:
                self.bot.log("BOSS", f"SKIP message={message_id}: no confirmed Boss tickets")
                return

        if random.randint(1, 100) > self.join_chance:
            self.bot.log(
                "BOSS",
                f"SKIP message={message_id}: join_chance={self.join_chance}% rejected this spawn"
            )
            self.joined_ids.add(tracking_id)
            self._save_state()
            return

        self.processing_ids.add(tracking_id)
        try:
            self.bot.log(
                "BOSS",
                f"JOIN attempt message={message_id} guild={guild_id} channel={channel_id} "
                f"battle={tracking_id} ticket={self.tickets}/3 custom_id={fight_btn.custom_id}"
            )

            delay = random.uniform(0.5, 1.5)
            await asyncio.sleep(delay)

            if self.bot.paused:
                self.bot.log("BOSS", f"ABORT message={message_id}: bot paused during {delay:.2f}s delay")
                return

            success = await self.bot.interactions.click_button_raw(
                custom_id=fight_btn.custom_id,
                message_id=message_id,
                channel_id=channel_id,
                author_id=author_id,
                guild_id=guild_id,
                flags=data.get("flags", 0)
            )

            if success:
                # The click itself is not treated as authoritative ticket state.
                # Ask OwO again and only continue according to the returned count.
                self.joined_ids.add(tracking_id)
                self._save_state()
                self.bot.log(
                    "SUCCESS",
                    f"Joined Boss Battle! guild={guild_id} battle={tracking_id}; syncing tickets with `oboss t`"
                )

                checked = await self._request_ticket_check("after-join")
                if checked is None:
                    self.bot.log("ERROR", "Boss joined but ticket check failed; stopping Boss loop until next spawn")
                elif checked <= 0:
                    self.bot.log("BOSS", "Boss tickets exhausted: 0/3. Waiting for reset.")
                else:
                    self.bot.log("BOSS", f"Boss tickets remaining: {checked}/3. Ready for next Boss.")
            else:
                self.bot.log(
                    "ERROR",
                    f"JOIN FAILED message={message_id} guild={guild_id} battle={tracking_id} "
                    f"custom_id={fight_btn.custom_id}"
                )
        finally:
            self.processing_ids.discard(tracking_id)


async def setup(bot):
    await bot.add_cog(Boss(bot))
