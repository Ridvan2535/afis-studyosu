# placement-engineer raporu — G4 (Tur 1, 2026-10-13)

Not: Bu oturumda özel ajan türü yüklenemedi; koordinatör `.claude/agents/placement-engineer.md` tanımıyla **genel amaçlı ajan** çalıştırdı.
Ortam: Linux bulut, ağsız, ücretli çağrı yok. **Windows'ta çalıştırılmadı.**

## Değişen dosyalar
- **Hiçbir kaynak/test dosyası değişmedi.** `compositor.BIRIKME_BANT_EN_FAZLA = 0.15` (VARSAYIM, K-54) yerinde bırakıldı.
- Yalnız: bu rapor, `ekip/pano.md` G4 satırı (sürüyor → bitti).
- Analiz betiği ve ham sonuçlar yalnız oturum çalışma klasöründe (proje dışı): `g4_analiz.py`, `g4_sonuc.json` (81 satır).
  Eşik yalnız çalışma anında modül değişkeni olarak 99'a çekilip bant ölçüldü, ardından 0,15'e geri alındı (betik sonunda `assert`).

## Yöntem
Her görsel için `banner_detect.detect(img, {"kind":"fabric"})` → `compositor.fabric_geometry(det.mask, 75, 200, scene_bgr=img)`.
Bant = (etek ucu − yayılma başlangıcı) / (etek ucu − üst kenar). Bant yalnız iki yanlı kenar yayılması bulunan sahnelerde
tanımlıdır; `maske_alti` (yayılma yok) ve `tek_tarafli_yayilma` (taşma şüphesi) kararları eşikten **bağımsızdır**.
Eşik t için karar: bant ≤ t → `kenar_yayilmasi` (birikme), bant > t → `temas_belirsiz`.
Kaynaklar (salt okunur): `tests/kontrol_ornekleri/*/`, `isler/*/sahneler_bos/` (`s*.png`, `*_ham.jpg`, `elenen_*`),
`mock_provider.square_scene(1536, 75/200, "birikmeli", seed 0–5, pool_frac 0,05/0,10/0,15/0,20)` = 24 sentetik.

## Tablo 1 — bandı ölçülen (iki yanlı yayılmalı) sahneler

| Sahne | Kaynak türü | Etiket | Bant | Karar @%15 | asılı cm (yayılma temas) | asılı cm (etek ucu temas) |
|---|---|---|---|---|---|---|
| 224824 s01 (= kontrol kabul_s01_ham) | ham | **KABUL** | 0,034 | birikme | 177,8 | — |
| 005509 s01 (= kontrol kabul_s01_ham) | ham | **KABUL** | 0,042 | birikme | 199,7 | — |
| sentetik birikmeli ×24 (pf 0,05–0,20) | sentetik | gerçek birikme | 0,053–0,054 | birikme (24/24) | 160–190 | — |
| 005509 s02 (= kontrol kabul_s02_ham) | ham | **KABUL** | 0,080 | birikme | 197,1 | — |
| 005509 elenen_02 | **yaklaşık** (ham değil) | kullanıcı: kullanılabilir | 0,199 | temas_belirsiz | 149,1 | 186,1 |
| 053942 ham (= işteki elenen_01_01_ham) | ham | kullanıcı: kullanılabilir | 0,309 | temas_belirsiz | 139,5 | 201,9 |
| 165800 s01 (eski iş, kare değil) | ham | etiketsiz | 0,312 | temas_belirsiz | 99,8 | 145,0 |
| 005509 elenen_05 | **yaklaşık** | kullanıcı: kullanılabilir | 0,360 | temas_belirsiz | 110,7 | 173,0 |
| 165800 s02 (eski iş, kare değil) | ham | etiketsiz | 0,397 | temas_belirsiz | 89,6 | 148,6 |

