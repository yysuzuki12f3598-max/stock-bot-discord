import os
import time
import re
import json
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# JSON文字列をPythonの配列/辞書型に変換
WATCH_LIST_JSON = os.getenv('WATCH_LIST', '[]')
try:
    WATCH_LIST = json.loads(WATCH_LIST_JSON)
except Exception as e:
    print(f"JSONのパースに失敗しました。設定を確認してください: {e}")
    WATCH_LIST = []

INTERVAL_SECONDS = 30 
TOTAL_LOOP_TIME = 300 

def check_amazon_stock_and_price(url, max_price, name):
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"【{name}】Amazonアクセス失敗 (Status: {response.status_code})")
            return False, 0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 1. 在庫切れチェック
        availability_div = soup.find('div', {'id': 'availability'})
        if availability_div and "現在在庫切れ" in availability_div.text:
            print(f"【{name}】ステータス: 現在在庫切れです。")
            return False, 0

        # 2. カートボタンのチェック
        add_to_cart_button = soup.find('input', {'id': 'add-to-cart-button'}) or soup.find('input', {'id': 'add-to-cart-button-ubb'})
        if not add_to_cart_button:
            add_to_cart_button = soup.find('span', {'id': 'submit.add-to-cart'})
            
        if not add_to_cart_button:
            print(f"【{name}】ステータス: カートに入れるボタンがありません。")
            return False, 0

        # 3. 価格の取得
        price_text = None
        price_selectors = [
            ('span', {'class': 'a-price-whole'}),
            ('span', {'id': 'priceblock_ourprice'}),
            ('span', {'id': 'priceblock_dealprice'}),
            ('span', {'class': 'a-color-price'}),
            ('span', {'class': 'price-large'}),
            ('div', {'id': 'corePrice_mobile_feature_div'})
        ]
        
        for tag, attrs in price_selectors:
            price_element = soup.find(tag, attrs)
            if price_element:
                price_text = price_element.text
                break

        if not price_text:
            print(f"【{name}】ステータス: カートはありますが、価格が読み取れませんでした。")
            return False, 0

        price_number = int(re.sub(r'\D', '', price_text))
        print(f"【{name}】現在の価格: {price_number}円 (目標: {max_price}円以下)")

        if price_number <= max_price:
            return True, price_number
        else:
            print(f"【{name}】値下がり待ち: 設定金額を超えています。")
            return False, price_number

    except Exception as e:
        print(f"【{name}】エラー発生: {e}")
        return False, 0

def send_discord_notification(name, url, current_price, max_price):
    data = {
        "content": f"**【Amazon値下げ・入荷情報】**\n**{name}** が **{current_price}円** で購入可能です！（目標: {max_price}円以下）\nURL: {url}"
    }
    try:
        requests.post(WEBHOOK_URL, json=data)
    except Exception as e:
        print(f"Discord通知送信エラー: {e}")

def main():
    if not WATCH_LIST:
        print("監視リストが空、または正しく設定されていません。終了します。")
        return

    print(f"Amazon複数価格監視スタート（登録件数: {len(WATCH_LIST)}件）")
    start_time = time.time()
    
    # すでに通知を飛ばした商品を記録するセット（同じ5分間で何度も通知が飛ばないように制御）
    notified_items = set()
    
    while (time.time() - start_time) < TOTAL_LOOP_TIME:
        print(f"[{time.strftime('%H:%M:%S')}] 順次在庫と価格をチェック中...")
        
        for item in WATCH_LIST:
            name = item.get('name', '不明な商品')
            url = item.get('url')
            max_price = int(item.get('max_price', 0))
            
            # すでに通知済みの商品はスキップ
            if name in notified_items:
                continue
                
            if not url:
                continue
                
            is_ok, current_price = check_amazon_stock_and_price(url, max_price, name)
            
            if is_ok:
                send_discord_notification(name, url, current_price, max_price)
                print(f"🎉 【{name}】条件クリア！Discordに通知しました。")
                notified_items.add(name)
        
        # すべての商品が通知済みになったらループを抜ける
        if len(notified_items) == len(WATCH_LIST):
            print("すべての登録商品の通知が完了したため、前倒しで終了します。")
            break
            
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()