# find_symbol.py
from delta_client import DeltaClient

dc = DeltaClient()
print("🔍 Fetching all products from Delta Testnet...\n")

products = dc.get_products()

if not products:
    print("❌ Could not fetch products. Check your API keys and internet.")
else:
    print("📋 ETH-related products found:\n")
    for p in products:
        symbol = p.get('symbol', '')
        product_id = p.get('id', '')
        contract_type = p.get('contract_type', '')
        
        # Filter only ETH products
        if 'ETH' in symbol.upper():
            print(f"   Symbol: {symbol} | ID: {product_id} | Type: {contract_type}")
    
    print("\n💡 Look for the PERPETUAL or FUTURES contract (not the options).")
    print("   Copy the EXACT symbol (e.g., 'ETHUSD' or 'ETH-PERP') and paste it into config.py")