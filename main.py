import os
import time
import re
import requests
from bs4 import BeautifulSoup

# GitHubの「Secrets」から安全に読み込みます
WEBHOOK_URL = os.getenv('WEBHOOK_URL')
AMAZON_URL = os.getenv('AMAZON_URL')
# 設定されていなかった場合のデフォルトは1600円にします
MAX_PRICE = int(os.getenv('MAX_PRICE', '1600')) 

INTERVAL_SECONDS = 30 
TOTAL_LOOP_TIME = 300 

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
}

def check_amazon_stock_and_price():
    try:
        response = requests.get(AMAZON_URL, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Amazonアクセス失敗 (Status: {response.status_code})")
            return False, 0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 在庫切れテキストのチェック
        availability_div = soup.find('div', {'id': 'availability'})
        if availability_div and "現在在庫切れ" in availability_div.text:
            print("ステータス: 現在在庫切れです。")
            return False, 0

        # 2. カートボタンのチェック
        add_to_cart_button = soup.find('input', {'id': 'add-to-cart-button'})
        if not add_to_cart_button:
            print("ステータス: カートに入れるボタンがありません。")
            return False, 0

        # 3. 価格の取得（複数のパターンに対応）
        price_text = None
        price_selectors = [
            ('span', {'class': 'a-price-whole'}),
            ('span', {'id': 'priceblock_ourprice'}),
            ('span', {'id': 'priceblock_dealprice'}),
            ('span', {'class': 'a-color-price'})
        ]
        
        for tag, attrs in price_selectors:
            price_element = soup.find(tag, attrs)
            if price_element:
                price_text = price_element.text
                break

        if not price_text:
            print("ステータs: カートはありますが、価格が読み取れませんでした。")
            return False, 0

        # 「￥1,600」などの文字から数字だけを抽出して整数(int)に変換
        price_number = int(re.sub(r'\D', '', price_text))
        print(f"現在の価格: {price_number}円 (目標: {MAX_PRICE}円以下)")

        # 4. 価格の判定
        if price_number <= MAX_PRICE:
            return True, price_number
        else:
            print(f"値下がり待ち: ボタンはありますが、設定金額を超えています。")
            return False, price_number

    except Exception as e:
        print(f"エラー発生: {e}")
        return False, 0

def send_discord_notification(current_price):
    data = {
        "content": f"**【Amazon値下げ・入荷情報】**\nお目当ての商品が **{current_price}円** で購入可能です！（目標: {MAX_PRICE}円以下）\nURL: {AMAZON_URL}"
    }
    requests.post(WEBHOOK_URL, json=data)

def main():
    print(f"Amazon価格監視スタート（間隔: {INTERVAL_SECONDS}秒 / 目標: {MAX_PRICE}円以下）")
    start_time = time.time()
    
    while (time.time() - start_time) < TOTAL_LOOP_TIME:
        print(f"[{time.strftime('%H:%M:%S')}] 在庫と価格をチェック中...")
        
        is_ok, current_price = check_amazon_stock_and_price()
        
        if is_ok:
            send_discord_notification(current_price)
            print("🎉 条件クリア！Discordに通知しました。")
            break
            
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()