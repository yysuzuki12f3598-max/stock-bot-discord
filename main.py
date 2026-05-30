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
    
    # 1分間（60秒）の短期決戦
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

                # 💡 【アプローチ1】発見してもらったカートボタンの周辺（formなど）から紐解く
                cart_button = soup.find(id="add-to-cart-button")
                if cart_button:
                    # カートボタンを含む親フォームを取得
                    form = cart_button.find_parent('form')
                    if form:
                        # フォーム内の非表示データ（価格や値引き情報）を全探索
                        for hidden_input in form.find_all('input', type='hidden'):
                            val = hidden_input.get('value', '')
                            # 3〜5桁の純粋な数字（価格っぽいもの）を抽出
                            if val.isdigit() and 300 <= int(val) <= 50000:
                                price_number = int(val)
                                break

                # 【アプローチ2】通常のHTMLタグ（予備）
                if not price_number:
                    price_selectors = [
                        ('span', {'class': 'a-price-whole'}),
                        ('span', {'class': 'a-color-price'}),
                        ('span', {'id': 'corePrice_desktop'}),
                        ('div', {'id': 'corePrice_mobile_feature_div'})
                    ]
                    for tag, attrs in price_selectors:
                        el = soup.find(tag, attrs)
                        if el and re.sub(r'\D', '', el.text):
                            price_number = int(re.sub(r'\D', '', el.text))
                            break

                # 【アプローチ3】HTML全体から「￥・¥数字」のパターン（最終予備）
                if not price_number:
                    price_candidates = re.findall(r'(?:￥|¥)\s*([\d,]+)', html_text)
                    for candidate in price_candidates:
                        num_str = re.sub(r'\D', '', candidate)
                        if num_str:
                            num = int(num_str)
                            if 300 <= num <= 50000:
                                price_number = num
                                break

                # 3. 判定判定
                if price_number:
                    print(f"現在の価格（カート周辺検出）: {price_number}円")
                    
                    if price_number <= max_price:
                        data = {
                            "content": f"**【Amazon値下げ情報】**\n"
                                       f"**{name}** が **{price_number}円** で購入可能です！（目標: {max_price}円以下）\n"
                                       f"URL: {url}"
                        }
                        requests.post(WEBHOOK_URL, json=data)
                        print("🎉 条件クリア！Discordに通知しました。")
                        return  # 1分待たずに即終了！
                    else:
                        print("値下がり待ち...")
                else:
                    print("価格データがどうしても見つかりませんでした。")
                    
        except Exception as e:
            print(f"通信エラー等が発生しました: {e}")
            
        #time.sleep(30)
        time.sleep(10) #debug

if __name__ == "__main__":
    main()