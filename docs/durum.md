# Proje durumu

Bu dosya her aşamanın sonunda güncellenir. Claude ve Codex aynı klasörü okur; bir aşamaya başlamadan önce
buradan başlayın. Gizli bilgi (anahtar, `ayarlar.json` içeriği, gizli bağlantı, base64 görsel) bu dosyaya yazılmaz.
Kararların gerekçeleri: `docs/kararlar.md`. Bulguların kanıtları: `docs/inceleme_2026-10-12.md`.

**Son güncelleme:** 2026-10-12 20:50 (Claude) · **Mevcut aşama:** Aşama 1 tamamlandı; Aşama 2 başlamadı,
fiziksel ürün yanıtları bekleniyor.

---

## 1. Tamamlanan işler ve değiştirilen dosyalar

### Aşama 1 — İnceleme ve temel (2026-10-12)

| Dosya | Değişiklik | Neden |
|---|---|---|
| `selector.py` | `_calls()` ve `pick()` yalnız `self.hist` kullanıyor (önce `hist + run` topluyordu) | `record()` sonucu ikisine de yazdığı için bu işin sonuçları seçimde iki kez sayılıyordu |
| `tests/test_selector.py` | 6b bölümü: üç regresyon kontrolü (çağrı sayısı, Thompson parametreleri, keşif dalı); seçim eşiği 380 → 330 | Eski eşik çift sayımın yarattığı sahte kesinliğe dayanıyordu (doğru beklenen ≈ 358/400) |
| `CLAUDE.md` (yeni) | Ürün gereksinimleri, koruma kuralları, ajan sorumlulukları, doğrulama yaklaşımı, aşamalar | Her oturumun okuyacağı tek gereksinim kaynağı |
| `docs/architecture.md` (yeni) | Bugünkü ve hedef mimari, durum makinesi, veri modeli, bulgu tablosu, notlarla çelişkiler | — |
| `docs/inceleme_2026-10-12.md` (yeni) | Mimari incelemenin dosya:satır kanıtları | — |
| `docs/roadmap.md` (yeni) | Aşama 2–6 planı; Aşama 2 için adım, sahip ve test tablosu | — |
| `ajanlar_kurulum/` (yeni) | 4 ajan tanımı + `ajanlari_kur.bat` | Uzaktan bağlantı `.claude/` klasörüne yazamıyor (bkz. §3) |
| `_yedek/kaynak_20261012_asama1_oncesi.zip` | Değişiklik öncesi kaynak kod yedeği (anahtar/log yok) | Geri alınabilirlik |
| `_yedek/afis_git_20261012.bundle` | İki Git kontrol noktası (önce/sonra) | Klasörde Git yok; `git clone` ile açılabilir |
| `docs/durum.md`, `docs/kararlar.md` (yeni) | Bu belgeler | Kullanıcı isteği: aşama sonu durum kaydı |

**Dokunulmayanlar:** `ayarlar.json`, `servis_karnesi.json`, `isler/`, `yuklemeler/`, `referanslar/`, `raporlar/`,
`PROJE_NOTLARI.md`, arayüz (`ui.html`, `app.py`), başlatma (`baslat.bat`).

**Ajanların kullanımı:** architecture-reviewer (bulgu doğrulama), provider-engineer (Selector düzeltmesi),
quality-reviewer (bağımsız inceleme, onay), image-engineer (Aşama 2 planı; kod yazmadı). Ajanlar Claude Code
oturumunda yeni tanımlandığı için genel ajanlara kendi tanım dosyaları verilerek çalıştırıldı.

## 2. Gerçekten çalıştırılan testler

Ortam: Claude'un bulut çalışma alanı, Linux, Python 3.13 (kullanıcının bilgisayarı: Windows 11, Python 3.12).

