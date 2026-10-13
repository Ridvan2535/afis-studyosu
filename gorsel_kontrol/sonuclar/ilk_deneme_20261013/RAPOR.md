# Görsel Kontrol — ilk 8 örneklik değerlendirme (2026-10-13)

**Kim değerlendirdi:** visual-inspector talimatlarıyla çalışan **genel amaçlı alt ajan** (Claude Code içinde). Kurulu proje
ajanı (`visual-inspector`) bu oturumda tanınmadığı için KULLANILMADI. Talimat metni ajan tanımının gövdesinin aynısıdır
(`verilen_talimat.md`). Ajan yeni ve temiz bağlamla başlatıldı; bu konuşmadaki program kararları, insan etiketleri ve
beklenen cevaplar aktarılmadı.

**Ücret / üretim:** yeni görsel/video üretimi yok, ayrı ücretli API çağrısı yok (Claude planı kullanımı). Kabul/ret
kayıtları, promptlar ve ayarlar DEĞİŞMEDİ. Ajanın sonuçları yalnız öneridir.

## Yöntem ve sınırlar
- Ajana yalıtılmış bir çalışma klasörü verildi: talimat, rehber (öğretim; 6 sentetik + 3 gerçek örnek) ve 8 örneklik paket
  (sahne, program maskesi, üst/alt kesit, ürün ölçüsü). Pakette program kararı/gerekçesi ve insan etiketi YOK.
- **Görüş testi:** ajan önce içeriğini bilmediği bir test görselini tarif etti (mavi daire içinde beyaz "48", sağda siyah
  çaprazlı turuncu kare) — doğru. Görselleri gerçekten görebildiği doğrulandı.
- **Erişim sınırı nasıl sağlandı:** (1) **Talimatla**: yalnız çalışma klasörünü okuma, kabuk/web kullanmama. Genel amaçlı
  ajanın araç erişimi teknik olarak kısıtlı DEĞİLDİ (dosya sistemine ve kabuğa erişebilirdi). (2) **Dosya kaldırma**:
  gizli cevap anahtarları çalışma süresince diskten silindi, sonra aynı koddan yeniden üretildi (paket birebir aynı).
  İş raporları (`rapor.json`) ve belgeler diskte duruyordu; bunlar kaldırılmadı. (3) **Sonradan denetim**: ajanın döküm
  kaydı tarandı: 61 okuma, 1 listeleme, 8 yazma; **hepsi çalışma klasörü içinde**, kabuk/web çağrısı yok
  (`arac_denetimi.txt`). 8 örneğin her birinde 5 dosyanın tamamı açıldı.
- Doğru cevap yok: program kararı ve kullanıcı etiketi doğruluk ölçütü sayılmaz; doğruluk yüzdesi verilmez.

## Sonuçlar — HAM görüntüler (3)
| Örnek | Estetik | Tasarım yerleştirilebilir mi? | Maske sorunu | Ajan sonucu | Belirsizlik / kısa gerekçe |
|---|---|---|---|---|---|
| 224824 s01 | kullanılabilir | belirsiz | yok (küçük çentikler) | İnceleme gerekli | Kumaş ürüne göre biraz geniş görünüyor (~0,42); farkın sınırda olup olmadığını gözle kesinleştiremiyor. |
| 224824 s02 | kullanılabilir | evet | yok | Uygun | Önden, oran ürüne yakın, etek zemine değiyor; belirsizlik düşük. |
| 005509 s01 | kullanılabilir | evet | yok (üst bandı tam kapsıyor mu, emin değil) | Uygun | Oran ürüne yakın (~0,37); maskenin çubuk bandını kapsayıp kapsamadığı küçük bir soru. |

