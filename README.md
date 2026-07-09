# stragetic_for_ETH

ETHUSDT 日K 機器學習交易策略研究專案。

這個專案的核心目標是建立一套可重跑、可替換策略、可驗證參數高原的 ETH 日K 回測框架。目前主策略採用：

```text
v2_no_funding_oi
```

也就是保留原本資料收集、特徵工程、標籤、回測流程，但模型訓練與推論時排除 Funding Rate / Open Interest 相關特徵。

---

## 目前主策略

主策略名稱：

```text
eth_literature_long_daily
```

主模型版本：

```text
v2_no_funding_oi
```

交易標的：

```text
ETHUSDT
```

時間週期：

```text
1d
```

方向：

```text
只做多
```

目標標籤：

```text
target_atr
```

標籤定義：

```text
TP = 3.0 * ATR
SL = 1.5 * ATR
Timeout = 24 根 K
```

日K 下代表最多持倉 24 天。

---

## no_funding_oi 是什麼

原本模型會使用 Funding Rate / Open Interest 相關特徵。

新版模型排除：

```text
funding_*
oi_*
funding_rate
```

也就是以下類型的特徵不再進入模型訓練與推論：

```text
funding_rate
funding_rate_ma_24
funding_zscore_30d
oi_change_1h
oi_change_24h
oi_price_divergence
```

但資料仍然可以保留在本機，方便未來研究。只是 v2 主模型不使用它們。

---

## 為什麼選 v2_no_funding_oi

同一組固定參數比較：

```text
threshold = 0.58
min_bull_score = 1
max_risk_score = 0
max_concurrent = 6
risk_pct = 0.03
```

| 模型 | Trades | Total Return | CAGR | MDD | Win Rate |
|---|---:|---:|---:|---:|---:|
| v1 baseline | 73 | +443.07% | 47.90% | -19.93% | 67.12% |
| v2 no_funding_oi | 81 | +531.50% | 53.15% | -20.56% | 66.67% |

v2 的 MDD 稍微高一點，但總報酬、CAGR、Sharpe、平均單筆損益都更好。

更重要的是 v2 多出來的交易品質較好：

| 類型 | 說明 | PnL |
|---|---|---:|
| both | v1/v2 都有進場 | v1: +3,662,237 / v2: +3,847,626 |
| v1_only | 只有 v1 有 | +768,419 |
| v2_only | 只有 v2 有 | +1,467,336 |

`v2_only` 的勝率約 `76.19%`，代表 v2 多出來的交易不是亂交易，而是有較好的品質。

---

## 正式主參數

目前正式使用原本主參數：

```text
threshold = 0.58
min_bull_score = 1
max_risk_score = 0
max_concurrent = 6
risk_pct = 0.03
```

參數說明：

| 參數 | 說明 |
|---|---|
| `threshold` | 模型預測機率門檻，越高越少交易 |
| `min_bull_score` | 多頭確認分數，越高越嚴格 |
| `max_risk_score` | 允許的最高風險分數，0 最嚴格 |
| `max_concurrent` | 最多同時持倉數 |
| `risk_pct` | 每筆交易承擔帳戶風險比例 |

這組是目前主策略回測與年度檢查採用的基準參數。後續如果要優化，應先以這組作為 baseline，再比較新參數是否真的改善 Sharpe、CAGR、MDD 與年度穩定性。

---

## 策略架構

整體架構是：

```text
資料 -> 特徵 -> 模型 -> 策略 -> 回測
```

### 1. 資料層

來源：

```text
Bybit V5 API
```

資料類型：

```text
K 線資料
Funding Rate
Open Interest
```

注意：雖然本機仍可收集 Funding / OI，但 v2 主模型不使用 Funding / OI 特徵。

### 2. 特徵層

包含：

```text
RSI
PPO
ATR / NATR
Bollinger Band Width
MA Bias
ROC
BTC cross momentum
K 線型態特徵
文獻型 binary/state 特徵
```

文獻型特徵包含：

```text
literature_bull_score
literature_long_risk_score
```

這兩個分數用來做策略層的額外過濾。

### 3. 模型層

模型：

```text
XGBoost classifier
```

驗證方式：

```text
Purged Walk-Forward Cross Validation
```

目標：

```text
target_atr
```

### 4. 策略層

進場條件：

