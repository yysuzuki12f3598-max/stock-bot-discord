import sys
import os
import time
import requests

# 1. 引数の受け取り
if len(sys.argv) < 4:
    print("エラー: 引数が足りません。[URL] [目標価格] [商品名] の順で指定してください。")
    sys.exit(1)

AMAZON_URL = sys.argv[1].strip('"\'')
MAX_PRICE = int(str(sys.argv[2]).strip('"\''))
name = sys.argv[3].strip('"\'')

WEBHOOK_URL = os.getenv('WEBHOOK_URL')
SCRAPER_API_KEY = os.getenv('SCRAPER_API_KEY')

INTERVAL_SECONDS = 15
TOTAL_LOOP_TIME = 60

def extract_asin(url):
    """URLからAmazonのASIN（商品コード）を抽出する"""
    import re
    match = re.search(r'/([A-Z0-9]{10})(?:[/?]|$)', url)
    if match:
        return match.group(1)
    return None

def check_amazon_stock_and_price():
    try:
        asin = extract_asin(AMAZON_URL)
        if not asin:
            print("エラー: URLからASIN(商品コード)が抽出できませんでした。")
            return False, 0
            
        # 💡 Amazon専用エンドポイントを叩く
        proxy_url = f"https://proxy.scrapeops.io/v1/amazon/?api_key={SCRAPER_API_KEY}&asin={asin}&country=jp"
        
        response = requests.get(proxy_url, timeout=30)
        
        if response.status_code != 200:
            print(f"身代わりプロキシ経由のアクセス失敗 (Status: {response.status_code})")
            return False, 0

        # 💡 ScrapeOpsのAmazonエンドポイントはJSONを返すため、そのまま辞書型にデコード
        data = response.json()
        
        # デバッグ用：念のため返ってきたデータ構造をログに出す
        # print(f"DEBUG: {data}")

        # 1. 在庫・カートボタン相当のステータスチェック
        # ScrapeOpsの仕様により、out_of_stock などのフラグが取れます
        if data.get('out_of_stock') or not data.get('is_buybox_winner', True):
            # もし明示的に在庫切れ、またはカートが取得できていない場合
            if data.get('out_of_stock'):
                print("ステータス: 現在在庫切れです。")
                return False, 0

        # 2. 価格の取得（ScrapeOpsが自動パースした価格フィールドを参照）
        # 通常、'price' や 'price_num' などのキーで数値が入ってきます
        price_number = data.get('price_num') or data.get('price')
        
        # 文字列で入ってきた場合の安全な数値化
        if isinstance(price_number, str):
            import re
            price_number = int(re.sub(r'\D', '', price_number))

        if not price_number:
            print("ステータス: 商品情報は取れましたが、価格が読み取れませんでした。")
            return False, 0

        print(f"現在の価格: {price_number}円 (目標: {MAX_PRICE}円以下)")

        # 3. 価格の判定
        if price_number <= MAX_PRICE:
            return True, price_number
        else:
            print(f"値下がり待ち: 設定金額を超えています。")
            return False, price_number

    except Exception as e:
        print(f"エラー発生: {e}")
        return False, 0

def send_discord_notification(current_price):
    data = {
        "content": f"**【Amazon値下げ・入荷情報】**\n"
                   f"お目当ての **{name}** が **{current_price}円** で購入可能です！（目標: {MAX_PRICE}円以下）\n"
                   f"URL: {AMAZON_URL}"
    }
    requests.post(WEBHOOK_URL, json=data)

def main():
    if not WEBHOOK_URL:
        print("エラー: WEBHOOK_URL が設定されていません。")
        sys.exit(1)
    if not SCRAPER_API_KEY:
        print("エラー: SCRAPER_API_KEY (ScrapeOps Key) が設定されていません。")
        sys.exit(1)

    print(f"Amazon価格監視スタート（ScrapeOps JSONバイパスモード） ➔ 【{name}】")
    start_time = time.time()
    
    while (time.time() - start_time) < TOTAL_LOOP_TIME:
        is_ok, current_price = check_amazon_stock_and_price()
        
        if is_ok:
            send_discord_notification(current_price)
            print("🎉 条件クリア！Discordに通知しました。")
            break
            
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()