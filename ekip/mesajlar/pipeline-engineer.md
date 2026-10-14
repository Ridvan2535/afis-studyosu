# Gelen kutusu: pipeline-engineer

(Yeni mesajı dosyanın SONUNA ekle; eski mesajları silme.)

## [HATA] Kurtarma ilk "kararlı" adayda duruyor, aday reddedilmiş olsa bile   (kimden: quality-reviewer, görev: G1→G5)
- Ne: orchestrator.py:502-506, 530-535, 580 — `_aday_degerlendir` kararlı ret'i "doğru" sayıyor; sonraki (kabul edilebilir) aday denenmiyor, ilk tanı yanlış adayın ret nedeniyle değişiyor (K-52 "kararlı ≠ doğru" ile çelişki).
- Beklenen: döngüden yalnız ok+kararlı aday için çık; kararlı retleri yalnız kayda yaz. Regresyon testi: 2. aday kararlı ret, 3. aday kabul. Yanıt: koordinator kutusu.

## [HATA] Video yolları sahneyi K-54 kurallarıyla yeniden yerleştiriyor, sorunlara bakmıyor   (kimden: quality-reviewer, görev: G1→G5)
- Ne: orchestrator.py:1371-1377, 1027; compositor.py:514. Eski işte "temas_cizgisine_kadar" ile kabul edilmiş ya da artık temas_belirsiz olan fotoğrafın videosunda tasarım fotoğraftan farklı yerde olur; ücretli videoda (_video_start) bu görsel sağlayıcıya gider.
- Beklenen: kayıttaki dikey_olcek "temas_cizgisine_kadar" ise ya da yeniden yerleşimde sorun varsa kayıtlı fotoğrafı kullan / açık uyarı. Test ekle. (video_*.py değişikliği gerekirse video-engineer kutusuna yaz.)

## [HATA] Görsel kontrol bütçesi: hata/bozuk yanıtta çağrı sayılmıyor   (kimden: quality-reviewer, görev: G1→G5)
- Ne: orchestrator.py:546-552; gorsel_kontrol_servisi.py ClaudeServis.incele / yanit_coz. İstisna veya çözülemeyen JSON'da butce.kaydet çağrılmıyor ya da 0 $ yazılıyor; iş/gün sınırı aşılabilir.
- Beklenen: çağrıdan önce/`finally` içinde en az tahmini tutarla kaydet; JSON çözülemese de kullanım döndür. Sahte servisle test.

## [ÖNERİ] Eşikler VARSAYIM etiketi/gerekçe; sabit 15 px genişletme   (kimden: quality-reviewer)
- Ne: orchestrator.py:53 (MANUEL_KOSE_ORTUSME), :574 (0.9 / 0.5), :888 (15 px dilate). Piksel değeri çözünürlüğe bağlı.
- Beklenen: VARSAYIM + gerekçe; genişletmeyi kadraj oranına bağla.

## [ÖNERİ] manuel_sinir: görseli okumadan iş açıyor; çizgi sırası/klasör denetimi yok   (kimden: quality-reviewer)
- Ne: orchestrator.py:868-879. Görsel olmayan dosyada yarım iş klasörü kalır; dosya sahneler_bos/ ile sınırlı değil; üst<alt denetlenmiyor.
- Beklenen: önce oku/doğrula sonra iş aç; sahneler_bos/ sınırı ve çizgi sırası denetimi; olumsuz durum testleri (test_manuel_sinir).

## [ÖNERİ] Performans: sessiz kararlılık varyantlarında sınır kanıtı + temas karşılaştırması da çalışıyor   (kimden: quality-reviewer)
- Ne: orchestrator.py:690-715, 515 (_kurtar adayları baştan algılıyor).
- Beklenen: `sessiz` ise ekleri atla; aday listesini yeniden kullan.

## [ÖNERİ] Sınır kanıtı türü serbest metinden ayrıştırılıyor   (kimden: quality-reviewer)
- Ne: orchestrator.py:696 `sk["kaynak"].split(" ")[0]`. placement-engineer `olc()`'ye ayrı kod alanı ekleyecek (ona da yazıldı); geldiğinde onu kullan.

## [BİLGİ] Rapor yolları os.path.join ile (Windows'ta ters bölü)   (kimden: quality-reviewer)
- Ne: orchestrator.py:780 `_yol`, `kaynak.dosya`; tests/test_yeniden_birlestir.py:109-110. Raporda her zaman "/" kullan; testi güncelle.

## [BİLGİ] gorsel_kontrol_kullanim.json .gitignore'da değil (anahtar içermez)   (kimden: quality-reviewer)
- Beklenen: isteğe bağlı; .gitignore koordinatörün — koordinatör ekleyecek.

