# Afiş Stüdyosu — Yol haritası

Son güncelleme: 2026-10-12. Gereksinimler: `CLAUDE.md`. Mimari ve bulgular: `docs/architecture.md`.
Her adım küçük, ayrı commit (veya `_yedek/` yedeği) ve kendi regresyon testiyle yapılır. Ücretli API yalnız
kullanıcı onayıyla, Aşama 2'nin sonunda örnek ürünlerle.

---

## Aşama 1 — İnceleme ve temel (TAMAMLANDI, 2026-10-12)

- [x] Kod, notlar, `kayit.log` ve son iki hata raporu incelendi (ayar kopyaları açılmadı).
- [x] `.claude/agents/`: `architecture-reviewer`, `image-engineer`, `provider-engineer`, `quality-reviewer`.
- [x] `CLAUDE.md`, `docs/architecture.md`, `docs/inceleme_2026-10-12.md`, bu dosya.
- [x] 7 bulgu koddan doğrulandı (1 hata, 1 hata+çelişki, 5 çelişki) + 14 ek bulgu.
- [x] **Selector çift sayım düzeltmesi** (`selector.py`) + regresyon testleri (`tests/test_selector.py` 6b).

---

## Aşama 2 — Fotoğraf hattı (SIRADAKİ)

Hedef: bir tasarım + ürün profili → 6 kare ürün görseli (3 ortam × önden/hafif yandan), tutarlı kumaş
yerleşimi, eksikleri tamamlama, 2 bilgi görseli pakette. Video'ya dokunulmaz.

### 2.0 Önce ürün sahibinden alınacak bilgiler (uydurulmayacak)

1. Her ölçü için **baskı alanı (cm)** ve kenar/dikiş payı; baskı kenara kadar mı?
2. Üst kenar yapısı: çubuk tüneli mi, kurdeleyle bağlama mı? Kurdele afişe nereden bağlanıyor?
3. Kuşgözü: adet, çap, renk, konum; ilan sahnelerinde kuşgözlü mü gösterilecek?
4. Kumaş: pamuk/keten oranı, gramaj, ton, alt kenar bitişi.
5. Sahnede boy: promptta yazan "yere değiyor, 20–30 cm fazlası yerde" doğru mu? (`prompts.py:12-13` — şu an
   kodda **uydurulmuş fiziksel bilgi** olarak duruyor.)
6. İlan sahnelerinde hangi ölçü gösterilecek (ürün başına tek ölçü mü?).
7. "Hafif yandan" kaç derece, hangi yönden; 3 ortamda aynı yön mü?
8. Düğün dışı kategoriler için 3 ortam + gün saati tablosu.
9. İki bilgi görseli: dosyalar nerede, kategoriye mi ürüne mi bağlı, kare mi?
10. Oran uyuşmazlığı politikası: (A) sahneyi esnetmeyi kapat, uymayan sahneyi yeniden üret **(öneri)** veya
    (B) en fazla %15 esnetmeye izin ver ve raporla.

### 2.1 Adımlar (sıra, sahip, test)

