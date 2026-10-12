# Proje durumu

Bu dosya her aşamanın sonunda güncellenir. Claude ve Codex aynı klasörü okur; bir aşamaya başlamadan önce
buradan başlayın. Gizli bilgi (anahtar, `ayarlar.json` içeriği, gizli bağlantı, base64 görsel) bu dosyaya yazılmaz.
Kararların gerekçeleri: `docs/kararlar.md`. Gereksinimler: `CLAUDE.md`.

**Son güncelleme:** 2026-10-13 00:35 (Claude) · **Mevcut aşama:** Aşama 2A + kopma düzeltmesi + düzlem (tek homografi)
yerleşim kuralı + uygulama akışında doğrulama tamamlandı. Sıradaki: Aşama 2B (6 sahne görevi + açılı görünüm + eksikleri
tamamla) — BAŞLAMADI (kullanıcı onayı bekleniyor). Video aşamasına başlanmadı.

---

## 0a. Son iş: düzlem yerleşim kuralı ve uygulama akışında doğrulama (2026-10-13)

**Gereksinim (kullanıcı, 2026-10-13):** öncelik tasarımın bütünlüğü. Tasarım kumaşın her dalgasını izlemez; önden oran ve
iç düzen korunarak, açılıda tamamına tek perspektifle yerleşir; satır satır kenar ve ışık gradyanı iç geometriyi bozmaz;
güçlü kıvrımda sahne uygunsuz. → `CLAUDE.md` §1, `docs/kararlar.md` K-23, K-24.

**Mevcut düzeltmenin (K-18/K-19) bu kurala uyumu:** *kısmen*. Kopmaları ve çift konturu gidermişti, ışık gradyanını
kapatmıştı (K-19 kurala tam uyuyor). Ama tasarım hâlâ yumuşatılmış kumaş kenarını satır satır izliyordu; kenar eğrildikçe
tasarımın iç geometrisi de bükülüyordu (dalgalı kenarlı test sahnesinde tasarımdaki düz çizgi %1,2 dalgada 1,7 px,
%3 dalgada 4,2 px bükülüyordu). Bu yüzden yerleşim **tek homografiye** çevrildi (K-23): aynı sahnelerde bükülme 0,00 px.

**Uygulamada yapılanlar:**
- `compositor.py`: tam kumaşta kenarlara sağlam düz doğrular + üst kenar + temas çizgisi → tek dörtgen → tek homografi.
  Sığma denetimi: kumaş dışına düşen baskı ve kenar sapması (K-24). Rapor alanları: `yerlesim_donusumu`, `dortgen`,
  `kenar_sapmasi`, `kumas_disi_baski`.
- `orchestrator.py`: "Kayıtlı sahnelerden yeniden birleştir" (`recompose_from_scenes`, K-21/K-22). Yeni üretim ve yeniden
  birleştirme aynı ortak fonksiyonları kullanır (`_evaluate_scene`, `_save_accepted`).
- `app.py` (`POST /api/yeniden_birlestir`), `ui.html` (sonuç ekranında düğme + başlıkta kaynak iş ve "servis çağrısı: 0").
- `product.py`: `sahne_kivrim` hata türü.
- Testler: `tests/test_duzlem_yerlesim.py` (yeni), `tests/test_yeniden_birlestir.py` (yeni).

**Sonuç nerede:** bilgisayarda `isler/20261013-001355_yeniden_20261012-224824/` (foto/01_kumas.jpg, foto/02_kumas.jpg,
foto/_ozet.jpg, onizleme/01_gizli.jpg, rapor.json). Kaynak iş `isler/20261012-224824_20261012-224717_design` değişmedi
(işlem öncesi/sonrası tüm dosyaların md5'i aynı). Önceki karşılaştırma klasörü: `karsilastirma/20261012-224824_kopma/`.

**Uygulamada açmak:** `baslat.bat` → "3 Sonuçlar" kartında "Önceki işler" listesinden
`20261013-001355_yeniden_20261012-224824` seç. Başlıkta "kayıtlı sahnelerden yeniden birleştirildi (kaynak: …; servis
çağrısı: 0)" yazar. Başka bir iş için: o işi seç → "Kayıtlı sahnelerden yeniden birleştir" düğmesi (ücretsiz).

