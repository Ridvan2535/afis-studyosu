# Görev panosu

Panoyu yalnız koordinatör günceller; ajanlar durumu son yanıtlarında bildirir. Ayrıntı ve haberleşme: `ekip/PROTOKOL.md`.

## Tur 1 — 2026-10-13 (ücretli çağrı yok; yeni üretim yok)

| No | Görev | Sahibi | Bağımlılık | Durum |
|---|---|---|---|---|
| G1 | Bugünkü değişikliklerin (commit cb0ca76..adb1d82; K-49…K-56) bağımsız incelemesi: kök neden, kapsam dışı davranış, regresyon testlerinin anlamlılığı. Bulgular sahibine göre. | quality-reviewer | — | bitti (koşullu onay; 3 HATA → G5a) |
| G2 | Mimari: sahiplik tablosunun kod sınırlarıyla uyumu (ortak/çakışan dosyalar), CLAUDE.md ↔ kod çelişkileri (K-54 sonrası). | architecture-reviewer | — | bitti (24 bulgu; protokol düzeltildi; 6 madde Tur 2'ye) |
| G3 | 224824 `elenen_01_04` sahnesinde algılamanın çok küçük (%1,3) bölge seçmesini incele; genel bir algılama hatasıysa düzelt + kalıcı regresyon örneği; kabul edilen sahneleri koru. | detection-engineer | — | bitti |
| G4 | `BIRIKME_BANT_EN_FAZLA` (%15, VARSAYIM) duyarlılık analizi: mevcut bütün ham sahnelerde bant oranları, %10–%20 aralığında hangi kararların değiştiği. Kanıt yoksa eşiğe dokunma; rapor yaz. | placement-engineer | — | bitti |
| G5a | Kurtarma döngüsü (ok+kararlı), video yeniden yerleşim tutarlılığı, bütçe sayımı (3 HATA) + VARSAYIM etiketleri, manuel_sinir doğrulama, sessiz varyant performansı, rapor yolları "/" | pipeline-engineer | G1, G2 | bitti |
| G5b | %0–0,5 kısa bandında gizli kısım, sinir_kaniti kod alanı + `is None`, eski yorum, birikmesiz "birikiyor" mesajı | placement-engineer | G1, G2 | bitti (karar bekleyen: ölçüm payı bandında gizli baskı uyarı mı ret mi) |
| G5c | VARSAYIM etiketleri, tespit_maskeden delik oranı, test geri yükleme (try/finally) | detection-engineer | G1 | bitti |
| G5d | "Elenen ham" kutusu varsayılan işaretsiz; kontrol.py hata mesajı düzeltmesi + test | ui-engineer | G1, G2 | bitti |
| G6 | Bütün testleri çalıştır, başarısızlıkları sahiplerine bildir. | test-runner | G3, G4, G5a–d | bitti (27/27 TAMAM; son 4'ü koordinatör çalıştırdı — ajan oturum sınırına takıldı) |
| G7 | durum.md / kararlar.md güncelle (Tur 1 sonuçları, ekip yapısı K-57). | docs-writer | G6 | kısmen (kararlar K-57…K-60 ve durum.md yazıldı; ajan oturum sınırına takıldı — architecture.md/roadmap.md/README güncellemesi Tur 2'ye) |
| G8 | Commit, cihaza yazma, kullanıcıya rapor. | koordinator | G7 | bitti |

## Tur 2 birikimi (bu tura alınmadı)
- architecture-reviewer 1, 2, 3, 5, 12, 13 (kurtarma/kutu denetimini banner_detect'e taşıma; tk_info sabit liste ve layout hata kodu; sade_neden metin eşleşmesi; video bölümünü ayrı modüle; pipeline.py eski yerleşim yolu; 9:16 video).
- G3 notu: 224824 elenen_01_04'ün asıl reddi "asılı ≈119 cm" ölçümüydü; ham görüntü yok, karar verilemedi.
- G4 notu: %15 eşiği %10–%18 aralığında karar değiştirmiyor; gerçek birikmeli ham örnek az (3).
- G7 kalanı: docs/architecture.md (§6, 93/97/179-181), docs/roadmap.md (12, 54-61) eski image-engineer/"sığdır" anlatımı; README pipeline.py uyarısı.
- K-59 kullanıcı kararı: ölçüm payı bandında gizli baskı uyarı mı ret mi.
