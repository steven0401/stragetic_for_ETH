# features/indicators.py
import numpy as np
import pandas as pd
import pandas_ta as ta


def _find_ppo_col(ppo_df: "pd.DataFrame", prefix: str) -> str:
    matches = [c for c in ppo_df.columns if c.startswith(prefix)]
    if len(matches) != 1:
        raise ValueError(
            f"Expected exactly 1 PPO column with prefix '{prefix}', "
            f"got {matches}. pandas-ta columns: {list(ppo_df.columns)}"
        )
    return matches[0]


def compute(hourly_df: pd.DataFrame, daily_df: pd.DataFrame, ref_df: pd.DataFrame = None, fr_df: pd.DataFrame = None, oi_df: pd.DataFrame = None) -> pd.DataFrame:
    df = hourly_df.copy()

    # 1. RSI: only 14 and 50 (rsi_7 removed)
    for period in [14, 50]:
        df[f"rsi_{period}"] = ta.rsi(df["close"], length=period)

    # 2. PPO replaces MACD — output is percentage-based, no absolute-value trap
    # pandas-ta column order varies by version; use prefix matching for safety
    ppo = ta.ppo(df["close"], fast=12, slow=26, signal=9)
    ppo_col      = _find_ppo_col(ppo, "PPO_")
    ppo_sig_col  = _find_ppo_col(ppo, "PPOs")
    ppo_hist_col = _find_ppo_col(ppo, "PPOh")
    df["ppo"]        = ppo[ppo_col]
    df["ppo_signal"] = ppo[ppo_sig_col]
    df["ppo_hist"]   = ppo[ppo_hist_col]

    # 3. ATR: [14, 72] — kept for labels.py usage
    for period in [14, 72]:
        df[f"atr_{period}"] = ta.atr(df["high"], df["low"], df["close"], length=period)

    # 4. Normalised ATR (immediately after raw ATR)
    df["natr_14"] = df["atr_14"] / df["close"]
    df["natr_72"] = df["atr_72"] / df["close"]

    # 5. Bollinger Band width = (upper - lower) / middle
    # pandas-ta bbands columns order: BBL, BBM, BBU, BBB, BBP
    for length, std_val in [(20, 2.0), (50, 2.5)]:
        bb = ta.bbands(df["close"], length=length, lower_std=std_val, upper_std=std_val)
        bbl_col = next(c for c in bb.columns if c.startswith("BBL"))
        bbm_col = next(c for c in bb.columns if c.startswith("BBM"))
        bbu_col = next(c for c in bb.columns if c.startswith("BBU"))
        lower, middle, upper = bb[bbl_col], bb[bbm_col], bb[bbu_col]
        df[f"bband_width_{length}"] = (upper - lower) / middle

    # 6. MA Bias = (close - SMA_N) / SMA_N
    for period in [20, 50, 200]:
        sma = ta.sma(df["close"], length=period)
        df[f"ma_bias_{period}"] = (df["close"] - sma) / sma

    # 7. Turnover ratio — only period 24 (turnover_ratio_12 removed)
    df["turnover_ratio_24"] = df["turnover"] / df["turnover"].rolling(24).mean()

    # 8. ROC (Rate of Change)
    df["roc_4"]  = df["close"].pct_change(4)
    df["roc_12"] = df["close"].pct_change(12)
    df["roc_24"] = df["close"].pct_change(24)

    # 9. Time-cycle features (extracted from timestamp)
    hour = df["timestamp"].dt.hour
    dow  = df["timestamp"].dt.dayofweek  # 0=Monday, 5=Saturday, 6=Sunday

    df["hour_sin"]   = np.sin(2 * np.pi * hour / 24)
    df["hour_cos"]   = np.cos(2 * np.pi * hour / 24)
    df["dow_sin"]    = np.sin(2 * np.pi * dow / 7)
    df["dow_cos"]    = np.cos(2 * np.pi * dow / 7)
    df["is_weekend"] = dow.isin([5, 6]).astype(int)

    # 10. Daily indicators — computed independently, then merged with look-ahead prevention
    df = _attach_daily_features(df, daily_df)

    # 11. daily_natr_14 — computed after _attach_daily_features() so daily_atr_14 exists
    df["daily_natr_14"] = df["daily_atr_14"] / df["close"]

    # 12. Cross-asset features (only when ref_df is provided)
    if ref_df is not None:
        # ref_df columns: ["timestamp", "ref_close"], timestamp aligned with hourly_df
        df = pd.merge(df, ref_df[["timestamp", "ref_close"]], on="timestamp", how="left")
        df["cross_ratio"]  = df["close"] / df["ref_close"]
        df["cross_roc_24"] = df["ref_close"].pct_change(24)
        df = df.drop(columns=["ref_close"])

    # 13. Funding Rate features
    df = _attach_funding_features(df, fr_df)

    # 14. Open Interest features
    df = _attach_oi_features(df, oi_df)

    # 15. Literature-inspired state features:
    # binary indicator states, candlestick states, and a compact multi-indicator score.
    df = _attach_literature_state_features(df)

    return df


