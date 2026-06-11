# ETH 日K v1 vs v2 決策摘要註解

這份文件是在解釋 `no_funding_oi` 版本為什麼被選為 ETH 日K 主模型候選。

## 結論

目前比較結果偏向選擇：

```text
v2_no_funding_oi
```

原因是 v2 在同一組固定參數下，整體報酬、CAGR、Sharpe、平均單筆損益都比 v1 高，MDD 只小幅變差。

## v1 / v2 定義

```text
v1_baseline
```

原本模型，包含所有特徵，也包含 funding rate / open interest 相關特徵。

```text
v2_no_funding_oi
```

新模型，資料收集、標籤、回測方式都和 v1 一樣，但模型訓練與推論時排除：

```text
funding_*
oi_*
funding_rate
```

也就是不讓模型使用資金費率與未平倉量特徵。

## 固定參數比較

固定參數是：

```text
threshold = 0.58
min_bull_score = 1
max_risk_score = 0
max_concurrent = 6
risk_pct = 0.03
```

結果摘要：

```text
v1 final_equity = 5,430,656
v2 final_equity = 6,314,962
```

v2 的總結果比較好。

```text
v1 MDD = -19.93%
v2 MDD = -20.56%
```

v2 回撤稍微大一點，但差距不大。

## 交易重疊

交易重疊分析分成三類：

```text
both
```

v1 和 v2 都有進場的日期。

```text
v1_only
```

只有 v1 有進場，v2 沒有。

```text
v2_only
```

只有 v2 有進場，v1 沒有。

重點解讀：

```text
both:
v1_pnl = 3,662,237
v2_pnl = 3,847,626
```

同樣日期的交易，v2 還是略好。

```text
v1_only:
v1_pnl = 768,419
```

v1 獨有交易也有賺，所以 v1 不是沒價值。

```text
v2_only:
v2_pnl = 1,467,336
v2_win_rate = 76.19%
```

這是最關鍵的地方。v2 多出來的交易品質很好，不只是亂增加交易次數。

## 參數高原

參數高原的意思是：

```text
不是只看單一最佳點，
而是看附近一整片參數區間是否都表現穩定。
```

v1 平衡參數：

```text
threshold = 0.58
min_bull_score = 1
max_risk_score = 0
max_concurrent = 6
risk_pct = 0.03
```

v2 平衡參數：

```text
threshold = 0.59
min_bull_score = 2
max_risk_score = 0
max_concurrent = 6
risk_pct = 0.04
```

不過最後建議使用 `risk_pct = 0.03`，降低實際使用時的資金波動。

## 最終建議參數

```text
model = v2_no_funding_oi
threshold = 0.59
min_bull_score = 2
max_risk_score = 0
max_concurrent = 6
risk_pct = 0.03
```

這組參數比原本固定參數更嚴格一點：

```text
threshold 從 0.58 提高到 0.59
min_bull_score 從 1 提高到 2
```

意思是進場會少一點，但交易品質更好。

## 建議

目前可以把 v2 當作主策略候選，但保留 v1 作為對照組。

建議下一步：

```text
1. 用 v2 建立正式主策略 profile
2. 用 risk_pct = 0.02 / 0.03 / 0.04 做三種風險版本
3. 繼續保留 v1 報告，不要刪掉
```
