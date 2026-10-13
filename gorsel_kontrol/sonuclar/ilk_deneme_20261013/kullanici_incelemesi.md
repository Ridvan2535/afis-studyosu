# Kullanıcı incelemesine ayrılanlar

Ajan ile program/insan etiketi uyuşmayanlar, ajanın 'inceleme gerekli' dediği ve çıktısı kurala uymayanlar. Ajan hiçbir sahneyi reddetmez.

Grup özeti (doğruluk değil, uyuşma): {"ilk_deneme/ham": {"ornek": 3, "celiski": 0, "inceleme": 1, "bagimsiz_degil": 0, "benzer_ifade": 0}, "ilk_deneme/yaklasik": {"ornek": 5, "celiski": 1, "inceleme": 3, "bagimsiz_degil": 0, "benzer_ifade": 0}}

# Ham görüntülü örnekler

## gb5a86a (20261012-224824 s01, ham)
- program: kabul/uygun · insan: —
- ajan: inceleme_gerekli · estetik kullanilabilir · yerleştirilebilir belirsiz
- gerekçe: Sahne estetik olarak temiz, etek zemine değiyor ve maske örtüşüyor; ancak kumaş ürün oranından biraz geniş görünüyor (~0,42) ve bu fark sınırda.
- belirsizlik: Oran farkının kabul edilebilir olup olmadığı; üst bandın dahil edilmesi oranı biraz değiştirir.

# Yaklaşık görüntülü örnekler (ham DEĞİL; ayrı raporlanır)

## g515065 (20261013-003750 c1, yaklasik)
- program: ret/inceleme · insan: —
- ajan: inceleme_gerekli · estetik kullanilabilir · yerleştirilebilir evet
- gerekçe: Sahnedeki kumaş uygun görünüyor, ancak maske alt yarıda iki yana duvara taşıyor ve sağ kurdeleyi içeriyor; maske ile görüntü çelişiyor ve bu çelişki maske kenarı çevresinde.
- belirsizlik: Kenar çevresindeki renk lekeleri yüzünden kumaşın gerçek yan kenarlarının birkaç piksellik konumu belirsiz.

## gf52da0 (20261013-003750 c3, yaklasik)
- program: ret/kesin_hata · insan: —
- ajan: inceleme_gerekli · estetik kullanilabilir · yerleştirilebilir evet
- gerekçe: Sahne kendi başına uygun görünüyor, ancak maske kumaş yerine sağdaki balon kümesini işaretliyor; maske ile görüntü açıkça çelişiyor.
- belirsizlik: Eteğin önde ne kadar yere yattığı ve buna bağlı alt kenar konumu tam net değil.
- **çelişki:** Program kesin hata diyor, ajan katılmıyor.

## g1cb1c3 (20261013-005509 c9, yaklasik)
- program: ret/inceleme · insan: kullanilabilir
- ajan: inceleme_gerekli · estetik kullanilabilir · yerleştirilebilir belirsiz
- gerekçe: Sahne estetik olarak iyi ve etek zemine değiyor, ancak kumaş ürün oranından biraz geniş görünüyor (~0,41) ve bu farkın kabul sınırında olup olmadığını gözle kesinleştiremiyorum.
- belirsizlik: Oran farkı küçük; üst bandın dahil edilip edilmemesi ve yaklaşık görüntüdeki kenar bozulması bu küçük farkı değiştirebilir.

