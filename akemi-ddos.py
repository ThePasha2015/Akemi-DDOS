import requests
import threading
import time
import argparse

def stres_testi(url, istek_sayisi, es_zamanli):
    basarisiz = 0
    baslangic_zamani = time.time()
    
    def istek_gonder():
        nonlocal basarisiz
        try:
            response = requests.get(url, timeout=5)
            print(f"İstek başarılı: {response.status_code}")
        except requests.RequestException as e:
            basarisiz += 1
            print(f"İstek başarısız: {e}")

    threadler = []
    for _ in range(istek_sayisi):
        for _ in range(es_zamanli):
            t = threading.Thread(target=istek_gonder)
            threadler.append(t)
            t.start()
        
        for t in threadler:
            t.join()
        
        time.sleep(0.1)  # Sunucuyu boğmamak için ufak bir mola

    gecen_zaman = time.time() - baslangic_zamani
    print(f"\nTest tamam! Toplam süre: {gecen_zaman:.2f} saniye")
    print(f"Başarısız istekler: {basarisiz}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Basit ama etkili ağ stres testi")
    parser.add_argument("url", help="Test edilecek URL (örn: http://example.com)")
    parser.add_argument("--istek", type=int, default=100, help="Toplam istek sayısı")
    parser.add_argument("--es-zamanli", type=int, default=10, help="Eş zamanlı istek sayısı")
    args = parser.parse_args()

    print(f"Test başlıyor: {args.url}")
    stres_testi(args.url, args.istek, args.es_zamanli)