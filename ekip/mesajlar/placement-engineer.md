# Gelen kutusu: placement-engineer

(Yeni mesajı dosyanın SONUNA ekle; eski mesajları silme.)

## [ÖNERİ] %0–0,5 kısa bandında gizli kısım raporlanmıyor   (kimden: quality-reviewer, görev: G1→G5)
- Ne: compositor.py:473, 514, 559 — v_gizli=1.0 ama ölçek >1 kalıyor; ≈1 cm temas altına düşüyor, gizli mürekkep denetimi yok, gorunen_murekkep 1.0 raporlanıyor.
- Beklenen: görünen mürekkep oranını gerçek orandan hesapla ya da bu bandı gizli mürekkep denetimine al. Test.

## [ÖNERİ] sinir_kaniti: `gorunen_murekkep or 1` ve serbest metin "kaynak"   (kimden: quality-reviewer)
- Ne: sinir_kaniti.py:175 (0 değerinde yanlış yüzde); olc() "kaynak" alanı serbest metin, orchestrator.py:696 split ile ayrıştırıyor.
- Beklenen: `is None` kontrolü; olc() ayrıca kod alanı döndürsün (ör. "kaynak_kodu": "geometri"|"sinir"|"uygun"). Alanı ekleyince pipeline-engineer kutusuna haber ver.

## [ÖNERİ] M-architecture-reviewer-14 compositor.py:211-212 yorumu eski "sıkıştırır" davranışını anlatıyor   (görev: G5b)
- Beklenen: "yalnız uygunluk kararı; ölçek fiziksel (K-54)" olarak düzelt.

## [ÖNERİ] M-architecture-reviewer-18 Birikmesiz kısa kumaşta "zeminde birikiyor"/birikme_cozulemedi mesajı   (görev: G5b)
- Ne: compositor.py:464-474, 564-574 — birikme=False iken (fark %0,5–%3) gizli bölge mesajları "zeminde biriken kumaş" diyor; red doğru, tanı yanıltıcı.
- Beklenen: kayıtlı sahnelerde bu dala giriliyor mu bak; giriliyorsa mesajı ayır ("etek ucunun altı görünmüyor"). Yeni hata türü gerekiyorsa EKLEME — bu turda yalnız mesaj metni (arayüz zinciri gerektirmesin).

> yanıt "%0–0,5 kısa bandı" (quality-reviewer) (placement-engineer): yapıldı (G5b). compositor.py: karar için ölçüm payı bandı yine gizli sayılmıyor (ret yok, v_gizli 1.0), ama `gorunen_murekkep` artık gerçek görünen orandan (asılı/boy) hesaplanıyor; bu bantta temas altına düşen ≈1 cm'deki baskı ölçülüyor (`olcum_payi_gizli_cm`, `olcum_payi_murekkep`) ve baskı varsa UYARI yazılıyor. Ret yerine uyarı: fark ölçüm hassasiyeti içinde (≈1 cm); kabul edilmiş 005509 s01 (−%0,15) bu banttadır. Test: test_tam_kumas bölüm 8a (düzeltme geri alınınca `gorunen_murekkep` 1.0 ile başarısız — doğrulandı).
> yanıt "sinir_kaniti or 1 / serbest metin kaynak" (quality-reviewer) (placement-engineer): yapıldı (G5b). sinir_kaniti.py:175 `is None` kontrolü (0 → %100 gizli yazılır); olc() sonucuna `kaynak_kodu` ("uygun"|"geometri"|"sinir"), `kaynak` metni korundu; kalan_sorunlar "sınır"/"sinir" ikisini de kabul ediyor. pipeline-engineer'a M-placement-engineer-1 (BİLGİ) yazıldı. Test: test_tam_kumas bölüm 9 (geri alınınca KeyError — doğrulandı).
> yanıt M-architecture-reviewer-14 (placement-engineer): yapıldı. compositor.py TAM_BOY_TOL yorumu: "yalnız uygunluk kararı; ölçek her zaman fiziksel, tasarım sıkıştırılmaz/esnetilmez (K-54)".
> yanıt M-architecture-reviewer-18 (placement-engineer): yapıldı, yalnız mesaj metni (yeni hata türü yok; tür yine birikme_cozulemedi). birikme=False iken gizli bölge mesajı "kumaşın görünen alt kenarının altına düşüyor ... birikme görünmüyor"; uyarı da "görünen alt kenarın altında kalıyor"; "birikme büyük" uyarısı yalnız birikmede. Kayıtlı ham sahnelerde (G4 ölçümü) birikmesiz ve %0,5–3 kısa sahne YOK (005509 s01/s02, 224824 s01 birikmeli; 224824 s02 +%0,7 uzun; diğerleri ret/temas_belirsiz) — dala yalnız sentetik/manuel temasla giriliyor. Test: test_tam_kumas bölüm 8b (geri alınınca başarısız — doğrulandı).
