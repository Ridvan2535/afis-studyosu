# Afiş Stüdyosu (sürüm 0.7-test)

Windows'ta çift tıklayarak çalışan yerel program. Adım adım kurulum: **KURULUM_REHBERI.md**.

```
kur.bat      (bir kere)  -> ortamı kurar ve kendini sınar
baslat.bat               -> programı açar (tarayıcıda arayüz)
```

## Program yapısı
| Dosya | Görevi |
|---|---|
| `app.py`, `ui.html` | Yerel arayüz (yalnızca bu bilgisayardan erişilir, ek paket gerektirmez) |
| `orchestrator.py` | İş akışı: sahne üret -> kalite kapısı -> tasarımı yerleştir -> video -> yazı onarımı -> kalite kontrol -> hata raporu |
| `providers.py` | Magnific / OpenAI / Gemini bağlantıları, ayarlar (`ayarlar.json`), harcama sınırları, en yeni görsel modelinin otomatik bulunması |
| `selector.py` | Otomatik servis seçimi: anahtarı olan servisler yarışır, sonuçlar `servis_karnesi.json`'a yazılır, iyi çalışan daha sık seçilir, hata veren bırakılır |
| `prompts.py` | Sahne ve video istemleri (boş afiş kuralları, kategori başına 6 sahne) |
| `mock_provider.py` | "Deneme modu": ücretsiz sahte sağlayıcılar (akışı anahtarsız sınamak için) |
| `layout.py`, `guide.py` | Sahne kuralı: afiş dik, karşıdan ve yere kadar uzanıyor mu (aksi halde elenir); OpenAI/Gemini'ye verilen kılavuz görsel |
| `banner_detect.py`, `compositor.py` | Afiş bulma + tasarımı perspektif/kumaş yapısına göre yerleştirme |
| `camera_move.py` | Varsayılan video: fotoğraf sabit, kamera "elinde yürüyen biri" gibi fiziksel olarak sallanır (adım ritmi, yaw/pitch/roll, hareket bulanıklığı, rolling shutter, gren); yapay zekâsız, ücretsiz, yazı bozulmaz |
| `video_composite.py` | "Hareketli sahne" videosu: yapay zekâ tasarımsız sahneyi SABİT kamerayla canlandırır (insanlar/ortam), kamera kayması giderilir, tasarım her kareye kodla basılır, önüne giren nesne algılanır, el kamerası kodla eklenir; kalite kontrol geçmezse otomatik kamera videosuna döner |
| `video_repair.py` | Videoda yazıyı her karede orijinal tasarımla yeniden yerleştirme + kalite ölçümü |
| `kontrol.py` | Kurulum sonrası hızlı kendini sınama |
| `tests/test_e2e_mock.py` | Sahte sağlayıcılarla uçtan uca sınama |

## Otomatik servis seçimi
Ayarlar'da sahne ve video servisleri varsayılan olarak **Otomatik**'tir; elle servis seçip sonucu kontrol edip başka servisi denemek gerekmez.
- Anahtarı girilmiş her servis denenir (sahne: OpenAI, Gemini, Magnific Seedream 4.5 Edit, Magnific Seedream 5 Pro Edit, Magnific Seedream; video: Veo 3.1, Kling Pro, Runway Gen-4.5). Edit servisleri ve OpenAI/Gemini, afişin yerini/oranını gösteren kılavuz görselle çalışır; yalnız-istem servisi (Seedream) en sona kalır.
- Her sahne/video kalite kapısından geçerse servise puan yazılır (kapıdan geçme x kalite puanı); kalıcı karne `servis_karnesi.json` içinde durur.
- Sonraki üretimlerde başarılı servis daha sık seçilir (Thompson örneklemesi); sahnede küçük bir keşif payı vardır, böylece şanssız bir ilk sonuç servisi sonsuza dek dışlamaz.
- Üst üste 3 hata veren ya da anahtarı reddedilen servis o iş boyunca bırakılır. Hiç servis kalmazsa üretim kredi harcamadan durur.
- Video: ilk deneme bir servisle, kalite kontrolden geçmezse ikinci deneme başka servisle yapılır; kontrolden geçen ve kalite puanı yüksek olan seçilir.
- Sonuç ekranında her fotoğrafta servis adı ve kalite puanı görünür, en yüksek puanlı fotoğraf "★ en iyi" olarak otomatik seçilir; servis karnesi tablosu da gösterilir.
- Hesap çapında hata (kredi bitti / kota dolu) görülürse o servisin diğer modelleri boşuna denenmez; kayıtta açık nedeni yazılır (ör. "OpenAI hesabında kredi kalmamış").
- Harcama tavanları (`max_scene_calls`, `max_video_tries`) otomatik modda da geçerlidir. Servis kodu/istemi değişince karne sıfırlanır (`SELECTOR_VERSION`).

