# Görsel Kontrol ajanı (`visual-inspector`): değerlendirme düzeni

Tarih: 2026-10-13. Durum: **hazır, çalıştırılmadı.** Ücretli üretim yapılmadı; ajan henüz hiçbir örnekte çalıştırılmadı.

## 1. Ajanın görevi ve sınırları
- Tanım: `.claude/agents/visual-inspector.md` (kurulum kopyası `ajanlar_kurulum/visual-inspector.md`). Araçlar yalnız
  `Read, Glob` (salt okunur). Dosya yazma, kabuk komutu, sahne reddi, yeni üretim, prompt/kılavuz/ayar değişikliği YOK.
- Her örnekte AYRI bakar: `sahne.jpg` (görüntünün tamamı), `maske.png` (programın kumaş maskesi; "iddia" olarak),
  `ust.jpg` / `alt.jpg` (çubuk bandı ve etek/zemin yakın kesitleri), `bilgi.json` (ürün ölçüsü ve en/boy oranı,
  görüntü türü, değerlendirme sınırı). Programın kararı ve ret gerekçesi pakette YOKTUR.
- Kontroller: kumaş sınırı, maske uyumu, zemine temas, perspektif, baskı alanının açıklığı, göreli oran gözlemi.
  **Santimetre yazmaz** (çıktıda "cm" geçerse çıktı kural dışı sayılır).
- İki ayrı karar: **estetik** (kullanılabilir / sınırda / kullanılamaz) ve **yerleştirilebilir** (tasarım oranı
  korunarak, kırpmadan/esnetmeden/baskılı kısmı gizlemeden: evet / belirsiz / hayır).
- Sonuç: **Uygun / İnceleme gerekli / Uygun değil** + kısa gerekçe (görselde gösterilebilir kanıt) + belirsizlik +
  değerlendirme sınırı.

## 2. Örnek planı (`gorsel_kontrol/ornek_plani.json`)
| Bölüm | Örnekler | Kullanım |
|---|---|---|
| **Rehber (öğretim)** — 8 | 5 sentetik (geometrisi kesin bilinen: dokunan, birikmeli, havada, geniş 0,46, dar/uzun) + 3 gerçek (005509: #13 geniş, #4 maske taşması, s02 kabul) | Açıklamalı; ajan okur. **Başarı ölçümünde kullanılmaz.** |
| **Değerlendirme (kör)** — 30 | 005509'dan kalan 11 (c1,2,3,5,6,8,9,10,12,14, s01) · 224824'ten 6 · 003750 baby-shower'dan 13 | Ajan cevapları görmez; cevap anahtarı `cevaplar_GIZLI/anahtar.json` (git'e girmez). |
| **Hariç** — 3 | 003750 c9 (algılama katmanı tüm kadrajı kaplıyor; sahne kurtarılamıyor), 165800 s01/s02 (ürün ölçüsü kayıtlı değil) | Gerekçesiyle dışarıda. |

Rehber ile değerlendirme kümeleri çakışmaz (testle denetlenir: `tests/test_gorsel_kontrol.py`).

**Değerlendirmenin sınırları (açıkça):**
- 30 örneğin **26'sı yaklaşık görüntü** (eski kaydın yeşil/kırmızı algılama katmanından hesaplandı; ham DEĞİL),
  1'i katmansız ama JPEG kayıplı, yalnız **3'ü ham**. Yaklaşık görüntüde maske kenarı çevresindeki renk ve ince
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
- **Bağımsız değil:** ajan programın ret gerekçesini kelimesi kelimesine tekrar ediyorsa ya da programın kararına/iç
  terimlerine atıf yapıyorsa ("program reddetmiş olmalı", `sahne_geometri` ...). Bu çıktılar bağımsız inceleme sayılmaz.
- Kural dışı çıktı: eksik alan, geçersiz karar, santimetre iddiası, görüntü türünü yanlış bildirme.
Ajanın hiçbir sonucu otomatik ret, yeni üretim ya da prompt değişikliği tetiklemez.

## 4. Çalıştırma ve maliyet (ÇALIŞTIRILMADI)
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

**Önerilen (ileride, ücretli, kullanıcı onayıyla) karşılaştırma:** aynı kategori, model, referans ve ayarlarla 2A ve
3B-aday için en az 12'şer çağrı (K-28/K-34 ölçütleri). Başarı: program kabul oranı + Görsel Kontrol ajanının
"yerleştirilebilir" kararı + kullanıcı beğenisi birlikte; tek başarı yetmez.
