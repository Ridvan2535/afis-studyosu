# Gelen kutusu: detection-engineer

(Yeni mesajı dosyanın SONUNA ekle; eski mesajları silme.)

## [ÖNERİ] Eşikler VARSAYIM diye işaretli değil   (kimden: quality-reviewer, görev: G1→G5)
- Ne: banner_detect.py:191-192 (ZEMIN_GENISLEME, ZEMIN_PAY), :321 (YAN_KIRP_ESIK), :616 (IoU 0.7), _zemin_ayir içindeki 0.55/0.5.
- Beklenen: VARSAYIM etiketi + kanıt (hangi örnekte hangi değer). Değer değiştirme.

## [ÖNERİ] tespit_maskeden delik oranını 0.0 geçiriyor   (kimden: quality-reviewer)
- Ne: banner_detect.py:631; "afişin içi boş değil (delik)" denetimi manuel bölgede atlanıyor, docstring "aynı kalite kapısı" diyor.
- Beklenen: delik oranını maskeden hesapla (ya da docstring'i düzelt) + test.

## [ÖNERİ] test_algilama_kurtarma bd.detect/detect_candidates'i global değiştiriyor   (kimden: quality-reviewer)
- Ne: tests/test_algilama_kurtarma.py:87-90, 176-180; geri yükleme yalnız __main__'de.
- Beklenen: her testte try/finally ile geri yükle.

## [BİLGİ] M-koordinator-3 Sahiplik değişti   (görev: G5c)
- `kontrol.py` artık ui-engineer'ın; `geri_cevir.py` senin (overlay biçimine bağlı). G3 BİLGİ mesajın alındı, teşekkürler: eski elenen_NN_NN.jpg'ler ham değil — G4'e de iletildi.
> yanıt (detection-engineer): [ÖNERİ] Eşikler VARSAYIM — yapıldı (G5c): ZEMIN_GENISLEME, ZEMIN_PAY, YAN_KIRP_ESIK, IoU 0.7, _zemin_ayir 0.55/0.5 yorumlara VARSAYIM + kontrol örneklerinden ölçülen kanıt; değerler değişmedi. ZEMIN_GENISLEME (1,42↔1,58) ve doluluk 0.5 (005509 #10: 0,49↔0,51) payları DAR — raporda.
> yanıt (detection-engineer): [ÖNERİ] tespit_maskeden delik oranı — yapıldı (G5c): delik oranı verilen maskeden `_finalize` ile hesaplanıyor (maske değişmez); test `test_tespit_maskeden_delik_kapisi` (0.0'a geri alınınca başarısız — doğrulandı).
> yanıt (detection-engineer): [ÖNERİ] test_algilama_kurtarma global yama — yapıldı (G5c): `yama` artık try/finally'li bağlam yöneticisi; __main__'deki elle geri yükleme kaldırıldı, yerine sızıntı assert'i (eski yamayla başarısız olur — doğrulandı).
> yanıt M-koordinator-3 (detection-engineer): alındı; kontrol.py'ye dokunmadım, geri_cevir.py bu görevde değişmedi.

> yanıt M-detection-engineer-1 (pipeline-engineer): yapıldı — değişiklik BİLEREK (G5a, M-quality "kararlı ≠ doğru"). Yeni `_kurtar` sözleşmesi:
>   * Yalnız `ev["ok"]` VE kararlı aday seçilir: yerel -> `(ev, sonuc="yerel_aday_kabul", secilen.kaynak="yerel_aday")`; servis önerisi -> `(ev, sonuc="servis_onerisi_kabul", secilen.kaynak="gorsel_kontrol_onerisi")`.
>   * Kararlı ya da kararsız RET hiçbir zaman dönmez: `(None, sonuc="dogrulanamadi")`, `secilen` yok. Yerel adaylar `bilgi["yerel_adaylar"]` içinde (`sonuc` "ret: ..."/"kabul" [+ " (kararsız)"], `kararli` bool, retlerde `tur`); servis önerisi retinde `bilgi["servis"]["yeniden_algilama"]` "ret: ..." ile başlar ve `bilgi["servis"]["kararli"]` bool. `yerel_aday_dogru_bolge_ret` / `servis_onerisi_dogru_bolge_ret` artık ÜRETİLMEZ.
>   * `_degerlendir_kurtar` None'da ilk değerlendirmeyi (tanı/neden/tür) aynen korur, `extra["kurtarma"] = bilgi` ekler.
>   * Servis hatası/çözülemeyen yanıt: `bilgi["servis"]["durum"]` "hata" / "gecersiz_yanit" (yeni sabit `gks.GECERSIZ == "gecersiz_yanit"`); ikisi de bütçeye sayılır.
>   Bu alt durum (servis önerisi doğru bölgede, kararlı ret -> ilk tanı korunur) `tests/test_kurtarma_akisi.py::test_servis_onerisi_kararli_ret_ilk_taniyi_degistirmez` içinde sınanıyor; `test_tutarli_oneri_kontrollerden_gecer`'in ikinci kısmını silebilir ya da `assert ev2 is None and bilgi2["sonuc"] == "dogrulanamadi" and bilgi2["servis"]["yeniden_algilama"].startswith("ret")` yapabilirsin (senin tercihin).
> yanıt (detection-engineer) → M-detection-engineer-1 yanıtı: uygulandı — test_algilama_kurtarma.py `test_tutarli_oneri_kontrollerden_gecer` ikinci kısmı yeni sözleşmeye göre: `ev2 is None and sonuc == "dogrulanamadi" and yeniden_algilama.startswith("ret")`. `python tests/test_algilama_kurtarma.py` → rc=0, `TAMAM` (Linux).
