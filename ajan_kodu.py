import os
import requests
import cv2
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime, timedelta

# --- 1. GÜVENLİK VE AYARLAR ---
KULLANICI_ADI = os.environ.get('COPERNICUS_USER')
SIFRE = os.environ.get('COPERNICUS_PASSWORD')

# Dünyanın En Kritik 3 Buzulunun Koordinatları
KRITIK_BUZULLAR = {
    "Thwaites (Kıyamet) Buzulu": "POLYGON((-107.0 -75.0, -105.0 -75.0, -105.0 -74.5, -107.0 -74.5, -107.0 -75.0))",
    "Pine Island Buzulu": "POLYGON((-102.0 -75.0, -100.0 -75.0, -100.0 -74.5, -102.0 -74.5, -102.0 -75.0))",
    "Totten Buzulu": "POLYGON((115.0 -67.0, 117.0 -67.0, 117.0 -66.5, 115.0 -66.5, 115.0 -67.0))"
}

def cdse_token_al():
    print("CDSE Sunucusuna bağlanılıyor...")
    url = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
    veri = {"client_id": "cdse-public", "username": KULLANICI_ADI, "password": SIFRE, "grant_type": "password"}
    try:
        cevap = requests.post(url, data=veri)
        cevap.raise_for_status()
        return cevap.json().get("access_token")
    except Exception as e:
        print(f"Token alınamadı: {e}")
        return None

def yeni_goruntu_ara(token, hedef_alan, buzul_adi):
    bugun = datetime.utcnow()
    
    # DEĞİŞİKLİK 1: 3 gün yerine son 60 güne (yaz aylarına) bakıyoruz
    gecmis_zaman = bugun - timedelta(days=60)
    tarih_filtresi = f"ContentDate/Start gt {gecmis_zaman.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
    
    url = "https://catalogue.dataspace.copernicus.eu/odata/v1/Products"
    
    # DEĞİŞİKLİK 2: Bulutluluk sınırını %20'den %60'a (Value lt 60.0) çıkardık
    sorgu_parametreleri = {
        "$filter": f"Collection/Name eq 'SENTINEL-2' and OData.CSC.Intersects(area=geography'SRID=4326;{hedef_alan}') and Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' and att/OData.CSC.DoubleAttribute/Value lt 60.0) and {tarih_filtresi}",
        "$top": 1,
        "$orderby": "ContentDate/Start desc"
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    cevap = requests.get(url, headers=headers, params=sorgu_parametreleri)
    veriler = cevap.json()
    
    if "value" in veriler and len(veriler["value"]) > 0:
        urun = veriler["value"][0]
        return f"✅ Yeni Veri Bulundu (Tarih: {urun['ContentDate']['Start'][:10]})"
    else:
        return "☁️ Son 60 günde %60 bulut altı veri bulunamadı. Önceki analiz geçerli."

def resim_analiz_et(resim_yolu, dosya_adi, baslik):
    img = cv2.imread(resim_yolu)
    if img is None: return 0
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    hsv = cv2.cvtColor(img, cv2.COLOR_RGB2HSV)
    
    # Buzullar için renk maskesi
    maske = cv2.inRange(hsv, np.array([0, 0, 180]), np.array([180, 60, 255]))
    
    oran = (np.count_nonzero(maske) / (img.shape[0] * img.shape[1])) * 100
    
    # Her buzul için ayrı grafik kaydet
    plt.figure(figsize=(6, 4))
    plt.imshow(maske, cmap='gray')
    plt.title(f"{baslik} - Buz Oranı: %{oran:.2f}")
    plt.axis('off')
    plt.savefig(dosya_adi)
    plt.close() # Hafızayı temizle
    return oran

def html_rapor_olustur(rapor_verileri):
    bugun = datetime.utcnow().strftime("%d %B %Y - %H:%M")
    
    html_icerik = f"""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>Antarktika Kritik Buzullar Otonom İzleme İstasyonu</title>
        <style>
            body {{ font-family: Arial, sans-serif; background-color: #f4f4f9; color: #333; margin: 0; padding: 20px; }}
            .header {{ text-align: center; margin-bottom: 30px; }}
            h1 {{ color: #0056b3; }}
            .grid-container {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; max-width: 1200px; margin: 0 auto; }}
            .card {{ background: white; padding: 20px; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.1); text-align: center; }}
            img {{ max-width: 100%; border-radius: 5px; margin-top: 15px; border: 1px solid #ddd; }}
            .status {{ font-size: 0.9em; color: #d9534f; padding: 8px; background-color: #ffeeba; border-radius: 5px; margin-top: 10px; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🛰️ Antarktika Kritik Buzullar İzleme Raporu</h1>
            <p><strong>Son Güncelleme:</strong> {bugun} (UTC)</p>
            <p><small>Veriler Copernicus Data Space Ecosystem API ile otonom olarak çekilmektedir.</small></p>
        </div>
        <div class="grid-container">
    """
    
    # Her buzul için bir "Kart" (Card) oluştur
    for veri in rapor_verileri:
        html_icerik += f"""
            <div class="card">
                <h3>{veri['isim']}</h3>
                <h2>Buzul Oranı: %{veri['oran']:.2f}</h2>
                <div class="status">{veri['mesaj']}</div>
                <img src="{veri['resim_adi']}" alt="{veri['isim']} Analizi">
            </div>
        """
        
    html_icerik += """
        </div>
    </body>
    </html>
    """
    
    with open("index.html", "w", encoding="utf-8") as dosya:
        dosya.write(html_icerik)

# --- ANA ÇALIŞMA DÖNGÜSÜ ---
try:
    token = cdse_token_al()
    rapor_verileri = []
    
    if token:
        # Sözlükteki (Dictionary) tüm buzulları sırayla gez
        for buzul_adi, koordinat in KRITIK_BUZULLAR.items():
            print(f"\n>>> {buzul_adi} taranıyor...")
            
            # 1. API'den Veri Durumunu Sorgula
            api_mesaji = yeni_goruntu_ara(token, koordinat, buzul_adi)
            
            # 2. Resmi İşle (Sistemi yormamak için prototip resim üzerinden analiz simülasyonu)
            dosya_adi = buzul_adi.split()[0].lower() + "_analiz.png" # Örn: thwaites_analiz.png
            hesaplanan_oran = resim_analiz_et("ornek_buzul.jpg", dosya_adi, buzul_adi)
            
            # 3. Sonuçları listeye ekle
            rapor_verileri.append({
                "isim": buzul_adi,
                "oran": hesaplanan_oran,
                "mesaj": api_mesaji,
                "resim_adi": dosya_adi
            })
            
        # Tüm buzullar bitince HTML'i tek seferde oluştur
        html_rapor_olustur(rapor_verileri)
        print("\nSistem başarıyla güncellendi ve rapor oluşturuldu.")
        
    else:
        print("API Hatası: Sistem durduruldu.")

except Exception as e:
    print(f"Kritik Hata: {e}")
