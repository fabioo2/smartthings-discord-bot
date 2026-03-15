# SmartThings Discord Bot

A Discord bot that monitors your Samsung SmartThings range and sends alerts when the stovetop or oven has been left on too long. Alerts include interactive snooze and dismiss buttons, and will repeat until acknowledged.

## Features

- Monitors both cooktop (burners) and oven independently
- Configurable alert thresholds (default: 30 min cooktop, 2 hr oven)
- Discord alerts with snooze buttons (30m, 1h, 2h) and dismiss
- Re-alerts every 15 minutes if no response
- Oven alerts include mode and temperature
- Alerts auto-clear when the appliance is turned off
- Runs as a lightweight Docker container
  
![Discord alert](https://github.com/user-attachments/assets/82f0506a-b35d-4849-9e3c-3bd1d8b420bb)

## Setup

### 1. SmartThings API Token

- Go to https://account.smartthings.com/tokens
- Generate a token with **Devices (read)** permission
- Find your range's device ID:
  ```bash
  curl -H "Authorization: Bearer YOUR_TOKEN" \
    https://api.smartthings.com/v1/devices
  ```

### 2. Discord Bot

- Create an application at https://discord.com/developers/applications
- Go to **Bot** tab and copy the bot token
- Go to **OAuth2 > URL Generator**, select scope **bot** with permissions **Send Messages** and **Embed Links**
- Use the generated URL to invite the bot to your server
- Copy the channel ID where you want alerts (enable Developer Mode in Discord settings, then right-click the channel)

### 3. Configuration

Copy `.env.example` to `.env` and fill in your values:

```
SMARTTHINGS_TOKEN=your_smartthings_token
STOVE_DEVICE_ID=your_device_id
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_channel_id

COOKTOP_THRESHOLD_MIN=30
OVEN_THRESHOLD_MIN=120
POLL_INTERVAL_SEC=60
REALERT_INTERVAL_MIN=15
```

### 4. Run

```bash
docker compose up -d --build
```

Check logs:
```bash
docker logs stove-monitor
```
