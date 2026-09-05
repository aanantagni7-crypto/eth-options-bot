# options_pricing.py (FINAL VERSION - Parses expiry from symbol)
import pandas as pd
from datetime import datetime, timedelta
import config

def parse_expiry_from_symbol(symbol):
    """
    Parse expiry date from symbol like: C-ETH-2470-040926
    Returns: datetime object, or None if parsing fails.
    """
    parts = symbol.split('-')
    if len(parts) < 4:
        return None
    
    # Last part is the date: DDMMYY (e.g., 040926 -> 04-09-2026)
    date_str = parts[-1]
    if len(date_str) != 6:
        return None
    
    try:
        day = int(date_str[0:2])
        month = int(date_str[2:4])
        year = 2000 + int(date_str[4:6])  # 26 -> 2026
        return datetime(year, month, day, 23, 59, 59)
    except:
        return None

def get_options_product_id(delta_client, target_expiry_hours=72, option_type="call"):
    """
    Find the best ATM option by parsing expiry from symbol.
    """
    print(f"\n   🔍 Searching for {option_type.upper()} options...")
    
    products = delta_client.get_products()
    if not products:
        print("❌ Could not fetch products")
        return None
    
    # Get current ETH price
    ticker = delta_client.get_ticker(config.ETH_FUTURES_SYMBOL)
    if not ticker:
        print("❌ Could not fetch ETH price")
        return None
    eth_price = float(ticker.get('mark_price', ticker.get('last_price', 0)))
    print(f"   ℹ️ Current ETH Price: ${eth_price:.2f}")
    
    # Target date = today + config.OPTION_TARGET_DAYS
    target_date = datetime.now() + timedelta(days=config.OPTION_TARGET_DAYS)
    print(f"   🎯 Target Expiry: {target_date.strftime('%Y-%m-%d')} (+{config.OPTION_TARGET_DAYS} days)")
    
    # Filter for ETH options
    target_type = 'call' if option_type == 'call' else 'put'
    candidates = []
    
    for p in products:
        symbol = p.get('symbol', '')
        if not symbol.startswith('C-ETH-') and not symbol.startswith('P-ETH-'):
            continue
        
        # Determine if it's a Call or Put
        if symbol.startswith('C-ETH-') and target_type != 'call':
            continue
        if symbol.startswith('P-ETH-') and target_type != 'put':
            continue
        
        # Parse strike from symbol (e.g., C-ETH-2470-040926 -> 2470)
        parts = symbol.split('-')
        if len(parts) < 4:
            continue
        try:
            strike = float(parts[2])
        except:
            continue
        
        # Parse expiry date from symbol
        expiry_dt = parse_expiry_from_symbol(symbol)
        if expiry_dt is None:
            continue
        
        # Must be in the future
        now = datetime.now()
        if expiry_dt <= now:
            continue
        
        hours_left = (expiry_dt - now).total_seconds() / 3600
        product_id = p.get('id', 0)
        
        # We want options expiring within a reasonable window (1 to 14 days)
        if hours_left < 24 or hours_left > 336:
            continue
        
        candidates.append({
            'symbol': symbol,
            'product_id': product_id,
            'strike': strike,
            'expiry_dt': expiry_dt,
            'hours_left': hours_left,
            'strike_diff': abs(strike - eth_price)
        })
    
    if not candidates:
        print(f"❌ No {target_type.upper()} options found. Try adjusting OPTION_TARGET_DAYS.")
        return None
    
    # Sort: closest to target date, then closest strike to ATM
    for c in candidates:
        c['date_diff'] = abs((c['expiry_dt'] - target_date).total_seconds() / 86400)
    
    candidates.sort(key=lambda x: (x['date_diff'], x['strike_diff']))
    
    best = candidates[0]
    
    print(f"\n   ✅ SELECTED BEST MATCH:")
    print(f"      Symbol:      {best['symbol']}")
    print(f"      Strike:      ${best['strike']:.2f} (diff from ATM: ${best['strike_diff']:.2f})")
    print(f"      Expires:     {best['expiry_dt'].strftime('%Y-%m-%d %H:%M')} (in {best['hours_left']:.1f}h)")
    print(f"      Date Diff:   {best['date_diff']:.2f} days from target")
    print(f"      Product ID:  {best['product_id']}\n")
    
    return best['product_id'], best['hours_left']


