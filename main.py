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
    "Cache-Control": "max-age=0",
    "Sec-Ch-Ua-Platform": '"Windows"'
}

WEBHOOK_URL = os.getenv('WEBHOOK_URL')

WATCH_LIST_JSON = os.getenv('WATCH_LIST', '[]')
try:
    WATCH_LIST = json.loads(WATCH_LIST_JSON)
except Exception as e:
    print(f"JSONのパースに失敗しました: {e}")
    WATCH_LIST = []

INTERVAL_SECONDS = 30 
TOTAL_LOOP_TIME = 300 

def check_amazon_stock_and_price(url, max_price, name):
    try:
        # キャッシュを避けるためにタイムスタンプをダミーで付与
        target_url = f"{url}&_ts={int(time.time())}" if "?" in url else f"{url}?_ts={int(time.time())}"
        
        response = requests.get(target_url, headers=HEADERS, timeout=15)
        if response.status_code != 200:
            print(f"【{name}】Amazonアクセス失敗 (Status: {response.status_code})")
            return False, 0

        soup = BeautifulSoup(response.text, 'html.parser')
        
        # ボット画面（キャプチャ画面）に遭遇していないかチェック
        if "api-services-support@amazon.com" in response.text or soup.find('form', action=re.compile(r'/validateCaptcha')):
            print(f"【{name}】⚠️ Amazonのロボット判定にブロックされました。")
            return False, 0

        # 1. 在庫切れチェック
        availability_div = soup.find('div', {'id': 'availability'})
        if availability_div and "現在在庫切れ" in availability_div.text:
            print(f"【{name}】ステータス: 現在在庫切れです。")
            return False, 0

        # 2. 価格の取得（ここを大幅強化）
        price_text = None
        price_selectors = [
            ('span', {'class': 'a-price-whole'}),
            ('span', {'id': 'priceblock_ourprice'}),
            ('span', {'id': 'priceblock_dealprice'}),
            ('span', {'class': 'a-color-price'}),
            ('span', {'class': 'price-large'}),
            ('span', {'id': 'kindle-price'}),
            ('div', {'id': 'corePrice_mobile_feature_div'})
        ]
        
        for tag, attrs in price_selectors:
            price_element = soup.find(tag, attrs)
            if price_element:
                price_text = price_element.text
                break

        # カートボタンが無くても、価格が取れれば在庫ありとみなす
        if not price_text:
            # 念のためカートボタン自体があるか最後のチェック
            add_to_cart_button = soup.find('input', {'id': 'add-to-cart-button'}) or soup.find('span', {'id': 'submit.add-to-cart'})
            if not add_to_cart_button:
                print(f"【{name}】ステータス: 画面の解析に失敗しました（ボット回避または仕様変更の可能性）。")
                return False, 0
            else:
                print(f"【{name}】ステータス: カートはありますが、価格が読み取れません。")
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
    notified_items = set()
    
    while (time.time() - start_time) < TOTAL_LOOP_TIME:
        print(f"[{time.strftime('%H:%M:%S')}] 順次在庫と価格をチェック中...")
        
        for item in WATCH_LIST:
            name = item.get('name', '不明な商品')
            url = item.get('url')
            max_price = int(item.get('max_price', 0))
            
            if name in notified_items or not url:
                continue
                
            is_ok, current_price = check_amazon_stock_and_price(url, max_price, name)
            
            if is_ok:
                send_discord_notification(name, url, current_price, max_price)
                print(f"🎉 【{name}】条件クリア！Discordに通知しました。")
                notified_items.add(name)
        
        if len(notified_items) == len(WATCH_LIST):
            print("すべての登録商品の通知が完了したため、終了します。")
            break
            
        time.sleep(INTERVAL_SECONDS)

if __name__ == "__main__":
    main()