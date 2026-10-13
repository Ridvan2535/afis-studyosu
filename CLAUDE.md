# Afiş Stüdyosu — Claude için proje talimatları

Bu dosya her Claude oturumunda okunur. **Güncel kullanıcı gereksinimleri buradadır.** `PROJE_NOTLARI.md` geçmiş
kararların günlüğüdür; onunla çelişen bir konu varsa bu dosya geçerlidir ve çelişki `docs/architecture.md`
"Gereksinim çelişkileri" bölümüne yazılır (notlar sessizce silinmez).

Kullanıcıyla Türkçe, anlaşılır ve somut konuş; ne yaptığını **ve neden** yaptığını anlat.

## 1. Ürün gereksinimleri

- Ürün: fiziksel, kişiselleştirilmiş **pamuk-keten kumaş afiş**.
- Tasarım girdisi PNG'dir ve yalnızca baskı tasarımını içerir. **Şeffaf alan = baskısız kumaş.**
- Yazı, isim, desen ve çizimler yapay zekâya **yeniden çizdirilmez**. Tasarım kodla, içeriği korunarak kumaşın
  perspektifine, kıvrımlarına ve ışığına uygulanır.
- Ölçü seçenekleri (cm, en × boy): **50×100, 50×150, 75×200, 150×300, 150×400**.
- **Fiziksel ürün ölçüsü, PNG oranı ve baskı alanı ayrı kavramlardır.** PNG oranından fiziksel ölçü çıkarılmaz.
  Aynı oranlı ölçüler (50×100 / 150×300, 75×200 / 150×400) ayrı kimliklerle seçilir.
