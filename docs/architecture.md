# Afiş Stüdyosu — Mimari

Son güncelleme: 2026-10-12 (Aşama 1). Güncel gereksinimler `CLAUDE.md`'dedir. Bu belge **bugünkü** yapıyı,
**hedef** yapıyı ve aradaki farkı anlatır. Ayrıntılı bulgu kanıtları: `docs/inceleme_2026-10-12.md`.

---

## 1. Bugünkü yapı (kısa)

| Modül | Bugünkü sorumluluk |
|---|---|
| `app.py` | Yerel HTTP sunucusu (`http.server`), tek iş çalıştıran `Runner`, `/api/*` uçları, `ui.html`'i sunar |
| `orchestrator.py` | İş klasörü, fotoğraf döngüsü, 4 video türü, `rapor.json`, hata raporu zip'i |
| `prompts.py` | Kategori sahne havuzu, ışık, sabit prompt metinleri, `size_for`, `frame_aspect`, video promptları |
| `providers.py` | `Settings`, `_http` (yeniden deneme + hata sınıfı), Magnific/OpenAI/Gemini/TopView/Veo/Kling adaptörleri |
| `selector.py` | Thompson örneklemesiyle otomatik servis seçimi, `servis_karnesi.json` |
| `banner_detect.py` | Sahnede boş afişi bulma, `rigid`/`fabric` sınıflandırma, boşluk kapısı |
| `layout.py` | Afiş geometrisi ölçümü, önden görünüm kapısı (`check`), geometri puanı (`score`) |
| `compositor.py` | Tasarımı afişe basma: `_place_rigid` (homografi) veya `_place_fabric` (kıvrımlı ağ) |
| `proportion.py`, `guide.py`, `ribbon.py` | Sahne genişletme, kılavuz görsel, kurdeleyi baskının üstüne geri koyma |
| `video_*.py`, `camera_move.py` | Kamera videosu, canlı video izleme/onarım, kompozit video |
| `refstore.py` | Kategori bazlı referans görsel deposu (stil rehberi) |

Bir iş bugün şöyle akar:

```
yükleme → generate_photos (n adet "daha") ──┐
   her deneme: pick servis → prompt → sahne → algıla → önden kapı → (gerekirse sahneyi genişlet) → puan
   kabul: composite → kurdele geri koy → foto/NN_<rigid|fabric>.jpg     ret: sahneler_bos/elenen_NN.jpg
   → (auto_video açıksa her fotoğraf için video)
```

Kalıcı bir durum makinesi yoktur; durum `rapor.json` içeriğinden ve bellekteki `Runner`'dan çıkarılır.
Uygulama kapanırsa sağlayıcıda süren iş kaybolur.

---

## 2. Doğrulanan bulgular (Aşama 1)

Sınıflar: **H** = doğrulanmış hata · **Ç** = gereksinim çelişkisi (kod kendi niyetine göre doğru, güncel gereksinime aykırı)
· **A** = araştırılması gereken konu.

