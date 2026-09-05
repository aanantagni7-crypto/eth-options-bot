# order_manager.py
import config
from datetime import datetime, timedelta

class OrderManager:
    def __init__(self, delta_client):
        self.delta = delta_client
        self.active_positions = {}  # product_id -> {entry_price, stop_loss, take_profit, signal_type, expiry_time}

    def execute_signal(self, signal_action, product_id, expiry_hours):
        if not product_id:
            return None
            
        # --- FLIP LOGIC ---
        if config.FLIP_ON_REVERSAL and len(self.active_positions) > 0:
            print(f"🔄 Reversal detected! Closing {len(self.active_positions)} old position(s)...")
            for old_id in list(self.active_positions.keys()):
                self.close_position(old_id)
        
        # Check max position size
        if len(self.active_positions) >= config.MAX_POSITION_SIZE:
            print("⚠️ Max positions reached.")
            return None

        # Get price for limit order
        ticker = self.delta.get_ticker_by_product_id(product_id)
        if not ticker:
            print("❌ Could not fetch option price")
            return None
        price = float(ticker.get('mark_price', 0))
        
        if price == 0:
            print("❌ Invalid price (0)")
            return None

        # Place order
        order = self.delta.place_order(
            product_id=product_id,
            side='buy',
            size=config.OPTIONS_TRADE_SIZE,
            price=price * 0.99 if config.OPTIONS_ORDER_TYPE == "limit" else None,
            order_type=config.OPTIONS_ORDER_TYPE
        )
        
        if order:
            entry_time = datetime.now()
            expiry_time = entry_time + timedelta(hours=expiry_hours)
            
            print(f"✅ ORDER PLACED: {signal_action} at ~${price:.2f} (Expires: {expiry_time.strftime('%Y-%m-%d %H:%M')})")
            
            self.active_positions[product_id] = {
                'entry_price': price,
                'entry_time': entry_time,
                'expiry_time': expiry_time,
                'signal_type': signal_action,
                'stop_loss': price * (1 - config.STOP_LOSS_PCT),
                'take_profit': price * (1 + config.TAKE_PROFIT_PCT)
            }
        return order

    def close_position(self, product_id, reason="Manual"):
        """Sell to close a position"""
        if product_id not in self.active_positions:
            return None
        
        pos = self.active_positions[product_id]
        print(f"🔒 Closing {pos['signal_type']} (Reason: {reason})")
        
        try:
            order = self.delta.place_order(
                product_id=product_id,
                side='sell',
                size=config.OPTIONS_TRADE_SIZE,
                order_type='market'
            )
            del self.active_positions[product_id]
            print(f"✅ Position closed successfully!")
            return order
        except Exception as e:
            print(f"❌ Failed to close position: {e}")
            return None

    def check_stop_loss_and_take_profit(self):
        """Check SL/TP AND close options with less than 36 hours to expiry (Theta Decay protection)"""
        to_close = []
        
        for product_id, pos in self.active_positions.items():
            ticker = self.delta.get_ticker_by_product_id(product_id)
            if not ticker:
                continue
                
            current_price = float(ticker.get('mark_price', 0))
            if current_price == 0:
                continue
            
            # 1. Check Stop Loss
            if current_price <= pos['stop_loss']:
                print(f"🛑 STOP LOSS triggered for {pos['signal_type']} (Price: ${current_price:.2f})")
                to_close.append((product_id, "Stop Loss"))
                continue
            
            # 2. Check Take Profit
            if current_price >= pos['take_profit']:
                print(f"🎯 TAKE PROFIT triggered for {pos['signal_type']} at ${current_price:.2f}")
                to_close.append((product_id, "Take Profit"))
                continue
            
            # 3. NEW: Check Theta Decay (less than 36 hours to expiry)
            now = datetime.now()
            hours_left = (pos['expiry_time'] - now).total_seconds() / 3600
            
            if hours_left < 36:
                print(f"⏰ THETA DECAY EXIT: {pos['signal_type']} has only {hours_left:.1f}h left. Closing to protect value.")
                to_close.append((product_id, "Theta Decay (<36h)"))
        
        # Execute all exits
        for product_id, reason in to_close:
            self.close_position(product_id, reason)

    def get_active_positions(self):
        return self.active_positions

    def get_pnl(self):
        total_pnl = 0
        for product_id, pos in self.active_positions.items():
            ticker = self.delta.get_ticker_by_product_id(product_id)
            if ticker:
                current_price = float(ticker.get('mark_price', 0))
                pnl = (current_price - pos['entry_price']) * config.OPTIONS_TRADE_SIZE
                total_pnl += pnl
        return total_pnl