- **İlan görsellerindeki örnek ölçü 75×200 cm**dir (Ayarlar: `ornek_olcu`); satış ölçüleri bundan ayrı tutulur.
- **Tam kumaş modu (2026-10-12'de kesinleşti):** PNG tuvali kumaşın TAMAMIDIR; PNG içindeki boşluklar yerleşimin
  parçasıdır. Otomatik kenar boşluğu, içeri küçültme, kırpma, ortalama veya oranı bozarak esnetme **yoktur**.
  Kumaşın perspektifi ve kıvrımı için gereken yüzey dönüşümü, kaynak oranı keyfî değiştirmekten ayrıdır.
- **Yerleştirme önceliği tasarımın bütünlüğüdür (2026-10-13, K-23):** PNG kumaşın her dalga/kıvrımını geometrik olarak
  izlemez. Tasarım BÜTÜN olarak tek düzlem dönüşümüyle yerleşir: önden görsellerde oranı ve iç düzeni korunarak
  (eşit yatay/dikey ölçek), açılı görsellerde tasarımın tamamına tek perspektif dönüşümü. Satır satır değişen kumaş
  kenarları ve ışık gradyanları tasarımın iç geometrisini bozamaz. Kumaşın ışığı, gölgesi ve dokusu baskıya çarpma
  modeliyle yansır. Baskı yüzeyi nispeten düz/hafif kıvrımlı sahneler tercih edilir; güçlü katlanma nedeniyle tasarım
  sığmıyorsa tasarım zorla deforme edilmez, sahne uygunsuz sayılır (`sahne_kivrim`).
- **Oran uyuşmazlığında** (PNG oranı ≠ kumaş oranı, tolerans %1): açık uyarı ve önizleme verilir, uyuşmazlık sessizce
  düzeltilmez ve o ürünün **nihai üretimi bekletilir** (hiç ücretli çağrı yapılmaz). *(Önceki "baskı alanına oranı
  koruyarak sığdır" kuralının yerine geçti; bkz. `docs/kararlar.md` K-10.)*
- PNG oran uyuşmazlığı ile **sahnenin ürün geometrisine uymaması** ayrı hata türleridir (`product.HATA_TURLERI`).
- Tüm ürün sahneleri **kurdelelidir**: kurdeleler ortama uygun **fiyonk** olarak görünür; ilan görsellerinde tek örnek
  kurdele rengi yeterli. Mevcut renk ayarı korunur; sipariş seçeneği / renk seçme geliştirmesi şimdilik kapsam dışı.
- **Kuşgözü opsiyonel ürün özelliğidir.** Görünür fiyonk ile fiziksel bağlantı bilgisi ürün profilinde ayrı tutulur.
  Kurdelenin kuşgözünden geçişinin görünmesi zorunlu değildir; görünmeyen bağlantı ayrıntısı kalite reddi nedeni olmaz.
- **Kumaşın altı zemine değer**, tercihen hafifçe birikir; havada bitmez. Birikme miktarı sabit uydurulmaz (kumaş boyu
  ölçünün boyudur, ör. 200 cm). Alt yazılar kıvrım/birikmede doğal olarak gizleniyorsa önizlemede gösterilir; yazı
  yapay olarak yukarı taşınmaz. Birikme doğru çizilemiyorsa sınır raporlanır, sonuç başarılı sayılmaz.
- **Fotoğraflar 1:1 karedir**; video ayarı fotoğraf kadrajını değiştiremez. Ürün ve stand kadrajda tamamen görünür.
  Video için 9:16 zorunluluğu konmaz (video oranı sonraki aşamada sağlayıcı desteğine göre belirlenir).
- **Stand pakete dahil değildir** (sahne dekorudur). Ürünün paket içeriği değiştirilmez.
- Belirsiz fiziksel ürün bilgisi (malzeme gramajı, karışım oranı, kuşgözü sayısı/çapı vb.) **uydurulmaz**; boş/None
  kalır. Bunlar bağımsız yazılım geliştirme adımlarını durdurmaz.
- Eski iş dosyaları ve çıktıları değiştirilmez.

### Ürün başına çıktı paketi
- **6 kare (1:1) ürün görseli:** 3 ortam × (önden + hafif yandan).
- **2 sabit bilgi görseli** (yeniden üretilmez; kare düzenleme gerekiyorsa ayrı işlem).
- **1 video**, seçilen tek sahneden, 4–8 sn. Fotoğraf başına otomatik ücretli video **yok**.
- İlk hedef: günde 5 yeni ürün.
- Örnek (Düğün): Kır düğünü/gündüz/önden + aynı ortam/hafif yandan; Salon düğünü/gündüz/önden + yandan;
  Bahçe düğünü/akşamüstü/önden + yandan. Diğer kategoriler aynı mantıkla.
- Ortam/açı değişse de ürün ölçüsü, kumaşı, baskı yerleşimi ve bağlantı özellikleri tutarlı kalır.
- Referans görseller stil/kompozisyon rehberidir; **rakip fotoğrafı teslim çıktısı olarak kullanılmaz.**

### Gelecek genişleme (şimdilik geliştirilmez)
Tişört, duvar saati, davetiye, menü. **Ürün türü ≠ etkinlik kategorisi.** İş takibi ve sağlayıcı bağlantıları ortak;
yüzeye tasarım uygulama motoru ürün türüne özel.

## 2. Dosya ve anahtar koruma kuralları

- **Dokunma / içeriğini yazdırma:** `ayarlar.json` (API anahtarları), `isler/` (iş çıktıları), `yuklemeler/`,
  `referanslar/`, `raporlar/*.zip` (içlerinde ayarlar kopyası var), `tasarim.*`, `servis_karnesi.json`
  (yalnız kod üzerinden okunur/yazılır), `.venv/`.
- Anahtarlar, ham ayar dosyası, gizli bağlantılar ve base64 görseller **konuşmaya, rapora, belgeye veya Git
  geçmişine yazılmaz.** `.gitignore` bunları dışarıda tutar.
- Değişiklikten önce geri alınabilir yedek: Git deposu varsa commit/kontrol noktası; yoksa `_yedek/` altına
  tarihli kaynak kod yedeği. Mevcut değişiklikler silinmez.
- Geliştirme ve doğrulamada **ücretli API çağrısı yapılmaz**; `mock_provider.py` ve yerel örnek görseller kullanılır.
- Gereksiz framework değişikliği yok (Python'un kendi `http.server` sunucusu `app.py` + tek sayfa `ui.html` +
  `baslat.bat` kalır; Flask'a vb. geçilmez). Mevcut arayüz ve
  başlatma biçimi çalışmaya devam etmeli.
- Rutin, geri alınabilir adımlar için her seferinde onay istenmez.

## 3. Ajan sorumlulukları (`.claude/agents/`)

| Ajan | Yetki | Sorumluluk |
|---|---|---|
| `architecture-reviewer` | Salt okunur (Read, Grep, Glob) | Mimari inceleme, bulgu doğrulama, gereksinim çelişkileri |
| `image-engineer` | Okuma + yazma + Bash | compositor, banner_detect, layout, proportion, ribbon, guide, cvio ve testleri |
| `provider-engineer` | Okuma + yazma + Bash | providers, selector, mock_provider, refstore, iş takibi/devam etme ve testleri |
| `quality-reviewer` | Salt okunur (Read, Grep, Glob) | Bağımsız diff ve test yeterliliği incelemesi |
| `visual-inspector` | Salt okunur (Read, Glob) | Görsel Kontrol: sahne + program maskesini ayrı inceler; estetik ve "oran korunarak yerleştirilebilir" kararını ayrı verir; yalnız öneri (ret/üretim/prompt yetkisi yok). `docs/gorsel_kontrol_plani.md` |

- Model seçimi oturumdan devralınır (`model: inherit`).
- **Aynı dosyayı iki ajan aynı anda değiştirmez.** `orchestrator.py`, `app.py`, `ui.html` ortak dosyalardır;
  bir aşamada tek sahibi olur (ana oturum atar).
- Testleri ana oturum veya ilgili uygulayıcı ajan çalıştırır; salt okunur ajanlar çalıştırmaz.
- Yeni/değişen ajan tanımları Claude Code oturumu yeniden açılınca tanınır.

## 4. Doğrulama yaklaşımı

- Testler: `python tests/test_<ad>.py` (pytest gerekmez; her dosya kendi kendine çalışır, sonunda `TAMAM` yazar).
  Windows'ta: `.venv\Scripts\python tests\test_selector.py`.
- Hata düzeltmesine **regresyon testi** eşlik eder ve test, düzeltme geri alınınca başarısız olmalıdır.
- "Test edildi" ifadesi her zaman üçe ayrılır:
  1. **Yerel test** (saf kod, ağsız),
  2. **Sahte servis testi** (`mock_provider` / taklit `requests`),
  3. **Gerçek sağlayıcı testi** (ücretli; yalnız kullanıcı onayıyla, model ve prompt sürümü kaydedilerek).
- Görsel değişikliklerde örnek çıktı (ör. `_ozet.jpg`) üretilip gözle kontrol edilir.
- Yerleştirme dönüşümü değişirse yalnız işaret merkezleri yetmez: `tests/test_sureklilik.py` (ince çizgi / harf
  sürekliliği, katlanma, satır sıçraması) geçmeli ve gerçek kayıtlı sahnelerde önce/sonra yakın görünüm incelenmeli.
- Işık gradyanı doğrudan kumaş geometrisi kabul edilmez (K-19).
- Algılama/yerleşim/kalite kapısı değişikliklerinde `tests/test_kontrol_ornekleri.py` geçmeli (iş 005509'un kalıcı
  kontrol örnekleri; kabuller kabul, fazla geniş 1/6/13 elenir, kullanılabilir etiketliler otomatik "kesin hata" olmaz).
  Kontrol sonuçları: Uygun / İnceleme gerekli / Kesin hata (K-35); insan etiketi otomatik kaydı değiştirmez (K-38).
- Yerleşim değişikliklerinde `tests/test_duzlem_yerlesim.py` geçmeli (dalgalı kenarda tasarım çizgileri düz, önden oran
  korunur, açılıda tek perspektif, güçlü kıvrımda `sahne_kivrim`).

## 5. Geliştirme aşamaları (ayrıntı: `docs/roadmap.md`)

- **Aşama 1 (tamamlandı, 2026-10-12):** mimari inceleme, ajanlar, bu dosya, `docs/`, Selector çift sayım düzeltmesi.
- **Aşama 2A (tamamlandı, 2026-10-12):** ürün profili (`product.py`), tasarım kontrolü + oran önizlemesi, tam kumaş
  yerleşimi, kare fotoğraf, arayüzde örnek ölçü seçimi ve oran uyarısı.
- **Aşama 2 (kalan):** fotoğraf hattı — 6 sahne görevi,
  önden/açılı kontrol profilleri (açılı görünümde tam kumaş yerleşimi), eksik görevleri tamamlama, bilgi görselleri pakete.
- **Aşama 3:** sahne kütüphanesi (onaylı sahneler, yeniden kullanım; sahne hazırlama ≠ günlük ürün hazırlama).
- **Aşama 4:** tek video (sabit kamera, hafif kurdele/ortam hareketi, kumaşla birlikte izleme).
- **Aşama 5:** sağlayıcı yaşam döngüsü sertleştirme (iş numarası, sorgulamadan yeniden üretim yok, sürüm kaydı).
- **Aşama 6:** ürün türü soyutlaması (tişört, saat, davetiye, menü).

### Aşama sonu belgeleri (zorunlu)
Proje Codex ile de inceleniyor; iki araç aynı klasörü okur. Her aşamanın sonunda:
- `docs/durum.md` güncellenir: tamamlanan işler ve değişen dosyalar, gerçekten çalıştırılan testler ve sonuçları
  (yerel / sahte servis / gerçek sağlayıcı ayrımıyla), doğrulanmamış konular ve mevcut hatalar, kullanıcıdan
  beklenen yanıtlar, sonraki önerilen adım.
- Önemli kararlar kısa gerekçeyle `docs/kararlar.md`'ye eklenir (eski kararlar silinmez).
- Bu dosyalara anahtar, ayar içeriği, gizli bağlantı veya base64 yazılmaz.

## 6. Video ve servis kuralları (sonraki aşamalar)

- Video bir adet; fotoğraf başına otomatik ücretli üretim yok.
- İlk video hedefi: sabit kamera, hafif kurdele ve ortam hareketi. Kumaş hareket ederse tasarım kumaşla izlenir.
- Yakınlaşma videosu, kurdele hareketli video şartının yerine **sessizce** kabul edilmez.
- Model ve prompt sürümleri kaydedilir; "en yeni model" diye üretim modeli sessizce değiştirilmez; model
  değişikliği örnek ürünlerle değerlendirilir.
- Hata sınıfları ayrılır: kota, kimlik doğrulama, geçersiz istek, geçici servis hatası, kalite reddi.
- Zaman aşımından sonra sağlayıcıdaki iş sorgulanmadan yeni üretim başlatılmaz; üretim POST'unda kör yeniden
  deneme yapılmaz (çift iş riski).
- Çağrı sayısı parasal maliyet gibi raporlanmaz.
- Uç nokta ve yetenekler entegrasyondan önce resmî belgelerden doğrulanır.
