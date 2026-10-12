# Afiş Stüdyosu — Kurulum Rehberi (Windows)

Kod bilmen gerekmiyor. Aşağıdaki adımları sırayla yap. Toplam süre yaklaşık 10–15 dakika.

## 1) Python'u kur (bir kere)

1. https://www.python.org/downloads/ adresine git, **Python 3.12** sürümünü indir.
2. Kurulum penceresi açılınca **en alttaki “Add python.exe to PATH” kutusunu işaretle**, sonra “Install Now”a bas.
   (Bu kutuyu işaretlemezsen kur.bat Python'u bulamaz.)

## 2) Programı hazırla

1. Aldığın `afis_mockup.zip` dosyasına sağ tıkla → “Tümünü ayıkla”. Masaüstünde bir klasör oluşsun.
2. Klasörün içine gir. İçinde `kur.bat` ve `baslat.bat` dosyalarını göreceksin.

## 3) Kur (bir kere)

1. `kur.bat` dosyasına çift tıkla. Siyah bir pencere açılır ve paketleri indirir (birkaç dakika sürer).
2. Windows “bilinmeyen yayıncı” uyarısı verirse “Yine de çalıştır” de.
3. Sonunda **“HER ŞEY TAMAM”** yazısını görmelisin. Başka bir şey görürsen o pencerenin fotoğrafını bana gönder.

## 4) Aç

`baslat.bat` dosyasına çift tıkla. Tarayıcında “Afiş Stüdyosu” sayfası açılır. Siyah pencere programın çalıştığı yerdir; kullanırken kapatma. İşin bitince kapatabilirsin.

## 5) Önce ücretsiz dene (hiç para harcamaz)

1. Sayfada **Ayarlar** sekmesine gir.
2. “Sahne üretimi” ve “Video üretimi” alanlarını **Deneme modu** yap, “Ayarları kaydet”e bas.
3. **Üret** sekmesine dön, tasarım dosyanı yükle, “Fotoğrafları üret”e bas.
4. Gelen fotoğraflardan birini seçip “Seçili fotoğraftan video üret”e bas.

Bu modda gerçek yapay zekâ kullanılmaz; sahneler sahtedir. Amaç, programın senin bilgisayarında baştan sona çalıştığını görmek.

## 6) Gerçek servislere geç

1. Her servisin sitesinde **sadece bu program için yeni bir API anahtarı** oluştur (Magnific, OpenAI, Gemini). Mümkünse her birinde **aylık harcama limiti** koy (ör. başlangıç için 20–30 dolar).
2. Anahtarı **sadece programdaki Ayarlar ekranına** yapıştır. Bana, e-postaya ya da sohbete yazma. Anahtar yalnızca senin bilgisayarında `ayarlar.json` dosyasında durur.
3. “Test et” düğmesi harcama yapmadan anahtarın geçerli olup olmadığına bakar.
4. Servis seçimini **“Otomatik”** bırak (varsayılan). Program anahtarını girdiğin servislerin hepsini kendisi dener, hangisinin daha iyi sonuç verdiğini ölçer ve sonuç ekranında “servis karnesi”ni gösterir. Elle seçmen gerekmez.
5. İlk gerçek denemede **az fotoğrafla başla** (ör. 2). Program her ücretli işten önce onay ister. “Harcama koruması” bölümündeki sınırlar, bir hata yüzünden kontrolsüz ücret çıkmasını engeller.

## Bir şey ters giderse

Programda hata görürsen **bana yazman yeterli** ("hata aldım" demek bile olur). Program klasörünü ben zaten görebiliyorum:
`kayit.log` (ne olduğunun kaydı), `isler\...\rapor.json` (elenen sahneler, video kontrol sonuçları), üretilen fotoğraflar ve videolar.
Dosya göndermene, zip indirmene gerek yok. Düzeltmeyi doğrudan klasördeki dosyalara yazarım; sen **programın siyah penceresini kapatıp `baslat.bat` ile yeniden açarsın**, hepsi bu.

Not: Anahtarlar yalnızca `ayarlar.json` içinde durur. Ben o dosyayı açmam ve değiştirmem; tasarım dosyanı da (`tasarim.*`) okumam.
Arayüzdeki **“Hata raporu hazırla”** düğmesi hâlâ var, ama artık zorunlu değil.

## Dosyalar nerede?

| Ne | Nerede |
|---|---|
| Üretilen fotoğraflar ve videolar | `isler\<tarih_isim>\foto` ve `video` |
| Elenen sahnelerin nedeni | iş klasöründeki `rapor.json` ve arayüzdeki “sahne elendi” listesi |
| Hata raporları | `raporlar` klasörü |
| Ayarlar ve anahtarlar | `ayarlar.json` (başkasına gönderme) |

## Önemli notlar

- **Gerçek servis bağlantıları henüz hiç gerçek anahtarla denenmedi.** Magnific bağlantısı resmi dokümandan, OpenAI ve Gemini bağlantıları bilinen arayüzlerinden yazıldı. İlk gerçek çalıştırmada küçük bir uyum hatası çıkabilir; rapor düğmesiyle bana gönder, düzelteyim.
- Video kalite kontrolü “geçmedi” derse videoyu mutlaka kendin izle.
- Etsy ilanında yapay zekâyla hazırlanan sahneleri belirt ve fotoğrafların gerçek ürünü doğru gösterdiğinden emin ol (baskı rengi, kumaş, ölçü). İlk üründen önce bir örnek bas.
