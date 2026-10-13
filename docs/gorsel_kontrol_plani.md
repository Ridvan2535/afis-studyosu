# Görsel Kontrol ajanı (`visual-inspector`): değerlendirme düzeni

Tarih: 2026-10-13. Durum: **ilk 8 örnek değerlendirildi** (visual-inspector talimatlı genel amaçlı alt ajanla; sonuç: `gorsel_kontrol/sonuclar/ilk_deneme_20261013/RAPOR.md`). 30 örnek çalıştırılmadı.

(Önceki durum:) **hazır, çalıştırılmadı.** Ücretli üretim yapılmadı;
ajan henüz hiçbir örnekte çalıştırılmadı.

**Kurulum durumu (açıkça):**
- Senin bilgisayarında: **kurulu DEĞİL.** `.claude\agents\` klasörü yok; tanım yalnız `ajanlar_kurulum\visual-inspector.md`
  olarak duruyor. Kurmak için `ajanlar_kurulum\ajanlari_kur.bat` çalıştırılır ve Claude Code yeniden açılır.
- Bu bulut oturumunun kod kopyasında: `.claude/agents/visual-inspector.md` dosyası var ama oturum açıldıktan sonra
  eklendiği için bu oturumda çağrılabilir ajan olarak **yüklü değil** (yeni oturumda tanınır).
- İlk çalıştırma yapılırsa bu iki yoldan biriyle olur; ikisi de senin onayını bekliyor.

## 1. Ajanın görevi ve sınırları
- Tanım: `.claude/agents/visual-inspector.md` (kurulum kopyası `ajanlar_kurulum/visual-inspector.md`). Araçlar yalnız
  `Read, Glob` (salt okunur). Dosya yazma, kabuk komutu, sahne reddi, yeni üretim, prompt/kılavuz/ayar değişikliği YOK.
- Her örnekte AYRI bakar: `sahne.jpg` (görüntünün tamamı), `maske.png` (programın kumaş maskesi; "iddia" olarak),
  `ust.jpg` / `alt.jpg` (çubuk bandı ve etek/zemin yakın kesitleri), `bilgi.json` (ürün ölçüsü ve en/boy oranı,
  görüntü türü, değerlendirme sınırı). Programın kararı ve ret gerekçesi pakette YOKTUR.
- Kontroller: kumaş sınırı, maske uyumu, zemine temas, perspektif, baskı alanının açıklığı, göreli oran gözlemi.
- **Hafif yan açı tek başına uygunsuzluk nedeni değildir** (plan: 3 ortam × önden + hafif yandan). Kumaş tek düz yüzey
  gibi duruyor, dört kenarı görünüyor ve baskı alanı kapanmıyorsa tasarım tek perspektif dönüşümüyle bütün kalır →
  açılı sahne uygun olabilir. Sorun sayılan: kenarı görünmeyecek kadar güçlü açı, tasarımı bölecek güçlü kıvrım.
  Not: programın bugünkü kalite kapısı (`strict_layout`) yan açılı afişi hâlâ reddeder; bu Aşama 2B'deki açılı kontrol
  profiliyle ele alınacak. O zamana kadar açılı bir sahnede program ret / ajan uygun derse örnek kullanıcı incelemesine düşer.
  **Santimetre yazmaz** (çıktıda "cm" geçerse çıktı kural dışı sayılır).
- İki ayrı karar: **estetik** (kullanılabilir / sınırda / kullanılamaz) ve **yerleştirilebilir** (tasarım oranı
  korunarak, kırpmadan/esnetmeden/baskılı kısmı gizlemeden: evet / belirsiz / hayır).
- Sonuç: **Uygun / İnceleme gerekli / Uygun değil** + kısa gerekçe (görselde gösterilebilir kanıt) + belirsizlik +
  değerlendirme sınırı.

## 2. Örnek planı (`gorsel_kontrol/ornek_plani.json`)
| Bölüm | Örnekler | Kullanım |
|---|---|---|
| **Rehber (öğretim)** — 9 | 6 sentetik (geometrisi kesin bilinen: dokunan, birikmeli, havada, geniş 0,46, dar/uzun, hafif yan açı) + 3 gerçek (005509: #13 geniş, #4 maske taşması, s02 kabul) | Açıklamalı; ajan okur. **Başarı ölçümünde kullanılmaz.** |
| **Değerlendirme (kör)** — 30 | 005509'dan kalan 11 (c1,2,3,5,6,8,9,10,12,14, s01) · 224824'ten 6 · 003750 baby-shower'dan 13 | Ajan cevapları görmez; cevap anahtarı `cevaplar_GIZLI/anahtar.json` (git'e girmez). |
| **Hariç** — 3 | 003750 c9 (algılama katmanı tüm kadrajı kaplıyor; sahne kurtarılamıyor), 165800 s01/s02 (ürün ölçüsü kayıtlı değil) | Gerekçesiyle dışarıda. |

Rehber ile değerlendirme kümeleri çakışmaz (testle denetlenir: `tests/test_gorsel_kontrol.py`).

**Değerlendirmenin sınırları (açıkça):**
- 30 örneğin **27'si yaklaşık görüntü** (eski kaydın yeşil/kırmızı algılama katmanından hesaplandı; ham DEĞİL),
  yalnız **3'ü ham**. Yaklaşık görüntüde maske kenarı çevresindeki renk ve ince
  ayrıntı güvenilmez; ajan bu örneklerde kenara dayanan kararları "İnceleme gerekli"ye bırakmalı.
- Yaklaşık görüntülerde maske, katmandan çıkarılan **o üretimdeki** program maskesidir; birkaç örnekte (ör. 003750
  c3, c7, c11) maske küçük/parçalı çıkıyor — o üretimde program afişi bulamamış olabilir ya da çıkarım kısmi kalmış
  olabilir. Ajanın "maske sahneyle çelişiyor" demesi beklenir.
- **Doğru cevap yok.** Program kararı da kullanıcı etiketi de doğru cevap sayılmaz: kullanıcı etiketleri görsel
  beğenidir (yalnız 10 örnekte var), fiziksel ölçüm doğrulaması değildir. Tablo doğruluk yüzdesi değil, **uyuşma ve
  çelişki** gösterir.
- Tek ürün ölçüsü (75×200), üç iş, iki kategori: güvenilir bir başarı iddiası için yetersiz. Öneri: yeni üretimlerde ham
  görüntüler artık kaydediliyor; en az 30 **ham** değerlendirme örneği (≥3 kategori) birikince ikinci tur.

## 3. Değerlendirme tablosu (`gorsel_kontrol/karsilastir.py`)
Sütunlar: kod · grup · iş · örnek · görüntü türü · program (karar/otomatik kontrol) · insan etiketi · ajan estetik ·
ajan yerleştirilebilir · ajan durum · ajan belirsizlik · çıktı hatası · çelişki · bağımsızlık · kullanıcı incelemesi.

Kullanıcı incelemesine ayrılanlar (`kullanici_incelemesi.md`):
- Ajan ile program anlaşmıyor (program reddetti / ajan uygun; program kabul etti / ajan uygun değil; program kesin hata /
  ajan katılmıyor), ajan ile insan etiketi çelişiyor, ajan "İnceleme gerekli" diyor.
- **Bağımsızlık ihlali (yalnız AÇIK ATIF):** ajan programın kararına, gerekçesine ya da iç kodlarına doğrudan gönderme
  yapıyorsa ("program bunu reddetmiş olmalı", "sahne elenmiş", "programın kararı", `sahne_geometri`...). Ajan bunları
  bilemez; bu çıktı bağımsız inceleme sayılmaz.
- **Benzer ifade (ihlal DEĞİL, yalnız inceleme işareti):** ajanın metni program gerekçesiyle 4 kelimelik ortak ifade
  içeriyorsa. Sahneyi doğru gören biri doğal olarak benzer kelimeler kullanır ("asılı kısım", "zemine değmiyor");
  bu tek başına bağımsız olmadığını kanıtlamaz.
- Ham ve yaklaşık görüntülü örnekler tabloda ve `kullanici_incelemesi.md`'de **ayrı bölümlerde** raporlanır.
- Kural dışı çıktı: eksik alan, geçersiz karar, santimetre iddiası, görüntü türünü yanlış bildirme.
Ajanın hiçbir sonucu otomatik ret, yeni üretim ya da prompt değişikliği tetiklemez.

## 4a. İlk küçük deneme (önerilen ilk çalıştırma; ÇALIŞTIRILMADI)
Amaç doğruluk yüzdesi değil: ajanın belirgin sorunları ve belirsizliği yararlı biçimde ayırıp ayıramadığını görmek.
Rehberle çakışmaz; ham örnekler önce, yaklaşık örnekler ayrı raporlanır. Liste: `ornek_plani.json → ilk_deneme`.

| # | İş | Örnek | Görüntü | Neden seçildi |
|---|---|---|---|---|
| 1 | 224824 | s01 | ham | program kabul etti (farklı iş) |
| 2 | 224824 | s02 | ham | program kabul etti (farklı iş) |
| 3 | 005509 | s01 | ham | program kabul etti ama ölçümü kararsız (A-01) |
| 4 | 003750 | c13 | yaklaşık | program kumaşı bulamadı ("bölge çok küçük"): sahne mi sorunlu, algılama mı? |
| 5 | 003750 | c3 | yaklaşık | program otomatik kesin hata ("çok dar ya da yan açılı"): açı kuralı |
| 6 | 003750 | c1 | yaklaşık | program "boş görünmüyor" dedi: baskı alanının açıklığı |
| 7 | 005509 | c6 | yaklaşık | kullanıcı "fazla geniş"; program inceleme gerekli |
| 8 | 005509 | c9 | yaklaşık | kullanıcı "kullanılabilir"; program oran farkıyla reddetti |

Yalnız 3 ham örnek var (eski işlerde elenenlerin ham görüntüsü kaydedilmemişti); yaklaşık örnekler ayrı yorumlanır.
Hazırlama: `python gorsel_kontrol/hazirla.py <isler> --kume ilk_deneme --cikti gorsel_kontrol/ilk_deneme`.
Tahmini kullanım: 1 ajan çalıştırması, ≈ 60.000 girdi (rehber dahil) + ≈ 4.000 çıktı jetonu; Claude Code alt ajanı olarak
ayrı ücret yok (plan kullanımı). API ile yapılsaydı kabaca Sonnet 5.5 ≈ 0,16 $, Opus 5.5 ≈ 0,32 $.

## 4. Çalıştırma ve maliyet — 30 örnek (ERTELENDİ; ilk denemeden sonra)
```
python gorsel_kontrol/rehber_hazirla.py <isler_klasoru>      # rehber görselleri (sentetik + 3 gerçek)
python gorsel_kontrol/hazirla.py <isler_klasoru>             # kör paket + gizli anahtar
# ajan: gorsel_kontrol/paket/<kod>/ okunur, çıktı JSON'u ana oturum ajan_ciktilari/<kod>.json olarak kaydeder
python gorsel_kontrol/karsilastir.py                         # tablo + kullanıcı incelemesi
```
- **Çağrı sayısı:** 3 ajan çalıştırması (her biri 10 değerlendirme örneği; her çalıştırmada rehber bir kez okunur).
- **Tahmini girdi:** örnek başına ~7.500 görsel+metin jetonu (sahne ≤1904 px ≈ 4.600, maske ≈ 1.300, iki kesit ≈ 1.000,
  bilgi ~300); rehber ~47.000 jeton/çalıştırma. Toplam ≈ 380.000 girdi + ≈ 15.000 çıktı jetonu.
- **Ücret:** Claude Code içinde alt ajan olarak çalıştırılırsa ayrı bir çağrı ücreti yoktur; kullanım Claude planından
  düşer. Aynı iş uygulamaya API ile bağlanırsa (yapılmadı) kabaca: Claude Sonnet 5.5 ile ≈ 0,9 $, Claude Opus 5.5 ile
  ≈ 1,8 $ (2026-10-13'te resmî fiyat sayfası: girdi/çıktı milyon jeton başına Sonnet 5.5 2 $/10 $, Opus 5.5 4 $/20 $).
  Magnific/sahne üretim çağrısı YOKTUR.

## 5. Ayrı izlenen algılama sorunu: A-01 küçültmede karar değişiyor
`tests/izle_kucultme_kararliligi.py` (izleme; başarısız olmaz). 2026-10-13 sonucu: kabul edilen s01 2000/1600 px'te ret
(208 cm), s02 1536/1280 px'te ret (156 cm). Kök neden K-37'de (temas satırı birikme yayılmasının başlangıcından
aranıyor). Ajan değerlendirmesi bu sorunu düzeltmez; ajan paketindeki sahneler 1904 px'e küçültüldüğü için ajanın
gördüğü görüntü programın ölçtüğüyle aynı çözünürlükte değildir — bu yüzden ajandan cm/oran ölçümü değil, göreli gözlem
istenir.

## 6. Oranı üretimde doğru kurmak: kısa prompt adayı + kılavuz önerisi (ücretli test YOK)
Kullanıcı kararı (2026-10-13): ana çözüm üretimde oranı prompt ve kılavuzla doğru kurmak; tasarım kırpılmaz, esnetilmez,
baskılı kısmı gizlenerek otomatik uyarlanmaz.

Gözlem: elenen sahnelerin çoğunda kumaş stand açıklığını dolduracak kadar geniş çizilmiş (ölçülen en/boy 0,40–0,46,
ürün 0,375); kılavuz v1'de dikmeler afişten kadraj eninin %5'i kadar uzakta ve kurdele kuyrukları bu boşlukta.
Hipotez (kanıtlanmadı): model dikmeler arasındaki boşluğu kumaşla dolduruyor.

**Kılavuz v2 (aday, `guide.py surum=2`):** aynı afiş dikdörtgeni (oran tam 0,375; yüksekliğin ~%75'i, genişliğin ~%28'i),
dikmeler afişe yakın (%1,2), kuyruklar dikmelerin DIŞINDA, afişin arkasında koyu düz zemin (kenar karşıtlığı), etekte ince
temas gölgesi. Görsel: `gorsel_kontrol/kilavuz_v1_v2.jpg`.

**Prompt 3B-aday (kılavuz v2 ile):** 3A-aday'ın aynısı; cümle eklenmedi, iki cümle değiştirildi:
- kamera: "...about 75% of the image height but only about 28% of its width; the stand is barely wider than the banner."
- model (kılavuz varken): "Image 1 is a layout guide: the light rectangle is the banner's exact outline; keep its width
  and height, never widen it to the posts. Replace only the grey and dark placeholder areas with the scene."
- Ürün kuralları bölümü değişmedi (özet `a3fdb2051e51277e`). En uzun 3B prompt 308 kelime (sınır 330); model bölümü 45/45.
- Etkin değil; hiçbir kategoride seçili değil. Seçilirse çağrı kaydına `prompt_surumu=3B-aday`, `ayar_ozeti.kilavuz_surumu=2`
  yazılır; karşılaştırma yalnız aynı kılavuz sürümü/ölçü/referans/ayar koşullarında yapılır (K-32).

**İki deney türü (K-44)** — prompt dışındaki koşullar (kategori, model, ölçü, sahne görevi, referans kümesi, üretim
ayarları) her ikisinde de aynı olmalı:
- **Yalnız prompt:** kılavuz aynı. Ör. 2A + kılavuz 1 ↔ 3A-aday + kılavuz 1. Fark prompta bağlanabilir.
- **Prompt + kılavuz paketi:** iki bileşen birlikte değişir ve ikisi de kayıtlıdır (`prompt_surumu`, `kilavuz_surumu`).
  Ör. 2A + kılavuz 1 ↔ 3B-aday + kılavuz 2. Kılavuz farkı bu karşılaştırmayı geçersiz KILMAZ (önceki sürümde
  `ayar_ozeti` içindeki kılavuz sürümü farkı yüzünden "karşılaştırılamaz" çıkıyordu; düzeltildi). Sonuç paketin
  etkisidir; **promptun tek başına etkisi bu deneyden çıkarılamaz**. Öneri metni bunu açıkça yazar.
Ücretli deneme (ileride, kullanıcı onayıyla): her kol için en az 12 çağrı (K-28/K-34). Başarı: program kabul oranı +
Görsel Kontrol ajanının "yerleştirilebilir" kararı + kullanıcı beğenisi birlikte; tek başarı yetmez.
