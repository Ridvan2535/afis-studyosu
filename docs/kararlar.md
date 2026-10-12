# Karar geçmişi

Önemli kararlar, kısa gerekçeleriyle. En yeni en üstte. Bir karar değişirse eskisi silinmez; yeni satırda
"önceki: K-xx yerine" diye belirtilir. Gizli bilgi yazılmaz.

Biçim: **K-numara · tarih · karar** — gerekçe · etki/geri alma.

---

### 2026-10-13 — Yerleştirme kuralı netleşti: tasarımın bütünlüğü önce

**K-24 · 2026-10-13 · Güçlü kıvrım/katlanmada sahne uygunsuz (`sahne_kivrim`); tasarım zorla deforme edilmez.**
Ölçütler (VARSAYIM, gerçek sahnelerle ayarlanacak): tasarımın baskılı kısmının %0,3'ünden fazlası kumaş dışına düşüyorsa
(`TASMA_ESIK`) ya da kumaş kenarının uydurulan doğrudan sapması (p98) enin %6'sını aşıyorsa (`KIVRIM_ESIK`) red;
%3–6 arası kenar sapması yalnız uyarı (kenarda yan döküm, baskı sığıyorsa kabul). Gerçek iş 20261012-224824'te: 01 kenar
sapması %3,9 → uyarı + kabul (kumaş dışı baskı %0,006), 02 %3,0 → kabul.