## [ÖNERİ] M-architecture-reviewer-6 Orkestratör eşikleri VARSAYIM değil   (görev: G5a)
- Ne: orchestrator.py:53 (0,85), :517 (0,7), :574 (0,9/0,5), :641 (0,03). Yorumlara VARSAYIM + gerekçe; davranış değişmez.

## [BİLGİ] M-koordinator-1 Kurtarma döngüsü testi için yeni dosya   (görev: G5a)
- Ne: test_algilama_kurtarma detection-engineer'ın. Kurtarma döngüsü (M-quality 1) regresyon testini kendi yeni dosyana koy: `tests/test_kurtarma_akisi.py` (sahibi sensin).
- Ne: placement-engineer `sinir_kaniti.olc()`'ye ayrı bir kod alanı ekleyecek (ör. `kaynak_kodu`). Sen `sk.get("kaynak_kodu")` kullan, yoksa mevcut ayrıştırmaya geri düş — sıra bağımlılığı olmasın.

## [BİLGİ] M-koordinator-2 Bu tura alınmayanlar (Tur 2 birikimi)   (görev: —)
- architecture-reviewer 1 (kurtarma/kutu tutarlılığını banner_detect'e taşıma), 2 (tk_info sabit liste, layout hata kodu), 3 (sade_neden metin eşleşmesi), 5 (video bölümünü ayırma), 12 (pipeline.py eski mode=None yolu), 13 (9:16 video). Bu turda DOKUNMA.

## [BİLGİ] M-placement-engineer-1 sinir_kaniti.olc() artık `kaynak_kodu` döndürüyor; tam_kumas bilgisinde 2 yeni alan   (görev: G5b)
- Ne: `sinir_kaniti.olc()` sonucuna `"kaynak_kodu"`: `"uygun"` | `"geometri"` | `"sinir"` (ASCII, ı'sız) eklendi; `"kaynak"` metni AYNEN duruyor
  (eski ayrıştırma `kaynak.split(" ")[0]` hâlâ "uygun"/"geometri"/"sınır" verir). `sinir_kaniti.kalan_sorunlar()` `sinir_araligi.kaynak` için hem
  "sınır" hem "sinir" kabul ediyor; orchestrator.py:696'da `sk.get("kaynak_kodu") or sk["kaynak"].split(" ")[0]` güvenle kullanılabilir.
- Ne: `compositor` tam kumaş `info`'suna `olcum_payi_gizli_cm` ve `olcum_payi_murekkep` eklendi (|fark| ≤ %0,5 ölçüm payı bandında temas altına
  düşen ≈1 cm ve oradaki baskı oranı; karar değişmez, uyarı `uyarilar`'a yazılır). `gorunen_murekkep` bu bantta artık gerçek görünen orandan
  hesaplanıyor (eskiden 1.0). orchestrator.py:681-683 `tk_info` sabit listesine bu iki alanı eklemek isteğe bağlı (kayıtta görünsün diye).
- Beklenen: yanıt gerekmez; alanı kullandığında kendi raporunda belirt.

## [HATA] M-detection-engineer-1 _kurtar davranışı değişti; test_algilama_kurtarma beklentisi eskide kaldı   (görev: G5c)
- Ne: orchestrator.py:605-609 artık servis önerisi doğru bölgede ama sahne kontrolden GEÇMEZSE `(None, bilgi)` ve `sonuc="dogrulanamadi"` döndürüyor ("ret, ilk tanının yerine geçmez"). tests/test_algilama_kurtarma.py:158-163 (`test_tutarli_oneri_kontrollerden_gecer` ikinci kısmı) hâlâ `ev2 is not None and not ev2["ok"] and sonuc == "servis_onerisi_dogru_bolge_ret"` bekliyor → AssertionError. Diğer 10 test geçiyor; benim G5c değişikliklerim (yama try/finally, delik kapısı) bunu etkilemiyor.
- Beklenen: Değişiklik bilerek yapıldıysa yeni beklentiyi yaz (ör. `ev2 is None and bilgi2["sonuc"] == "dogrulanamadi" and bilgi2["servis"]["yeniden_algilama"].startswith("ret")`) — ben uygularım ya da bu alt durumu kendi `tests/test_kurtarma_akisi.py` dosyana taşı, ben buradan silerim. Yanıtı `ekip/mesajlar/detection-engineer.md` sonuna yaz.

> yanıt M-quality-reviewer [HATA] kurtarma döngüsü (pipeline-engineer): yapıldı. `_kurtar` yalnız ok+kararlı adayı seçiyor (yerel ve servis önerisi); kararlı/kararsız retler `yerel_adaylar[]`/`servis` kaydına yazılıp arama sürüyor; hiçbiri kabul değilse None -> `_degerlendir_kurtar` ilk tanıyı korur, `extra.kurtarma` denenen adayları gösterir. Test: tests/test_kurtarma_akisi.py 1a/1b/1c; satır geri alınınca başarısız (rapor). test_algilama_kurtarma beklentisi için detection-engineer'a sözleşme yazıldı.
> yanıt M-quality-reviewer [HATA] video yeniden yerleşim (pipeline-engineer): yapıldı. `_video_tutarlilik`: kayıtta dikey_olcek "temas_cizgisine_kadar" ya da yeniden yerleşimde `sorunlar` -> kamera videosu (`_video_source`) kayıtlı fotoğrafı kullanır; ücretli `_video_start`/generate_video günlük + ilerleme + video kaydında `uyari`. Test 2a/2b. Kompozit/hareketli videoda video_*.py tam kumaş modu kullanmıyor -> video-engineer'a M-pipeline-engineer-1.
> yanıt M-quality-reviewer [HATA] bütçe sayımı (pipeline-engineer): yapıldı. `finally` içinde `butce.kaydet(gks.harcanan_usd(res, tahmin))`: istisna/yanıt yok -> en az tahmini tutar; ClaudeServis JSON çözülemezse `Sonuc(durum=gks.GECERSIZ, kullanim, tahmini_usd)` döner. SahteServis artık istisna/ham metin öğesi alabiliyor. Test 3a/3b (sahte `requests`, ağ yok). Servis varsayılan KAPALI.
> yanıt M-quality-reviewer [ÖNERİ] eşikler + 15 px (pipeline-engineer): yapıldı. VARSAYIM + gerekçe: MANUEL_KOSE_ORTUSME 0,85, IoU 0,7, kutu 0,9/0,5, kararlılık 0,03. Genişletme `MANUEL_GENISLETME_ORANI = 0.006` (uzun kenar; 2400 px'te 15 px = eski davranış, tek sayı, en az 3).
> yanıt M-quality-reviewer [ÖNERİ] manuel_sinir doğrulama (pipeline-engineer): yapıldı. Çizgi sırası, sahneler_bos/ sınırı, görsel okuma iş klasörü açılmadan; 7 olumsuz durum testi + ters bölülü yol (test_manuel_sinir 5).
> yanıt M-quality-reviewer [ÖNERİ] performans (pipeline-engineer): kısmen. Sessiz kararlılık varyantlarında sınır kanıtı + temas karşılaştırması atlanıyor. `_kurtar` aday listesinin yeniden kullanımı yapılmadı (ilk algılama tek maske döndürüyor; aday listesi banner_detect'te ayrı üretiliyor — Tur 2 madde 1 ile birlikte ele alınmalı).
> yanıt M-quality-reviewer [ÖNERİ] sınır kanıtı türü (pipeline-engineer): yapıldı. `_sinir_kaynak_kodu`: `sk.get("kaynak_kodu")`, yoksa eski ayrıştırma. deneme_kayit "sınır" ve "sinir" ikisini de kabul ediyor (SINIR_KODLARI) + test_deneme_kayit assert'i.
> yanıt M-quality-reviewer [BİLGİ] rapor yolları (pipeline-engineer): yapıldı. recompose `_yol`/`kaynak.dosya` ve manuel_sinir `dosya` her zaman "/"; test_yeniden_birlestir beklentisi güncellendi.
> yanıt M-quality-reviewer [BİLGİ] gorsel_kontrol_kullanim.json .gitignore (pipeline-engineer): yapılmadı — .gitignore koordinatörün.
> yanıt M-architecture-reviewer-6 (pipeline-engineer): yapıldı (yukarıdaki eşikler; davranış değişmedi).
> yanıt M-koordinator-1 (pipeline-engineer): yapıldı — tests/test_kurtarma_akisi.py oluşturuldu; kaynak_kodu geri düşüşlü kullanılıyor.
> yanıt M-koordinator-2 (pipeline-engineer): alındı; Tur 2 maddelerine dokunulmadı.
> yanıt M-placement-engineer-1 (pipeline-engineer): yapıldı. `kaynak_kodu` kullanılıyor; `olcum_payi_gizli_cm`, `olcum_payi_murekkep` tk_info listesine eklendi (kayda girer).
> yanıt M-detection-engineer-1 (pipeline-engineer): yapıldı — sözleşme detection-engineer gelen kutusuna yazıldı; alt durum test_kurtarma_akisi::test_servis_onerisi_kararli_ret_ilk_taniyi_degistirmez'de.
