import os
import sys
import time
import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Language": "ja,en-US;q=0.9,en;q=0.8"
}

WEBHOOK_URL = os.getenv('WEBHOOK_URL')

def main():
    if len(sys.argv) < 4:
        print("引数が足りません。")
        return
    
    url = sys.argv[1]
    max_price = int(sys.argv[2])
    name = sys.argv[3]

    print(f"Amazon価格監視スタート ➔ 【{name}】（目標: {max_price}円以下）")
    
    start_time = time.time()
    # 5分間（300秒）ループ
    while (time.time() - start_time) < 300:
        try:
            # キャッシュ対策
            target_url = f"{url}&_ts={int(time.time())}" if "?" in url else f"{url}?_ts={int(time.time())}"
            response = requests.get(target_url, headers=HEADERS, timeout=15)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # ボット判定チェック
                if "api-services-support@amazon.com" in response.text or soup.find('form', action=re.compile(r'/validateCaptcha')):
                    print(f"⚠️ Amazonのロボット判定にブロックされました。再試行します。")
                else:
                    # 価格の取得
                    price_element = soup.find('span', {'class': 'a-price-whole'})
                    if price_element:
                        price_number = int(re.sub(r'\D', '', price_element.text))
                        print(f"現在の価格: {price_number}円")
                        
                        if price_number <= max_price:
                            # Discordへ通知
                            data = {"content": f"**【Amazon値下げ情報】**\n**{name}** が **{price_number}円** で購入可能です！（目標: {max_price}円以下）\nURL: {url}"}
                            requests.post(WEBHOOK_URL, json=data)
                            print("🎉 条件クリア！Discordに通知しました。")
                            break
                        else:
                            print("値下がり待ち...")
                    else:
                        print("価格タグが見つかりませんでした。")
                        
        except Exception as e:
            print(f"エラー発生: {e}")
            
        time.sleep(30)

if __name__ == "__main__":
    main()