**K-23 · 2026-10-13 · Tam kumaş yerleşimi TEK HOMOGRAFİ: tasarım bütün olarak tek düzlem dönüşümüyle yerleşir.**
(kullanıcı kararı) PNG kumaşın her dalgasını izlemez. Kenarlara bant içinde (asılı boyun %10–85'i) sağlam düz doğrular
uydurulur; üst kenar ve zemine temas doğrularıyla dörtgen kurulur; PNG tuvalinin tamamı bu dörtgene tek perspektif
dönüşümüyle oturur (önden: eşit ölçek, oran korunur; açılı: tek perspektif). Fiziksel dikey ölçek, gizli bölge ve ±%3
kuralı (K-16) aynen. Işık/gölge/doku çarpma modeliyle. **Önceki K-18'in (yumuşatılmış satır kenarlarıyla yerleşim) yerine
geçti**: K-18 kopmaları gidermişti ama tasarım kenar eğrisini izlediği için iç geometri hafifçe bükülebiliyordu
(dalgalı kenarda tasarımdaki düz çizgi 1,7–4,2 px bükülüyordu; tek homografide 0,00 px). K-18'in yumuşatılmış kenarları
yalnız tanı/temas hesabında kalır.

### 2026-10-13 — Düzeltmenin uygulama akışında doğrulanması

**K-22 · 2026-10-13 · Yeniden birleştirme sonucu YENİ iş olarak kaydedilir; kaynak iş ve görselleri değişmez.**
Yeni iş adı `<tarih>_yeniden_<kaynak tarih>`; raporda `islem: kayitli_sahnelerden_yeniden_birlestirme`, `kaynak_is`,
`saglayici_cagrisi: 0`, her fotoğrafta `kaynak` (iş/sahne/foto/servis). Seçici (servis karnesi) hiç çalışmaz, karne değişmez.

**K-21 · 2026-10-13 · "Kayıtlı sahnelerden yeniden birleştir" işlemi eklendi (ücretsiz, sağlayıcıya istek yok).**
`Orchestrator.recompose_from_scenes(kaynak_is)`; arayüzde sonuç ekranında düğme; `POST /api/yeniden_birlestir`.
Aynı kuralların uygulanması için sahne değerlendirme + yerleştirme (`_evaluate_scene`) ve kabul kaydı (`_save_accepted`)
generate_photos'tan ortak fonksiyonlara ayrıldı; yeni üretim ve yeniden birleştirme aynı kodu kullanır. Oranı
uyuşmayan tasarımda yeni iş "beklemede" kalır.

### 2026-10-12 — Aşama 2A düzeltmesi: baskıda kopmalar

**K-20 · 2026-10-12 · Yalnız işaret merkezi ölçen testler yeterli değil; süreklilik testi zorunlu.**
`tests/test_sureklilik.py`: pürüzlü kenarlı ve sert ışık bantlı sahnede ince çizgi ve harf benzeri şekiller; dönüşümde
satır ikinci farkı ≤ 1 px, katlanma 0, ince çizgi merkezinde satırdan satıra sıçrama ≤ 1,5 px, kopuk satır 0. Eski kodla
başarısız (ham kenar: 7,98 px; yalnız kıvrım kayması: 2,17 px).

**K-19 · 2026-10-12 · Tam kumaş modunda ışık gradyanından kıvrım kayması KAPALI (`TAM_KUMAS_FOLD_SHIFT = 0`).**
Işık gradyanı kumaş geometrisi değildir; gerçek s01 sahnesinde dönüşümü 1688 pikselde katlayıp W/O harflerinde çift
kontur yaptı. Güvenilir bir kıvrım geometrisi yöntemi gelene kadar 0. Kumaş dokusu ve ışık, çarpma baskı modeliyle
(baskı = sahne × tasarım) aynen korunur. Eski yol (mode=None) 0,01 ile değişmeden kalır.

**K-18 · 2026-10-12 · [K-23 ile yerine geçildi] Kumaş kenarları satır satır değil, yumuşak eğri olarak kullanılır (`KENAR_YUMUSATMA` = boyun %2'si).**
Kök neden: satır bazlı alt-piksel kenar ölçümündeki sıçramalar tasarımı o satırlarda yatay koparıyordu (iş
20261012-224824: s01'de 121, s02'de 42 satır). Temas çizgisi altı temas değeriyle sabitlenip Gauss uygulanır; ham kenarlar
tanı için saklanır. Yerleşim koordinatları (üst kenar, cm ölçeği, asılı boy, gizli bölge) değişmez. Bilinen sınır:
kurdele kumaş kenarını örterse o bölgedeki çentik de yumuşatılarak izlenir.

### 2026-10-12 — Aşama 2A

**K-17 · 2026-10-12 · Yerleşim eşikleri VARSAYIM olarak işaretlendi ve raporlanıyor.**
`ORAN_TOLERANSI` %1 (PNG ↔ kumaş), `TAM_BOY_TOL` %3 (sahnede görünen boy ↔ ürün boyu), `OLCUM_PAYI` %0,5, `GIZLI_EN_FAZLA`
%25, `SPREAD_FRAC` %4, `MUREKKEP_ESIK` %0,1. Sentetik sahnelerle seçildi; gerçek sahnelerle ayarlanmadı.

**K-16 · 2026-10-12 · Dikey ölçek: kumaş sahnede kısa görünürse tasarım SIKIŞTIRILMAZ.**
Bağımsız inceleme (quality-reviewer B1) sonrası. Asılı boy ürün boyundan kısa ise ölçek fizikseldir, görünmeyen alt kısım
gizli bölge sayılır ve mürekkep denetimine girer; %3'ten fazla kısa ve birikme yoksa sahne "havada bitiyor" diye reddedilir.
Ürün boyundan en fazla %3 uzun ise tasarım görünen boya sığdırılır ve bu kullanıcıya UYARI olarak yazılır (sessiz değil);
daha uzunsa red. Gerekçe: "yazıyı yapay olarak yukarı taşıma" ve "oranı bozarak esnetme yok" kuralları.

**K-15 · 2026-10-12 · Zemindeki birikmede baskı varsa sahne başarılı sayılmaz (`birikme_cozulemedi`).**
Birikmedeki kıvrımların üzerinde baskı doğru çizilemiyor. Gizli bölge baskısızsa kabul + uyarı + gizli kısım önizlemesi.

**K-14 · 2026-10-12 · Fotoğraf hattında sahne esnetme (`proportion.widen`) kapalı; algılamada kumaş zorunlu.**
Sahne `bd.detect(hint={"kind":"fabric"})` ile alınır; otomatik sert/kumaş sınıflandırması yerleşimi değiştirmez.
Eski yollar (`compositor` mode=None) video modülleri ve eski işler için korunur.

**K-13 · 2026-10-12 · Fotoğraf kadrajı sabit 1:1.** `auto_video_kind` kadrajı etkilemez (önceki: canlı video seçiliyken
9:16). Video koduna yeni 9:16 zorunluluğu eklenmedi; video oranı sonraki aşamada belirlenecek.

**K-12 · 2026-10-12 · Ürün profili `product.UrunProfili` ve örnek ölçü `Settings.ornek_olcu` = 75×200.**
Ölçü kimlikle seçilir (aynı oranlılar ayrı); ölçü cm değerleri rapora kaydedilir; görünür fiyonk (`gorunur_fiyonk`) ile
fiziksel bağlantı (`fiziksel_baglanti.kusgozu`) ayrı; bilinmeyenler None. Profil her işin `rapor.json`'una kopyalanır.

**K-11 · 2026-10-12 · Tam kumaş modu: PNG tuvali = kumaşın tamamı.** (kullanıcı kararı) Kenar payı, içeri küçültme,
kırpma, ortalama ve oran bozan esneme yok. Yatayda kumaşın gerçek kenarları, dikeyde fiziksel ölçek (px/cm = en).

**K-10 · 2026-10-12 · Oran uyuşmazlığında üretim BEKLETİLİR.** (kullanıcı kararı) Uyarı + önizleme; hiç ücretli çağrı
yapılmaz (arayüz/app ve orkestratör iki katmanda). **Önceki öneri "(A) sahne esnetmeyi kapat / (B) %15 esnetme" ve
CLAUDE.md'deki "baskı alanına oranı koruyarak sığdır" kuralının yerine geçti.**

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

### Aşama 2 için önerilen kararlar (Aşama 1'de yazılmıştı) — durum
- Fotoğraf kadrajı sabit 1:1 → **K-13 ile uygulandı** (9:16 video kırpması yerine "video oranı sonra belirlenecek").
- Kumaş ürününde yerleşim her zaman kumaş yolundan → **K-14 ile uygulandı**; "baskı alanı profilden" yerine tam kumaş (K-11).
- Oran uyuşmazlığında (A)/(B) seçimi → **yanıtlandı: K-10** (ne esnetme ne sığdırma; üretim bekletilir).
