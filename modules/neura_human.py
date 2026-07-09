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
import random
import time
import traceback

# you can edit these according to you :
SPEED_PRESETS = {
    "fast": {
        "reaction_min": 0.1,
        "reaction_max": 0.4,
        "key_delay_min": 0.01,
        "key_delay_max": 0.03,
        "mistake_rate": 0.0,
        "enter_delay_min": 0.2,
        "enter_delay_max": 0.4
    },
    "medium": {
        "reaction_min": 0.4,
        "reaction_max": 1.0,
        "key_delay_min": 0.02,
        "key_delay_max": 0.05,
        "mistake_rate": 0.02,
        "enter_delay_min": 0.3,
        "enter_delay_max": 0.6
    },
    "slow": {
        "reaction_min": 1.0,
        "reaction_max": 2.2,
        "key_delay_min": 0.04,
        "key_delay_max": 0.08,
        "mistake_rate": 0.05,
        "enter_delay_min": 0.5,
        "enter_delay_max": 1.0
    }
}

def get_speed_preset(preset_name, custom_overrides=None):
    preset = SPEED_PRESETS.get(preset_name, SPEED_PRESETS["medium"]).copy()
    if custom_overrides and isinstance(custom_overrides, dict):
        for key in preset:
            if key in custom_overrides and isinstance(custom_overrides[key], (int, float)):
                preset[key] = custom_overrides[key]
    return preset

def update_speed_preset(preset_name, overrides):
    if preset_name in SPEED_PRESETS:
        for key, value in overrides.items():
            if key in SPEED_PRESETS[preset_name] and isinstance(value, (int, float)):
                SPEED_PRESETS[preset_name][key] = value
        return True
    return False

def normalize_time(val):
    if not isinstance(val, (int, float)): return 0.1
    return val / 1000.0 if val >= 2 else val


