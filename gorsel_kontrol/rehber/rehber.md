# Görsel Kontrol rehberi (öğretim örnekleri)

Bu örnekler **öğretim** içindir; değerlendirme/başarı ölçümünde kullanılmaz. Her örnekte `<ad>_sahne.jpg` (sahne) ve
`<ad>_maske.png` (programın maskesi; beyaz = program kumaş sanıyor) vardır. Ürün: 75×200 cm, en/boy 0,375.
Açıklamalar gözle incelemeye dayanır; **sentetik örneklerin geometrisi kesin bilinir**, gerçek örneklerinki bilinmez
(oradaki açıklamalar kesin fiziksel ölçüm değildir).

## Sentetik (geometri kesin)
| Örnek | Ne öğretir | Beklenen değerlendirme |
|---|---|---|
| `sentetik_dokunan` | Kumaş oranı 0,375; etek zemin çizgisine tam değiyor; maske kumaşla örtüşüyor. | estetik: kullanılabilir · yerleştirilebilir: evet · **uygun** |
| `sentetik_birikmeli` | Etek zemine değip iki yana simetrik yayılıyor (birikme). Maskenin altı genişler; bu taşma değil. | yerleştirilebilir: evet (alt kısım birikmede görünmeyebilir) · **uygun** ya da kısa gerekçeyle inceleme |
| `sentetik_havada` | Etek zeminin belirgin üstünde bitiyor; kumaş zemine değmiyor. | yerleştirilebilir: hayır · **uygun değil** (havada bitiyor) |
| `sentetik_genis` | Aynı stand, kumaş oranı 0,46 (ürüne göre belirgin geniş/kısa). Estetik olarak düzgün görünür. | estetik: kullanılabilir · yerleştirilebilir: **hayır** (oran) · **uygun değil** |
| `sentetik_uzun` | Kumaş ürüne göre dar/uzun. | yerleştirilebilir: hayır · **uygun değil** |
| `sentetik_hafif_aci` | Aynı doğru oranlı kumaş, hafif yandan (sol kenar daha uzakta). Kumaş tek düz yüzey, dört kenarı görünüyor. Planda her ortam için önden + hafif yandan görsel var; tasarım tek perspektif dönüşümüyle bütün kalır. | perspektif: hafif açı (tek düzlem) · yerleştirilebilir: evet · **uygun**. Hafif yan açı ret nedeni DEĞİLDİR. |

Ders: **estetik** ile **yerleştirilebilir** ayrı sorulardır; düzgün görünen bir sahnenin oranı tutmayabilir.
Hafif yan açı tek başına sorun değildir; sorun, kumaşın tek düzlem gibi durmaması ya da kenarın görünmemesidir.

## Gerçek (iş 20261013-005509; görüntü türü belirtilmiş)
| Örnek | Görüntü | Gözle inceleme | Beklenen değerlendirme |
|---|---|---|---|
| `gercek_005509_13` | **yaklaşık** (algılama katmanından; ham değil) | Maske kumaşla örtüşüyor; kumaş belirgin geniş (yaklaşık oran 0,5 civarı). Kullanıcı da "fazla geniş" dedi. | estetik: sınırda/kullanılabilir · yerleştirilebilir: hayır · **uygun değil** |
| `gercek_005509_04` | **yaklaşık** | Kumaşın oranı ürüne yakın görünüyor; **maske sağ altta zemin karolarına taşıyor** (tek yanlı genişleme). Zemine temas bu yüzden belirsiz. Kullanıcı "kullanılabilir" dedi. | maske_uyumu: taşıyor · zemine temas: belirsiz · **inceleme gerekli** |
| `gercek_005509_s02` | ham | Önden, dik; etek zemine değiyor; baskı alanı açık. Program kabul etti. (Program ölçümü JPEG/%80 varyantında kararlı ama 1536 px'e küçültmede değişiyor; bu ayrı izlenen bir algılama sorunu, sahnenin kendisiyle ilgili değil.) | estetik: kullanılabilir · yerleştirilebilir: evet · **uygun** |

## Hatırlatmalar
- Maskeyi doğru kabul etme: maskeyi sahneyle karşılaştır (taşma, eksik bant, eksik etek).
- Santimetre yazma. "Ürüne göre belirgin geniş görünüyor" gibi göreli konuş, belirsizliği yaz.
- Yaklaşık görüntüde maske kenarı çevresindeki renk/ayrıntı bozulmuş olabilir; buna dayanan kararları "inceleme gerekli"ye bırak.
