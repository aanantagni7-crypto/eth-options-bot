# main.py
import sys
import time
import logging
from datetime import datetime

# Force Windows CMD to handle UTF-8 (emojis)
sys.stdout.reconfigure(encoding='utf-8')

# Import our modules
from config import *
from delta_client import DeltaClient
from signal_generator import SignalGenerator
from order_manager import OrderManager
from options_pricing import get_options_product_id, display_near_term_options

# Setup logging (no emojis in logs to avoid encoding errors)
log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logger = logging.getLogger(__name__)
logger.setLevel(getattr(logging, LOG_LEVEL) if 'LOG_LEVEL' in dir() else logging.INFO)

# Console handler (prints to CMD)
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter(log_format))
logger.addHandler(console)

# File handler (saves to file)
file_handler = logging.FileHandler('eth_options_bot.log', encoding='utf-8')
file_handler.setLevel(logging.INFO)
file_handler.setFormatter(logging.Formatter(log_format))
logger.addHandler(file_handler)

# --- Print startup banner ---
print("="*60)
print("🚀 ETH OPTIONS BOT STARTING (TESTNET)")
print(f"📅 Expiry Target: {OPTION_TARGET_DAYS} days")
print(f"📊 Trade Size: {OPTIONS_TRADE_SIZE} contracts")
print(f"🎯 Take Profit: {TAKE_PROFIT_PCT*100:.0f}%")
print(f"🛑 Stop Loss: {STOP_LOSS_PCT*100:.0f}%")
print(f"🔄 Flip on Reversal: {FLIP_ON_REVERSAL}")
print("="*60)


class ETHOptionsBot:
    def __init__(self):
        self.delta = DeltaClient()
        self.signal_gen = SignalGenerator(self.delta)
        self.order_mgr = OrderManager(self.delta)
        
        self.last_signal_time = None
        self.signal_cooldown_minutes = 15
        self.running = True
        self.iteration = 0
        
        logger.info("Bot initialized successfully")

    def get_adaptive_expiry(self):
        try:
            ticker = self.delta.get_ticker(ETH_FUTURES_SYMBOL)
            if ticker:
                high = float(ticker.get('high_24h', 0))
                low = float(ticker.get('low_24h', 0))
                current = float(ticker.get('mark_price', 0))
                
                if current > 0:
                    volatility_pct = (high - low) / current
                    
                    if volatility_pct > 0.08:
                        return min(OPTIONS_EXPIRY_HOURS, 60)
                    elif volatility_pct < 0.03:
                        return max(OPTIONS_EXPIRY_HOURS, 96)
        except Exception as e:
            logger.warning(f"Could not calculate adaptive expiry: {e}")
        
        return OPTIONS_EXPIRY_HOURS

    def run_iteration(self):
        self.iteration += 1
        print(f"\n" + "="*50)
        print(f"📊 Loop #{self.iteration} @ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*50)
        
        # --- NEW: Display Options Dashboard every loop ---
        display_near_term_options(self.delta, target_days=OPTION_TARGET_DAYS)
        
        # --- Get signal from signal generator ---
        signal = self.signal_gen.get_signal()
        action = signal.get('action')
        confidence = signal.get('confidence', 'low')
        reason = signal.get('reason', '')
        
        print(f"📡 Signal: {action or 'NONE'} | Confidence: {confidence}")
        print(f"📝 Reason: {reason}")
        
        # --- Cooldown check ---
        if self.last_signal_time:
            elapsed = (datetime.now() - self.last_signal_time).total_seconds() / 60
            if elapsed < self.signal_cooldown_minutes:
                print(f"⏳ Cooldown: {elapsed:.1f}/{self.signal_cooldown_minutes} min - Skipping")
                self.order_mgr.check_stop_loss_and_take_profit()
                return
        
        # --- Execute signal ---
        if action == 'EXIT_ALL':
            print("🚨 EXIT ALL triggered! Closing positions...")
            self.order_mgr.close_all_positions(reason="3m SAR Bearish")
            return
        
        if action in ['BUY_CALL', 'BUY_PUT']:
            expiry = self.get_adaptive_expiry()
            print(f"📅 Using expiry: {expiry} hours (adaptive)")
            
            option_type = 'call' if action == 'BUY_CALL' else 'put'
            product_id = get_options_product_id(self.delta, expiry, option_type)
            
            if product_id:
                # product_id is a tuple (product_id, expiry_hours)
                if isinstance(product_id, tuple):
                    prod_id, exp_hours = product_id
                else:
                    prod_id, exp_hours = product_id, expiry
                
                order = self.order_mgr.execute_signal(action, prod_id, exp_hours)
                if order:
                    self.last_signal_time = datetime.now()
                    print(f"🎯 ✅ TRADE EXECUTED: {action}")
                    logger.info(f"Trade executed: {action}")
                else:
                    print(f"❌ Order failed for {action}")
                    logger.error(f"Order failed for {action}")
            else:
                print(f"⚠️ No option found for {action} with expiry {expiry}h")
                logger.warning(f"No option found for {action}")
        
        # --- Check stop-loss and take-profit ---
        print(f"\n📊 Checking existing positions...")
        self.order_mgr.check_stop_loss_and_take_profit()
        
        # --- Display positions ---
        positions = self.order_mgr.get_active_positions()
        if positions:
            pnl = self.order_mgr.get_pnl()
            print(f"📈 Active positions: {len(positions)} | Total P&L: ${pnl:.2f}")
            for pid, pos in positions.items():
                print(f"   - Product {pid}: {pos['signal_type']} | Entry: ${pos['entry_price']:.2f} | TP: ${pos['take_profit']:.2f} | SL: ${pos['stop_loss']:.2f}")
        else:
            print(f"📭 No active positions")

    def run(self):
        logger.info("Starting main trading loop...")
        print("\n🔄 Bot is now running. Press Ctrl+C to stop.\n")
        
        while self.running:
            try:
                self.run_iteration()
                print(f"\n⏳ Waiting 1 minute until next check...")
                time.sleep(60)   # 1 minute (since we use 1m candles)
            except KeyboardInterrupt:
                print("\n🛑 Received shutdown signal (Ctrl+C)")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                print(f"❌ ERROR: {e}")
                print("⏳ Waiting 60 seconds before retrying...")
                time.sleep(60)
    
    def shutdown(self):
        print("\n🛑 Shutting down bot gracefully...")
        positions = self.order_mgr.get_active_positions()
        if positions:
            print(f"Closing {len(positions)} open positions...")
            for product_id in list(positions.keys()):
                self.order_mgr.close_position(product_id)
        print("✅ Shutdown complete. Goodbye!")
        logger.info("Bot shutdown complete")


if __name__ == "__main__":
    bot = ETHOptionsBot()
    try:
        bot.run()
    except KeyboardInterrupt:
        bot.shutdown()
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        print(f"❌ FATAL ERROR: {e}")
        bot.shutdown()