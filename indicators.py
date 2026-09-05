# indicators.py
# This version uses ONLY pure pandas/numpy - NO pandas_ta required!
import pandas as pd
import numpy as np

def calculate_parabolic_sar(high, low, close, acceleration=0.02, maximum=0.20):
    """
    Custom Parabolic SAR calculation without external TA libraries.
    This uses a simple loop (perfect for our 5-minute data).
    """
    h = high.values
    l = low.values
    c = close.values
    n = len(c)
    
    # Initialize arrays
    sar = np.zeros(n)
    signal = np.zeros(n)
    
    if n < 2:
        return {
            'sar': pd.Series(sar, index=high.index),
            'signal': pd.Series(signal, index=high.index),
            'flip_bullish': pd.Series([False]*n, index=high.index),
            'flip_bearish': pd.Series([False]*n, index=high.index),
            'proximity_alert': pd.Series([False]*n, index=high.index)
        }
    
    # Determine initial trend (1 = Bullish, -1 = Bearish)
    trend = 1
    if c[1] < c[0]:  # If price dropped from bar 0 to bar 1, start bearish
        trend = -1
    
    # Set initial Extreme Point (EP) and Acceleration Factor (AF)
    ep = h[0] if trend == 1 else l[0]
    af = acceleration
    sar[0] = l[0] if trend == 1 else h[0]  # Initial SAR placed at low or high
    signal[0] = trend

    # Loop through the bars (this is the classic PSAR math)
    for i in range(1, n):
        prev_sar = sar[i-1]
        
        if trend == 1:  # We are in an Uptrend
            sar[i] = prev_sar + af * (ep - prev_sar)
            
            # Check if SAR crosses above the low (Reversal to Bearish)
            if sar[i] > l[i]:
                trend = -1
                sar[i] = ep  # SAR jumps to the previous Extreme Point
                af = acceleration
                ep = l[i]
            else:
                # Check for new high to increase AF
                if h[i] > ep:
                    ep = h[i]
                    af = min(af + acceleration, maximum)
        
        else:  # We are in a Downtrend
            sar[i] = prev_sar + af * (ep - prev_sar)
            
            # Check if SAR crosses below the high (Reversal to Bullish)
            if sar[i] < h[i]:
                trend = 1
                sar[i] = ep  # SAR jumps to the previous Extreme Point
                af = acceleration
                ep = h[i]
            else:
                # Check for new low to increase AF
                if l[i] < ep:
                    ep = l[i]
                    af = min(af + acceleration, maximum)
        
        signal[i] = trend

    # Convert to Pandas Series
    signal_series = pd.Series(signal, index=close.index)
    sar_series = pd.Series(sar, index=close.index)
    
    # Find exactly when the signal flips (-1 to 1, or 1 to -1)
    flip_bullish = (signal_series.diff() == 2)   # Went from -1 to 1
    flip_bearish = (signal_series.diff() == -2)  # Went from 1 to -1

    # PROXIMITY ALERT (Method 2 from our strategy)
    sar_distance = abs(close - sar_series)
    avg_distance = sar_distance.rolling(50).mean()
    proximity_alert = (sar_distance / avg_distance) < 0.10

    return {
        'sar': sar_series,
        'signal': signal_series,
        'flip_bullish': flip_bullish,
        'flip_bearish': flip_bearish,
        'proximity_alert': proximity_alert
    }


def calculate_adx(high, low, close, period=14):
    """
    Calculate ADX (Average Directional Index) using pure pandas/numpy.
    ADX > 25 means a strong trend is present.
    """
    h = high.values
    l = low.values
    c = close.values
    n = len(c)
    
    tr = np.zeros(n)
    plus_dm = np.zeros(n)
    minus_dm = np.zeros(n)
    
    # Calculate True Range (TR) and Directional Movements (DM)
    tr[0] = h[0] - l[0]  # First bar TR
    for i in range(1, n):
        # True Range
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i-1]), abs(l[i] - c[i-1]))
        
        # Plus DM & Minus DM
        up = h[i] - h[i-1]
        down = l[i-1] - l[i]
        
        if up > down and up > 0:
            plus_dm[i] = up
        else:
            plus_dm[i] = 0
            
        if down > up and down > 0:
            minus_dm[i] = down
        else:
            minus_dm[i] = 0
    
    # Convert to Pandas Series for easy smoothing
    tr_series = pd.Series(tr, index=high.index)
    plus_dm_series = pd.Series(plus_dm, index=high.index)
    minus_dm_series = pd.Series(minus_dm, index=high.index)
    
    # Wilder's Smoothing (EMA with alpha = 1/period)
    atr = tr_series.ewm(alpha=1/period, adjust=False).mean()
    smoothed_plus = plus_dm_series.ewm(alpha=1/period, adjust=False).mean()
    smoothed_minus = minus_dm_series.ewm(alpha=1/period, adjust=False).mean()
    
    # Calculate DI and DX
    plus_di = 100 * (smoothed_plus / atr)
    minus_di = 100 * (smoothed_minus / atr)
    
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di)
    adx = dx.ewm(alpha=1/period, adjust=False).mean()
    
    return adx


def generate_signal(data):
    """
    Generate raw SAR flip signals (no ADX filter here).
    ADX filtering is handled in signal_generator.py using config.ADX_THRESHOLD.
    """
    high = data['high']
    low = data['low']
    close = data['close']
    
    sar_result = calculate_parabolic_sar(high, low, close)
    
    # Get latest values
    latest_signal = sar_result['signal'].iloc[-1]   # 1 = Bullish, -1 = Bearish
    
    # Check for flips
    if sar_result['flip_bullish'].iloc[-1] and latest_signal == 1:
        return 'BUY'
    elif sar_result['flip_bearish'].iloc[-1] and latest_signal == -1:
        return 'SELL'
    
    # Proximity warnings (optional)
    if sar_result['proximity_alert'].iloc[-1]:
        if latest_signal == 1:
            return 'BUY_WARNING'
        elif latest_signal == -1:
            return 'SELL_WARNING'
    
    return None