def display_near_term_options(delta_client, target_days=3):
    """
    DISPLAY DASHBOARD: Shows available Call/Put options near ATM.
    Parses expiry directly from symbol.
    """
    products = delta_client.get_products()
    if not products:
        print("   ⚠️ Could not fetch products.")
        return
    
    # Get current ETH price
    ticker = delta_client.get_ticker(config.ETH_FUTURES_SYMBOL)
    eth_price = 0
    if ticker:
        eth_price = float(ticker.get('mark_price', ticker.get('last_price', 0)))
    
    target_date = datetime.now() + timedelta(days=target_days)
    options_dict = {}
    
    for p in products:
        symbol = p.get('symbol', '')
        if not symbol.startswith('C-ETH-') and not symbol.startswith('P-ETH-'):
            continue
        
        # Parse strike and expiry
        parts = symbol.split('-')
        if len(parts) < 4:
            continue
        try:
            strike = float(parts[2])
        except:
            continue
        
        expiry_dt = parse_expiry_from_symbol(symbol)
        if expiry_dt is None:
            continue
        
        now = datetime.now()
        if expiry_dt <= now:
            continue
        
        hours_left = (expiry_dt - now).total_seconds() / 3600
        
        # We want options expiring between 24h and 168h (1 to 7 days)
        if hours_left < 24 or hours_left > 168:
            continue
        
        product_id = p.get('id', 0)
        is_call = symbol.startswith('C-ETH-')
        is_put = symbol.startswith('P-ETH-')
        
        # Fetch current price of this option
        opt_price = 0
        opt_ticker = delta_client.get_ticker_by_product_id(product_id)
        if opt_ticker:
            opt_price = float(opt_ticker.get('mark_price', opt_ticker.get('last_price', 0)))
        
        # Initialize for this strike
        if strike not in options_dict:
            options_dict[strike] = {
                'expiry': expiry_dt,
                'hours': hours_left,
                'call': 0,
                'put': 0
            }
        
        if is_call:
            options_dict[strike]['call'] = opt_price
        elif is_put:
            options_dict[strike]['put'] = opt_price
    
    if not options_dict:
        print("   ℹ️ No ETH options found in the 24h-168h window.")
        return
    
    # Print the Dashboard
    print(f"\n   📊 OPTIONS DASHBOARD (Target Expiry: ~{target_days} days):")
    print(f"   Current ETH Spot: ~${eth_price:.2f}")
    print("   " + "-" * 65)
    print(f"   {'Strike':>8} | {'Expiry (Hrs)':>12} | {'Call Price':>10} | {'Put Price':>10} | {'Sentiment'}")
    print("   " + "-" * 65)
    
    for strike in sorted(options_dict.keys()):
        data = options_dict[strike]
        call_p = data['call']
        put_p = data['put']
        
        # Only show strikes within $150 of spot
        if abs(strike - eth_price) > 150:
            continue
        
        # Sentiment: Put > Call = Bearish, Call > Put = Bullish
        sentiment = "⚖️ Neutral"
        if call_p > 0 and put_p > 0:
            ratio = put_p / call_p
            if ratio > 1.2:
                sentiment = "🐻 Bearish"
            elif ratio < 0.8:
                sentiment = "🐂 Bullish"
        
        marker = " <-- ATM" if abs(strike - eth_price) < 15 else ""
        print(f"   {strike:>8.0f} | {data['hours']:>11.1f}h | {call_p:>10.2f} | {put_p:>10.2f} | {sentiment}{marker}")
    
    print("   " + "-" * 65)
    print(f"   💡 Sentiment Guide: Put > Call = Bearish | Call > Put = Bullish\n")