## Otomatik video
Varsayılan olarak her fotoğraf üretimi bitince, onaylanan hareketle (yaklaşırken sağa doğru dön, doğal el sallantısı) her fotoğraf için ücretsiz kamera videosu da hazırlanır. Ayarlar > Otomatik video'dan kapatılabilir ya da hareket değiştirilebilir. Ayarlar `ayarlar.json` içinde kalıcıdır; güncellemeler bu dosyaya dokunmaz.

## Video türleri
1. **Kamera hareketi** (varsayılan, ücretsiz): hazır fotoğraf + fiziksel el kamerası. Yazı değişemez. Yakınlaşma hareketleri gerçek yürüyüş gibi sabit hızla, sakin ve uzun adımlarla afişe yaklaşır (kadraj ~2 kat daralır; el sallantısı bilerek hafif tutulur): "Afişe doğru yürü", "Yaklaşırken sağa/sola doğru dön" (kamera afişin etrafında ~24° yay çizer, perspektif gerçek bir yürüyüş gibi değişir), "Çok yakına git" (~2.7 kat). "Yan kaydır" seçenekleri yakınlaşmaz. Yakın planda yazı net kalsın diye kaynak sahne 1.6 kat büyütülüp tasarım orijinal çözünürlüğünden yeniden basılır (gerekirse kayıtlı fotoğrafa dönülür). Çıktı boyutu, en yakın karede görüntü en fazla ~1.3 kat büyütülecek biçimde otomatik ayarlanır (yazı bulanıklaşmasın).
2. **Hareketli sahne** (ücretli, insanlı sahneler için): yapay zekâ videosu + kodla baskı + kodla el kamerası. Kalite kontrolden
   geçmezse (kamera çok oynadı, afişin önüne bir şey girdi, takip noktası yok…) otomatik olarak 1. türe döner ve nedeni raporlar.
3. **Ham yapay zekâ videosu** (eski yöntem): yazıyı bozabilir; yalnızca karşılaştırma içindir.