def _attach_literature_state_features(df: pd.DataFrame) -> pd.DataFrame:
    result = df.copy()

    # Binary/state indicator features inspired by continuous-vs-binary indicator studies.
    result["rsi_14_oversold"] = (result["rsi_14"] < 30).astype(int)
    result["rsi_14_overbought"] = (result["rsi_14"] > 70).astype(int)
    result["rsi_14_rising"] = (result["rsi_14"] > result["rsi_14"].shift(1)).astype(int)
    result["ppo_bull"] = (result["ppo"] > result["ppo_signal"]).astype(int)
    result["ppo_hist_rising"] = (result["ppo_hist"] > result["ppo_hist"].shift(1)).astype(int)
    result["ma20_bull"] = (result["ma_bias_20"] > 0).astype(int)
    result["ma50_bull"] = (result["ma_bias_50"] > 0).astype(int)
    result["ma200_bull"] = (result["ma_bias_200"] > 0).astype(int)
    result["roc_4_bull"] = (result["roc_4"] > 0).astype(int)
    result["roc_12_bull"] = (result["roc_12"] > 0).astype(int)
    result["roc_24_bull"] = (result["roc_24"] > 0).astype(int)
    if "cross_roc_24" in result.columns:
        result["cross_roc_24_bull"] = (result["cross_roc_24"] > 0).astype(int)

    natr_72_median = result["natr_14"].rolling(72, min_periods=24).median()
    natr_30d_q80 = result["natr_14"].rolling(720, min_periods=120).quantile(0.80)
    result["atr_expanding"] = (result["natr_14"] > natr_72_median).astype(int)
    result["atr_extreme_high"] = (result["natr_14"] > natr_30d_q80).astype(int)

    bband_q30 = result["bband_width_20"].rolling(720, min_periods=120).quantile(0.30)
    result["bb_squeeze"] = (result["bband_width_20"] < bband_q30).astype(int)

    # Candlestick and two-bar pattern features inspired by candlestick + ML studies.
    candle_range = (result["high"] - result["low"]).replace(0, np.nan)
    body = result["close"] - result["open"]
    result["candle_body_pct"] = body / result["open"]
    result["candle_range_pct"] = candle_range / result["open"]
    result["candle_close_position"] = (result["close"] - result["low"]) / candle_range
    result["candle_bull"] = (body > 0).astype(int)
    result["candle_bear"] = (body < 0).astype(int)
    result["candle_strong_bull"] = (
        (result["candle_bull"] == 1) & (result["candle_close_position"] >= 0.75)
    ).astype(int)
    result["candle_strong_bear"] = (
        (result["candle_bear"] == 1) & (result["candle_close_position"] <= 0.25)
    ).astype(int)
    result["break_prev_high"] = (result["close"] > result["high"].shift(1)).astype(int)
    result["break_prev_low"] = (result["close"] < result["low"].shift(1)).astype(int)
    result["two_bar_bull"] = (
        (result["close"] > result["close"].shift(1)) &
        (result["open"] >= result["low"].shift(1)) &
        (result["close"] >= result["open"])
    ).astype(int)
    result["two_bar_bear"] = (
        (result["close"] < result["close"].shift(1)) &
        (result["open"] <= result["high"].shift(1)) &
        (result["close"] <= result["open"])
    ).astype(int)

    score_cols = [
        "ppo_bull",
        "ppo_hist_rising",
        "ma20_bull",
        "ma50_bull",
        "roc_24_bull",
        "rsi_14_rising",
        "candle_strong_bull",
        "break_prev_high",
    ]
    if "cross_roc_24_bull" in result.columns:
        score_cols.append("cross_roc_24_bull")
    result["literature_bull_score"] = result[score_cols].sum(axis=1)

    risk_cols = [
        "rsi_14_overbought",
        "atr_extreme_high",
        "candle_strong_bear",
        "break_prev_low",
    ]
    result["literature_long_risk_score"] = result[risk_cols].sum(axis=1)

    return result