## Sonuçlar — YAKLAŞIK görüntüler (5; ham DEĞİL, ayrı yorumlanır)
| Örnek | Estetik | Tasarım yerleştirilebilir mi? | Maske sorunu | Ajan sonucu | Belirsizlik / kısa gerekçe |
|---|---|---|---|---|---|
| 003750 c13 | kullanılabilir | hayır | **evet — maske kumaşı değil, soldaki ince duvar şeridini işaretliyor** | Uygun değil | Kumaş belirgin geniş (~0,5); etek temasını ve kurdelenin kumaşı ne kadar örttüğünü kesin seçemiyor. |
| 003750 c3 | kullanılabilir | evet | **evet — maske kumaş yerine sağdaki balon kümesini işaretliyor** | İnceleme gerekli | Sahne kendi başına uygun görünüyor (~0,38); eteğin öne ne kadar yattığı net değil. |
| 003750 c1 | kullanılabilir | evet | **evet — maske alt yarıda iki yana duvara taşıyor, sağ kurdeleyi de içine alıyor** | İnceleme gerekli | Kumaş uygun görünüyor (~0,38); taşma kararı kenar ayrıntısına dayandığı için yaklaşık görüntüde inceleme gerekli. |
| 005509 c6 | kullanılabilir | hayır | yok | Uygun değil | Kumaş belirgin geniş (~0,46); kenar renk bozulması kaba oran kararını etkilemiyor. |
| 005509 c9 | kullanılabilir | belirsiz | yok | İnceleme gerekli | Biraz geniş (~0,41); fark küçük, yaklaşık görüntüdeki kenar bozulması bunu değiştirebilir. |

## Ajanın yararlı yakaladıkları
- **003750 c3 — program ölçüm hatasını yakaladı.** Program bu sahneyi "çok dar ya da yan açılı" diye otomatik *kesin hata*
  saymıştı; ajan programın maskesinin kumaşı değil balonları işaretlediğini gördü ve kumaşın kendisini uygun buldu.
  Program ile ajan burada çelişiyor → kullanıcı incelemesine ayrıldı.
- **003750 c13 — iki ayrı sorunu ayırdı:** maske yanlış yerde (duvar şeridi) VE sahnedeki kumaş zaten belirgin geniş.
  Programın "bölge çok küçük" reddi algılama başarısızlığıydı; ajan sahneyi ayrıca oran yüzünden uygun bulmadı.
- **003750 c1 — programın "boş görünmüyor" reddine olası açıklama:** baskı alanı ajan için açık; maske duvara taşıyıp
  kurdele kuyruğunu içine alıyor. (Kurdelenin maskeye girmesi "detay var" ölçümünü tetiklemiş olabilir — bu bir hipotez.)
- **224824 s01 — programın kabul ettiği bir sahnede oran şüphesi:** ajan kumaşı biraz geniş gördü (~0,42). Program bu
  sahneyi kabul etmişti; o sahnede program kendi ölçümünde de oranı ürünün üstünde bulmuştu (yaklaşık 0,41). Kabul edilen
  sahnelerin de gözden geçirilmesi gerekebileceğini gösteriyor.
- **Estetik ile yerleştirilebilirliği ayırdı:** 8 örneğin hepsine "estetik olarak kullanılabilir" dedi ama 2'sinde
  "yerleştirilemez" (oran), 2'sinde "belirsiz" dedi — kullanıcının "görsel olarak kullanılabilir" gözlemiyle uyumlu bir ayrım.

## Kararsız kaldığı yerler
- **Sınırdaki oranlar (~0,41–0,42):** 224824 s01 ve 005509 c9'da "belirsiz/inceleme gerekli" dedi; gözle %9–12 farkın
  kabul edilip edilemeyeceğine karar veremedi. Bu, istenen davranış: kesin ölçü iddia etmedi.
- **Çubuk üst bandı:** kumaşın oranına bandın dahil edilip edilmeyeceğini (s01'ler, c6, c9) belirsizlik olarak yazdı —
  programdaki aynı belirsizlikle (K-35) örtüşüyor.
- **Zemine temas:** c13 ve c3'te eteğin tam değip değmediğini/ne kadar yattığını seçemedi.
- **Yaklaşık görüntüler:** kenar renk bozulmalarını her seferinde not etti; kenara dayanan kararları (c1 taşması, c9
  sınırdaki oran) "inceleme gerekli"ye bıraktı.

## Kullanıcı incelemesine ayrılanlar (4)
224824 s01 (ajan: inceleme), 003750 c1 (ajan: inceleme), **003750 c3 (program kesin hata ↔ ajan katılmıyor)**,
005509 c9 (ajan: inceleme). Bağımsızlık ihlali (açık atıf) ve benzer ifade işareti: yok. Çıktı kural hatası (eksik alan,
santimetre iddiası): yok.

## Dosyalar
`ajan_ciktilari/<kod>.json` (8), `degerlendirme_tablosu.csv`, `kullanici_incelemesi.md`, `arac_denetimi.txt`,
`verilen_talimat.md`. Kod ↔ örnek eşlemesi tablo dosyasındadır.
