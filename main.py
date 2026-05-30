import sys
import re
import time
import requests
from bs4 import BeautifulSoup

# 引数の受け取り
if len(sys.argv) < 4:
    print("エラー: 引数が足りません。 [URL] [目標価格] [商品名] の順で指定してください。")
    sys.exit(1)

url = sys.argv[1]
max_price = int(sys.argv[2])
name = sys.argv[3]

import os
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# 本物のWindows Chromeブラウザに完全偽装
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ja-JP,ja;q=0.9",
    "Accept-Encoding": "gzip, deflate, br, zstd",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Ch-Ua": '"Not-A.Brand";v="99", "Chromium";v="124", "Google Chrome";v="124"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-User": "?1",
    "Sec-Fetch-Dest": "document",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache"
}

def main():
    if not WEBHOOK_URL:
        print("エラー: WEBHOOK_URL が設定されていません。")
        sys.exit(1)

    print(f"Amazon価格監視スタート ➔ 【{name}】（目標: {max_price}円以下）")
    
    start_time = time.time()
    
    # テスト用：1分間（60秒）の短期決戦
    #while (time.time() - start_time) < 300:
    while (time.time() - start_time) < 60: #debug
        try:
            response = requests.get(url, headers=HEADERS, timeout=15)
            html_text = response.text
            soup = BeautifulSoup(html_text, 'html.parser')
            
            # ロボット判定チェック
            if "api-services-support@amazon.com" in html_text or soup.find('form', action=re.compile(r'/validateCaptcha')):
                print("⚠️ Amazonのロボット判定にブロックされました。再試行します。")
            else:
                price_number = None

                # 【アプローチ1】通常のHTMLタグから探す（PC版や一部のモバイル版）
                price_selectors = [
                    ('span', {'class': 'a-price-whole'}),
                    ('span', {'class': 'a-color-price'}),
                    ('span', {'class': 'price-large'})
                ]
                for tag, attrs in price_selectors:
                    el = soup.find(tag, attrs)
                    if el and re.sub(r'\D', '', el.text):
                        price_number = int(re.sub(r'\D', '', el.text))
                        break

                # 【アプローチ2】HTML内のJavaScriptに埋め込まれた価格データを正規表現で直接引っこ抜く（スマホ版の遅延対策）
                if not price_number:
                    # スクリプト等に書かれた価格パターン（例: "buyingPrice":2246 や "priceAmount":2246 など）を抽出
                    patterns = [
                        r'"buyingPrice"\s*:\s*(\d+)',
                        r'"priceAmount"\s*:\s*(\d+)',
                        r'"displayPrice"\s*:\s*"￥?([\d,]+)"',
                        r'"price"\s*:\s*(\d+)'
                    ]
                    for pattern in patterns:
                        match = re.search(pattern, html_text)
                        if match:
                            raw_val = match.group(1)
                            price_number = int(re.sub(r'\D', '', raw_val))
                            if price_number > 0:
                                break

                # 3. 判定判定
                if price_number and price_number > 0:
                    print(f"現在の価格: {price_number}円")
                    
                    if price_number <= max_price:
                        data = {
                            "content": f"**【Amazon値下げ情報】**\n"
                                       f"**{name}** が **{price_number}円** で購入可能です！（目標: {max_price}円以下）\n"
                                       f"URL: {url}"
                        }
                        requests.post(WEBHOOK_URL, json=data)
                        print("🎉 条件クリア！Discordに通知しました。")
                        return  # 💡 1分待たずに即終了！
                    else:
                        print("値下がり待ち...")
                else:
                    print("価格データがどうしても見つかりませんでした。")
                    
        except Exception as e:
            print(f"通信エラー等が発生しました: {e}")
            
        # テスト用：10秒待機
        #time.sleep(30)
        time.sleep(10) #debug

if __name__ == "__main__":
    main()