| # | Bulgu | Sınıf | Ana kanıt | Durum |
|---|---|---|---|---|
| 1 | Canlı video türü seçiliyse fotoğraf kadrajı 9:16'ya zorlanıyor; `auto_video` kapalı olsa bile (varsayılan tür `canli` olduğundan **varsayılan ayarla her iş 9:16**). 1:1 kadraj hiç yok. | Ç | `orchestrator.py:192-194`, `providers.py:75`, `prompts.py:243-248` | Aşama 2 |
| 2 | Prompt "perfectly FRONTAL, NOT angled" diyor; kalite kapısı taper/kenar eğimi/yan oranla açılı sahneyi eliyor. Hafif yandan görünüm üretilemiyor. | Ç | `prompts.py:49-56, 90-97`, `layout.py:92-99`, `providers.py:81` | Aşama 2 |
| 3 | Fiziksel ölçü PNG oranından seçiliyor (`size_for`). **Ek hata:** 50×100 ile 150×300 (0.5) ve 75×200 ile 150×400 (0.375) aynı oran; 150×300 ve 150×400 **asla seçilemiyor**, büyük afiş küçük ölçüyle tarif ediliyor. | Ç + H | `prompts.py:222-240` (yerelde çalıştırılarak doğrulandı: `size_for(0.5) → (50,100)`) | Aşama 2 |
| 4 | `rigid` sınıfında tasarım dört köşeye tam gerilir (±%15 orana kadar **sessizce esnetme**), `fabric` sınıfında paylı sığdırılır. Aynı ürün sahneye göre farklı basılıyor. | Ç | `banner_detect.py:252-265`, `compositor.py:19, 56-64, 88-150, 208-212` | Aşama 2 |
| 5 | `Selector.record` sonucu hem `hist`'e hem `run`'a yazıyor; seçimde `hist + run` toplandığı için bu işin sonuçları iki kez ağırlıklanıyordu. | H | `selector.py` (eski 65-66, 79-82, 91-95) | **Düzeltildi** |
| 6 | `auto_video` açıksa her fotoğraf için video; `canli` türünde fotoğraf başına bir ücretli çağrı. (Varsayılan kapalı.) | Ç | `orchestrator.py:332-354`, `ui.html:263-268` | Aşama 4 |
| 7 | Kalite puanının 100 puanı da geometriden: oran, taper, eğim, yan bakış, boy, ortalama. Baskı sadakati, kurdele, gerçekçilik ölçülmüyor; önden görünümü ödüllendirip açılıyı cezalandırıyor. | Ç | `layout.py:105-119`, `orchestrator.py:300-303, 325-327` | Aşama 2 (profil) + sonra |

Ek bulgular:

| # | Bulgu | Sınıf |
|---|---|---|
| E1 | Arayüzden "eksikleri tamamla" yapılamıyor: `app._start_photos` her seferinde **yeni iş** açıyor; `generate_photos(n)` "n'e tamamla" değil "n tane daha"; tekrar çalıştırmada `elenen_NN.jpg` dosyaları üzerine yazılıyor. | H |
| E2 | 6 sahne görevi (3 ortam × önden/yandan) yapısı ve rapor alanı yok. | Ç |
| E3 | Bağlantı biçimi (kurdele, kuşgözü) kaydı yok; kuşgözü yalnız kılavuzlu prompta giriyor. | Ç |
| E4 | "Kurdelesiz" seçeneği var; gereksinim: tüm sahneler kurdeleli. | Ç (küçük) |
| E5 | Onaylı sahne kütüphanesi yok; boş sahneler yalnız kendi işinde kalıyor. | Ç |
| E6 | Sağlayıcı iş numarası (`task_id`) yalnız bellekte; zaman aşımında yeni ücretli çağrı başlıyor. | Ç |
| E7 | `_http` üretim POST'larını da bağlantı hatası/429/5xx'te 3 kez körlemesine yeniden deniyor (çift iş riski). | Ç |
| E8 | Model `auto` ile çalışma anında "en yeni"ye kayabiliyor; model ve prompt sürümü rapora yazılmıyor. | Ç |
| E9 | Geçersiz istek (400) ile geçici hata aynı sınıf (`ProviderError`). Kalite reddi ayrı ama rapor alanında türü yok. | A |
| E10 | Çağrı sayısı tek gösterge; parasal maliyet alanı yok. | Ç (küçük) |
| E11 | İki bilgi görseli / çıktı paketi kavramı yok. | Ç |
| E12 | Şeffaf alan beyaza oturtuluyor; tasarımdaki **beyaz baskı** ile şeffaf alan ayırt edilemiyor. | A |

### Gereksinim çelişkileri: notlar ↔ güncel gereksinim

