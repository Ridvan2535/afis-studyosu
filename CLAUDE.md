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
  Tasarım sessizce esnetilmez veya kırpılmaz. Oran uyuşmazlığında tasarım oranı korunarak tanımlı baskı alanına
  sığdırılır ve bu önizlemede gösterilir.
- Tüm ürün sahneleri **kurdelelidir**; ilan görsellerinde tek örnek kurdele rengi yeterli. Mevcut renk ayarı korunur;
  sipariş seçeneği / renk seçme geliştirmesi şimdilik kapsam dışı.
- **Kuşgözü opsiyoneldir.** Sahnede kullanılan bağlantı biçimi ürün profilinde açıkça kaydedilir.
- **Stand pakete dahil değildir** (sahne dekorudur). Ürünün paket içeriği değiştirilmez.
- Belirsiz fiziksel ürün bilgisi (malzeme gramajı, kuşgözü sayısı/çapı, baskı payı vb.) **uydurulmaz**; "belirsiz"
  diye işaretlenip kullanıcıya sorulur.

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

## 5. Geliştirme aşamaları (ayrıntı: `docs/roadmap.md`)

- **Aşama 1 (tamamlandı, 2026-10-12):** mimari inceleme, ajanlar, bu dosya, `docs/`, Selector çift sayım düzeltmesi.
- **Aşama 2:** fotoğraf hattı — kare kadraj videodan bağımsız, ürün profili + baskı alanı, 6 sahne görevi,
  önden/açılı kontrol profilleri, kumaşta tutarlı yerleştirme, eksik görevleri tamamlama, bilgi görselleri pakete.
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
