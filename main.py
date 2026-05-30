import sys
import os
import time
import re
import requests
from bs4 import BeautifulSoup

# 1. GitHub Actionsからの引数受け取り
if len(sys.argv) < 4:
    print("エラー: 引数が足りません。[URL] [目標価格] [商品名] の順で指定してください。")
    sys.exit(1)

# 💡 引数の前後に残る「"」や「'」を完全に削ぎ落とす
AMAZON_URL = sys.argv[1].strip('"\'')
MAX_PRICE = int(str(sys.argv[2]).strip('"\''))
name = sys.argv[3].strip('"\'')

WEBHOOK_URL = os.getenv('WEBHOOK_URL')

# Amazonを完全に沈黙させた最強の回線・マシン偽装ヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Device-Memory": "8",
    "Downlink": "10",
    "ECT": "4g",
    "RTT": "50",
    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1"
}

INTERVAL_SECONDS = 10
TOTAL_LOOP_TIME = 60

def check_amazon_stock_and_price():
    try:
        response = requests.get(AMAZON_URL, headers=HEADERS, timeout=10)
        if response.status_code != 200:
            print(f"Amazonアクセス失敗 (Status: {response.status_code})")
            return False, 0

        html_text = response.text
        soup = BeautifulSoup(html_text, 'html.parser')
        
        # 1. 在庫切れテキストのチェック
        availability_div = soup.find('div', {'id': 'availability'})
        if availability_div and "現在在庫切れ" in availability_div.text:
            print("ステータス: 現在在庫切れです。")
            return False, 0

        # 2. カートボタンのチェック
        add_to_cart_button = soup.find(['input', 'button', 'a'], {'id': 'add-to-cart-button'})
        
        if not add_to_cart_button:
            add_to_cart_button = soup.find(lambda tag: tag.name in ['input', 'button', 'span', 'a'] and (
                (tag.get('id') in ['add-to-cart-button', 'add-to-cart-button-ubb', 'smartBuyingAddToCart_feature_div']) or
                (tag.get('class') and any(cls in tag.get('class') for cls in ['atc-button-element', 'a-button-input']))
            ))

        if not add_to_cart_button:
            print("ステータス: カートに入れるボタンがありません。")
            return False, 0

        # 3. 価格の取得ロジック
        price_text = None

        # 【ルートA】通常のHTMLタグから探す
        price_selectors = [
            ('span', {'class': 'a-price-whole'}),
            ('span', {'id': 'priceblock_ourprice'}),
            ('span', {'id': 'priceblock_dealprice'}),
            ('span', {'class': 'a-color-price'}),
            ('span', {'class': 'price-large'})
        ]
        for tag, attrs in price_selectors:
            el = soup.find(tag, attrs)
            if el and re.sub(r'\D', '', el.text):
                price_text = re.sub(r'\D', '', el.text)
                break

        # 【ルートB】カートボタンの親フォーム内から数字をぶっこ抜く
        if not price_text and add_to_cart_button:
            form = add_to_cart_button.find_parent('form')
            if form:
                for hidden_input in form.find_all('input', type='hidden'):
                    name_attr = hidden_input.get('name', '').lower()
                    val = hidden_input.get('value', '')
                    clean_val = re.sub(r'\D', '', val)
                    if clean_val and (300 <= int(clean_val) <= 200000):
                        price_text = clean_val
                        if 'price' in name_attr or 'amount' in name_attr:
                            break

        # 【ルートC】HTML全体の生テキストからスキャン
        if not price_text:
            price_candidates = re.findall(r'(?:￥|¥)\s*([\d,]+)', html_text)
            for candidate in price_candidates:
                num_str = re.sub(r'\D', '', candidate)
                if num_str and (300 <= int(num_str) <= 200000):
                    price_text = num_str
                    break

        if not price_text:
            print("ステータス: カートはありますが、価格が読み取れませんでした。")
            return False, 0

        # 整数(int)に変換
        price_number = int(price_text)
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
        "content": f"**【Amazon値下げ・入荷情報】**\n"
                   f"お目当ての **{name}** が **{current_price}円** で購入可能です！（目標: {MAX_PRICE}円以下）\n"
                   f"URL: {AMAZON_URL}"
    }
    requests.post(WEBHOOK_URL, json=data)

def main():
    if not WEBHOOK_URL:
        print("エラー: WEBHOOK_URL が設定されていません。")
        sys.exit(1)

    print(f"Amazon価格監視スタート ➔ 【{name}】")
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