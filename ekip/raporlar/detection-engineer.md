# detection-engineer raporu — Tur 1, G3 (2026-10-13)

Not: Özel ajan türü yüklenemedi; genel amaçlı ajan, `.claude/agents/detection-engineer.md` tanımıyla çalıştı.
Ortam: Linux bulut. Testler Windows'ta ÇALIŞTIRILMADI.

## Sonuç: algılama hatası DEĞİL — girdi dosyası ham sahne değil, algılama katmanlı tanı görseli. Kod değiştirilmedi.

## Bulgu (görselde ne gördüm)
`isler/20261012-224824_.../sahneler_bos/elenen_01_04.jpg` (2400×2400) açıldı (küçük kopya /tmp/g3/k.jpg):
- Bahçe düğünü; ahşap stand, iki pembe fiyonk, standda tam boy asılı kumaş afiş, kadraj içinde.
- Kumaş bölgesinin TAMAMI düz **yeşil** boyalı (ort. BGR ≈ 117/202/127, std ≈ 5), kenarlarda **mavi** eğri çizgiler var.
  Bu `banner_detect.overlay()` çıktısıdır: `vis[m] = 0.6·vis + 0.4·(0,200,0)` (det.ok=True → yeşil) ve kenar eğrileri
  `(255,0,0)` BGR = mavi (banner_detect.py:702-716). Kenar şeritlerinde maske dışında kalan krem kumaş görünüyor.
- Eski kayıt biçimi: `rapor.json` elenenler[3] kaydında yalnız `"dosya": "sahneler_bos/elenen_01_04.jpg"` var, `ham_dosya` YOK.
  O dönemde ret anında yalnız algılama katmanlı görsel kaydediliyordu; şimdiki kod hamı ayrıca `_ham.jpg` olarak yazar
  (orchestrator.py:306-312) ve arayüz eski kayıtta `dosya`yı zaten "algılama görseli" sayar (app.py:315-316).
- Bu sahnenin asıl elenme nedeni de algılama değil: `sahne_geometri` — "görünen asılı boy ≈119 cm < 200 cm"
  (o anki algılama ham görüntüde başarılıydı; yeşil katman bunun kanıtı).

## Kök neden (neden %1,3 seçiliyor)
`bd.detect_candidates(img, {"kind":"fabric"}, en_fazla=4)` sonuçları:
| # | alan | skor | açıklık / kroma | ret |
|---|---|---|---|---|
| 1 (seçilen) | %1,31 (x 318–683, y 1484–1741) | 0,437 | 200 / 21,9 | "afiş boş görünmüyor (güçlü detay %0,34)" + uyarı "küçük kadraj %1,3" |
| 2 | %0,14 | 0,04 | 197 / 23,3 | güvenilir bölge yok, çok küçük |
| 3 | %0,03 | 0,01 | 186 / 2,8 | çok küçük, çok dar |
| 4 | **%23,9** (x≈830–1566, y 366–2115 = afiş) | **0,0** | 187 / **53** | "açık renkli/nötr değil (kroma 53)" |

Gerçek afiş 4. aday olarak bulunuyor ama yeşil katman yüzünden kroma 53 → "krem/beyaz/açık gri değil" kuralı doğru
şekilde reddediyor. Seçilen %1,3'lük bölge soldaki **beyaz masa örtüsü** (ve masa üstü nesneleri → "detay" reddi).
Yani algılama, kendisine verilen (boyanmış) görüntüde doğru davranıyor.

Karşı kanıt (yalnız tanı amaçlı, test örneği DEĞİL): yeşil katmanı 4. adayın genişletilmiş maskesinde
`ham ≈ (vis − 0,4·renk)/0,6` ile kabaca geri çevirdim (/tmp/g3/geri.jpg; mavi çizgiler kalır, JPEG kaybı büyür).
Bu yaklaşık görüntüde `detect` → **ok=True, alan %23,8, ret yok** (uyarı: güçlü detay %0,21). Kumaş krem renkte ve boş.

## Neden kod değişikliği / regresyon örneği YOK
- Genel algılama hatası yok; "krem/nötr" kuralını gevşetmek yeşil boyalı bölgeleri kumaş saydırır — yanlış olur.
- Tanı görselini `elenen_01_04_ham.jpg` adıyla kalıcı örnek yapmak yanıltıcı olur (ham değil). Geri çevrilmiş görüntü de
  sentetik/yaklaşık olduğundan "ham" etiketiyle eklenmedi. `tests/kontrol_ornekleri/is_224824/kontrol.json` DEĞİŞTİRİLMEDİ.
