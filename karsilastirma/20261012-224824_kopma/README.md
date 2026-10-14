# Kopma kök neden karşılaştırması — iş 20261012-224824_20261012-224717_design

Tarih: 2026-10-12. Ücretli çağrı yok. Orijinal iş klasörüne dokunulmadı; bu klasördeki her şey kayıtlı boş sahnelerden
(`sahneler_bos/s01.png`, `s02.png`) ve aynı `tasarim.png`'den yeniden üretildi.

## Varyantlar (her seferinde TEK değişken)

| Varyant | Değişiklik | 01 (s01) | 02 (s02) |
|---|---|---|---|
| V0_mevcut | Yok (o anki kod). Orijinal fotoğrafla ortalama fark 0,55 / 0,77 (JPEG sıkıştırması düzeyi) → yeniden üretim doğru | Kopmalar var | Kopmalar var |
| V1_fold0 | Yalnız `fold_shift=0` | Kopmalar **kalıyor**; WELCOME'daki W/O çift konturu kalkıyor | Kopmalar **kalıyor** |
| V2_kenar_duz | Yalnız kumaş kenarları satır satır yerine düzgün eğri | Kopmalar **kalkıyor**; W/O'da hafif çift kontur kalıyor | Kopmalar **kalkıyor** |
| V3_kurdele_yok | Yalnız kurdele geri koyma kapalı | V0 ile **piksel piksel aynı** (0 piksel fark) | Aynı |
| V4_duzeltilmis | Düzeltilmiş kod (kenar düzgünleştirme + tam kumaşta kıvrım kayması kapalı) | Temiz | Temiz |

## Ölçümler (`metrikler.json`, `metrikler_duzeltilmis.json`)

"Satır ikinci farkı" = dönüşümde satırdan satıra ani yatay sıçrama (çıktı pikseli); "katlanma" = dönüşümün kendi
üzerine kapandığı piksel sayısı.

| | s01 ikinci fark maks | s01 katlanma | s02 ikinci fark maks | s02 katlanma |
|---|---|---|---|---|
| V0 | 428,5 px | 1688 | 247,7 px | 0 |
| V1 (fold 0) | 432,9 px | **0** | 248,2 px | 0 |
| V2 (kenar düz) | **0,64 px** | 1414 | **0,79 px** | 0 |
| V4 (düzeltilmiş) | **0,47 px** | **0** | **0,31 px** | **0** |

Yerleşim koordinatları değişmedi: asılı boy (177,7 / 201,4 cm), gizli bölge (22,3 / 0 cm), cm ölçeği (11,702 / 9,567
px/cm) rapordakiyle aynı; dikey koordinat farkı 0; yatay konum farkı medyan 3,3 / 1,7 px (kumaş eni ≈ 900 px),
en büyük farklar kopma satırlarında.

## Sonuç

1. **Ana neden:** kumaşın sol/sağ kenarı her satır için ayrı (alt-piksel) ölçülüyor; birkaç satırda kenar sıçrıyor
   (s01'de 121, s02'de 42 satır > 1,5 px). Tasarımın yatay koordinatı bu kenarlara bağlı olduğundan o satırlar yatayda
   kayıyor → y kuyruğu, BABY SHOWER, ayıcık, alt BABY, WELCOME'daki L kopmaları.
2. **İkincil neden:** ışık gradyanından türetilen kıvrım kayması (`fold_shift=0,01`) s01'de dönüşümü 1688 pikselde
   katlıyor → WELCOME'daki W ve O'da çift kontur.
3. **Kurdele geri koyma** kopmalara katkı vermiyor.

`yakin/once_sonra_*.png`: önce/sonra yakın görünümler. `yakin/yakin_*.png`: dört tek değişkenli varyant.
`tam/`: tam boy görseller (JPEG %95). Betikler (`deney*.py`, `crops*.py`) Claude'un çalışma alanındaki yollarla yazıldı;
kayıt amaçlıdır.
