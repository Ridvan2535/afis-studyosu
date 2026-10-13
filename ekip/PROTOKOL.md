# Geliştirme ekibi — görev dağılımı ve haberleşme protokolü (K-57)

Bu klasör **geliştirme** ekibinin çalışma alanıdır. Uygulamanın kendisi (app.py, orchestrator.py...) bu ajanları ÇAĞIRMAZ;
uygulamanın otomatik görsel kontrol servisi (`gorsel_kontrol_servisi.py`) ayrı bir modüldür (K-50).

## Roller ve dosya sahipliği
Her dosyanın TEK sahibi vardır. Sahibi olmayan ajan dosyayı DÜZENLEMEZ; değişiklik isteğini sahibine mesajla yollar.

| Ajan | Tür | Sahip olduğu dosyalar (yalnız bunları düzenler) | Kendi testleri |
|---|---|---|---|
| `koordinator` (ana oturum) | yönetir | `ekip/pano.md`, `CLAUDE.md`, git commit, kullanıcıya rapor | — |
| `detection-engineer` | yazar | `banner_detect.py`, `kontrol.py` | test_algilama_kurtarma, test_farkli_ortamlar (algılama kısmı) |
| `placement-engineer` | yazar | `compositor.py`, `layout.py`, `proportion.py`, `ribbon.py`, `guide.py`, `cvio.py`, `sinir_kaniti.py`, `product.py` | test_tam_kumas, test_duzlem_yerlesim, test_sureklilik, test_kare_kadraj, test_product |
| `pipeline-engineer` | yazar | `orchestrator.py`, `deneme_kayit.py`, `gorsel_kontrol_servisi.py`, `prompt_yapisi.py`, `prompts.py`, `pipeline.py` | test_deneme_kayit, test_durma_ve_karsilastirma, test_yeniden_birlestir, test_kontrol_ornekleri, test_manuel_sinir, test_gorsel_kontrol |
| `provider-engineer` | yazar | `providers.py`, `selector.py`, `mock_provider.py`, `refstore.py` | test_selector, test_refstore, test_magnific_fix, test_topview, test_e2e_mock |
| `ui-engineer` | yazar | `app.py`, `ui.html`, `baslat.bat`, `kur.bat` | test_elenen_arayuz, test_manuel_sinir_tarayici, test_unicode_path |
| `video-engineer` | yazar | `video_*.py`, `camera_move.py` | test_video_*, test_camera_move |
| `test-runner` | yalnız çalıştırır | `ekip/raporlar/test_*.md` | bütün `tests/` |
| `docs-writer` | yazar | `docs/durum.md`, `docs/kararlar.md`, `docs/*.md` | — |
| `quality-reviewer` | salt okunur | — (raporunu koordinatöre mesajla verir) | — |
| `architecture-reviewer` | salt okunur | — | — |
| `visual-inspector` | salt okunur | — (yalnız `gorsel_kontrol/paket` ve `rehber`) | — |

Test dosyası, test ettiği modülün sahibine aittir. Ortak dosyaya (ör. `tests/kontrol_ornekleri/`) yeni örnek ekleyen
sahibi `ekip/pano.md`'de duyurur.

## Haberleşme
1. **Pano** (`ekip/pano.md`): görevler; No · görev · sahibi · bağımlılık · durum (bekliyor / sürüyor / bitti / engelli).
   Durumu yalnız görevin sahibi değiştirir (yalnız kendi satırını).
2. **Gelen kutusu** (`ekip/mesajlar/<ajan>.md`): bir ajana iş/bulgu iletmek için o ajanın dosyasının SONUNA ekle
   (asla mevcut satırı silme/düzenleme). Biçim:
   ```
   ## [ÖNEM] <kısa konu>   (kimden: <ajan>, görev: <No>)
   - Ne: ... (dosya:satır kanıtı)
   - Beklenen: ... (yanıtı kimin kutusuna yaz)
   ```
   ÖNEM: `ENGEL` (iş durur) · `HATA` · `ÖNERİ` · `BİLGİ`.
3. Her ajan işe başlarken kendi gelen kutusunu okur; bitirirken yanıtladığı mesajın altına `> yanıt (<ajan>): ...` ekler.
4. Ajanlar ayrıca koordinatöre (`main`) kısa mesaj gönderebilir; koordinatör bağımlı ajanı devam ettirir.
5. Bitiş: her yazar ajan `ekip/raporlar/<ajan>.md` yazar: değişen dosyalar, neden, çalıştırdığı testler ve gerçek çıktıları,
   doğrulanamayanlar.

## Ortak kurallar (CLAUDE.md'den, hepsi için)
- Ücretli API/model/görsel/video çağrısı YOK. Ağ YOK.
- `ayarlar.json`, `raporlar/*.zip` açılmaz; anahtar, gizli bağlantı, base64 yazılmaz.
- Kaynak iş klasörleri ve eski çıktılar DEĞİŞTİRİLMEZ (okunabilir).
- Eşik yalnız sonuç geçirmek için gevşetilmez; her eşik "VARSAYIM" diye işaretlenir ve gerekçelendirilir.
- Hata düzeltmesine regresyon testi eşlik eder; test, düzeltme geri alınınca başarısız olmalı.
- "Test edildi" = yerel / sahte servis / gerçek sağlayıcı ayrımı; Windows'ta çalıştırılmayan test Windows'ta geçmiş sayılmaz.
- Git commit'i yalnız koordinatör yapar. Ajanlar `git` ile durum/diff okuyabilir, commit/checkout/reset yapamaz.
- Uzun testleri aynı anda çok sayıda çalıştırma (bellek). Kendi testlerini sırayla çalıştır.