| Konu | `PROJE_NOTLARI.md` | Güncel gereksinim (geçerli olan) |
|---|---|---|
| Ölçü | "Afiş oranı tasarımdan gelir" (satır 9) | Fiziksel ölçü, PNG oranı, baskı alanı ayrı; ölçü PNG'den çıkarılmaz |
| Sahne | "Varsayılan: duvara asılı, karşıdan" (20); ayrıca serbest ahşap çerçeve (18) | 3 ortam × önden + hafif yandan; stand yalnız dekor |
| Kuşgözü | "Gerçekte afişte kuşgözü bulunur" (18) | Kuşgözü **opsiyonel**; sahnedeki bağlantı ürün profiline yazılır |
| Kurdele | "Kurdelesiz seçeneği düz çubuk" (19) | Tüm ürün sahneleri kurdeleli |
| Video | "Her fotoğraf için otomatik video" (16; v14'te varsayılan kapatıldı) | Ürün başına tek video, seçilen sahneden |
| Kadraj | "Canlı video açıkken sahneler baştan 9:16" (47, 62) | 6 kare (1:1) ürün görseli; kare kadraj videodan bağımsız |

Notlar silinmedi; geçmiş kayıt olarak kalıyor.

---

## 3. Hedef mimari

Gereksiz katman eklemeden, mevcut modülleri koruyarak. Yeni olan yalnız **ince veri yapıları** ve tek bir
ürün-türü noktasıdır.

| Sorumluluk | Nerede (hedef) | Bugünden farkı |
|---|---|---|
| **Ürün profili**: ölçü (cm), malzeme, bağlantı biçimi, baskı alanı (cm, pay) | yeni `product.py` (dataclass + 5 ölçü tablosu) | Bugün yok; ölçü PNG'den tahmin ediliyor |
| **Tasarım girdisi**: PNG, şeffaflık, oran, çözünürlük (DPI) kontrolü | `compositor.load_design` + yeni `check_design()` | Oran/çözünürlük uyarısı ve "baskı alanına sığdır" önizlemesi eklenecek |
| **Sahne planı**: 6 sabit görev (ortam × açı) | `prompts.py` içinde `scene_plan(category)` | Bugün kategori havuzundan sıradan sahne |
| **Sahne kütüphanesi**: onaylı özgün boş sahneler + yerleştirme bilgisi (dörtgen/kenarlar, açı, ışık) | `refstore.py`'nin yanında `scenelib.py`, klasör `sahneler/<kategori>/<ortam>_<aci>/` | Bugün sahne işte kalıyor |
| **Sağlayıcı adaptörleri** | `providers.py` (değişmez yapı) | İş no + model/prompt sürümü dönüşü, POST güvenli yeniden deneme |
| **Yerleştirme motoru** (ürün türüne özel) | `compositor.py` → kumaş için tek yol | `fabric` zorunlu; baskı alanı profilden |
| **Kalite kontrolü** | `layout.py` (görünüm profilli geometri) + `banner_detect` kapıları + sonra görsel değerlendirme | Profil: `front` / `angled` |
| **İş takibi** | `orchestrator.py` + `rapor.json` içinde `gorevler[]` | Görev durumu, denemeler, dosyalar, sağlayıcı iş no, devam etme |
| **Çıktı paketi**: 6 ürün görseli + 2 bilgi görseli + 1 video | `orchestrator.package()` → `paket/` | Bugün yok |

Gelecek ürün türleri için tek ayrım noktası: `product.kind` (`kumas_afis`, ileride `tisort`, `saat`…). İş takibi,
sağlayıcılar, seçici ortak; **yalnız yerleştirme motoru ve kalite profili türe özel**. Etkinlik kategorisi
(Düğün, Baby shower…) ürün türünden bağımsız bir alandır.

### İki ayrı akış

```
(1) SAHNE HAZIRLAMA  (seyrek, ücretli)                (2) GÜNLÜK ÜRÜN HAZIRLAMA  (günde ~5, çoğunlukla ücretsiz)
kategori + ortam + açı → sağlayıcı → boş sahne         tasarım PNG + ürün profili + kategori
→ algıla + kapı (görünüm profili)                      → sahne planı: 6 görev
→ İNSAN ONAYI → sahne kütüphanesi                      → her görev: kütüphanede uygun onaylı sahne var mı?
                                                            evet → doğrudan yerleştir (API yok)
                                                            hayır → (1)'i tetikle, sonra yerleştir
                                                       → kalite kontrol → paket (6 + 2 bilgi + 1 video)
```

---

## 4. Durum makinesi (hedef)

**İş** (`rapor.json` → `durum`):

```
olusturuldu → planlandi → uretiliyor ⇄ beklemede(eksik) → paketlendi
                              ↓
                           hata (yeniden başlatılabilir; tamamlanan görevler korunur)
```

**Sahne görevi** (`gorevler[i].durum`), her biri bağımsız:

```
bekliyor → sahne_araniyor ─(kütüphanede var)→ yerlestiriliyor → kontrol → tamam
                │                                                  │
                └─(yok)→ uretim_gonderildi(task_id) → uretim_bekleniyor ┘   kontrol başarısız → bekliyor (deneme+1)
                              │ zaman aşımı → SORGULA (yeni üretim başlatma)
                              └ deneme sınırı → basarisiz
```

Kural: `tamam` görev bir daha üretilmez. Devam etme = yalnız `tamam` olmayan görevleri çalıştırmak.

---

## 5. Veri modeli (hedef, `rapor.json` ekleri)

Mevcut alanlar korunur; yeni alanlar eklenir (eski raporlar okunmaya devam eder).

```jsonc
{
  "surum": "0.8",
  "urun": {                                  // ürün profili (kullanıcıdan; uydurulmaz)
    "tur": "kumas_afis",
    "olcu_cm": [75, 200],
    "malzeme": "pamuk-keten",
    "baglanti": {"kurdele": true, "kusgozu": false, "cubuk": "ahşap"},   // sahnede kullanılan biçim
    "baski_alani_cm": {"x": null, "y": null, "w": null, "h": null}      // belirsizse null + uyarı
  },
  "tasarim": {"px": [3000, 8000], "oran": 0.375, "seffaf": true, "sigdirma": "contain", "uyumsuzluk": 0.0},
  "kategori": "Düğün",
  "gorevler": [
    {"id": "g1", "ortam": "kir_dugunu", "isik": "gunduz", "aci": "onden",
     "durum": "tamam", "denemeler": 2, "sahne": "sahneler/dugun/kir_onden/003.png",
     "servis": "magnific-edit-pro", "model": "seedream-v5-pro-edit", "prompt_surum": "p14",
     "saglayici_is_no": "…", "dosya": "foto/g1.jpg", "kalite": {"teknik": 88, "tutarlilik": null}}
    // … g2..g6
  ],
  "bilgi_gorselleri": ["paket/bilgi_1.jpg", "paket/bilgi_2.jpg"],
  "video": {"gorev": "g3", "durum": "yok"},
  "durum": "beklemede"
}
```

---

## 6. Modül sahipliği (ajanlar)

| Dosyalar | Sahip ajan |
|---|---|
| `compositor.py`, `banner_detect.py`, `layout.py`, `proportion.py`, `guide.py`, `ribbon.py`, `cvio.py`, yeni `product.py` (yerleştirme kısmı) | `image-engineer` |
| `providers.py`, `selector.py`, `mock_provider.py`, `refstore.py`, yeni `scenelib.py` | `provider-engineer` |
| `orchestrator.py`, `app.py`, `ui.html`, `prompts.py` | **Ortak** — her aşamada tek sahibi ana oturum belirler |
| Tümü (okuma) | `architecture-reviewer`, `quality-reviewer` |
