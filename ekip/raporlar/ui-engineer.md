# ui-engineer raporu — G5d (Tur 1, 2026-10-13)

Bu oturumda özel ajan türü yüklenemediği için genel amaçlı ajan, `.claude/agents/ui-engineer.md` tanımıyla çalıştı.
Ücretli çağrı / ağ / git commit yok; `ayarlar.json` açılmadı.

## Değişen dosyalar
| Dosya | Değişiklik | Neden |
|---|---|---|
| `ui.html` (~223) | `#elenenHam` onay kutusundan `checked` kaldırıldı (varsayılan işaretsiz) | "Kayıtlı sahnelerden yeniden birleştir" düğmesinin varsayılan davranışı sessizce genişlemesin (quality-reviewer, G1) |
| `kontrol.py` | `"...: " + det.reject` → `"; ".join(map(str, det.reject))`; `yerlestirme(sahne_yolu=None)`; adımlar `main()` içine + `if __name__ == "__main__"` | Liste metne eklenince kullanıcı asıl neden yerine TypeError görüyordu (M-architecture-reviewer-11). Ana koruma, testin ağır kurulum adımlarını çalıştırmadan içe aktarabilmesi için; `kur.bat` çağrısı (`python kontrol.py`) aynı kalır. Kullanılmayan `import cv2` kaldırıldı. |
| `tests/test_kontrol_kurulum.py` (yeni) | Afişsiz düz gri sahneyle `kontrol.yerlestirme()` → RuntimeError, mesajda "afiş bulunamadı" + algılamanın bütün nedenleri; `adim()` çıktısında TypeError yok; içe aktarma adımları çalıştırmaz | Regresyon testi |
| `tests/test_manuel_sinir_tarayici.py` | 5. kontrol `elenen_ham_kutusu()`: kutu görünür + işaretsiz; işaretsiz tıklamada gövde `elenen_ham: false`, işaretlenince `true`. `/api/yeniden_birlestir` isteği `page.route` ile tarayıcıda yakalanıp yanıtlanır, sunucuya ulaşmaz (kaynak iş değişmez, sonraki md5 kontrolü korunur) | Gerçek tarayıcıyla doğrulama |

## Çalıştırılan testler (sırayla; hepsi YEREL test — ağsız, sağlayıcısız)
Ortam: Linux bulut, Python + Playwright başsız Chromium. **Windows'ta çalıştırılmadı** (Windows'ta geçmiş sayılmaz).

1. `python tests/test_kontrol_kurulum.py`
   ```
   hata mesajı: örnek sahnede afiş bulunamadı: bulunan bölge açık renkli/nötr değil (açıklık 76/255, kroma 0); baskı modeli beyaz/krem/açık gri boş afiş ister; bulunan bölge çok büyük (%100); duvar/arka plan olabilir; afiş kadraja taşıyor/kesilmiş
   test_kontrol_kurulum: TAMAM
   ```
   Düzeltme geri alındığında (satır 62 eski haline getirildi):
   `AssertionError: yanıltıcı TypeError (det.reject listesi metne eklenmiş): can only concatenate str (not "list") to str` → düzeltme geri konunca yine TAMAM.
2. `python tests/test_elenen_arayuz.py`
   ```
   3 elenen; eski kayıt 1; sınıflar {'belirsiz': 3}; deneme kaydı var: True
   durma simülasyonu (kayıtlı sıra, tavan 1): şimdiki ayarla 1. çağrı (hedef)
   test_elenen_arayuz: TAMAM
   ```
3. `python tests/test_manuel_sinir_tarayici.py` (o anki orchestrator.py ile; başarısızlık yok)
   ```
   elenen ham kutusu: varsayılan işaretsiz; gönderilen gövdeler [{'job': '20261013-053942_Baby-shower', 'elenen_ham': False}, {'job': '20261013-053942_Baby-shower', 'elenen_ham': True}]
   pencere 1280px: yeni iş 20261013-172512_manuel_20261013-053942; ...
   pencere 700px: yeni iş 20261013-172521_manuel_20261013-053942; ...
   dört köşe (zayıf örtüşme): baskı yok, uyarı: Verdiğin köşeler kumaşla güvenle eşleşmedi; ...
   test_manuel_sinir_tarayici: TAMAM
   ```
   ui.html'de `checked` geri konduğunda: `AssertionError: 'elenen ham' kutusu varsayılan olarak işaretli` → geri alındı.