- Değişen dosyalar: yalnız bu rapor, `ekip/pano.md` (G3 satırı), `ekip/mesajlar/koordinator.md` (BİLGİ eklendi).

## Çalıştırılan testler (sırayla, yerel test, ağsız; kod değişmediği için mevcut durumun doğrulaması)
- `python tests/test_algilama_kurtarma.py` → rc=0, son satır: `TAMAM`
- `python tests/test_farkli_ortamlar.py` → rc=0, son satırlar:
  `224824 kabul_s01_ham.png: kabul, asılı 177.7 cm, kararsız=True` /
  `224824 kabul_s02_ham.png: kabul, asılı 201.4 cm, kararsız=False` / `test_farkli_ortamlar: TAMAM`
- `python tests/test_kontrol_ornekleri.py` → rc=0; 005509 `kabul_s01_ham.png … KABUL 0.353 199.5 … KARARSIZ (bilinen)`,
  `kabul_s02_ham.png … KABUL 0.344 197.1 … kararlı`; son satır: `test_kontrol_ornekleri: TAMAM`
Önceden kabul edilen sahneler (005509 s01/s02, 224824 s01/s02) kabul.

## Doğrulanamayanlar
- 224824 çağrı 4'ün GERÇEK ham görüntüsü kayıtlı değil; ham üzerinde algılama/ölçüm yeniden yapılamaz. 119 cm asılı boy
  ölçümünün (temas_yontemi=kenar_yayilmasi, temas_y=1371) doğruluğu bu yüzden bağımsız doğrulanamadı; geri çevrilmiş
  yaklaşık görüntüde afiş zemine kadar uzanıyor gibi görünüyor — o ölçüm şüpheli olabilir (K-54 "kenar genişlemesi tek
  başına temas kanıtı değildir" ile ilgili). Ham olmadan karar verilmedi.
- Windows'ta çalıştırılmadı.

---

# G5c (2026-10-13) — quality-reviewer bulguları
Ortam: Linux bulut, yerel test (ağsız, ücretsiz). Windows'ta ÇALIŞTIRILMADI. Pano güncellenmedi (protokol: yalnız koordinatör).

## Değişen dosyalar
1. `banner_detect.py`
   - Eşiklere **VARSAYIM** etiketi + kanıt (DEĞERLER DEĞİŞMEDİ). Kanıt, 18 kontrol örneğinde (`tests/kontrol_ornekleri/*`) ölçüldü
     (betik: /tmp/g3/g5c/kanit*.py, çıktı kanit*.txt; kalıcı değil):
     | Eşik | Değer | Ölçüm | Pay |
     |---|---|---|---|
     | ZEMIN_GENISLEME | 1,5 | en geniş satır/gövde: 054333 3,14 (ayrılmalı); 005509 #10 1,64–1,91, #13 1,58; 053942 1,42 | **dar** (1,42↔1,58) |
     | ZEMIN_PAY | 0,012 | YAN_TASMA_PAY ile aynı; ayrı ölçülmüş kanıt yok (yalnız 054333 testi) | belirsiz |
     | YAN_KIRP_ESIK | 0,15 | ilk yan_tasma: 053942 0,29; diğer 17 örnek 0,00–0,048 | ~0,10 |
     | IoU (aday kopyası) | 0,7 | kopyalar 0,76 / 0,91 / 0,97–0,99; ayrı bölgeler 0,00 | 0,06 (yanılma yönü zararsız) |
     | _zemin_ayir arama başı | 0,55 | gözlenen kesimler boyun %92 ve %94'ünde | geniş |
     | _zemin_ayir doluluk | 0,5 | 054333 kesim 0,36 / gövde ≥0,58; 005509 #10 kesim 0,49 / gövde ≥0,51 | **çok dar** (±0,01) |
   - `tespit_maskeden`: delik oranı artık sabit 0.0 değil, VERİLEN maskeden otomatik yolla aynı biçimde (`_finalize`: kapatma +
     iç delik / alan, çalışma çözünürlüğünde) hesaplanıyor; maske DOLDURULMUYOR (yalnız ölçülüyor). Docstring güncellendi.
     Manuel köşe modunda maske = dörtgen ∩ genişletilmiş otomatik maske (zaten dolu) olduğundan pratikte delik ≈0; kapı yalnız
     gerçekten içi delik bir bölge verildiğinde devreye girer.
2. `tests/test_algilama_kurtarma.py`
   - `yama()` → `contextlib.contextmanager`, `try/finally` ile geri yükler; bütün çağrılar `with yama(...):`.
     `__main__`'deki elle geri yükleme kaldırıldı; yerine her testten sonra "yama sızdı" assert'i.
   - Yeni `test_tespit_maskeden_delik_kapisi` (sentetik: koyu zemin, krem kumaş, ortada maske dışı ~%8 delik → "afişin içi boş
     değil" reddi, maske değişmedi; deliksiz maske → delik kapısı yok).
3. `ekip/mesajlar/detection-engineer.md` (yanıtlar), `ekip/mesajlar/pipeline-engineer.md` (M-detection-engineer-1).

## Geri alınınca başarısız olma (doğrulandı)
- `tespit_maskeden` 0.0'a döndürülünce (bellek içinde): `AssertionError: delik oranı ölçülmedi: 0.0`.
- Eski (try/finally'siz) yama uygulanınca sızıntı denetimi `False` → `__main__` assert'i başarısız olur.
- Her test tek tek çalıştırıldı (başarısız olan dahil) → hiçbirinden sonra `bd.detect`/`detect_candidates` sızmadı.

## Testler (sırayla)
- `python tests/test_algilama_kurtarma.py` → **rc=1**. 7 test geçti, sonra:
  `AssertionError` @ test_algilama_kurtarma.py:163 (`test_tutarli_oneri_kontrollerden_gecer`, ikinci kısım).
  Neden: pipeline-engineer eşzamanlı olarak `orchestrator._kurtar`'ı değiştirdi (orchestrator.py:605-609: doğru bölgede ret artık
  `(None, sonuc="dogrulanamadi")`). Benim değişikliğimle ilgisi yok; tek tek çalıştırmada kalan 10 test geçti. Beklenti
  pipeline'ın modülüne ait → `M-detection-engineer-1` ile sahibine soruldu; onun isteği olmadan assert değiştirilmedi.
  (İlk denemede ayrıca `gks.GECERSIZ` yok hatası alındı — pipeline yarım düzenlemedeydi; yeniden çalıştırınca kayboldu.)
- `python tests/test_farkli_ortamlar.py` → rc=0; son satırlar: `224824 kabul_s01_ham.png: kabul, asılı 177.7 cm, kararsız=True` /
  `224824 kabul_s02_ham.png: kabul, asılı 201.4 cm, kararsız=False` / `test_farkli_ortamlar: TAMAM`
- `python tests/test_manuel_sinir.py` → rc=0; `1) köşeler kumaşta: kabul, kurdele piksellerinin %0.00'i değişti, asılı 199.7 cm` /
  `2) ... sahne_kivrim` / `3) köşeler duvarda: ... baskı yapılmadı` / `test_manuel_sinir: TAMAM` — manuel köşe modu bozulmadı.

## Doğrulanamayanlar / açık
- test_algilama_kurtarma TAMAM'a ulaşmıyor: pipeline-engineer yanıtı bekleniyor (yeni beklenti ya da alt durumun taşınması).
- test_kontrol_ornekleri bu turda istenmediği için çalıştırılmadı (algılama davranışı değişmedi; yalnız manuel yolda delik ölçümü).
- ZEMIN_GENISLEME ve _zemin_ayir 0.5 payları dar; daha fazla ham örnek olmadan sağlamlık doğrulanamaz.

### G5c ek (engel kalktı)
pipeline-engineer'ın yanıtına göre (M-detection-engineer-1, G5a sözleşmesi) `test_tutarli_oneri_kontrollerden_gecer` ikinci kısmı
güncellendi: `ev2 is None and bilgi2["sonuc"] == "dogrulanamadi" and bilgi2["servis"]["yeniden_algilama"].startswith("ret")`.
`python tests/test_algilama_kurtarma.py` → rc=0, son satır `TAMAM` (11 test; Linux, Windows'ta çalıştırılmadı).
