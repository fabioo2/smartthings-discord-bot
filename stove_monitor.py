import os
import asyncio
from datetime import datetime, timedelta

import aiohttp
import discord
from discord.ui import View, Button

SMARTTHINGS_TOKEN = os.environ["SMARTTHINGS_TOKEN"]
DEVICE_ID = os.environ["STOVE_DEVICE_ID"]
DISCORD_BOT_TOKEN = os.environ["DISCORD_BOT_TOKEN"]
DISCORD_CHANNEL_ID = int(os.environ["DISCORD_CHANNEL_ID"])
COOKTOP_THRESHOLD_MIN = float(os.environ.get("COOKTOP_THRESHOLD_MIN", "30"))
OVEN_THRESHOLD_MIN = float(os.environ.get("OVEN_THRESHOLD_MIN", "120"))
POLL_INTERVAL_SEC = int(os.environ.get("POLL_INTERVAL_SEC", "60"))
REALERT_INTERVAL_MIN = float(os.environ.get("REALERT_INTERVAL_MIN", "15"))

API_URL = f"https://api.smartthings.com/v1/devices/{DEVICE_ID}/status"


class SnoozeView(View):
    def __init__(self, monitor, appliance):
        super().__init__(timeout=None)
        self.monitor = monitor
        self.appliance = appliance

        for label, mins in [("30m", 30), ("1h", 60), ("2h", 120)]:
            btn = Button(
                label=f"Snooze {label}",
                style=discord.ButtonStyle.primary,
                custom_id=f"snooze_{appliance}_{mins}_{id(self)}",
            )
            btn.callback = self._make_snooze(mins)
            self.add_item(btn)

        ok_btn = Button(
            label="It's OK",
            style=discord.ButtonStyle.success,
            custom_id=f"dismiss_{appliance}_{id(self)}",
        )
        ok_btn.callback = self._dismiss
        self.add_item(ok_btn)

    def _make_snooze(self, minutes):
        async def callback(interaction: discord.Interaction):
            until = datetime.now() + timedelta(minutes=minutes)
            setattr(self.monitor, f"{self.appliance}_snoozed_until", until)
            setattr(self.monitor, f"{self.appliance}_alert_msg", None)
            setattr(self.monitor, f"{self.appliance}_last_alert", None)
            embed = discord.Embed(
                description=(
                    f"Snoozed **{self.appliance}** alert for **{minutes}m**. "
                    f"I'll check again at {until.strftime('%I:%M %p')}."
                ),
                color=discord.Color.green(),
            )
            await interaction.response.edit_message(embed=embed, view=None)

        return callback

    async def _dismiss(self, interaction: discord.Interaction):
        until = datetime.now() + timedelta(hours=24)
        setattr(self.monitor, f"{self.appliance}_snoozed_until", until)
        setattr(self.monitor, f"{self.appliance}_alert_msg", None)
        setattr(self.monitor, f"{self.appliance}_last_alert", None)
        embed = discord.Embed(
            description=(
                f"Got it! I won't alert about the **{self.appliance}** "
                f"again until it's turned off and back on."
            ),
            color=discord.Color.green(),
        )
        await interaction.response.edit_message(embed=embed, view=None)