| Test | Tür | Düzeltme öncesi | Düzeltme sonrası |
|---|---|---|---|
| `tests/test_selector.py` | Yerel | TAMAM | TAMAM (3 kez) |
| Yeni regresyon kontrolleri, **eski** `selector.py` ile | Yerel | — | **Başarısız** (beklenen): `AssertionError: 2`; keşif dalında yanlış seçim |
| `tests/test_camera_move.py`, `test_video_composite.py`, `test_video_repair.py`, `test_video_track.py`, `test_refstore.py`, `test_magnific_fix.py` | Yerel | TAMAM | — (değişiklikten etkilenmez; öncesinde çalıştı) |
| `tests/test_e2e_mock.py`, `test_unicode_path.py`, `test_topview.py` | Sahte servis | TAMAM | TAMAM |
| `kontrol.py` | Yerel | — | HER ŞEY TAMAM |
| Anahtar / base64 taraması (Git'teki dosyalar) | Yerel | — | Bulunmadı |
| Bilgisayara yazılan `selector.py` ve testin, test edilen kopyayla bayt eşitliği | — | — | Eşit |
| **Gerçek sağlayıcı testi** | — | **Yapılmadı** | **Yapılmadı** |

## 3. Doğrulanmamış konular ve mevcut hatalar

### Doğrulanmamış
- Testlerin kullanıcının Windows bilgisayarında (`.venv`, Python 3.12) çalışması.
- Ajanların Claude Code'da tanınması: `ajanlar_kurulum\ajanlari_kur.bat` henüz çalıştırılmadı (bilinen durum);
  çalıştırıldıktan sonra Claude Code'un yeniden açılması gerekir.
- Gerçek sahnelerde "sert/rigid" sınıflandırmasının sıklığı.
- Açılı görünüm için önerilen eşikler (yalnız sentetik sahnelerle tahmin edildi).
- Sağlayıcıların 1:1 kare desteği (kodda tablo var, resmî belgeyle doğrulanmadı).
- Beyaz mürekkepli tasarım olup olmadığı (şeffaf alan beyaza oturtuluyor; ayırt edilemiyor).

### Mevcut hatalar (doğrulanmış, henüz düzeltilmedi)
| Hata | Yer | Planlanan aşama |
|---|---|---|
| 150×300 ve 150×400 hiç seçilemiyor (oranlar 50×100 ve 75×200 ile çakışıyor) | `prompts.py` `size_for` | 2 (adım 1, 5) |
| "Eksikleri tamamla" arayüzden yapılamıyor; aynı işte tekrar çalıştırma "n tane daha" ekliyor; `elenen_NN.jpg` üzerine yazılıyor | `app.py`, `orchestrator.py` | 2 (adım 7) |
| "Sert" sahnede tasarım ±%15'e kadar sessizce esnetiliyor | `compositor.py` | 2 (adım 3) |

### Gereksinim çelişkileri (kod niyetine göre doğru, güncel isteğe aykırı)
Varsayılan ayarla her iş 9:16 üretiliyor, 1:1 yok · açılı sahne üretilemiyor · ölçü PNG oranından tahmin ediliyor ·
"oran düzeltme" sahne fotoğrafını yatayda esnetiyor · kumaş/sert yerleşim farkı · otomatik video fotoğraf
başına ücretli çağrı · kalite puanı yalnız geometri · iş numarası saklanmıyor, üretim POST'u kör yeniden deneniyor ·
model/prompt sürümü kaydı yok · bilgi görseli/paket yok. Ayrıntı: `docs/architecture.md` §2.

## 4. Kullanıcıdan beklenen yanıtlar

Aşama 2 bunlar yanıtlanmadan başlamaz (uydurulmayacak):

1. Her ölçü için **baskı alanı (cm)** ve kenar/dikiş payı. Baskı kenara kadar mı?
2. Üst kenar yapısı: çubuk tüneli mi, kurdeleyle bağlama mı? Kurdele afişe nereden bağlanıyor?
3. Kuşgözü: adet, çap, renk, konum. İlan sahnelerinde kuşgözlü mü gösterilecek?
4. Kumaş: pamuk/keten oranı, gramaj, ton, alt kenar bitişi.
5. Sahnedeki boy: prompttaki "yere değiyor, 20–30 cm fazlası yerde kıvrılıyor" doğru mu? 50×100 ve 150×400
   nasıl sergilenecek?
6. İlan sahnelerinde hangi ölçü gösterilecek (ürün başına tek ölçü mü)?
7. "Hafif yandan" kaç derece, hangi yönden; üç ortamda aynı yön mü?
8. Düğün dışı kategoriler için 3 ortam + gün saati tablosu.
9. İki bilgi görseli: dosyalar nerede, kategoriye mi ürüne mi bağlı, kare mi?
10. Oran uyuşmazlığı politikası: (A) sahne esnetmeyi kapat, uymayan sahneyi yeniden üret (**öneri**) ya da
    (B) en fazla %15 esnetmeye izin ver ve raporla.

Ayrıca: `ajanlari_kur.bat` çalıştırılıp Windows'ta `.venv\Scripts\python tests\test_selector.py` ve
`.venv\Scripts\python kontrol.py` sonuçlarının bildirilmesi.

## 5. Sonraki önerilen adım

Yanıtlar geldikten sonra **Aşama 2, adım 1–4** (birbirinden bağımsız, farklı dosyalar): ürün profili
(`product.py`), layout açı profilleri, kumaşta tutarlı yerleşim, sahte servisin kare/açılı sahne üretmesi. Ardından
sırayla adım 5 (prompt/kılavuz), 6 (kare kadraj videodan bağımsız), 7 (6 görev + eksikleri tamamla), 8 (paket).
Ayrıntı ve testler: `docs/roadmap.md` §2.1.