```text
model probability >= threshold
literature_bull_score >= min_bull_score
literature_long_risk_score <= max_risk_score
```

目前策略只做多。

### 5. 回測層

使用 DRC portfolio simulation：

```text
固定風險比例
最多同時持倉數
TP / SL / timeout 出場
複利資金曲線
MDD / CAGR / Sharpe 統計
```

---

## 主要指令

### 安裝

```powershell
git clone https://github.com/steven0401/stragetic_for_ETH.git
cd stragetic_for_ETH

python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### 設定 API

```powershell
copy .env.example .env
```

填入：

```text
BYBIT_API_KEY=
BYBIT_API_SECRET=
DISCORD_WEBHOOK_URL=
```

### 抓資料

```powershell
python main.py
```

### 建立日K特徵

```powershell
python build_features.py --timeframe 1d
```

### 訓練模型

```powershell
python train_models.py --timeframe 1d
```

### 跑 threshold scan

```powershell
python run_backtest.py --timeframe 1d
```

### 跑主策略

```powershell
python run_strategy_backtest.py --strategy eth_literature_long_daily --symbol ETHUSDT --timeframe 1d
```

### 雲端實盤 / Testnet 跑策略

先打包 live 必要模型檔：

```powershell
python package_live_artifacts.py
```

雲端主機 clone 專案、安裝套件後，把 `live_artifacts.zip` 解壓到專案根目錄，接著設定 `.env`：

```text
BYBIT_API_KEY=
BYBIT_API_SECRET=
DISCORD_WEBHOOK_URL=
BYBIT_TESTNET=true
LIVE_TRADING_ENABLED=true
LIVE_TRADING_CONFIRM=I_UNDERSTAND_TESTNET
LIVE_MAX_NOTIONAL_PCT=1.0
LIVE_MAX_ACTIVE_PER_SYMBOL=1
```

啟動：

```bash
python run_live_daily_trade.py
```

完整雲端部署與 systemd 教學見：

```text
docs/live_cloud_trading.md
```

---

## 專案結構

```text
stragetic_for_ETH/
├── config.py
├── main.py
├── build_features.py
├── train_models.py
├── run_backtest.py
├── run_strategy_backtest.py
├── run_live_daily_trade.py
├── package_live_artifacts.py
├── data/
├── features/
├── models/
├── backtest/
├── strategies/
├── tests/
└── docs/
```

重要檔案：

| 檔案 | 說明 |
|---|---|
| `config.py` | 主要參數、路徑、no_funding_oi 特徵排除 |
| `features/indicators.py` | 技術指標與文獻型特徵 |
| `features/labels.py` | Triple-barrier 標籤 |
| `models/builder.py` | 模型訓練流程 |
| `strategies/literature_long.py` | 文獻型做多策略 |
| `run_strategy_backtest.py` | 策略回測入口 |
| `run_live_daily_trade.py` | 雲端日K實盤/Testnet 入口，會下 Bybit 單並發 Discord 通知 |
| `package_live_artifacts.py` | 打包雲端 live 必要模型與 validation report |
| `docs/no_funding_oi_decision_summary.md` | v1/v2 決策摘要 |
| `docs/live_cloud_trading.md` | 雲端部署、Discord、Testnet/Mainnet 啟動教學 |

---

## storage 資料夾說明

`storage/` 是本機輸出資料夾，不會上傳到 GitHub。

| 資料夾 | 用途 |
|---|---|
| `storage/raw` | 原始 Bybit 資料 |
| `storage/features` | 特徵矩陣與 validation report |
| `storage/models` | 訓練好的模型 `.pkl` |
| `storage/backtest` | 回測結果、交易明細、參數高原 |
| `storage/excel` | 匯出的 Excel |

GitHub 只保留 `.gitkeep`，不包含大型資料、模型、回測圖表。

---

## 測試

```powershell
pytest
```

目前本機測試結果：

```text
157 passed, 4 warnings
```

---

## 注意事項

- 這是研究回測專案，不是投資建議。
- GitHub 不包含歷史資料與模型，需要自行重跑。
- 目前主力研究對象是 `ETHUSDT` 日K。
- 不建議直接把同一組參數套到 BTC、ADA、SOL 或其他週期。
- 4H 測試曾顯示同一組日K參數不適合直接套用。
