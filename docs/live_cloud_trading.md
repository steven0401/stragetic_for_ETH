# Live Cloud Trading

This guide runs the ETHUSDT daily strategy on a cloud machine, submits Bybit
USDT perpetual orders, and sends Discord webhook notifications.

## What Runs

Live entry point:

```bash
python run_live_daily_trade.py
```

Strategy:

```text
symbol = ETHUSDT
timeframe = 1d
threshold = 0.58
min_bull_score = 1
max_risk_score = 0
risk_pct = 0.03
TP = entry + 3.0 * ATR
SL = entry - 1.5 * ATR
timeout = 24 daily bars
```

The live runner checks every `LIVE_DAILY_INTERVAL_MINUTES`, but each closed
daily candle is processed only once.

## Safety Defaults

Execution is locked unless all three are true:

```env
LIVE_TRADING_ENABLED=true
BYBIT_API_KEY=...
BYBIT_API_SECRET=...
```

Testnet also requires:

```env
BYBIT_TESTNET=true
LIVE_TRADING_CONFIRM=I_UNDERSTAND_TESTNET
```

Mainnet requires:

```env
BYBIT_TESTNET=false
LIVE_TRADING_CONFIRM=I_UNDERSTAND_MAINNET_RISK
```

The default live setting allows only one active ETHUSDT position:

```env
LIVE_MAX_ACTIVE_PER_SYMBOL=1
```

This is intentional. The backtest can model overlapping daily positions, but
Bybit one-way USDT perpetual mode merges entries into one net position.

## Files Needed On The Cloud Machine

GitHub contains the code, but not the trained model artifacts under `storage/`.
Before starting live trading, copy these files to the cloud machine:

```text
storage/features/ETHUSDT_1d_validation_report.json
storage/models/ETHUSDT_1d_target_atr_fold1.pkl
storage/models/ETHUSDT_1d_target_atr_fold2.pkl
storage/models/ETHUSDT_1d_target_atr_fold3.pkl
storage/models/ETHUSDT_1d_target_atr_fold4.pkl
storage/models/ETHUSDT_1d_target_atr_fold5.pkl
```

Create a zip locally:

```powershell
python package_live_artifacts.py
```

Upload it:

```powershell
scp live_artifacts.zip user@your_server_ip:~/stragetic_for_ETH/
```

Extract it on the cloud machine:

```bash
cd ~/stragetic_for_ETH
unzip -o live_artifacts.zip
```

## Cloud Setup

```bash
git clone https://github.com/steven0401/stragetic_for_ETH.git
cd stragetic_for_ETH
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env`:

```env
BYBIT_API_KEY=your_key
BYBIT_API_SECRET=your_secret
DISCORD_WEBHOOK_URL=your_discord_webhook
BYBIT_TESTNET=true
LIVE_TRADING_ENABLED=true
LIVE_TRADING_CONFIRM=I_UNDERSTAND_TESTNET
LIVE_MAX_NOTIONAL_PCT=1.0
LIVE_MAX_ACTIVE_PER_SYMBOL=1
```

Start manually:

```bash
source .venv/bin/activate
python run_live_daily_trade.py
```

## Run With systemd

Create a service:

```bash
sudo nano /etc/systemd/system/eth-strategy.service
```

Paste and adjust `User` and `WorkingDirectory`:

```ini
[Unit]
Description=ETH daily strategy live trader
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/stragetic_for_ETH
ExecStart=/home/ubuntu/stragetic_for_ETH/.venv/bin/python run_live_daily_trade.py
Restart=always
RestartSec=15

[Install]
WantedBy=multi-user.target
```

Enable it:

```bash
sudo systemctl daemon-reload
sudo systemctl enable eth-strategy
sudo systemctl start eth-strategy
```

Check logs:

```bash
sudo journalctl -u eth-strategy -f
```

## Discord Notifications

The runner sends Discord messages when:

```text
daemon starts
order is submitted
existing position causes a signal skip
Bybit position disappears, likely TP/SL/manual close
timeout close is submitted
```

## Pause Trading

Create a kill-switch file:

```bash
touch .disabled
```

Remove it to resume new entries:

```bash
rm .disabled
```

Existing exchange TP/SL remains on Bybit.

## Mainnet Checklist

Before switching to mainnet:

```text
1. Run Testnet first.
2. Confirm Discord receives startup and order messages.
3. Confirm Bybit Testnet position size, TP, and SL are correct.
4. Confirm .disabled pauses new entries.
5. Only then set BYBIT_TESTNET=false and LIVE_TRADING_CONFIRM=I_UNDERSTAND_MAINNET_RISK.
```