**Sağlayıcı çağrısı:** YOK. Uygulama sunucusu sahne/video sağlayıcı fabrikaları çağrılırsa hata verecek şekilde kilitli
çalıştırıldı → 0 çağrı; ayarlarda anahtar yok; rapor `saglayici_cagrisi: 0`, `cagri: 0`; servis karnesine kayıt yok.

**Doğrulama (bulut çalışma alanı, Linux, Python 3.13; kayıtlı GERÇEK sahneler, sahte servis yok):**
- Tarayıcıda (headless Chromium) uygulama arayüzünden: iş seçildi → düğme → 2/2 fotoğraf, yeni iş ekranda açıldı,
  JavaScript hatası yok.
- Ürün profili 75×200, tasarım kontrolü uyumlu (3000×8000 şeffaf PNG), çıktılar 2400×2400 kare, `yerlesim_donusumu:
  homografi`, kıvrım kayması 0. Yerleşim: asılı 177,7 / 201,4 cm, gizli 22,3 / 0 cm, 11,702 / 9,567 px/cm (kaynakla aynı).
- Sığma: 01 kenar sapması %3,9 (uyarı, kabul), kumaş dışı baskı %0,006; 02 %3,0, kumaş dışı baskı 0.
- Gözle (kaydedilen JPEG'lerden yakın görünüm): Candy's y kuyruğu, BABY SHOWER, WELCOME TO ve iki ayıcık çizgileri
  kesintisiz ve düz; kumaş dokusu ve ışık baskıda görünüyor; 01'de etek zeminde birikiyor (alt ≈22 cm, tasarımda boş),
  02'de etek zemine değiyor.
- `test_duzlem_yerlesim`: TAMAM (dalgalı kenarda düz çizgi artığı 0,49 px ve model bükülmesi 0,000 px; önden yatay/dikey
  ölçek 5,933 / 5,985 px/cm; açılıda tek homografiden sapma 0,0001; ortada katlanma ve güçlü kenar dalgası → `sahne_kivrim`).
  Eski (K-18) kodla anlamlı biçimde BAŞARISIZ: "iç geometri kenar dalgasıyla bükülüyor: 1,67 px".
- `test_yeniden_birlestir`: TAMAM.
- **Tam test takımı (düzlem yerleşimle, bulut/Linux):** 16 test dosyasının hepsi TAMAM (`test_video_repair` hatasız
  bitti, sonunda TAMAM yazmıyor), `kontrol.py` "HER ŞEY TAMAM".

**Windows:** Testler bilgisayarındaki Windows ortamında ÇALIŞTIRILMADI — bu oturumda bilgisayarda komut çalıştırma aracı
yok. Yukarıdaki sonuçların hepsi bulut çalışma alanına aittir.

## 0. Son iş: baskıdaki kopmaların kök nedeni ve düzeltmesi (2026-10-12 gece)

**Gözlem (kullanıcı + Codex):** iş `isler/20261012-224824_20261012-224717_design`; 02'de "Candy's" y kuyruğu ve BABY SHOWER
üstlerinde, 01'de WELCOME, ayıcık ve alt BABY'de yatay kopmalar. Kaynak PNG'de yok.

**Yöntem:** kayıtlı boş sahne + aynı tasarım; her seferinde tek değişken (V0 mevcut, V1 fold_shift=0, V2 kenarlar düz,
V3 kurdele geri koyma yok). V0 orijinal fotoğrafı yeniden üretti (ortalama fark 0,55 / 0,77 = JPEG düzeyi).
Sonuçlar ve yakın görünümler: bilgisayarda `karsilastirma/20261012-224824_kopma/` (README.md içinde tablo).

**Kanıtlanan neden:**
1. *Ana neden* — satır bazlı kumaş kenarı (K-18): yalnız kenar düzgünleştirmek bütün kopmaları kaldırdı; satır ikinci
   farkı 428 → 0,6 px (s01), 248 → 0,8 px (s02). fold_shift=0 kopmaları kaldırmadı.
2. *İkincil neden* — ışık gradyanından kıvrım kayması (K-19): s01'de 1688 katlanan piksel (W/O çift kontur); fold 0 → 0.
3. Kurdele geri koyma: etkisiz (0 piksel fark).

**Düzeltme** (`compositor.py`, yalnız tam kumaş yolu): kenarlar yumuşak eğri; tam kumaşta kıvrım kayması 0. Yerleşim
koordinatları değişmedi (asılı boy, gizli bölge, cm ölçeği rapordakiyle aynı; dikey koordinat farkı 0). Işık ve doku
çarpma modeliyle korunuyor. Eski yol değişmedi. Gerçek iki sahnede önce/sonra gözle incelendi: kopmalar ve çift kontur yok.
Orijinal iş klasörüne dokunulmadı; düzeltilmiş görseller yalnız karşılaştırma klasöründe.

**Yeni regresyon testi:** `tests/test_sureklilik.py` (K-20) — düzeltilmiş kodla TAMAM; eski kodla, yalnız ham kenarla ve
yalnız kıvrım kaymasıyla ayrı ayrı BAŞARISIZ.

**Tam test takımı (düzeltme sonrası, Linux/Python 3.13):** 14 test dosyasının hepsi TAMAM (`test_video_repair` hatasız
bitti), `kontrol.py` "HER ŞEY TAMAM". Windows'ta çalıştırılmadı. Gerçek sağlayıcı çağrısı yapılmadı.

---

## 1. Tamamlanan işler ve değiştirilen dosyalar

### Aşama 2A — Ürün profili, tam kumaş yerleşimi, kare fotoğraf (2026-10-12)

| Dosya | Değişiklik | Neden / yapan |
|---|---|---|
| `product.py` (yeni) | `UrunProfili` (ölçü kimliği + cm, tam kumaş modu, malzeme, sergileme, görünür fiyonk, fiziksel bağlantı; bilinmeyenler None), `OLCULER`, `HATA_TURLERI`, `tasarim_kontrol()` (boyut, oran, şeffaflık, dpi, yön, karşılık gelen boy), `oran_onizleme()`, `gizli_bolge_onizleme()`, `murekkep_orani()` | Ölçü PNG'den tahmin edilmesin; uyuşmazlık açıkça gösterilsin — ana oturum |
| `compositor.py` | Yeni `composite(..., mode="tam_kumas", profile=...)`: gerçek kenarlar (kenar payı / içeri alma / kırpma / ortalama yok), fiziksel dikey ölçek, zemine temas çizgisi, yerde kalan gizli bölge, `sahne_geometri` ve `birikme_cozulemedi` sorunları. Eski yollar (mode=None) video ve eski işler için aynen duruyor | Tam kumaş modu — image-engineer; dikey ölçek politikası (sıkıştırma yok) bağımsız inceleme sonrası ana oturum |
| `orchestrator.py` | `new_job(..., profile)` ve `generate_photos(..., profile)`: profil ve tasarım kontrolü rapora; oran uyuşmazsa `onizleme_oran.png` + `durum: beklemede` + hiç sağlayıcı çağrısı yok; kadraj sabit 1:1; algılama kumaş zorunlu; `proportion.widen` kapalı; elenenlerde `tur`; dosya adı `NN_kumas.jpg`; elenen dosyaları üzerine yazmıyor; gizli bölge önizlemesi `onizleme/NN_gizli.jpg`; video tam kumaş fotoğrafında aynı yerleşimi ve fotoğrafın kendi ölçüsünü kullanıyor | image-engineer; hata türü ayrımı ve video ölçüsü ana oturum |
| `prompts.py` | `build_scene_prompt(..., profile=)`: ölçü profilden ("exactly 75 cm wide and 200 cm long"), kare kamera metni (ürün + stand tamamen görünür), uydurulmuş "20–30 cm" ifadesi kaldırıldı (yalnız profilsiz eski yolda duruyor), kuşgözü cümlesi kaldırıldı, renk seçilmese de kurdele fiyonku | Ana oturum |
| `guide.py` | Kare kılavuz; stand ve kumaş tamamen görünür; kuşgözü yok; fiyonk her zaman | image-engineer |
| `mock_provider.py` | Kare sahne; afiş oranı prompt'taki cm ölçüsünden; yeni sahte servisler `mock_touch`, `mock_pool`, `mock_air`, `mock_long` | image-engineer |
| `providers.py`, `selector.py` | `Settings.ornek_olcu = "75x200"` (geçersizse düzeltilir); yeni sahte servis adları | Ana oturum |
| `app.py` | `/api/tasarim_kontrol`, `/api/tasarim_onizleme`; yüklemede kontrol; `start_photos` ölçü alır, uyumsuz tasarımda iş açmadan 400 döner; iş bilgisinde profil/kontrol/durum/gizli önizleme | Ana oturum |
| `ui.html` | 1. adımda "Görsellerde gösterilecek ölçü" seçimi, oran uyarısı + taralı önizleme, uyumsuzsa üretim düğmesi bekletir; sonuçta "Kumaş (tam tuval)", "gizli kısım" düğmesi, bekletme mesajı, elenen nedenin türü; kare küçük resimler | Ana oturum |
| `tests/test_product.py`, `tests/test_tam_kumas.py`, `tests/test_kare_kadraj.py` (yeni) | Aşağıda | — |
| `tests/test_e2e_mock.py`, `tests/test_unicode_path.py` | Tam oranlı test tasarımı kullanıyor (75×200'e uymayan `design_candy.jpg` artık bekletiliyor); "oran düzeltme" bölümü "kapalı" olarak tersine çevrildi | image-engineer (gerekçeli; beklentiler silinmedi) |
| `CLAUDE.md`, `docs/kararlar.md` (K-10…K-17), `docs/roadmap.md`, bu dosya | Kesinleşen gereksinimler; eski "baskı alanına sığdır" kuralının yerine "bekletme" geçti | Ana oturum |

**Dokunulmayanlar:** `ayarlar.json`, `servis_karnesi.json`, `isler/` (eski işler), `yuklemeler/`, `referanslar/`,
`raporlar/`, `PROJE_NOTLARI.md`, `baslat.bat`, video modülleri (`video_*.py`, `camera_move.py`), `test_paketi.py`.

**Ajanlar:** Proje ajanları bu oturumda Claude Code tarafından **tanınmadı** (bilgisayarda `.claude\agents` klasörü yok:
`ajanlar_kurulum\ajanlari_kur.bat` henüz çalıştırılmamış). Hepsi **genel ajan** olarak, kendi tanım dosyaları ve
sınırlarıyla çalıştırıldı: architecture-reviewer (veri modeli incelemesi, 13 öneri — çoğu uygulandı), image-engineer
(yerleştirme, kare kadraj, sahte sahneler, orkestratör), quality-reviewer (bağımsız inceleme: koşullu onay; B1, B2, B4,
B8 düzeltildi). quality-reviewer bir kez yanlışlıkla zararsız bir kabuk komutu çalıştırdığını kendisi bildirdi.

### Aşama 1 — İnceleme ve temel (2026-10-12)
Selector çift sayım düzeltmesi (`selector.py`, `tests/test_selector.py`), `CLAUDE.md`, `docs/architecture.md`,
`docs/inceleme_2026-10-12.md`, `docs/roadmap.md`, `ajanlar_kurulum/`, `_yedek/` (kaynak zip + Git bundle).
Ayrıntı: `docs/kararlar.md` K-01…K-09.

## 2. Gerçekten çalıştırılan testler

Ortam: Claude'un bulut çalışma alanı, **Linux, Python 3.13**. **Windows'ta çalıştırılmadı** (bu oturumda bilgisayarda komut
çalıştırma aracı yok). Gerçek sağlayıcı (ücretli) testi **yapılmadı**.

| Test | Tür | Sonuç (2A son hâli) |
|---|---|---|
| `test_sureklilik` (yeni, kopma düzeltmesi) | Yerel | TAMAM — satır ikinci farkı maks 0,50 px, katlanma 0, ince çizgi merkez sıçraması maks 0,50 px, kopuk satır 0 |
| Gerçek iki sahnede yeniden üretim (iş 20261012-224824) | Yerel (kayıtlı sahne, ücretsiz) | V0 orijinali yeniden üretti; düzeltilmiş: satır ikinci farkı 0,47 / 0,31 px, katlanma 0 |
| `test_product` | Yerel | TAMAM |
| `test_tam_kumas` | Yerel | TAMAM — 8 işaret kumaşta beklenen yerde (sapma ≤ en %0,7 / boy %0,1); şeffaf alanda değişen piksel 0; "sert" görünen sahnede de tam kumaş; birikmeli sahnede temas ±1 px, alttaki baskılı bölge `birikme_cozulemedi`; uzun/havada sahne `sahne_geometri`; boyu %2 kısa sahnede tasarım sıkıştırılmıyor, %2 uzun sahnede uyarı veriliyor |
| `test_kare_kadraj` | Sahte servis | TAMAM — canlı ve kamera video ayarında kadraj 1:1; 50×100 ve 150×300 prompt'ları farklı; uyumsuz tasarımda sağlayıcı çağrısı 0, `onizleme_oran.png` var; havada biten kumaş `sahne_geometri` |
| `test_e2e_mock`, `test_unicode_path` | Sahte servis | TAMAM |
| `test_selector`, `test_camera_move`, `test_magnific_fix`, `test_refstore`, `test_topview` | Yerel | TAMAM |
| `test_video_composite`, `test_video_track` | Yerel | TAMAM |
| `test_video_repair` | Yerel | Hatasız bitti (çıkış 0; bu dosya sonunda TAMAM yazmıyor — Aşama 1'de de böyleydi) |
| `kontrol.py` | Yerel | HER ŞEY TAMAM |
| Arayüz (headless Chromium, sahte servis) | Sahte servis | `design_candy.jpg` → "Oran uyuşmuyor, üretim bekletiliyor" + önizleme, üretim başlamadı; tam oranlı 750×2000 PNG → 2/2 kare fotoğraf; JavaScript hatası yok |
| Yeni testlerin eski koda karşı başarısız olduğu | Yerel | Kanıtlandı (eski orkestratör/compositor ile ve tek tek geri alınan düzeltmelerle; dikey ölçek testi eski "temasa sığdır" davranışında başarısız) |

**Gözle incelenen örnekler** (bulut alanında `ornekler/`; bilgisayara `docs/ornekler_2A/` altında kopyalandı):
işaretli yerleşim (zemine değen / birikmeli), sahte iş özeti (4 kare fotoğraf), kare kılavuz, `design_candy.jpg` oran
önizlemesi, arayüzün oran uyarısı ve sonuç ekranı. Gözlem: işaretler beklenen artılarla çakışıyor; stand, fiyonklar ve
kumaşın tamamı karede; birikmede alt kısım basılmıyor.

## 3. Doğrulanmamış konular ve mevcut hatalar

### Doğrulanmamış
- **Gerçek sahneler:** tüm geometri testleri sentetik sahnelerle. Gerçek fotoğraf `scene.jpg` denemesinde yan dökümler
  genişliği (px/cm) şişirdi; 75×200 için asılı boy ≈170 cm ölçüldü ve sahne reddedildi. Eşikler (K-17) gerçek sahnelerle
  ayarlanmalı.
- Gerçek servislerin 1:1 çıktı verip vermediği ve yeni prompt'a (ölçü, kare, fiyonk, zemine değme) uyumu.
- Testlerin Windows'ta (`.venv`, Python 3.12) çalışması.
- Ajanların Claude Code'da tanınması (`ajanlari_kur.bat` çalıştırılmalı, ardından Claude Code yeniden açılmalı).

### Bilinen sınırlamalar / mevcut hatalar
| Konu | Ayrıntı |
|---|---|
| Kıvrım geometrisi | Tam kumaşta kıvrım kayması kapalı (K-19): baskı kumaş kıvrımında yana kaymıyor, yalnız ışık/gölge çarpma modeliyle geliyor. Güçlü kıvrımlarda baskı biraz "düz" görünebilir; güvenilir yöntem (ör. çok görüntüden derinlik ya da kenar eğrilerinden yüzey modeli) sonraki iş |
| Kurdelenin kenarı örtmesi | Kenar yumuşatıldığı için örtülen bölgedeki çentik de yumuşak izlenir; o satırlarda tasarım hafifçe daralabilir |
| Açılı ("hafif yandan") görünüm | Henüz yok; prompt ve kalite kapısı önden görünüm istiyor. Aşama 2B |
| Birikmenin yönü | Yalnız yana yayılan birikme tanınıyor; öne/arkaya katlanan birikme "uzun kumaş" sayılıp reddedilir (temkinli) |
| Zemin algılama yok | Ürünle orantılı küçük çizilmiş ve havada biten kumaş geometriyle anlaşılamaz |
| Kurdele kumaş kenarını örterse | O satırlarda tasarım örtülen kenara göre daralır |
| Üst kenar | Kumaş çubuğa sarılıyorsa (tünel/dikiş) görünen üst kenar tuvalin üstü sayılıyor |
| Açık renkli baskı | Gizli bölgede parlaklığı 0,85'in üstündeki baskı "baskısız" sayılır |
| Video (kapsam dışı) | Yapay zekâ videosu yazı onarımı yeni kare sahte sahnelerde "takipte sıçrama" eşiğinde (2,5 px) sınırda: image-engineer'ın çalıştırmasında 2/2 başarısız, ana oturumun son çalıştırmasında 1. denemede geçti → kararsız. `test_e2e_mock` bunu denetlemiyor. Kare fotoğraftan 9:16 video kırpması daha sık "sığmıyor" diyebilir |
| `test_paketi.py` | Hâlâ eski (profilsiz) prompt yolunu kullanıyor ("20–30 cm", 9:16 kılavuz) |
| Önceki işler | Eski işler eski yerleşimle duruyor; aynı işte yeni üretim yapılırsa eski ve yeni yerleşim karışır (arayüz her üretimde yeni iş açar) |

## 4. Kullanıcıdan beklenen yanıtlar

0. ~~Kopma düzeltmesinin onayı~~ — **yanıtlandı (2026-10-12):** Codex düzeltilmiş iki görselde kopmaların giderildiğini
   doğruladı. Yeni: düzlem yerleşimle uygulamada üretilen `isler/20261013-001355_yeniden_20261012-224824` işinin gözle onayı.

1. Windows'ta: `ajanlar_kurulum\ajanlari_kur.bat` ve şu testlerin sonucu (proje klasöründe, komut isteminde):
   `.venv\Scripts\python tests\test_sureklilik.py`, `.venv\Scripts\python tests\test_yeniden_birlestir.py`,
   `.venv\Scripts\python tests\test_tam_kumas.py`, `.venv\Scripts\python tests\test_kare_kadraj.py`,
   `.venv\Scripts\python tests\test_product.py`, `.venv\Scripts\python kontrol.py`.
2. **Doğru oranlı gerçek bir tasarım dosyası** (75×200 için en/boy 0,375; ör. 2953×7874 px ≈ 100 dpi). `design_candy.jpg`
   0,515 oranında olduğu için bekletiliyor.
3. "Hafif yandan" görünüm kaç derece, hangi yönden; üç ortamda aynı yön mü?
4. Düğün dışı kategoriler için 3 ortam + gün saati tablosu.
5. İki bilgi görseli: dosyalar nerede, kategoriye mi ürüne mi bağlı, kare mi?
6. Gerçek servisle küçük bir deneme (ör. 1 ürün, en fazla 4 sahne çağrısı) için onay — eşikleri gerçek sahnelerle ayarlamak için.

## 5. Sonraki önerilen adım

Uygulamada yeniden birleştirilen işin onayı (§4-0) ve mümkünse Windows test sonuçları (§4-1); ardından:

**Aşama 2B:** (a) gerçek servisle küçük kalibrasyon denemesi (onayla) ve eşiklerin ayarı; (b) `layout` önden/açılı
kontrol profilleri ve açılı görünümde tam kumaş yerleşimi (üst/alt kenar eğrisi); (c) 6 sahne görevi
(`rapor.json["gorevler"]`) ve "eksikleri tamamla" (arayüz düğmesi). Bilgi görselleri paketi ve video sonraki turlara.
Ayrıntı: `docs/roadmap.md` §2.1.