4. Ek: `python kontrol.py` uçtan uca → 5 adım [TAMAM], "HER ŞEY TAMAM." (davranış değişmedi).

## Doğrulanamayanlar
- Windows (`kur.bat` → `.venv\Scripts\python.exe kontrol.py`) üzerinde çalıştırılmadı.
- Kutunun işaretli gönderimiyle sunucu tarafının gerçek ham yeniden denemesi bu testte sınanmadı (istek bilerek yakalandı; sunucu yolu pipeline testlerinde).

---
# G9 — Manuel sınırdan sonra kaynak işte kal (M-koordinator-4)

## Değişen dosyalar
- `app.py`
  - `_manuel_sinir.work()`: sonuca `donus_is` (düzenleyicinin açıldığı iş) eklendi; bitince `RUN.job` bu işe geri alınır (sayfa yenilense de kaynak iş açılır). orchestrator.py'ye dokunulmadı.
  - Yeni `_manuel_sonuclari()`: `isler/` altında yalnız adında `manuel_` geçen klasörlerin `rapor.json`'u okunur (değişiklik zamanına göre önbellek); `islem=="manuel_sinir"` kayıtlarından `(kaynak.is, kaynak.dosya) -> [{job, sonuc}]` üretir. sonuc: `fotograflar` → kabul, `elenenler` tur `manuel_maske_zayif` → uygulanmadi, diğer → kabul_edilmedi.
  - `_job_info`: her elenen kartına `manuel_sonuclar` (kartın `manuel_kaynak_is or bu iş`, `manuel_dosya` ile eşleşir; yeniden birleştirme işlerinde de çalışır; işin kendisi listeden çıkarılır).
- `ui.html`
  - `poll()`: sonuçta `donus_is` varsa yeni işe GEÇMEZ, kaynak işi yeniden yükler; `#msBildirim` bildiriminde durum + "yeni sonucu aç" / "kapat".
  - Elenen kartı: "Manuel sınır sonuçları (ayrı iş; bu iş değişmedi)" — her sonuç için durum çipi (kabul / kabul edilmedi / uygulanmadı (baskı yok)) + iş adı + "aç".
  - Manuel iş açılınca `#kaynakBag`: "Manuel sınır sonucu. Kaynak iş: <ad> — kaynağa dön".
- `tests/test_manuel_sinir_tarayici.py`: kaynak iş artık 3 elenen sahneli (kullanıcı vakası). Yeni kontrol 6: Uygula sonrası `#jobSel` kaynak işte, 3 kart görünür, yalnız ilgili kartta manuel sonuç + "aç", bildirimde "yeni sonucu aç"; "aç" → yeni iş + "kaynağa dön" görünür; "kaynağa dön" → kaynak iş, 3 kart. Köşe (zayıf) senaryosunda kartta "uygulanmadı" ve toplam 3 manuel sonuç.
- `tests/test_elenen_arayuz.py`: değişmedi.

## Testler (Linux bulut, başsız Chromium/Playwright; Windows'ta çalıştırılmadı)
- `python tests/test_manuel_sinir_tarayici.py` → son satırlar:
  `pencere 1280px: yeni iş 20261014-093122_manuel_20261013-053942; ...` / `pencere 700px: yeni iş 20261014-093128_manuel_20261013-053942; ...` /
  `dört köşe (zayıf örtüşme): baskı yok, uyarı: Verdiğin köşeler kumaşla güvenle eşleşmedi; ...` / `test_manuel_sinir_tarayici: TAMAM`
- Regresyon: `poll()` içinde `donus` null yapılınca (eski davranış: yeni işe geçiş) test `waiting for locator("#rejBox [data-acis=...]")` zaman aşımıyla BAŞARISIZ (denendi, sonra geri alındı).
- `python tests/test_elenen_arayuz.py` → `test_elenen_arayuz: TAMAM`
- `python tests/test_manuel_sinir.py` (pipeline'ın; yalnız çalıştırıldı) → `5) 7 olumsuz durum: hepsi reddedildi, iş klasörü açılmadı` / `test_manuel_sinir: TAMAM`

## Doğrulanamayanlar
- Windows'ta çalıştırılmadı. Gerçek kullanıcı işi (20261014-091258) üzerinde denenmedi (test geçici kopya klasörde).
- Manuel iş, yeniden birleştirme işinden başlatıldıysa "kaynağa dön" rapordaki `kaynak_is`'e (sahnenin asıl işi) döner, yeniden birleştirme işine değil.