class StoveMonitor(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        super().__init__(intents=intents)
        self.cooktop_on_since = None
        self.oven_on_since = None
        self.cooktop_snoozed_until = None
        self.oven_snoozed_until = None
        self.cooktop_alert_msg = None
        self.oven_alert_msg = None
        self.cooktop_last_alert = None
        self.oven_last_alert = None

    async def setup_hook(self):
        self.loop.create_task(self._monitor_loop())

    async def on_ready(self):
        print(f"Stove monitor online as {self.user}")

    async def _fetch_status(self):
        headers = {"Authorization": f"Bearer {SMARTTHINGS_TOKEN}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(API_URL, headers=headers) as resp:
                if resp.status == 200:
                    return await resp.json()
                print(f"SmartThings API error: {resp.status}")
                return None

    async def _monitor_loop(self):
        await self.wait_until_ready()
        channel = self.get_channel(DISCORD_CHANNEL_ID)
        if channel is None:
            channel = await self.fetch_channel(DISCORD_CHANNEL_ID)

        while not self.is_closed():
            try:
                data = await self._fetch_status()
                if data:
                    await self._check(data, channel)
            except Exception as e:
                print(f"Monitor error: {e}")
            await asyncio.sleep(POLL_INTERVAL_SEC)

    async def _check(self, data, channel):
        now = datetime.now()
        main = data.get("components", {}).get("main", {})

        # --- Cooktop (stovetop burners) ---
        cooktop_val = (
            main.get("custom.cooktopOperatingState", {})
            .get("cooktopOperatingState", {})
            .get("value")
        )

        if cooktop_val == "run":
            if self.cooktop_on_since is None:
                self.cooktop_on_since = now
            elapsed = (now - self.cooktop_on_since).total_seconds() / 60
            snoozed = self.cooktop_snoozed_until and now < self.cooktop_snoozed_until
            if elapsed >= COOKTOP_THRESHOLD_MIN and not snoozed:
                should_alert = not self.cooktop_alert_msg
                if self.cooktop_last_alert:
                    since_last = (now - self.cooktop_last_alert).total_seconds() / 60
                    if since_last >= REALERT_INTERVAL_MIN:
                        should_alert = True
                if should_alert:
                    await self._alert(channel, "cooktop", elapsed)
        else:
            self.cooktop_on_since = None
            self.cooktop_snoozed_until = None
            self.cooktop_alert_msg = None
            self.cooktop_last_alert = None

        # --- Oven ---
        oven_val = (
            main.get("samsungce.ovenOperatingState", {})
            .get("operatingState", {})
            .get("value")
        )

        if oven_val == "running":
            if self.oven_on_since is None:
                self.oven_on_since = now
            elapsed = (now - self.oven_on_since).total_seconds() / 60
            snoozed = self.oven_snoozed_until and now < self.oven_snoozed_until
            if elapsed >= OVEN_THRESHOLD_MIN and not snoozed:
                should_alert = not self.oven_alert_msg
                if self.oven_last_alert:
                    since_last = (now - self.oven_last_alert).total_seconds() / 60
                    if since_last >= REALERT_INTERVAL_MIN:
                        should_alert = True
                if should_alert:
                    oven_mode = (
                        main.get("samsungce.ovenMode", {})
                        .get("ovenMode", {})
                        .get("value", "")
                    )
                    oven_temp = (
                        main.get("temperatureMeasurement", {})
                        .get("temperature", {})
                        .get("value", "?")
                    )
                    await self._alert(channel, "oven", elapsed, oven_mode, oven_temp)
        else:
            self.oven_on_since = None
            self.oven_snoozed_until = None
            self.oven_alert_msg = None
            self.oven_last_alert = None

    async def _alert(self, channel, appliance, elapsed_min, mode=None, temp=None):
        h, m = int(elapsed_min // 60), int(elapsed_min % 60)
        time_str = f"{h}h {m}m" if h else f"{m}m"
        desc = f"Your **{appliance}** has been on for **{time_str}**!"
        if appliance == "oven" and mode and mode != "NoOperation":
            desc += f"\nMode: **{mode}** at **{temp}\u00b0F**"

        embed = discord.Embed(
            title="\U0001f525 Stove Alert",
            description=desc,
            color=discord.Color.red(),
        )
        embed.set_footer(text="Is this intentional?")

        view = SnoozeView(self, appliance)
        msg = await channel.send(embed=embed, view=view)
        setattr(self, f"{appliance}_alert_msg", msg)
        setattr(self, f"{appliance}_last_alert", datetime.now())


StoveMonitor().run(DISCORD_BOT_TOKEN)