def _attach_funding_features(
    hourly_df: pd.DataFrame,
    fr_df: pd.DataFrame,
) -> pd.DataFrame:
    result = hourly_df.copy()

    # If no funding rate data, add NaN columns and return
    if fr_df is None or len(fr_df) == 0:
        result["funding_rate"] = np.nan
        result["funding_rate_ma_24"] = np.nan
        result["funding_zscore_30d"] = np.nan
        return result

    hourly_sorted = result.sort_values("timestamp").copy()
    fr_sorted = fr_df.sort_values("timestamp").copy()

    # Normalize timestamp precision to prevent merge issues
    hourly_sorted["timestamp"] = hourly_sorted["timestamp"].astype("datetime64[us, UTC]")
    fr_sorted["timestamp"] = fr_sorted["timestamp"].astype("datetime64[us, UTC]")

    # merge_asof with direction="backward" prevents look-ahead bias
    merged = pd.merge_asof(
        hourly_sorted,
        fr_sorted[["timestamp", "funding_rate"]],
        on="timestamp",
        direction="backward",
    )

    # Rolling features on the merged funding_rate
    merged["funding_rate_ma_24"] = merged["funding_rate"].rolling(24, min_periods=1).mean()

    rolling_mean_720 = merged["funding_rate"].rolling(720, min_periods=1).mean()
    rolling_std_720 = merged["funding_rate"].rolling(720, min_periods=1).std()
    # Replace std=0 with NaN to avoid division by zero
    rolling_std_720 = rolling_std_720.replace(0, np.nan)
    merged["funding_zscore_30d"] = (merged["funding_rate"] - rolling_mean_720) / rolling_std_720

    return merged


def _attach_oi_features(
    hourly_df: pd.DataFrame,
    oi_df: pd.DataFrame,
) -> pd.DataFrame:
    result = hourly_df.copy()

    # If no open interest data, add NaN columns and return
    if oi_df is None or len(oi_df) == 0:
        result["oi_change_1h"] = np.nan
        result["oi_change_24h"] = np.nan
        result["oi_price_divergence"] = np.nan
        return result

    hourly_sorted = result.sort_values("timestamp").copy()
    oi_sorted = oi_df.sort_values("timestamp").copy()

    # Normalize timestamp precision
    hourly_sorted["timestamp"] = hourly_sorted["timestamp"].astype("datetime64[us, UTC]")
    oi_sorted["timestamp"] = oi_sorted["timestamp"].astype("datetime64[us, UTC]")

    # merge_asof with direction="backward" prevents look-ahead bias
    merged = pd.merge_asof(
        hourly_sorted,
        oi_sorted[["timestamp", "open_interest"]],
        on="timestamp",
        direction="backward",
    )

    merged["oi_change_1h"] = merged["open_interest"].pct_change(1)
    merged["oi_change_24h"] = merged["open_interest"].pct_change(24)

    # Divergence: OI and price moving in opposite directions
    merged["oi_price_divergence"] = (
        np.sign(merged["oi_change_24h"]) * np.sign(merged["roc_24"]) < 0
    ).astype(int)

    # Drop raw open_interest — only keep derived features
    merged = merged.drop(columns=["open_interest"], errors="ignore")

    return merged


def _attach_daily_features(
    hourly_df: pd.DataFrame,
    daily_df: pd.DataFrame,
) -> pd.DataFrame:
    daily = daily_df.copy()

    daily["daily_rsi_14"] = ta.rsi(daily["close"], length=14)
    daily["daily_atr_14"] = ta.atr(daily["high"], daily["low"], daily["close"], length=14)
    for period in [20, 50, 200]:
        sma = ta.sma(daily["close"], length=period)
        daily[f"daily_ma_bias_{period}"] = (daily["close"] - sma) / sma

    # Shift forward by 1 day to prevent look-ahead bias (same logic as Phase 1)
    daily["date_available"] = daily["timestamp"] + pd.Timedelta(days=1)

    feat_cols = [
        "date_available", "daily_rsi_14", "daily_atr_14",
        "daily_ma_bias_20", "daily_ma_bias_50", "daily_ma_bias_200",
    ]
    hourly_sorted = hourly_df.sort_values("timestamp").copy()
    daily_sorted = daily[feat_cols].sort_values("date_available").copy()
    # Normalize precision: Parquet reads as ms, in-memory ops may produce us
    hourly_sorted["timestamp"] = hourly_sorted["timestamp"].astype("datetime64[us, UTC]")
    daily_sorted["date_available"] = daily_sorted["date_available"].astype("datetime64[us, UTC]")

    merged = pd.merge_asof(
        hourly_sorted,
        daily_sorted,
        left_on="timestamp",
        right_on="date_available",
        direction="backward",
    )
    return merged.drop(columns=["date_available"], errors="ignore")
