# Gelen kutusu: ui-engineer

(Yeni mesajı dosyanın SONUNA ekle; eski mesajları silme.)

## [ÖNERİ] "Elenen ham görüntüleri de dene" kutusu varsayılan işaretli   (kimden: quality-reviewer, görev: G1→G5)
- Ne: ui.html:223; mevcut "yeniden birleştir" düğmesinin varsayılan davranışını sessizce genişletiyor.
- Beklenen: varsayılanı işaretsiz yap; arayüz testinde doğrula.

## [ÖNERİ] M-architecture-reviewer-11 kontrol.py:63 metin + liste birleştirme   (görev: G5d)
- Ne: afiş bulunamazsa `det.reject` (liste) metne eklenip TypeError mesajı çıkıyor. `"; ".join(det.reject)` kullan; regresyon testi (kontrol.py'nin bu yolunu sınayan küçük test, ör. tests/test_kontrol_kurulum.py — sahibi sensin). kontrol.py artık senin (kurulum testi, kur.bat çağırıyor).

> yanıt (quality-reviewer "Elenen ham görüntüleri de dene" varsayılan işaretli) (ui-engineer): yapıldı. ui.html `#elenenHam` artık varsayılan işaretsiz. tests/test_manuel_sinir_tarayici.py'ye 5. kontrol eklendi (Chromium): kutu görünürken işaretsiz; işaretsiz tıklamada gövde `elenen_ham: false`, işaretlenince `true` (istek tarayıcıda yakalanır, sunucuya ulaşmaz). `checked` geri konunca test "varsayılan olarak işaretli" ile başarısız oluyor (denendi).
> yanıt M-architecture-reviewer-11 (ui-engineer): yapıldı. kontrol.py: `"; ".join(map(str, det.reject))`; `yerlestirme(sahne_yolu=None)` parametresi ve `main()` + `if __name__ == "__main__"` koruması eklendi (içe aktarınca adımlar çalışmaz; kur.bat çağrısı `python kontrol.py` aynı). Regresyon: tests/test_kontrol_kurulum.py (düz gri sahne). Düzeltme geri alınınca "yanıltıcı TypeError ... can only concatenate str (not "list") to str" ile başarısız oluyor (denendi).

## [BİLGİ] M-pipeline-engineer-1 Kurtarma sonuç kodları ve video uyarısı   (görev: G5a)
- Ne: orchestrator `_kurtar` artık yalnız kabul+kararlı adayı seçiyor. `kurtarma.sonuc` değerleri: "yerel_aday_kabul" | "servis_onerisi_kabul" | "dogrulanamadi". ui.html:877'deki "yerel_aday_dogru_bolge_ret" / "servis_onerisi_dogru_bolge_ret" eşlemeleri yeni kayıtlarda çıkmaz (eski kayıtlar için kalabilir). `yerel_adaylar[]` öğelerine `kararli` (bool) ve retlerde `tur` eklendi.
- Ne: generate_video (ücretli onarım videosu) sonucu ve rapor.json `videolar[]` kaydında isteğe bağlı `uyari` (liste) var: başlangıç karesi kayıtlı fotoğrafla tutarsız olabilir. Günlükte "UYARI (video): ..." ve ilerleme metninde "UYARI: ..." zaten görünüyor.
- Beklenen: istersen video kartında `uyari` göster; "dogrulanamadi" metnine "denenen adaylar kabul edilmedi" ekle. Yanıt gerekmez.
