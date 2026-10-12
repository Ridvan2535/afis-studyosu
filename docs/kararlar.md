# Karar geçmişi

Önemli kararlar, kısa gerekçeleriyle. En yeni en üstte. Bir karar değişirse eskisi silinmez; yeni satırda
"önceki: K-xx yerine" diye belirtilir. Gizli bilgi yazılmaz.

Biçim: **K-numara · tarih · karar** — gerekçe · etki/geri alma.

---

### 2026-10-12 — Aşama 1

**K-09 · 2026-10-12 · Aşama sonu belgeleri: `docs/durum.md` ve `docs/kararlar.md`.**
Kullanıcı projeyi Codex ile de değerlendiriyor; iki araç aynı klasörü okuyor. Her aşama sonunda durum belgesi
güncellenir, önemli kararlar buraya eklenir.

**K-08 · 2026-10-12 · Aşama 2, fiziksel ürün soruları yanıtlanmadan başlamaz.**
Baskı alanı, kuşgözü ve üst kenar yapısı yerleştirmeyi doğrudan belirliyor; uydurulmamalı (`CLAUDE.md`).
Sorular: `docs/durum.md` §4.

**K-07 · 2026-10-12 · Ajan dosyaları `ajanlar_kurulum/` klasörüne konur, kullanıcı `ajanlari_kur.bat` ile kurar.**
Uzaktan bağlantı `.claude/` klasörüne yazmaya izin vermiyor. Kurulumdan sonra Claude Code yeniden açılmalı.

**K-06 · 2026-10-12 · Yedekleme: Git yerine `_yedek/` (zip + Git bundle).**
Kullanıcının klasöründe Git yok ve uzaktan komut çalıştırılamıyor. Çalışma Claude'un alanındaki Git deposunda
yapılıyor; değişiklikten önce kaynak zip'i, sonra bundle bilgisayara yazıldı. `ayarlar.json`, log, karne, iş
çıktıları yedeğe ve Git'e girmez (`.gitignore`).

**K-05 · 2026-10-12 · Selector düzeltmesinde `SELECTOR_VERSION` artırılmadı.**
`save()` yalnız `hist`'i yazdığı için `servis_karnesi.json`'da çift sayım hiç oluşmamıştı. Sürümü artırmak
kullanıcının doğru öğrenilmiş servis verisini sıfırlardı. quality-reviewer onayladı.

**K-04 · 2026-10-12 · Selector seçim hesabı yalnız `hist` kullanır; `run` raporlama içindir.**
`hist` zaten "kalıcı karne + bu iş" toplamı. Thompson formülü, keşif oranı, ardışık hata sınırı, kayıt biçimi
değiştirilmedi (kapsam dışı davranış değişikliği yok). Test eşiği 380 → 330 (doğru beklenen ≈ 358/400).
Geri alma: `_yedek/` zip'indeki `selector.py`.

**K-03 · 2026-10-12 · Mevcut çatı korunur: `app.py` (`http.server`) + `ui.html` + `baslat.bat`.**
Gereksiz framework değişikliği yok; yeni sorumluluklar ince modüllerle eklenir (`product.py`, `scene_plan.py`,
`package.py`, ileride `scenelib.py`).

**K-02 · 2026-10-12 · Güncel gereksinimler `CLAUDE.md`'dedir; `PROJE_NOTLARI.md` geçmiş kaydıdır.**
Çelişkiler sessizce silinmez, `docs/architecture.md` §2'de tabloya yazılır (kuşgözü, kurdelesiz seçenek,
duvar/stand, 9:16 kadraj, fotoğraf başına video, ölçünün PNG'den türetilmesi).

**K-01 · 2026-10-12 · Hedef mimari: sahne hazırlama ile günlük ürün hazırlama ayrılır; ürün türü etkinlik
kategorisinden ayrıdır.**
Onaylı sahneler kütüphanede tekrar kullanılır, günlük üretimde gereksiz ücretli çağrı olmaz. Gelecek ürünler
(tişört, saat, davetiye, menü) için yalnız yerleştirme motoru ve kalite profili türe özel olur.

### Aşama 2 için önerilen, henüz onaylanmamış kararlar
- Fotoğraf kadrajı sabit 1:1; 9:16 yalnız video aşamasında kırpılır.
- Kumaş ürününde yerleşim her zaman kumaş yolundan; baskı alanı ürün profilinden.
- Oran uyuşmazlığında sahne esnetme kapatılır, uymayan sahne yeniden üretilir (seçenek A) — **kullanıcı kararı bekleniyor.**
