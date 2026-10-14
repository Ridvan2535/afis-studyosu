# pipeline-engineer — G5a raporu (2026-10-13)

Ortam: Linux bulut kapsayıcısı, Python 3 (proje .venv değil, sistem Python'u). **Windows'ta çalıştırılmadı.**
Bütün testler yerel / sahte servis testidir; gerçek sağlayıcı ya da Anthropic çağrısı, ağ, git commit YOK.
Ajan türü yüklenemediği için rol tanımıyla genel amaçlı ajan olarak çalışıldı.

## Değişen dosyalar
- `orchestrator.py` — madde 1, 2, 3, 4 (aşağıda)
- `gorsel_kontrol_servisi.py` — madde 3
- `deneme_kayit.py` — `SINIR_KODLARI = ("sınır", "sinir")` (G5b'nin `kaynak_kodu` değeri "sinir" ile eski "sınır" kayıtları aynı sınıflanır)
- `tests/test_kurtarma_akisi.py` (YENİ), `tests/test_manuel_sinir.py`, `tests/test_yeniden_birlestir.py`, `tests/test_deneme_kayit.py`, `tests/test_gorsel_kontrol.py`
- Mesajlar: detection-engineer (M-detection-engineer-1 yanıtı: yeni `_kurtar` sözleşmesi), video-engineer (M-pipeline-engineer-1), ui-engineer (M-pipeline-engineer-1); kendi gelen kutuma bütün yanıtlar.

## 1. Kurtarma döngüsü (HATA) — yapıldı
- Değişiklik: `_kurtar` yerel adaylarda ve servis önerisinde yalnız `ev["ok"] and kararli` adayda döner. Kararlı/kararsız retler
  `bilgi["yerel_adaylar"]` (yeni alanlar: `kararli`, retlerde `tur`) ya da `bilgi["servis"]` (`yeniden_algilama`, `kararli`) kaydına
  yazılır, arama sürer. Hiçbiri kabul edilmezse `(None, sonuc="dogrulanamadi")` -> `_degerlendir_kurtar` ilk değerlendirmenin
  tanısını (tür/neden/tanı görseli) korur, `extra.kurtarma` denenen adayları gösterir. `*_dogru_bolge_ret` sonuç kodları artık üretilmez.
- Neden: K-52 "kararlı ≠ doğru"; yanlış adayın kararlı reddi doğru adayın denenmesini engelliyor ve ilk tanının yerine geçiyordu.
- Etki: `tests/test_algilama_kurtarma.py:163` (detection-engineer'ın) eski sözleşmeyi bekliyor ve şu an BAŞARISIZ. Sözleşme
  detection-engineer'a yazıldı; aynı alt durum `test_kurtarma_akisi::test_servis_onerisi_kararli_ret_ilk_taniyi_degistirmez`'de.

## 2. Video yeniden yerleşim tutarlılığı (HATA) — yapıldı (orchestrator kısmı)
- `_video_tutarlilik(entry, info)`: kayıtta `tam_kumas.dikey_olcek == "temas_cizgisine_kadar"` (eski K-16) ya da yeniden yerleşimde
  `info["sorunlar"]` boş değilse uyarı listesi.
- Kamera videosu (`_video_source`, ücretsiz): bu durumda yeniden basmaz, **kayıtlı fotoğrafı** kullanır (günlükte neden yazılır).
- Ücretli yol (`_video_start` -> `generate_video`): `st["uyari"]`; günlükte "UYARI (video): …", ilerleme metninde "UYARI: …",
  rapor.json video kaydında `uyari`. (Davranış: uyarı; ücretli çağrı engellenmez — görev tanımındaki en küçük güvenli çözüm.)
- Yapılmayan: kompozit/hareketli videoda (`video_composite.py:219`, `video_track.py:201`) tasarım `mode="tam_kumas"` olmadan
  basılıyor — fotoğrafla tutarsızlık kaynağı. video_*.py değiştirilmedi; video-engineer'a M-pipeline-engineer-1 yazıldı.

## 3. Görsel kontrol bütçesi (HATA) — yapıldı
- `orchestrator._kurtar`: servis çağrısı `try/except/finally`; `finally` içinde `butce.kaydet(gks.harcanan_usd(res, butce.tahmini_usd()))`.
  Gerçek kullanım (usage jetonu) varsa ondan; istisna/yanıt yok/kullanım boşsa EN AZ tahmini tutar (0 $ yazılmaz).
- `gorsel_kontrol_servisi`: `_yanit_isle` — JSON çözülemese de `Sonuc(durum=GECERSIZ="gecersiz_yanit", kullanim, tahmini_usd)` döner;
  `tahmini_cagri_usd`, `harcanan_usd`, `Butce.tahmini_usd`; `SahteServis` istisna ve ham metin öğesi alabilir. Servis varsayılan KAPALI (testli).

## 4. Öneriler
- VARSAYIM etiket + gerekçe (davranış değişmedi): `MANUEL_KOSE_ORTUSME` 0,85; IoU 0,7; kutu 0,9/0,5; kararlılık oynaması 0,03.
- 15 px genişletme -> `MANUEL_GENISLETME_ORANI = 0.006` × uzun kenar (tek sayı, en az 3). 2400 px'te 15 px (eski değer; test_manuel_sinir bu çözünürlükte).
- `manuel_sinir`: çizgi sırası (soldan sağa eşlenmiş iki uçta üst < alt; köşe modunda köşelerden), dosya yalnız `sahneler_bos/`
  içinde, görsel okunabilirliği — hepsi **iş klasörü açılmadan**. Ters bölülü yol kabul, raporda "/".
- Sessiz kararlılık varyantlarında sınır kanıtı ve temas karşılaştırması atlanıyor.
- Sınır kanıtı türü: `sk.get("kaynak_kodu")`, yoksa eski `kaynak.split(" ")[0]`. G5b'nin `olcum_payi_gizli_cm`, `olcum_payi_murekkep` alanları tk_info'ya eklendi.
- Rapor yolları: `recompose_from_scenes` `_yol`/`kaynak.dosya` ve `manuel_sinir` `dosya` her zaman "/".

## Testler (güncel kod, sırayla; gerçek son satırlar)
| Test | Sonuç |
|---|---|
| test_kurtarma_akisi | `TAMAM` (7 test) |
| test_manuel_sinir | `5) 7 olumsuz durum: hepsi reddedildi, iş klasörü açılmadı` / `test_manuel_sinir: TAMAM` |
| test_yeniden_birlestir | `test_yeniden_birlestir: TAMAM` |
| test_deneme_kayit | `test_deneme_kayit: TAMAM` |
| test_durma_ve_karsilastirma | `test_durma_ve_karsilastirma: TAMAM` |
| test_gorsel_kontrol | `not: ajanlar_kurulum/visual-inspector.md yok; kopya eşitliği denetlenmedi` / `test_gorsel_kontrol: TAMAM` |
| test_algilama_kurtarma (detection'ın) | **BAŞARISIZ** satır 163 `assert ev2 is not None and … "servis_onerisi_dogru_bolge_ret"` — beklenen; sözleşme değişikliği detection-engineer'a iletildi |
| test_kontrol_ornekleri | `kabul_s01_ham.png … KABUL 0.353 199.5`, `kabul_s02_ham.png … KABUL 0.344 197.1` / `test_kontrol_ornekleri: TAMAM` (005509 s01/s02 kabul) |
| test_e2e_mock (provider'ın) | `anahtar sızıntısı yok, tasarım rapora girmedi` / `test_e2e_mock: TAMAM` |
| test_farkli_ortamlar (ek, entegrasyon) | `224824 kabul_s01_ham.png: kabul, asılı 177.7 cm` / `224824 kabul_s02_ham.png: kabul, asılı 201.4 cm` / `TAMAM` |

Taban çizgisi (değişiklikten önceki kopyada): test_gorsel_kontrol ZATEN başarısızdı — koordinatör `ajanlar_kurulum/visual-inspector.md`'yi
silmiş (çalışma kopyasında), test kopyayla eşitlik bekliyordu. Kopya varsa eşitlik denetimi sürüyor; yoksa not yazılıyor. Koordinatör kopyayı geri koyacaksa denetim kendiliğinden döner.

## Düzeltme geri alınınca başarısız (kanıt)
Proje kopyasında (scratchpad) güncel kod + YALNIZ ilgili satır eski haline, `python -B tests/test_kurtarma_akisi.py`:
- yerel aday seçimi `if dogru:` -> `test_kararli_ret_aramayi_bitirmez_kabul_secilir: kararlı ret aramayı bitirdi`, `test_hicbiri_kabul_degil_ilk_tani_korunur: ilk tanı yanlış adayın ret nedeniyle değişti: A2 YANLIŞ ADAY RET NEDENİ`
- servis önerisi `if dogru:` -> `test_servis_onerisi_kararli_ret_ilk_taniyi_degistirmez: AssertionError: ÖNERİ BÖLGESİ RET`
- bütçe (eski: yalnız yanıt varsa kaydet) -> `test_butce_hata_ve_bozuk_yanit_sayilir: hata/bozuk yanıt çağrı sayılmadı: 1`
- video kaynağı denetimi kapalı -> `test_video_kaynagi_eski_kayitta_kayitli_foto: eski K-16 kaydında video kaynağı yeniden basıldı`
- `_video_start` uyarısı boş -> `test_ucretli_video_yolunda_gorunen_uyari: AssertionError: []`
- HEAD `gorsel_kontrol_servisi.py` -> `test_claude_servis_bozuk_json_kullanim_doner: AssertionError: None`
- HEAD `orchestrator.py` + yeni test_manuel_sinir -> görsel olmayan dosyada iş açıldıktan sonra `AttributeError: 'NoneType' object has no attribute 'shape'` (test düşer).
- Not: test_yeniden_birlestir'in "/" beklentisi Linux'ta eski kodla da geçer (os.path.join zaten "/"); fark yalnız Windows'ta görünür, Windows'ta çalıştırılmadı.

## Yapılmayanlar
- `_kurtar` aday listesinin ilk algılamadan yeniden kullanımı (performans önerisinin ikinci yarısı): ilk algılama aday listesi döndürmüyor; banner_detect arayüzü gerekir — Tur 2 madde 1 ile birlikte.
- Kompozit/hareketli video tam kumaş yerleşimi: video-engineer'ın dosyaları (mesaj yazıldı).
- `gorsel_kontrol_kullanim.json` .gitignore: koordinatörün dosyası.
- Tur 2 maddeleri (M-koordinator-2): dokunulmadı.
- Ücretli video yolunda tutarsızlıkta çağrıyı engellemek yerine uyarı verildi (görev tanımı); engelleme istenirse küçük bir değişiklik.