| # | İş | Sahip | Dosyalar | Regresyon testi (düzeltme geri alınınca başarısız olmalı) |
|---|---|---|---|---|
| 1 | **Ürün profili**: 5 ölçü tablosu, malzeme, bağlantı (`kurdele`, `kusgozu`), baskı alanı (belirsizse `None` + uyarı), `sigdir()` (contain, esnetme yok) | image-engineer | yeni `product.py`, `tests/test_product.py` | 50×100 ile 150×300 ayrı profiller; 0.44 tasarım → 0.5 alan: ölçek doğru, ≈%6 yan boşluk, esnetme yok |
| 2 | **Layout görünüm profilleri** `front` / `angled` (varsayılan `front` = bugünkü davranış) | image-engineer | `layout.py`, `tests/test_layout_profiles.py` | front: yaw 0 geçer, 0.14 elenir; angled: 0.07 ve 0.14 geçer, ters perspektif elenir |
| 3 | **Kumaşta tutarlı yerleşim**: kumaş üründe `detect(hint={"kind":"fabric"})`; baskı alanı profilden; açılı kumaş için sütun bazlı üst/alt eğri | image-engineer | `banner_detect.py`, `compositor.py`, `tests/test_fabric_placement.py` | aynı tasarım iki sahnede göreli konum ±%2; "rigid" görünen sahnede bile kumaş yolu; açılıda maske dışına taşma ≈0 |
| 4 | **Sahte servis**: kare istenince kare, açılı sahte sahne (`mock_angled`) | provider-engineer | `mock_provider.py` | — (test altyapısı) |
| 5 | **Prompt ve kılavuz**: ölçü profilden ("exactly W cm × H cm"); `CAMERA_FRONT` / `CAMERA_ANGLED`; kuşgözü cümlesi yalnız profilde varsa; `size_for` foto hattından çıkar | image-engineer | `prompts.py`, `guide.py` | 150×300 seçilince prompt "150 cm" içerir; "grommet" yalnız kuşgözlü profilde |
| 6 | **Kare kadraj videodan bağımsız**: fotoğraf `frame = 1.0`; `auto_video_kind` bağlılığı kalkar; 9:16 yalnız `_video_start`'ta kırpılır; `proportion.widen` politikası (2.0/10) | image-engineer (bu commit'te `orchestrator.py` sahibi) | `orchestrator.py`, `tests/test_frame.py` | `canli` ve `kamera` ayarında da sağlayıcıya giden oran 1.0 (eski kod 0.562 verir) |
| 7 | **6 sahne görevi + eksikleri tamamla**: `scene_plan(kategori)` → 6 görev; `rapor.json["gorevler"]`; görev başına deneme sınırı; `complete_missing(job)`; `POST /api/eksikleri_tamamla`; arayüz düğmesi; `elenen_*` üzerine yazma sorunu | provider-engineer (orchestrator sahipliği 6'dan sonra devredilir) | yeni `scene_plan.py`, `orchestrator.py`, `app.py`, `ui.html`, `tests/test_tasks.py` | 4 kabul + 2 eksik → tamamla → 6/6, ilk 4 dosyanın md5'i aynı, çağrı sayısı yalnız eksikler kadar (eski davranış 8 foto üretir) |
| 8 | **Paket**: `paket/01-06` görevler + `07-08` bilgi görselleri (byte byte kopya, yeniden üretim yok); `kare_yap()` ayrı, elle tetiklenen işlem, orijinale dokunmaz | image-engineer | yeni `package.py`, `tests/test_package.py` | kopya md5 = kaynak; kare olmayan görsele yalnız uyarı; sahte servis çağrısı 0 |
| 9 | e2e testinin güncellenmesi + bağımsız inceleme | ana oturum + quality-reviewer | `tests/test_e2e_mock.py` | tüm testler + `kontrol.py` |

- 1, 2, 3, 4 birbirinden bağımsızdır (farklı dosyalar), paralel yürüyebilir.
- 6 ve 7 sıralıdır: `orchestrator.py` aynı anda tek ajanda olur.
- 6 ve 7'de `rapor.json` şema sürümü artırılır; eski işler okunmaya devam eder ("eski iş" etiketiyle).
- Aşama sonunda: kullanıcı onayıyla **tek bir gerçek sağlayıcı denemesi** (1 ürün, 6 görev), model ve prompt
  sürümü kayıtlı.

### 2.2 Bilinen riskler

- Kare sahneden kamera videosu 1:1 çıkar; video oranı Aşama 4'te karara bağlanır.
- Açılı profil eşikleri sentetik ölçümlerden tahmin; gerçek sahnelerle ayarlanmalı.
- Sağlayıcıların 1:1 desteği tablolarda var (`square_1_1`, `"1:1"`, `1024x1024`) ama resmî belgeden doğrulanmadı.
- `video_composite` / `video_track` kendi algılamasını yapıyor; fotoğraf–video yerleşim farkı Aşama 4'te kapanır.

---

## Aşama 3 — Sahne kütüphanesi

- `sahneler/<kategori>/<ortam>_<aci>/NNN.png` + yerleştirme bilgisi (`.json`: dörtgen/kenar eğrileri, açı, ışık,
  üreten servis, model, prompt sürümü).
- "Sahne hazırla" akışı (ücretli) ile "günlük ürün hazırla" akışı (çoğunlukla ücretsiz) ayrılır.
- Yeni üretilen sahne **insan onayıyla** kütüphaneye girer; günlük üretimde uygun onaylı sahne varsa yeniden
  üretim yapılmaz.
- Sahne, ürün oranına uygunluk etiketi taşır (ör. 0.5 ve 0.375 oranları için ayrı sahneler).
- Referans görseller yalnız stil/kompozisyon rehberi; rakip fotoğrafı teslim çıktısı olamaz.

## Aşama 4 — Tek video

- Ürün başına **1 video**, seçilen tek sahne görevinden, 4–8 sn. `_auto_videos` (fotoğraf başına video) kaldırılır
  veya en fazla 1 ücretsiz türle sınırlanır.
- İlk hedef: sabit kamera, hafif kurdele ve ortam hareketi. Kumaş hareket ederse tasarım kumaşla birlikte
  izlenir (`video_track`), ürün profili ve baskı alanı videoya da geçer.
- Yakınlaşma (kamera) videosu, kurdele hareketli video şartının yerine **sessizce** kabul edilmez; yedeğe
  düşülürse raporda ve arayüzde açıkça yazılır.

## Aşama 5 — Sağlayıcı yaşam döngüsü

- Sağlayıcı iş numarası (`task_id`) `rapor.json`'a, POST'tan hemen sonra yazılır.
- Zaman aşımında önce iş **sorgulanır**; yeni üretim başlatılmaz.
- `_http`: üretim POST'larında yalnız "bağlantı hiç kurulamadı" durumunda yeniden deneme; 5xx/okuma zaman aşımında
  sorgulama.
- Hata sınıfları: kota · kimlik doğrulama · geçersiz istek (400) · geçici servis hatası · kalite reddi.
- Model ve prompt sürümü her görev kaydına; `auto` model keşfi üretimde **sabitlenmiş** modelle değiştirilir;
  model değişikliği örnek ürünlerle karşılaştırmalı değerlendirilir.
- Çağrı sayısı ile parasal maliyet ayrı alanlar; maliyet bilinmiyorsa "bilinmiyor".
- Uç noktalar entegrasyondan önce resmî belgelerden doğrulanır.

## Aşama 6 — Ürün türü genişlemesi

- `product.kind`: `kumas_afis` → `tisort`, `duvar_saati`, `davetiye`, `menu`. Etkinlik kategorisi ayrı alan.
- Ortak: iş takibi, sağlayıcılar, seçici, paket. Türe özel: yerleştirme motoru ve kalite profili.
- Bu aşamaya kadar diğer ürünlerin motorları geliştirilmez.
