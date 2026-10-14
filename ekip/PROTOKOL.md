# Geliştirme ekibi — görev dağılımı ve haberleşme protokolü (K-57)

Bu klasör **geliştirme** ekibinin çalışma alanıdır. Uygulamanın kendisi (app.py, orchestrator.py...) bu ajanları ÇAĞIRMAZ;
uygulamanın otomatik görsel kontrol servisi (`gorsel_kontrol_servisi.py`) ayrı bir modüldür (K-50).

## Roller ve dosya sahipliği
Her dosyanın TEK sahibi vardır. Sahibi olmayan ajan dosyayı DÜZENLEMEZ; değişiklik isteğini sahibine mesajla yollar.

| Ajan | Tür | Sahip olduğu dosyalar (yalnız bunları düzenler) | Kendi testleri |
|---|---|---|---|
| `koordinator` (ana oturum; mesajlarda `main` adıyla da ulaşılır) | yönetir | `ekip/pano.md`, `ekip/PROTOKOL.md`, `.claude/agents/*`, `ajanlar_kurulum/*`, `CLAUDE.md`, `.gitignore`, `PROJE_NOTLARI.md` (dondurulmuş), git commit, kullanıcıya rapor | — |
| `detection-engineer` | yazar | `banner_detect.py`, `geri_cevir.py` | test_algilama_kurtarma, test_farkli_ortamlar (entegrasyon; yerleşim/kayıt beklentisi değişikliği ilgili sahibin isteğiyle) |
| `placement-engineer` | yazar | `compositor.py`, `layout.py`, `proportion.py`, `ribbon.py`, `guide.py`, `cvio.py`, `sinir_kaniti.py`, `product.py` (HATA_TURLERI dahil) | test_tam_kumas, test_duzlem_yerlesim, test_sureklilik, test_product |
| `pipeline-engineer` | yazar | `orchestrator.py` (video bölümü video-engineer'ın isteğiyle değişir), `deneme_kayit.py`, `gorsel_kontrol_servisi.py`, `prompt_yapisi.py`, `prompts.py`, `pipeline.py`, `test_paketi.*`, `gorsel_kontrol/*.py` + `ornek_plani.json`, `tests/kontrol_ornekleri/` (diğerleri örnek eklemeyi mesajla ister ya da kendi eklediği yeni `is_*` klasörünün sahibi olur) | test_deneme_kayit, test_durma_ve_karsilastirma, test_yeniden_birlestir, test_kontrol_ornekleri, test_manuel_sinir, test_gorsel_kontrol, test_kare_kadraj, test_unicode_path, izle_kucultme_kararliligi |
| `provider-engineer` | yazar | `providers.py`, `selector.py`, `mock_provider.py`, `refstore.py`, `make_test_scenes.py` | test_selector, test_refstore, test_magnific_fix, test_topview, test_e2e_mock (entegrasyon) |
| `ui-engineer` | yazar | `app.py`, `ui.html`, `baslat.bat`, `kur.bat`, `kontrol.py` (kurulum testi), `requirements.txt` | test_elenen_arayuz, test_manuel_sinir_tarayici |
| `video-engineer` | yazar | `video_*.py`, `camera_move.py` | test_video_*, test_camera_move |
| `test-runner` | yalnız çalıştırır | `ekip/raporlar/test_*.md`, `ekip/raporlar/test-runner.md` | bütün `tests/` |
| `docs-writer` | yazar | `docs/*.md`, `README.md`, `KURULUM_REHBERI.md`, `scene_prompts.md` | — |
| `quality-reviewer` | salt okunur | — (raporunu koordinatöre mesajla verir) | — |
| `architecture-reviewer` | salt okunur | — | — |
| `visual-inspector` | salt okunur | — (okuma kapsamı: yalnız `gorsel_kontrol/paket`, `rehber`; bağımsız kalması için gelen kutusu YOK) | — |

Her test dosyasının tablodaki TEK sahibi vardır. Birden çok modülü sınayan "entegrasyon" testlerinde, başka bir sahibin
modülüyle ilgili beklenti değişikliği o sahibin mesajla isteğiyle yapılır. Her ajan `ekip/raporlar/<ajan>.md` raporunun sahibidir.

**Arayüz değişikliği zinciri:** bir hata türü / kayıt alanı / mesaj kodu eklenirken sıra: placement (veya detection) →
pipeline → ui → docs. Her halka bir sonrakine mesaj yazar.

## Haberleşme
1. **Pano** (`ekip/pano.md`): görevler (No · görev · sahibi · bağımlılık · durum). Eşzamanlı yazma kaybını önlemek için
   panoyu YALNIZ koordinatör günceller; ajan, görev durumunu son yanıtında bildirir.
2. **Gelen kutusu** (`ekip/mesajlar/<ajan>.md`): iş/bulgu iletmek için alıcının dosyasının SONUNA ekle; mevcut satır
   silinmez/düzenlenmez. Her mesajın kimliği vardır:
   ```
   ## [ÖNEM] M-<gönderen>-<n> <kısa konu>   (görev: <No>)
   - Ne: ... (dosya:satır kanıtı)
   - Beklenen: ...
   ```
   ÖNEM: `ENGEL` (iş durur) · `HATA` · `ÖNERİ` · `BİLGİ`. Yanıt da dosyanın SONUNA eklenir: `> yanıt M-<...> (<ajan>): yapıldı / yapılmadı + neden`.
3. Her ajan işe başlarken kendi gelen kutusunu okur, açık (yanıtsız) mesajları işler.
4. Koordinatöre ulaşmanın tek yolu: ajanın son yanıtı (özet + açık istekler). Acil durumda `ekip/mesajlar/koordinator.md`'ye ekler.
   Koordinatör bağımlı ajanı başlatır/devam ettirir ve mesajları aktarır.
5. Salt okunur ajanlar (quality-reviewer, architecture-reviewer) dosya yazmaz: bulgularını yanıtlarında verir, koordinatör
   ilgili gelen kutularına aktarır.
6. Bitiş: her yazar ajan `ekip/raporlar/<ajan>.md` yazar: değişen dosyalar, neden, çalıştırdığı testler ve gerçek çıktıları,
   doğrulanamayanlar.
7. Yazar ajanlar aynı anda çalışabilir ama yalnız kendi dosyalarına yazar; uzun testleri sırayla çalıştırır.

## Ortak kurallar (CLAUDE.md'den, hepsi için)
- Ücretli API/model/görsel/video çağrısı YOK. Ağ YOK.
- `ayarlar.json`, `raporlar/*.zip` açılmaz; anahtar, gizli bağlantı, base64 yazılmaz.
- Kaynak iş klasörleri ve eski çıktılar DEĞİŞTİRİLMEZ (okunabilir).
- Eşik yalnız sonuç geçirmek için gevşetilmez; her eşik "VARSAYIM" diye işaretlenir ve gerekçelendirilir.
- Hata düzeltmesine regresyon testi eşlik eder; test, düzeltme geri alınınca başarısız olmalı.
- "Test edildi" = yerel / sahte servis / gerçek sağlayıcı ayrımı; Windows'ta çalıştırılmayan test Windows'ta geçmiş sayılmaz.
- Git commit'i yalnız koordinatör yapar. Ajanlar `git` ile durum/diff okuyabilir, commit/checkout/reset yapamaz.
- Uzun testleri aynı anda çok sayıda çalıştırma (bellek). Kendi testlerini sırayla çalıştır.
