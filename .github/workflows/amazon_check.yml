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

# DiscordのWebhook URL（GitHub Secretsから渡される想定）
import os
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")

# 本物のWindows Chromeブラウザ＋日本語環境にガチガチに偽装するヘッダー
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ja-JP,ja;q=0.9,en-US;q=0.8,en;q=0.7",
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
        print("エラー: WEBHOOK_URL が環境変数に設定されていません。")
        sys.exit(1)

    print(f"Amazon価格監視スタート ➔ 【{name}】（目標: {max_price}円以下）")
    
    start_time = time.time()
    
    # 5分間（300秒）ループする
    while (time.time() - start_time) < 300:
        try:
            # タイムアウトは15秒に設定
            response = requests.get(url, headers=HEADERS, timeout=15)
            
            # HTMLを解析
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # 1. ロボット判定（Captcha）の厳重チェック
            if "api-services-support@amazon.com" in response.text or soup.find('form', action=re.compile(r'/validateCaptcha')):
                print("⚠️ Amazonのロボット判定にブロックされました。再試行します。")
            else:
                # 2. スマホ版・PC版のあらゆる価格タグを絨毯爆撃で探す
                price_text = None
                price_selectors = [
                    ('span', {'class': 'a-price-whole'}),           # PC版基本
                    ('span', {'class': 'a-color-price'}),           # モバイル版・セール価格
                    ('span', {'id': 'priceblock_ourprice'}),        # 旧世代の定番
                    ('span', {'id': 'priceblock_dealprice'}),       # 特価用
                    ('div', {'id': 'corePrice_mobile_feature_div'}), # モバイル特有のエリア
                    ('span', {'class': 'price-large'})              # 予備
                ]
                
                for tag, attrs in price_selectors:
                    price_element = soup.find(tag, attrs)
                    if price_element:
                        price_text = price_element.text
                        break

                # 3. 価格が取得できた場合の判定処理
                if price_text:
                    # 数字以外の文字を消し去る
                    price_number = int(re.sub(r'\D', '', price_text))
                    print(f"現在の価格: {price_number}円")
                    
                    if price_number <= max_price:
                        data = {
                            "content": f"**【Amazon値下げ情報】**\n"
                                       f"**{name}** が **{price_number}円** で購入可能です！（目標: {max_price}円以下）\n"
                                       f"URL: {url}"
                        }
                        requests.post(WEBHOOK_URL, json=data)
                        print("🎉 条件クリア！Discordに通知しました。")
                        break
                    else:
                        print("値下がり待ち...")
                else:
                    # 💡 【デバッグ機能】価格が見つからない原因を特定するため、HTMLの頭を出力する
                    print("❌ 価格タグが見つかりませんでした。Amazonから返ってきたHTMLの冒頭を出力します：")
                    clean_html = re.sub(r'\s+', ' ', response.text)[:1200]
                    print(f"【生ログ】: {clean_html}")
                    
        except Exception as e:
            print(f"通信エラー等が発生しました: {e}")
            
        # 30秒待機して次の周回へ
        time.sleep(30)

if __name__ == "__main__":
    main()