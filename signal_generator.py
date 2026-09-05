# signal_generator.py (FIXED - Handles Delta's list-of-lists format)
import pandas as pd
from indicators import generate_signal
from options_pricing import get_options_product_id
import config

class SignalGenerator:
    def __init__(self, delta_client):
        self.delta = delta_client
        self.counter = 0

    def fetch_futures_data(self):
        candles = self.delta.get_candles(config.ETH_FUTURES_SYMBOL, resolution="1m", limit=200)
        
        if not candles:
            print("⚠️ WARNING: No candles returned from API!")
            return None
        
        # --- Try to convert to DataFrame intelligently ---
        try:
            # If it's a list of lists, assume order: [timestamp, open, high, low, close, volume]
            if isinstance(candles, list) and len(candles) > 0 and isinstance(candles[0], list):
                df = pd.DataFrame(candles, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            # If it's a list of dicts, use as-is
            elif isinstance(candles, list) and len(candles) > 0 and isinstance(candles[0], dict):
                df = pd.DataFrame(candles)
            # If it's a dict with a 'data' field (common in some APIs)
            elif isinstance(candles, dict) and 'data' in candles:
                df = pd.DataFrame(candles['data'])
            else:
                # Fallback: try to convert directly
                df = pd.DataFrame(candles)
            
            if df.empty:
                print("⚠️ WARNING: Empty DataFrame!")
                return None
            
            # Identify the timestamp column: look for 'timestamp', 'time', 't', 'dt', etc.
            timestamp_col = None
            for col in df.columns:
                if col.lower() in ['timestamp', 'time', 't', 'dt', 'datetime']:
                    timestamp_col = col
                    break
            if timestamp_col is None:
                # If no obvious timestamp, assume the first column is timestamp
                timestamp_col = df.columns[0]
                print(f"   ℹ️ Using '{timestamp_col}' as timestamp column")
            
            # Convert timestamp to datetime
            df[timestamp_col] = pd.to_datetime(df[timestamp_col], unit='s') if df[timestamp_col].dtype.kind in 'iuf' else pd.to_datetime(df[timestamp_col])
            df.set_index(timestamp_col, inplace=True)
            
            # Ensure numeric columns
            for col in ['open', 'high', 'low', 'close']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col])
            df = df.iloc[::-1]
            return df
            
        except Exception as e:
            print(f"❌ Error parsing candle data: {e}")
            print(f"   🔍 Raw first 2 items: {candles[:2] if isinstance(candles, list) else candles}")
            return None
    def get_signal(self):
        data = self.fetch_futures_data()
        if data is None:
            return {'action': None, 'reason': 'No data from API'}
        
        # --- DEBUG: Show the numbers ---
        from indicators import calculate_parabolic_sar, calculate_adx
        high = data['high']
        low = data['low']
        close = data['close']
        
        sar_result = calculate_parabolic_sar(high, low, close)
        adx = calculate_adx(high, low, close)
        
        latest_sar = sar_result['sar'].iloc[-1]
        latest_signal = sar_result['signal'].iloc[-1]  # 1 = Bullish, -1 = Bearish
        latest_adx = adx.iloc[-1]
        latest_close = close.iloc[-1]
        
        # Print diagnostic info every loop
        print(f"   🔍 DEBUG: ADX = {latest_adx:.2f} (Threshold: {config.ADX_THRESHOLD})")
        print(f"   🔍 DEBUG: SAR Signal = {latest_signal} (1=Bullish, -1=Bearish)")
        print(f"   🔍 DEBUG: Price = {latest_close:.2f}, SAR = {latest_sar:.2f}")
        
        flip_bullish = sar_result['flip_bullish'].iloc[-1]
        flip_bearish = sar_result['flip_bearish'].iloc[-1]
        print(f"   🔍 DEBUG: Flip Bullish? {flip_bullish} | Flip Bearish? {flip_bearish}")
        
        # --- Run the actual signal logic ---
        raw = generate_signal(data)
        
        if raw in ['BUY', 'SELL']:
            self.counter += 1
            print(f"   ⏳ Confirmation counter: {self.counter}/{config.CONFIRMATION_BARS}")
            if self.counter >= config.CONFIRMATION_BARS:
                self.counter = 0
                if raw == 'BUY':
                    return {'action': 'BUY_CALL', 'confidence': 'High', 'reason': 'Confirmed Bullish Flip'}
                else:
                    return {'action': 'BUY_PUT', 'confidence': 'High', 'reason': 'Confirmed Bearish Flip'}
            else:
                return {'action': None, 'reason': f'Waiting for bar {self.counter}/{config.CONFIRMATION_BARS}'}
        else:
            self.counter = 0
        
        if raw == 'BUY_WARNING':
            return {'action': None, 'reason': '⚠️ Early Warning: Prepare for BUY (price near SAR)'}
        if raw == 'SELL_WARNING':
            return {'action': None, 'reason': '⚠️ Early Warning: Prepare for SELL (price near SAR)'}
        
        if latest_adx < config.ADX_THRESHOLD:
            return {'action': None, 'reason': f'No signal (ADX {latest_adx:.2f} < {config.ADX_THRESHOLD})'}
        
        return {'action': None, 'reason': 'No signal (SAR not flipped)'}