## Durum (dürüst özet)
Sınandı (sahte sağlayıcılarla, Linux'ta): afiş bulma ve kalite kapısı, yerleştirme, çoklu sahne akışı, video yazı onarımı
(sentetik videoda), arayüzün tarayıcıda baştan sona çalışması, anahtar maskeleme, hata raporunun anahtar/tasarım içermemesi.

SINANMADI: gerçek bir yapay zekâ videosunda "hareketli sahne" hattı (sentetik videoyla sınandı; eşikler gerçek videolarla ayarlanacak),
gerçek Magnific/OpenAI/Gemini çağrıları (Magnific yolu resmi dokümandan, diğerleri bilinen arayüzden yazıldı),
Windows .bat dosyaları, gerçek yapay zekâ videosunda yazı onarımı, `imageio-ffmpeg` ile video kodlama (bu ortamda sistem
ffmpeg'i kullanıldı). İlk gerçek çalıştırmada sorun çıkarsa arayüzdeki "Hata raporu hazırla" düğmesiyle raporu gönder.

---

# Komut satırı modülleri (ileri düzey)

## Algılama + yerleştirme + çoklu sahne (pipeline.py)

Tasarım dosyanı, boş afişli sahnelere **yazıları bozmadan** yerleştirir. Yazı/çizim hiçbir aşamada yapay zekaya
çizdirilmez; hepsi senin dosyandan gelir.

## Kurulum
```
pip install -r requirements.txt
```

## Kullanım
```
python pipeline.py --design tasarim.png --scenes sahneler/ --out cikti/ --n 6
```
Çıktı klasörü: `01_*.jpg ...` (mockup'lar), `_overview.jpg` (hepsi bir arada), `report.json` (neden elenenler,
metrikler), `debug/` (her sahnede neyin afiş sayıldığı).

Sahne yanına `sahne.json` koyarak ipucu verebilirsin: `{"point":[0.5,0.55]}`, `{"kind":"fabric"}`,
`{"polygon":[[x,y],...]}` (kenarları elle işaretle, algılamayı atlar).

Sahneleri üretmek için `scene_prompts.md`. Pipeline'ı sınamak için sentetik sahneler: `python make_test_scenes.py tests/scenes`.

## Ne yapıyor
1. **Algılama** (`banner_detect.py`): afiş maskesini bulur, sert afiş (4 köşe) / kumaş (kenar eğrileri) ayırır.
2. **Kalite kapısı**: afiş bulunamadı, kadraja taşıyor, çok büyük/küçük, açık-nötr renkli değil, içinde yazı/desen var,
   en-boy oranı tasarıma uymuyor (düzeltilemeyecek kadar) -> sahne elenir, nedeni yazılır.
   **Oran düzeltme** (`proportion.py`): yapay zekâ afişi tasarımdan daha ince çizdiyse (oran farkı %7-%60) sahne atılmaz; afişin bulunduğu yatay şerit
   yumuşak geçişle genişletilir, afiş tasarımla birebir aynı orana gelir (kayıtta "yatayda xN genişletildi", raporda `oran_duzeltme`).
   Düzeltilmiş sahne kalite puanında hafif geride kalır; %60'tan fazla uzatma gerekiyorsa sahne yine elenir.
3. **Yerleştirme** (`compositor.py`): sert afişe perspektif, kumaşa yumuşak ağ warp. Sonuç = sahne x tasarım (çarpma),
   böylece kâğıdın/kumaşın ışığı, gölgesi, dokusu korunur.

## Bilinen sınırlar (dürüst liste)
- **Beyaz afiş / beyaz duvar** (ya da beyaz çerçeve) klasik algılamayla ayrılamaz; sahne elenir. Bunun için SAM 2
  arkauç hazır ama **bu ortamda test edilemedi** (model ağırlıklarına erişim yoktu). Kendi makinende:
  `SAM2_CKPT=/yol/sam2.1_hiera_large.pt python pipeline.py ... --backend sam2` ve sonuçları `debug/` ile doğrula.
- Eşikler (boşluk/yazı kontrolü) 1 gerçek + birkaç sentetik sahneyle ayarlandı. Gerçek üretilmiş sahnelerde
  `report.json` metriklerine bakıp `banner_detect.py` başındaki eşikleri ayarla.
- Afişin **önündeki nesneler** (el, balon, çiçek) maskelenmiyor; tasarım onların üstüne biner. Bu tür sahneleri üretme.
- Sert afişte en-boy oranı yaklaşık hesaplanır (±%15 tolerans). Farklı oran = sahne elenir.
- Baskı modeli çarpmaya dayanır: boş afiş beyaz/krem/açık gri olmalı.
- Komut satırı `pipeline.py` sahneleri klasörden alır; sahne üretimini bağlayan ana program `app.py`'dir.

## Video yazı onarımı (video_repair.py) - DURUM
Yapay zeka videosundaki bozulmuş yazıyı orijinal tasarımla kare kare yeniden yerleştirir.
Sınama: `python tests/test_video_repair.py 24 1.0` (doğrusu bilinen sentetik video; ~1 dk).

Sentetik testte (24 kare, zoom+kayma+dönüş+kumaş dalgalanması, yazı giderek bozuluyor) ölçülenler:
- Ortalama hata (MAE) 7.7 -> 5.6, benzerlik (SSIM) 0.83 -> 0.88. Görsel olarak tüm karelerde yazı temiz.
- Yazı bölgesinde takip hatası: ilk karelerde ~0.3 px, son karede ~3.9 px (hareket ve bozulma en fazlayken).
- Hız: ~2.2 sn/kare (2 çekirdekli CPU, 1140x1710). 5 sn'lik video ~4-5 dk.

Henüz YAPILMAYANLAR / BİLİNEN SINIRLAR:
- Gerçek yapay zeka videosuyla denenmedi (sadece sentetik). Gerçek bozulma farklı olabilir.
- Tam uzunlukta (72 kare) ve iki kat bozulmalı zorlama testi çalıştırılmadı.
- Takip çok geniş ölçekte yumuşatılıyor (sigma 40 px): ince kumaş kıpırtısı izlenmez, baskı kıvrımlara
  birebir yapışmak yerine hafif kayabilir.
- Afişin önünden geçen nesneler maskelenmez. Kalite eşikleri (summarize) başlangıç değeri.
- Denenip bırakılan yöntemler: (1) dar ölçekli yazı takibi -> yazıyı da bozuk şekle uydurdu;
  (2) yazısı bastırılmış kumaş takibi -> düz kumaşta rastgele sürüklenip dağıldı.

## Hata mesajları
Servis hata verdiğinde günlükte servisin kendi açıklaması görünür (ör. "HTTP 429: ... limit: 0"). Kota/bakiye bitmişse ya da modele erişim kapalıysa
(ör. OpenAI'da kuruluş doğrulaması gerekiyorsa) program beklemeden o modeli/servisi bırakır; OpenAI ve Gemini'de sıradaki model denenir
(model listesi pro > flash > lite, sonra yeni sürüm sırasıyla). Kısa süreli hız sınırlarında ise bekleyip yeniden dener.