class NeuraHuman:
    last_break_check = time.time()
    break_lock = asyncio.Lock()
    is_on_break = False
    
    @staticmethod
    async def neura_send(bot, channel, content):
        start_time = time.time()
        
        if NeuraHuman.is_on_break:
            bot.log("STEALTH", "Waiting for existing break to finish...")
            while NeuraHuman.is_on_break:
                await asyncio.sleep(1)
        
        stealth_cfg = bot.config.get('stealth', {})
        hb_cfg = stealth_cfg.get('human_break', {})
        hb_enabled = hb_cfg.get('enabled', True)
        hb_duration = hb_cfg.get('duration_min', 10) * 60
        hb_interval = hb_cfg.get('interval_min', 45) * 60

        runtime = time.time() - NeuraHuman.last_break_check
        if hb_enabled and runtime > hb_interval: 
            async with NeuraHuman.break_lock:
                if time.time() - NeuraHuman.last_break_check > hb_interval and not NeuraHuman.is_on_break:
                    NeuraHuman.is_on_break = True
                    start_break_time = time.time()
                    bot.log("STEALTH", f"Pausing for {int(hb_duration/60)}mins for human behaviour (Break Time)")
                    try:
                        while NeuraHuman.is_on_break:
                            curr_stealth = bot.config.get('stealth', {})
                            curr_hb = curr_stealth.get('human_break', {})
                            
                            if not curr_hb.get('enabled', True):
                                bot.log("STEALTH", "Break interrupted: Human Break disabled in settings.")
                                break
                            
                            curr_duration = curr_hb.get('duration_min', 10) * 60
                            if time.time() - start_break_time >= curr_duration:
                                break
                                
                            await asyncio.sleep(1)
                    finally:
                        NeuraHuman.last_break_check = time.time()
                        NeuraHuman.is_on_break = False
                        bot.log("STEALTH", "Break finished. Resuming operations.")
                elif NeuraHuman.is_on_break:
                     while NeuraHuman.is_on_break:
                        await asyncio.sleep(1)

        stealth_cfg = bot.config.get('stealth', {})
        if not isinstance(stealth_cfg, dict):
            stealth_cfg = {}

        typing_enabled = stealth_cfg.get('typing_enabled', None)
        typing_cfg = stealth_cfg.get('typing', {})
        if typing_enabled is None:
            typing_enabled = typing_cfg.get('enabled', False) if isinstance(typing_cfg, dict) else False
        
        if not typing_enabled:
            try:
                await channel.send(content)
                return True
            except:
                return False
        
        speed_preset_name = stealth_cfg.get('speed_preset', 'medium')
        custom_overrides = stealth_cfg.get('speed_custom', None)
        if isinstance(custom_overrides, dict) and not custom_overrides.get('enabled', False):
            custom_overrides = None
        
        if speed_preset_name in SPEED_PRESETS:
            preset = get_speed_preset(speed_preset_name, custom_overrides)
            reaction_min = normalize_time(preset["reaction_min"])
            reaction_max = normalize_time(preset["reaction_max"])
            key_delay_min = normalize_time(preset["key_delay_min"])
            key_delay_max = normalize_time(preset["key_delay_max"])
            mistake_rate = preset["mistake_rate"]
            enter_delay_min = normalize_time(preset["enter_delay_min"])
            enter_delay_max = normalize_time(preset["enter_delay_max"])
        else:
            reaction_min = typing_cfg.get('reaction_min', 1.0) if isinstance(typing_cfg, dict) else 1.0
            reaction_max = typing_cfg.get('reaction_max', 3.0) if isinstance(typing_cfg, dict) else 3.0
            mistake_rate = typing_cfg.get('mistake_rate', 5) if isinstance(typing_cfg, dict) else 5
            extra_delay = typing_cfg.get('extra_delay', 0) if isinstance(typing_cfg, dict) else 0
            key_delay_min = 0.02
            key_delay_max = 0.08
            enter_delay_min = 0.3
            enter_delay_max = 0.7
        
        if isinstance(mistake_rate, (int, float)) and mistake_rate > 1:
            mistake_rate /= 100.0

        reaction_time = random.uniform(reaction_min if isinstance(reaction_min, (int, float)) else 1.0, 
                                       reaction_max if isinstance(reaction_max, (int, float)) else 3.0)
        if reaction_time > 0.1:
            await asyncio.sleep(reaction_time)

        try:
            async with channel.typing():
                chars = list(str(content))
                i = 0
                typo_count = 0
                
                start_time = time.time()
                
                while i < len(chars):
                    if bot.paused:
                        return False
                    char = chars[i]
                    delay = random.uniform(key_delay_min, key_delay_max)
                    if char in ".,!?;": delay += random.uniform(0.1, 0.2)
                    
                    if isinstance(mistake_rate, (int, float)) and random.random() < mistake_rate and i < len(chars) - 1:
                        typo_count += 1
                        await asyncio.sleep(random.uniform(0.1, 0.2)) 
                        await asyncio.sleep(random.uniform(0.2, 0.5))
                        await asyncio.sleep(random.uniform(0.1, 0.2))
                    
                    await asyncio.sleep(delay)
                    i += 1
                
                if speed_preset_name in SPEED_PRESETS:
                    enter_delay = random.uniform(enter_delay_min, enter_delay_max)
                else:
                    extra_delay_val = stealth_cfg.get('speed_custom', {}).get('extra_delay', typing_cfg.get('extra_delay', 0)) if isinstance(typing_cfg, dict) else 0
                    enter_delay = random.uniform(0.3, 0.7) + (random.uniform(0, extra_delay_val) if isinstance(extra_delay_val, (int, float)) and extra_delay_val > 0 else 0)
                await asyncio.sleep(enter_delay)
                
                total_time = round(time.time() - start_time, 2)
                if typo_count > 0:
                    bot.log("STEALTH", f"Typing: {total_time}s (Simulated {typo_count} typos)")
                
                await channel.send(content)
                return True
        except Exception:
            try:
                await channel.send(content)
                return True
            except Exception as final_e:
                bot.log("ERROR", f"Critical send failure: {final_e}")
                return False
    
    @staticmethod
    def neura_calculate_typing_speed(text, wpm=55):
        return (len(text) / 5) / wpm * 60