**Ham değil — geçersiz (tabloya ve karar sayımlarına katılmadı; koordinatör düzeltmesi, G3'te `banner_detect.overlay` çıktısı olduğu
doğrulandı):** iş klasörlerindeki `elenen_NN_NN.jpg` (sonu `_ham` olmayanlar: 224824 ×4, 003750 ×14, 005509 ×12) ve
054333 `elenen_01_01_algilama.jpg`. Bunlar algılama maskesi (yeşil boya + mavi kenar) çizilmiş tanı görselleridir; üzerlerindeki
ölçüm anlamsızdır (ör. 003750 elenen_01_12'de çıkan 0,464 bant da geçersizdir).

Bandı OLMAYAN (eşikten bağımsız) sahneler:
- `maske_alti`: 224824 **s02 (KABUL)**, 054333 ham, 005509 yaklaşık 01/03/06/08/09/10/12/13/14 (01/06/13 kullanıcı: gerçekten hatalı; diğerleri kullanılabilir).
- `tek_tarafli_yayilma`: 005509 yaklaşık 04 (kullanılabilir).
- Ham değil / geçersiz dosyalar (yukarıdaki not) bu listeye de katılmadı.
- Kopyalar (md5 aynı): iş klasöründeki 005509 s01/s02 ≠ kontrol kopyasıyla dosya olarak farklı ama sonuçlar birebir aynı; 224824 s01/s02,
  053942 ve 054333 ham dosyaları kontrol örnekleriyle bayt düzeyinde aynı.

## Tablo 2 — eşik değişseydi hangi kararlar değişirdi (%15'e göre)

| Eşik | Değişen karar | Kabul edilen sahneler (005509 s01/s02, 224824 s01/s02) | Kullanıcı etiketliler |
|---|---|---|---|
| %10 | yok | değişmez (en büyük kabul bandı 0,080) | değişmez |
| %12 | yok | değişmez | değişmez |
| %15 (mevcut) | — | 3'ü birikme, 224824 s02 maske_alti | hepsi temas_belirsiz / eşikten bağımsız |
| %18 | yok | değişmez | değişmez |
| %20 | **005509 elenen_02_yaklasik**: temas_belirsiz → birikme (bant 0,1988) | değişmez | elenen_02 (kullanılabilir, YAKLAŞIK görsel) birikme sayılır ve temas boyun ≈%75'ine (149 cm) iner: ≈51 cm tasarım otomatik gizlenirdi |

## Sonuç
- **%15 savunulabilir; eşiğe DOKUNULMADI.** Kararlar %10–%18 aralığında hiçbir sahnede değişmiyor; ilk değişim %19,9'da ve o da
  ham olmayan (yaklaşık) bir görsel.
- **İki küme arasındaki boşluk:** birikme kümesi 0,034–0,080 (3 kabul ham + 24 sentetik); belirsiz küme ham sahnelerde 0,309–0,397,
  yaklaşık görseller dahil 0,199–0,360. Ham-yalnız boşluk 0,080 → 0,309; yaklaşık dahil 0,080 → 0,199. %15 bu boşluğun içinde
  (0,080 ile 0,199'un aritmetik ortası ≈0,14, geometrik ortası ≈0,126).
- **Fiziksel tutarlılık kanıtı (eşiği destekler):** düşük bantlı sahnelerde yayılma başlangıcını temas almak 178–200 cm asılı boy
  veriyor (75×200 ürünle uyumlu). Yüksek bantlılarda aynı kabul 90–149 cm verir (ürünün %45–75'i — 50–110 cm tasarım gizlenirdi);
  etek ucunu temas almak ise 145–202 cm veriyor (053942: 201,9 cm ≈ ürün boyu; kontrol notu da "yavaşça genişliyor, birikme değil" diyor).
  Yani yüksek bantlılar birikme değil, yavaş genişleme/perspektif.
- **%20'ye çıkarmaya karşı:** tek etkisi 005509 elenen_02'de ≈51 cm tasarımı otomatik gizlemek olur; K-54 "temas belirsizse otomatik
  gizleme yok" ilkesine aykırı. **%10'a indirmeye** gerek yok ama zararı da gözlenmedi (en yüksek kabul bandı 0,080; pay yalnız 0,02).
  Aşağı yönlü pay yukarı yönlüden darsa: kabul sahneleri ile %10 arasında 2 puan, %15 arasında 7 puan pay var — %15 kabul edilenleri
  korumak için daha güvenli.
- **Az örnek riski:** gerçek birikmeli ham sahne yalnız **3** (iki iş); belirsiz kümede ham **3** sahne (biri etiketli). Sentetik 24 sahne
  pool_frac'tan bağımsız olarak hep ≈%5,3 bant veriyor (mock'taki birikme biçimi sabit profil) — eşik sınırını hiç sınamıyor, yalnız
  "gerçek birikme düşük bant verir" iddiasını destekliyor. Sınırın %8–%20 arasında tam nerede olması gerektiğini bu veriyle
  belirlemek mümkün değil. Uzun, katmanlı birikme (ör. bandı %10–15 olan ama gerçekten yerde biriken) örneği yok; böyle bir sahne
  gelirse `temas_belirsiz` (inceleme gerekli) olur — güvenli tarafta hata (gizleme yok, kullanıcı inceler / manuel sınır, K-54).
- Öneri (uygulanmadı, bilgi): yeni ham birikmeli sahneler geldikçe bu analiz `g4_analiz.py` mantığıyla tekrar edilmeli; özellikle
  bandı 0,10–0,20 aralığına düşen ilk gerçek sahne kalıcı kontrol örneği yapılmalı. 224824 s01 birikme kararı verip asılı 177,8 cm
  ölçüyor (bilinen kararsız durum, kontrol.json'da not edilmiş) — eşikle ilgisi yok.

## Çalıştırılan testler (yerel, ağsız; Linux bulut — Windows'ta çalıştırılmadı)
Sırayla çalıştırıldı, kod değişikliği yok:

`python3 tests/test_tam_kumas.py` (18,7 sn) — son satırlar:
```
uzun: asılı ≈260 cm -> ['sahne_geometri']
havada: asılı ≈172 cm -> ['sahne_geometri']
asılı/ürün 0.98: dikey ölçek fiziksel, olcek_farki -0.0199, uyarı: ['Kumaşın görünen boyu ürün boyundan ≈4 cm kısa; kalan kısım zemine değen kenarda (görünmeyen) kabul edildi, tasarım sıkıştırılmadı.']
asılı/ürün 1.02: dikey ölçek fiziksel, olcek_farki 0.0202, uyarı: ['Sahnedeki kumaş ürün boyundan ≈%2.0 uzun görünüyor (≈204 cm). Tasarım SIKIŞTIRILMADI (fiziksel ölçek); altta ≈4 cm baskısız kumaş görünür. Gözle kontrol edin.']
test_tam_kumas: TAMAM
```
`python3 tests/test_duzlem_yerlesim.py` (7,7 sn) — son satırlar:
```
dalgalı kenarda düz çizgilerin doğruya uyum artığı: maks 0.50 px; kenar sapması %0.7
ölçek: yatay 5.933 px/cm, dikey 5.907 px/cm
ortada katlanma: ['sahne_kivrim'] kumaş dışı baskı 0.04754
güçlü kenar dalgası: ['temas_belirsiz', 'sahne_geometri', 'sahne_kivrim'] kenar sapması 0.0911
açılı sahne: dönüşüm tek homografiden sapma maks 0.0001 (u birimi), sorunlar []
test_duzlem_yerlesim: TAMAM
```

## Doğrulanamayanlar
- Windows'ta çalıştırma yapılmadı.
- `*_yaklasik.jpg` görseller eski algılama katmanlı kayıttan geri çevrilmiştir; bantları gerçek ham sahnenin bandıyla aynı olmayabilir
  (en yakın sınır örneği elenen_02 tam da bu türden).
- Kullanıcı etiketleri ("kullanılabilir") görsel kabuldür; zemine temas/birikme için fiziksel doğrulama değildir.
- İş klasörlerindeki `elenen_NN_NN.jpg` ve `*_algilama.jpg` dosyaları ham değil (algılama katmanlı tanı görseli; geçersiz); bu
  sahnelerin ham hâli kayıtlı değil, analiz dışı. Ham kabul edilenler: `s*.png`, `*_ham.jpg`, kontrol örneklerindeki `*_ham.*`/`ham.jpg`,
  sentetik; `*_yaklasik.jpg` ayrı (yaklaşık) gösterildi.
- G3 (detection-engineer) algılamayı aynı anda değiştiriyor olabilir; bu ölçümler çalıştırma anındaki `banner_detect.py` ile alınmıştır.
  Algılama değişirse bantlar yeniden ölçülmeli.

---

# G5b — gelen kutusundaki 4 mesaj (Tur 1, 2026-10-13)

Ortam: Linux bulut, ağsız, ücretli çağrı yok. **Windows'ta çalıştırılmadı.** Pano güncellenmedi (yeni protokol: yalnız koordinatör).
orchestrator.py'ye dokunulmadı.

## Değişen dosyalar
- `compositor.py`
  1. **Ölçüm payı bandı (|fark| ≤ OLCUM_PAYI = %0,5):** karar aynı (bu bant ret nedeni değil, `v_gizli` 1.0, `gizli_cm` 0). Ama fiziksel ölçekte
     ≈1 cm gerçekten temas çizgisinin altına düşüyor: `gorunen_murekkep` artık gerçek görünen orandan (`min(1, asılı/boy)`) hesaplanıyor
     (eskiden 1.0 yazıyordu); bu banttaki baskı `product.murekkep_orani` ile ölçülüyor → yeni alanlar `olcum_payi_gizli_cm`,
     `olcum_payi_murekkep`; baskı > MUREKKEP_ESIK ise UYARI ("ölçüm payı içinde ... ret değil, gözle kontrol edin").
     Neden ret değil: fark ölçüm hassasiyeti içinde (≈1 cm, 200 cm'de); kabul edilmiş 005509 s01 (−%0,15) bu bantta — ret yapmak kabul
     edilmiş sahneyi yalnız ölçüm gürültüsüyle düşürebilirdi. Karar koordinatöre açık (bkz. açık konular).
  2. **Birikmesiz gizli bölge metni (M-architecture-reviewer-18):** `birikme=False` iken (ör. %0,5–3 kısa kumaş, manuel temas) mesaj artık
     "zeminde biriken kumaş" demiyor: "kumaşın görünen alt kenarının (zemine temas çizgisi) altına düşüyor ... birikme görünmüyor". Tür aynı
     (`birikme_cozulemedi`), yeni hata türü yok. Baskısız durumda uyarı da ayrıldı; "birikme büyük" uyarısı yalnız birikmede.
     Kayıtlı ham sahnelerde (G4 ölçümü) bu dala giren sahne yok; yalnız sentetik ve manuel temasla giriliyor.
  3. **TAM_BOY_TOL yorumu (M-architecture-reviewer-14):** "sıkıştırır" ifadesi kaldırıldı → "yalnız uygunluk kararı; ölçek her zaman fiziksel (K-54)".
- `sinir_kaniti.py`: `kalan_sorunlar` içinde `gorunen_murekkep or 1` → `is None` kontrolü (0 değerinde "%0 gizlenir" yerine "%100");
  `olc()` sonucuna `kaynak_kodu` = "uygun" | "geometri" | "sinir" (mevcut `kaynak` metni korundu); `kalan_sorunlar` `sinir_araligi.kaynak`
  için "sınır" ve "sinir" ikisini de kabul ediyor. pipeline-engineer gelen kutusuna **M-placement-engineer-1 (BİLGİ)** yazıldı.
- `tests/test_tam_kumas.py`: bölüm 8 (a: ölçüm payı bandında alt şeritli tasarım → ret yok, `gorunen_murekkep` < 0,95, uyarı; alt kenarı boş
  tasarımda uyarı yok ve 1.0; b: birikmesiz %2 kısa kumaşta metin "birik..." içermiyor, tür birikme_cozulemedi) ve bölüm 9 (sinir_kaniti
  `kaynak_kodu` uygun/geometri; `gorunen_murekkep` 0 → "%100'i gizlenir"; "sinir" kodu kabul).
- Gelen kutuma 4 yanıt satırı eklendi.

## Regresyon doğrulaması (düzeltme geri alınınca test başarısız mı?)
Çalışma klasörüne kopyalanan modüllerle (`git show HEAD:` sürümleri), sırayla:
- compositor + sinir_kaniti eski: `AssertionError: 1.0` (test_tam_kumas:226, `gorunen_murekkep` eski kodda 1.0).
- compositor yeni, sinir_kaniti eski: `KeyError: 'kaynak_kodu'`.
- yalnız metin düzeltmesi geri alınmış compositor: `AssertionError: Tasarımın alt ≈4 cm'si zeminde biriken kumaşta kalıyor ...`.
Üçü de başarısız → testler anlamlı.

## Çalıştırılan testler (yerel, sırayla; gerçek son satırlar)
`python3 tests/test_tam_kumas.py` (48,7 sn):
```
asılı/ürün 1.02: dikey ölçek fiziksel, olcek_farki 0.0202, uyarı: ['Sahnedeki kumaş ürün boyundan ≈%2.0 uzun görünüyor (≈204 cm). Tasarım SIKIŞTIRILMADI (fiziksel ölçek); altta ≈4 cm baskısız kumaş görünür. Gözle kontrol edin.']
ölçüm payı bandı: fark -0.0047, gizli ≈0.94 cm, görünen mürekkep 0.4 -> uyarı, ret yok
birikmesiz kısa kumaş: tür birikme_cozulemedi, metin: Tasarımın alt ≈4 cm'si kumaşın görünen alt kenarının (zemine temas çizgisi) altı ...
sinir_kaniti: kaynak_kodu uygun/geometri; görünen mürekkep 0 -> %100 gizli yazılır
test_tam_kumas: TAMAM
```
`python3 tests/test_duzlem_yerlesim.py` (12,9 sn): `açılı sahne: dönüşüm tek homografiden sapma maks 0.0001 (u birimi), sorunlar []` / `test_duzlem_yerlesim: TAMAM`
`python3 tests/test_sureklilik.py` (4,5 sn): `çapraz çizgi kopuk satır: 0, E dikeyi kopuk satır: 0` / `test_sureklilik: TAMAM`
`python3 tests/test_product.py` (3,1 sn): `test_product: TAMAM`

## Doğrulanamayanlar / açık konular
- Windows'ta çalıştırılmadı.
- Başka sahiplerin testleri (test_kontrol_ornekleri, test_farkli_ortamlar, test_manuel_sinir*) çalıştırılmadı (test-runner G6). Etki analizi:
  `gorunen_murekkep` yalnız |fark| ≤ %0,5 bandında değişir; bu testlerin tasarımlarında alt %5–8 boş olduğundan ≥0,999 beklentileri
  etkilenmemeli. Yeni uyarı yalnız alt ≈1 cm'de baskı varsa yazılır; kayıtlı kabul sahnelerinin gerçek tasarımlarıyla (tasarim.* — açılmadı)
  uyarı çıkıp çıkmadığı doğrulanmadı. Uyarı listesini birebir karşılaştıran bir test varsa etkilenebilir.
- Koordinatöre açık karar: ölçüm payı bandındaki gizli baskı UYARI mı kalmalı yoksa ret (birikme_cozulemedi) mi olmalı? Şimdilik uyarı
  (gerekçe yukarıda). `olcum_payi_*` alanları orchestrator `tk_info` sabit listesinde yok; kayda girmesi için pipeline-engineer eklemeli.
