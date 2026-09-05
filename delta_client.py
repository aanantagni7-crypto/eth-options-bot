# delta_client.py
import requests
import time
import json
import hashlib
import hmac
from config import DELTA_BASE_URL, DELTA_API_KEY, DELTA_API_SECRET

class DeltaClient:
    def __init__(self):
        self.base_url = DELTA_BASE_URL
        self.api_key = DELTA_API_KEY
        self.api_secret = DELTA_API_SECRET
        self.session = requests.Session()

    def _generate_signature(self, timestamp, method, path, body=""):
        """Generate HMAC-SHA256 signature for Delta API."""
        if body is None:
            body = ""
        message = timestamp + method + path + body
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            message.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature

    def _request(self, method, path, params=None, body=None):
        """Make an authenticated request to Delta."""
        timestamp = str(int(time.time() * 1000))
        signature = self._generate_signature(timestamp, method, path, json.dumps(body) if body else "")
        
        headers = {
            "api-key": self.api_key,
            "api-timestamp": timestamp,
            "api-signature": signature,
            "Content-Type": "application/json"
        }
        
        url = self.base_url + path
        response = self.session.request(method, url, headers=headers, params=params, json=body)
        if response.status_code != 200:
            print(f"API Error {response.status_code}: {response.text}")
            return None
        return response.json().get('result', {})

    # --- PUBLIC/PRIVATE METHODS ---
    def get_products(self):
        return self._request("GET", "/v2/products")

    def get_ticker(self, symbol):
        return self._request("GET", f"/v2/tickers/{symbol}")

    def get_ticker_by_product_id(self, product_id):
        # Delta doesn't have a direct product_id ticker, so we fetch all tickers and filter
        tickers = self._request("GET", "/v2/tickers")
        if tickers and isinstance(tickers, list):
            for t in tickers:
                if t.get('product_id') == product_id:
                    return t
        return None


    def get_candles(self, symbol, resolution="5m", limit=200):
        import time
        end = int(time.time())
        # Convert resolution to seconds
        if resolution.endswith("m"):
            seconds = int(resolution[:-1]) * 60
        elif resolution.endswith("h"):
            seconds = int(resolution[:-1]) * 3600
        elif resolution.endswith("d"):
            seconds = int(resolution[:-1]) * 86400
        else:
            seconds = 300
        start = end - (limit * seconds)
        params = {"symbol": symbol, "resolution": resolution, "start": start, "end": end}
        
        print(f"   📡 Requesting candles for: {symbol}")
        result = self._request("GET", "/v2/history/candles", params=params)
        
        # --- DEBUG: print type and first few items ---
        if result is None:
            print("   ❌ Delta returned None")
        else:
            print(f"   ✅ Delta returned {len(result)} items")
            if len(result) > 0:
                print(f"   🔍 Type of first element: {type(result[0])}")
                print(f"   🔍 First element: {result[0]}")
                if len(result) > 1:
                    print(f"   🔍 Second element: {result[1]}")
        return result

    def place_order(self, product_id, side, size, price=None, order_type="limit"):
        body = {
            "product_id": product_id,
            "size": size,
            "side": side,
            "order_type": "limit_order" if order_type == "limit" else "market_order"
        }
        if price and order_type == "limit":
            body["limit_price"] = str(price)
        return self._request("POST", "/v2/orders", body=body)

    def get_live_orders(self):
        return self._request("GET", "/v2/orders/live")