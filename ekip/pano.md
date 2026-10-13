# Görev panosu

Durumu yalnız görevin sahibi değiştirir (kendi satırı). Ayrıntı ve haberleşme: `ekip/PROTOKOL.md`.

## Tur 1 — 2026-10-13 (ücretli çağrı yok; yeni üretim yok)

| No | Görev | Sahibi | Bağımlılık | Durum |
|---|---|---|---|---|
| G1 | Bugünkü değişikliklerin (commit cb0ca76..adb1d82; K-49…K-56) bağımsız incelemesi: kök neden, kapsam dışı davranış, regresyon testlerinin anlamlılığı. Bulgular sahibine göre. | quality-reviewer | — | bekliyor |
| G2 | Mimari: sahiplik tablosunun kod sınırlarıyla uyumu (ortak/çakışan dosyalar), CLAUDE.md ↔ kod çelişkileri (K-54 sonrası). | architecture-reviewer | — | bekliyor |
| G3 | 224824 `elenen_01_04` sahnesinde algılamanın çok küçük (%1,3) bölge seçmesini incele; genel bir algılama hatasıysa düzelt + kalıcı regresyon örneği; kabul edilen sahneleri koru. | detection-engineer | — | bekliyor |
| G4 | `BIRIKME_BANT_EN_FAZLA` (%15, VARSAYIM) duyarlılık analizi: mevcut bütün ham sahnelerde bant oranları, %10–%20 aralığında hangi kararların değiştiği. Kanıt yoksa eşiğe dokunma; rapor yaz. | placement-engineer | — | bekliyor |
| G5 | G1/G2 bulgularından kendi dosyalarına düşenleri uygula (her sahip kendi gelen kutusundan). | ilgili sahipler | G1, G2 | bekliyor |
| G6 | Bütün testleri çalıştır, başarısızlıkları sahiplerine bildir. | test-runner | G3, G4, G5 | bekliyor |
| G7 | durum.md / kararlar.md güncelle (Tur 1 sonuçları, ekip yapısı K-57). | docs-writer | G6 | bekliyor |
| G8 | Commit, cihaza yazma, kullanıcıya rapor. | koordinator | G7 | bekliyor |
