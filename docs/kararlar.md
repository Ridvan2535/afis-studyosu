# Karar geçmişi

Önemli kararlar, kısa gerekçeleriyle. En yeni en üstte. Bir karar değişirse eskisi silinmez; yeni satırda
"önceki: K-xx yerine" diye belirtilir. Gizli bilgi yazılmaz.

Biçim: **K-numara · tarih · karar** — gerekçe · etki/geri alma.

---

### 2026-10-13 — Görsel Kontrol ilk değerlendirmesi

**K-48 · 2026-10-13 · İlk 8 örnek, visual-inspector talimatlı genel amaçlı alt ajanla değerlendirildi (kullanıcı onayı).**
Kurulu proje ajanı bulut oturumunda tanınmadı; sessiz ikame yapılmadı, kullanıcı 3. yolu onayladı. Kayıtlarda yöntem
"visual-inspector talimatlarıyla çalışan genel amaçlı ajan" olarak geçer. Erişim sınırı talimatla sağlandı (araç
erişimi kısıtlı değildi); ek önlem: cevap anahtarı çalışma süresince diskten kaldırıldı, döküm denetimi yapıldı.
Sonuçlar öneridir; hiçbir kabul/ret kaydı, prompt ya da ayar değiştirilmedi.

### 2026-10-13 — Codex incelemesi: Görsel Kontrol düzeltmeleri

**K-47 · 2026-10-13 · İlk ajan değerlendirmesi 6–8 örnekle sınırlı (`ornek_plani.json → ilk_deneme`, 8 örnek: 3 ham + 5
yaklaşık).** Rehberle çakışmaz; ham örnekler önce, yaklaşık örnekler ayrı raporlanır. Amaç doğruluk yüzdesi değil,
ajanın belirgin sorunları ve belirsizliği ayırıp ayıramadığını görmek. 30 örneklik çalıştırma ertelendi. Ajan
kullanıcının bilgisayarında kurulu değil; bu görevde çalıştırılmadı.

**K-46 · 2026-10-13 · Hafif yan açı ajan için uygunsuzluk nedeni değildir.** Plan 3 ortam × (önden + hafif yandan);
tasarım tek perspektif dönüşümüyle bütün kalabiliyorsa açılı sahne uygun olabilir. Rehbere sentetik hafif açılı örnek
eklendi. Programın `strict_layout` kapısı yan açıyı hâlâ reddeder (Aşama 2B açılı profil işi); çelişki kullanıcı
incelemesine düşer.

**K-45 · 2026-10-13 · Bağımsızlık: açık atıf ≠ doğal ifade benzerliği (K-42'yi düzeltir).** İhlal yalnız programın
kararına/gerekçesine/iç kodlarına açık atıftır. Program gerekçesiyle ortak ifade ("asılı kısım ...") yalnız inceleme
işaretidir; tek başına bağımsız olmadığını kanıtlamaz.

**K-44 · 2026-10-13 · İki deney türü ayrıldı: yalnız prompt / prompt + kılavuz paketi.** Kılavuz sürümü `ayar_ozeti`
karşılaştırmasından çıkarılıp ayrı deney bileşeni yapıldı; böylece kılavuz 1 ↔ 2 farkı paket karşılaştırmasını
otomatik geçersiz kılmaz. Öneride `deney_turu` ve `degisen_bilesenler` yazılır; paket deneyinden promptun tek başına
etkisi iddia edilmez. Kılavuz kullanılmış ama sürümü kayıtlı olmayan çağrılar "karşılaştırılamaz" (tahminle doldurulmaz).

### 2026-10-13 — Oranı üretimde kurma kararı ve Görsel Kontrol ajanı

**K-43 · 2026-10-13 · A-01 (küçültmede karar değişmesi) ayrı algılama sorunu olarak izlenir.**
`tests/izle_kucultme_kararliligi.py` (izleme, başarısız olmaz). Çözülünce gerçek regresyon testine dönüşür.
Görsel Kontrol ajanı bu sorunu düzeltmez ve onun yerine geçmez.

**K-42 · 2026-10-13 · Görsel Kontrol ajanı (`visual-inspector`) yalnız öneri üretir.**
Salt okunur (Read, Glob). Görüntünün tamamını ve program maskesini ayrı inceler; estetik ve "oran korunarak
yerleştirilebilir" kararlarını ayrı verir; Uygun / İnceleme gerekli / Uygun değil + gerekçe + belirsizlik. Santimetre
iddia etmez. Program kararı/gerekçesi pakette yoktur; gerekçeyi tekrar eden ya da programa atıf yapan çıktı "bağımsız
değil" sayılır. Ajan ile program/insan etiketi çelişirse kullanıcı incelemesine ayrılır. Otomatik ret, yeni üretim,
prompt/kılavuz değişikliği yetkisi YOK. Örnekler rehber (8, öğretim) ve kör değerlendirme (30) olarak ayrıldı; aynı örnek
ikisinde olamaz. Program kararı ve kullanıcı etiketi doğru cevap sayılmaz (etiketler görsel beğeni). Ayrıntı:
`docs/gorsel_kontrol_plani.md`. Ajan henüz çalıştırılmadı.

**K-41 · 2026-10-13 · Prompt 3B-aday + kılavuz v2 (aday, etkin değil).**
Kılavuzda dikmeler afişe yakın, kuyruklar dikmelerin dışında, koyu arka zemin, temas gölgesi; promptta iki cümle
DEĞİŞTİRİLDİ (eklenmedi): kamera "stand is barely wider than the banner", model "light rectangle is the banner's exact
outline; never widen it to the posts". Ürün kuralları değişmedi. Kılavuz sürümü karşılaştırma anahtarına (`ayar_ozeti`)
girer. Ücretli deneme yapılmadı.

**K-40 · 2026-10-13 · Oran sorunu üretimde çözülür (kullanıcı kararı: seçenek c).**
Kumaş oranı prompt ve kılavuzla doğru kurulmaya çalışılır. Tasarım kırpılarak, esnetilerek ya da baskılı kısmı gizlenerek
otomatik uyarlanmaz. "Şüpheli ölçümde dur" açık kalır (K-36).

### 2026-10-13 — Kullanıcının gözle incelemesi: yanlış retleri azaltma (prompttan önce)

**K-39 · 2026-10-13 · İş 20261013-005509'un 12 eleneni + 2 kabulü kalıcı kontrol örneğidir.**
`tests/kontrol_ornekleri/is_005509/` + `tests/test_kontrol_ornekleri.py`. Elenenler eski kaydın algılama katmanlı
görselinden hesaplanan YAKLAŞIK görüntülerdir (ham değil; orijinal sahne kaydedilmemiş, kurtarılamaz). İnsan etiketi:
1, 6, 13 gerçekten hatalı (fazla geniş), diğer 9 kullanılabilir. Algılama/yerleşim değişikliklerinde bu test geçmeli:
kabuller kabul, 1/6/13 elenmeye devam, kullanılabilir etiketlilerden hiçbiri otomatik "kesin hata" değil.

**K-38 · 2026-10-13 · Elenen denemeye insan etiketi: "Kullanılabilir" / "Gerçekten hatalı" (ayrı dosya).**
`insan_degerlendirme.json → elenenler["<üretim no>:<çağrı>"]`. Otomatik kaydı (rapor.json) silmez/değiştirmez; yalnız
gösterimi etkiler. "Kullanılabilir" görsel kabuldür, fiziksel ölçü doğrulaması sayılmaz; sahne bu nedenle ürün
fotoğrafına dönüştürülmez. Otomatik "kesin hata" ile insan "kullanılabilir" çelişirse durum "İnceleme gerekli".

**K-37 · 2026-10-13 · Ölçüm kararlılığı testi (ücretsiz): her sahne JPEG %92 ve %80 ölçek varyantıyla yeniden ölçülür.**
Karar değişiyor ya da asılı boy %3'ten fazla oynuyorsa ölçüm "kararsız": ret kesin sayılmaz (güven düşük), kabul
uyarıyla işaretlenir. Kök neden: zemine temas satırı birikme yayılmasının BAŞLANGICINDAN bulunuyor; kumaş alta doğru
yavaşça genişlediğinde başlangıç yukarı kayıyor ve tek satırlık maske çentiği sonucu belirliyor. Kanıt (kontrol
örnekleri): kabul edilen s01 aynı sahnenin %80 ölçeğinde 199,5 → 208,4 cm (ret); s02 1536 px'te 197 → 156 cm; #5'te
asılı boy 111 cm gibi fiziksel olmayan değerler. Temas yöntemini değiştirmeyi denedim (yarı-yayılma noktası): s02'yi
kararlı ama 173 cm yaptı, s01'i bozdu; daha iyi olmadığı için GERİ ALINDI. Kalıcı çözüm (temas çizgisini zeminle
kumaşın birleştiği gerçek kenardan bulmak) ayrı bir iş olarak açık.

**K-36 · 2026-10-13 · Şüpheli ölçümde dur (Ayarlar, varsayılan AÇIK).**
Algılama güveni düşük bir ret olursa üretim durur; şüpheli ölçüm yüzünden otomatik yeni ücretli çağrı yapılmaz. Kabul
edilenler saklanır, eksik sayısı gösterilir. Bedeli: iş 005509'da 2. çağrıda dururdu (0 kabul); sınır tablosunda görünür.

**K-35 · 2026-10-13 · Kontrol sonuçları üç durum: Uygun / İnceleme gerekli / Kesin hata (önceki "üretim/olası
algılama/belirsiz" sınıflaması K-31'in yerine geçer; K-31 silinmedi).**
Aynı maske ölçümünden hem ret hem teşhis çıkarmak bağımsız doğrulama değildir. Bu yüzden: Kesin hata (otomatik) yalnız
algılama güveni düşük DEĞİLKEN ve afiş en/boy oranı üründen ±%30'dan fazla farklıyken (layout'un kendi kaba sınırı).
±%3 boy kuralına takılan ama ±%30 içinde kalan retler "İnceleme gerekli" (sahne kullanılmaz, ama kesin hata denmez).
Güven düşük: birikme yalnız kenar yayılmasından çıkarıldıysa, alt kenarda belirgin tek taraflı yayılma varsa (maske
taşması), maske kenarı satırların %4'ünden fazlasında taşıyorsa, üstte kararı değiştirebilecek kumaş bandı varsa,
ölçüm kararsızsa (K-37). Eşikler gevşetilmedi (±%3 ve 0,72–1,30 aynı).
Bulgular (kontrol örnekleri, gözle maske incelemesi): kullanılabilir bulunan 9 örneğin çoğunda maske kumaşla örtüşüyor;
oran farkı (%7–21) gerçek çizim farkı. Ölçülen orana göre insan etiketleri ayrışmıyor (6: %+17 "geniş", 12/14:
%+18–21 "kullanılabilir"); 12 etiketle görsel bir oran eşiği türetilemez. Tespit edilen algılama hataları: #4 maske
sağ altta zemin karolarına taşmış (sahte birikme), #5 maske sağda masa örtüsüyle birleşmiş + birikme belirsiz,
#8 üstteki çubuk bandı eski kayıtta maske dışında (aynı bant kabul edilen s01'de de dışarıda; kullanıcı onaylı
yerleşim bandın altından başlar, bu yüzden bant maskeye EKLENMEDİ, yalnız belirsizlik olarak ölçülür).

### 2026-10-13 — Codex incelemesi: karşılaştırılabilirlik ve sonuçsuz çağrı sınırı

**K-34 · 2026-10-13 · Terfi ölçütleri sıkılaştırıldı (K-28'i günceller; K-28 silinmedi).**
En az 12 çağrı ve 3 insan değerlendirmesi şartı artık **etkin sürüm için de** geçerli: tek (başarısız) eski denemeye karşı
aday önerilemez. Beğeni verisi olmayan grup "beğeni %0" sayılmaz; `begeni_orani` boş kalır ve sonuç "yetersiz veri" olur.
Karar sırası: karşılaştırılamaz → yetersiz veri → etkin kalsın / aday önerilir. Öneri hiçbir ayarı değiştirmez.

**K-33 · 2026-10-13 · Sonuçsuz çağrı sınırı: son kabulden beri 8 çağrı sonuç vermezse durur (ayarlanır, 0 = kapalı).**
Aynı-hata sınırı (K-30) korunur. Sonuçsuz sayaç nedenden bağımsızdır (farklı ret türleri ve servis hataları sayılır),
kabulde sıfırlanır. Toplam çağrı tavanı (`max_scene_calls`) ayrıca geçerlidir. Gerekçe: iş 20261013-005509'da kabuller
7. ve 11. çağrıda geldi; en uzun sonuçsuz dizi 6 (1–6). Kayıtlı sırayla hesap: sınır 4/5/6 → 4./5./6. çağrıda durur ve
iki kabulü de kaçırırdı; 7 ve 8 → durmaz (14. çağrı, tavan). 8, gözlenen en uzun diziden 2 çağrı pay bırakır ve tamamen
başarısız bir üretimi tavandan (14) önce keser. Not: ~%14 kabul oranında 8 ardışık sonuçsuzluk şans eseri de ~%30 olasılıkla
görülür; bu sınır kesin arıza işareti değil, harcamayı kullanıcının bakacağı noktaya bağlayan bir korumadır. Aynı hata
sınırı 3 bu işte 3. çağrıda durur ve iki kabulü kaçırırdı; 5 durmaz (K-30 değeri korunur).
Geriye dönük hesap `deneme_kayit.durma_simulasyonu`; orkestratörle aynı kural (testle eşitliği doğrulanır).

**K-32 · 2026-10-13 · Prompt sürümleri yalnız prompt dışındaki her şey aynıyken karşılaştırılır.**
Karşılaştırma anahtarı: kategori, model, ürün ölçüsü (`olcu_id`), sahne görevi (`sahne_gorevi`; şimdilik tek görev
`onden_kare`), referans kümesi (`referans_kumesi`: işte kullanılabilen tüm referans kimliklerinin özeti ya da
`referanssiz`), üretim ayarları (`ayar_ozeti`: kadraj, kılavuz, insanlı, kurdele, katı yerleşim, uzun kenar). Bu alanlar
her çağrı kaydına yazılır. Alanı eksik kayıt (eski biçim) "karşılaştırılamaz" grubuna düşer; tahminle doldurulmaz.

### 2026-10-13 — Çağrı kaydı, insan değerlendirmesi ve kontrollü prompt gelişimi

**K-31 · 2026-10-13 · Ret kaynağı sınıflanır; olası algılama hataları öğrenme verisine katılmaz.**
`deneme_kayit.siniflandir`: oran üründen %8+ farklı → üretim; oran ±%5 uyumlu ama birikme algılanıp boy kısa → olası
algılama; arası → belirsiz; servis hatası ayrı. Eşikler VARSAYIM. İş 20261013-005509: 10 üretim, 1 olası algılama
(#4), 1 belirsiz (#2) — `docs/elenen_analizi_20261013-005509.md`. Kalite eşikleri gevşetilmedi.

**K-30 · 2026-10-13 · Aynı hata art arda 5 kez olursa ücretli üretim durur (Ayarlar'dan değişir, 0 = kapalı); 3'te uyarı.**
Gerekçe: gözlenen kabul oranı ~%14, retlerin ~%75'i aynı imzada → bir sonraki çağrının aynı nedenle elenme olasılığı
≈0,64; 5 ardışık aynı ret şans eseri ≈%11 olasılıkla görülür, yani sorun büyük olasılıkla süreklidir. 3 çok erken
(≈%27 şans eseri). İmza = hata türü + alt neden (kısa/uzun/geniş/…); kabul edilen çağrı seriyi sıfırlar. Durunca kabul
edilenler saklanır, raporda `son_uretim.durdurma` ve eksik sayısı görünür. Sessiz tekrar yok.

**K-29 · 2026-10-13 · İnsan değerlendirmesi (Beğendim / Uygun değil + kısa not) ayrı dosyada: `insan_degerlendirme.json`.**
Otomatik kalite kaydı (`rapor.json`) değişmez; ikisi karıştırılmaz. Yalnız kabul edilen fotoğraflar puanlanır.

**K-28 · 2026-10-13 · Prompt sürümü terfi ölçütleri (yalnız öneri; geçiş kullanıcı onayıyla, geri dönülebilir).**
Aynı kategori + aynı model karşılaştırılır. Aday için en az 12 çağrı, 3 kabul, 3 insan değerlendirmesi; tek başarı
yetmez. Kabul oranı (olası algılama ve servis hataları hariç) etkinden en az 10 puan yüksek, beğeni oranı düşmemiş,
ortalama süre %25'ten fazla artmamış olmalı. Denemeler mevcut harcama tavanı (`max_scene_calls`) içinde yapılır.
Otomatik ücretli iyileştirme döngüsü YOK. Bir kategorinin sürümü diğerlerini etkilemez (`prompt_surumleri` kategori bazlı).

**K-27 · 2026-10-13 · Kısa, bölümlü prompt yapısı (`prompt_yapisi.py`); aday `3A-aday` hiçbir kategoride etkin değil.**
Bölümler ve sınırlar: ürün ≤120 (DEĞİŞTİRİLEMEZ kurallar; metin özeti testle sabit), kamera ≤60, ortam ≤115 (mevcut
havuzda ölçülen en uzun 111), model ≤45; toplam ≤330 (etkin 2A ≈1150 kelime). Sınır aşılırsa sessiz kesme yok, hata.
Her başarısızlıkta cümle EKLENMEZ: tekrarlayan hatanın kaynağı (üretim/algılama) önce ayrılır, gerekirse cümle
değiştirilir/çıkarılır ve sürüm numarası artar. Ürün kurallarını kod otomatik değiştiremez.

**K-26 · 2026-10-13 · Elenen sahnede ham görsel ve algılama görseli ayrı kaydedilir.**
`elenen_<..>_ham.jpg` (servisten gelen) + `elenen_<..>_algilama.jpg` (maske işaretli). `dosya` alanı geriye uyum için
kalır. Eski kayıtlarda ham görsel yoktur; arayüz bunu açıkça yazar, uydurmaz.

**K-25 · 2026-10-13 · Her sahne çağrısı `rapor.json` → `denemeler` altında kaydedilir.**
Alanlar: çağrı no, üretim no, zaman, servis, model kimliği, prompt sürümü, son prompt metni ve özeti, kelime sayısı,
referans kimlikleri (`depo:<kategori>/<dosya>`, `yukleme:<dosya>`), kılavuz, tohum, süre, sonuç, tür, neden, sade
neden, sınıf, hata imzası, art arda sayısı, görsel dosyaları. Anahtar, bağlantı ve base64 yazılmaz (servis hata metni
temizlenir). Eski işlere sonradan eklenmez.

### 2026-10-13 — Yerleştirme kuralı netleşti: tasarımın bütünlüğü önce

**K-24 · 2026-10-13 · Güçlü kıvrım/katlanmada sahne uygunsuz (`sahne_kivrim`); tasarım zorla deforme edilmez.**
Ölçütler (VARSAYIM, gerçek sahnelerle ayarlanacak): tasarımın baskılı kısmının %0,3'ünden fazlası kumaş dışına düşüyorsa
(`TASMA_ESIK`) ya da kumaş kenarının uydurulan doğrudan sapması (p98) enin %6'sını aşıyorsa (`KIVRIM_ESIK`) red;
%3–6 arası kenar sapması yalnız uyarı (kenarda yan döküm, baskı sığıyorsa kabul). Gerçek iş 20261012-224824'te: 01 kenar
sapması %3,9 → uyarı + kabul (kumaş dışı baskı %0,006), 02 %3,0 → kabul.

**K-23 · 2026-10-13 · Tam kumaş yerleşimi TEK HOMOGRAFİ: tasarım bütün olarak tek düzlem dönüşümüyle yerleşir.**
(kullanıcı kararı) PNG kumaşın her dalgasını izlemez. Kenarlara bant içinde (asılı boyun %10–85'i) sağlam düz doğrular
uydurulur; üst kenar ve zemine temas doğrularıyla dörtgen kurulur; PNG tuvalinin tamamı bu dörtgene tek perspektif
dönüşümüyle oturur (önden: eşit ölçek, oran korunur; açılı: tek perspektif). Fiziksel dikey ölçek, gizli bölge ve ±%3
kuralı (K-16) aynen. Işık/gölge/doku çarpma modeliyle. **Önceki K-18'in (yumuşatılmış satır kenarlarıyla yerleşim) yerine
geçti**: K-18 kopmaları gidermişti ama tasarım kenar eğrisini izlediği için iç geometri hafifçe bükülebiliyordu
(dalgalı kenarda tasarımdaki düz çizgi 1,7–4,2 px bükülüyordu; tek homografide 0,00 px). K-18'in yumuşatılmış kenarları
yalnız tanı/temas hesabında kalır.

### 2026-10-13 — Düzeltmenin uygulama akışında doğrulanması

**K-22 · 2026-10-13 · Yeniden birleştirme sonucu YENİ iş olarak kaydedilir; kaynak iş ve görselleri değişmez.**
Yeni iş adı `<tarih>_yeniden_<kaynak tarih>`; raporda `islem: kayitli_sahnelerden_yeniden_birlestirme`, `kaynak_is`,
`saglayici_cagrisi: 0`, her fotoğrafta `kaynak` (iş/sahne/foto/servis). Seçici (servis karnesi) hiç çalışmaz, karne değişmez.

**K-21 · 2026-10-13 · "Kayıtlı sahnelerden yeniden birleştir" işlemi eklendi (ücretsiz, sağlayıcıya istek yok).**
`Orchestrator.recompose_from_scenes(kaynak_is)`; arayüzde sonuç ekranında düğme; `POST /api/yeniden_birlestir`.
Aynı kuralların uygulanması için sahne değerlendirme + yerleştirme (`_evaluate_scene`) ve kabul kaydı (`_save_accepted`)
generate_photos'tan ortak fonksiyonlara ayrıldı; yeni üretim ve yeniden birleştirme aynı kodu kullanır. Oranı
uyuşmayan tasarımda yeni iş "beklemede" kalır.

### 2026-10-12 — Aşama 2A düzeltmesi: baskıda kopmalar

**K-20 · 2026-10-12 · Yalnız işaret merkezi ölçen testler yeterli değil; süreklilik testi zorunlu.**
`tests/test_sureklilik.py`: pürüzlü kenarlı ve sert ışık bantlı sahnede ince çizgi ve harf benzeri şekiller; dönüşümde
satır ikinci farkı ≤ 1 px, katlanma 0, ince çizgi merkezinde satırdan satıra sıçrama ≤ 1,5 px, kopuk satır 0. Eski kodla
başarısız (ham kenar: 7,98 px; yalnız kıvrım kayması: 2,17 px).

**K-19 · 2026-10-12 · Tam kumaş modunda ışık gradyanından kıvrım kayması KAPALI (`TAM_KUMAS_FOLD_SHIFT = 0`).**
Işık gradyanı kumaş geometrisi değildir; gerçek s01 sahnesinde dönüşümü 1688 pikselde katlayıp W/O harflerinde çift
kontur yaptı. Güvenilir bir kıvrım geometrisi yöntemi gelene kadar 0. Kumaş dokusu ve ışık, çarpma baskı modeliyle
(baskı = sahne × tasarım) aynen korunur. Eski yol (mode=None) 0,01 ile değişmeden kalır.

**K-18 · 2026-10-12 · [K-23 ile yerine geçildi] Kumaş kenarları satır satır değil, yumuşak eğri olarak kullanılır (`KENAR_YUMUSATMA` = boyun %2'si).**
Kök neden: satır bazlı alt-piksel kenar ölçümündeki sıçramalar tasarımı o satırlarda yatay koparıyordu (iş
20261012-224824: s01'de 121, s02'de 42 satır). Temas çizgisi altı temas değeriyle sabitlenip Gauss uygulanır; ham kenarlar
tanı için saklanır. Yerleşim koordinatları (üst kenar, cm ölçeği, asılı boy, gizli bölge) değişmez. Bilinen sınır:
kurdele kumaş kenarını örterse o bölgedeki çentik de yumuşatılarak izlenir.

### 2026-10-12 — Aşama 2A

**K-17 · 2026-10-12 · Yerleşim eşikleri VARSAYIM olarak işaretlendi ve raporlanıyor.**
`ORAN_TOLERANSI` %1 (PNG ↔ kumaş), `TAM_BOY_TOL` %3 (sahnede görünen boy ↔ ürün boyu), `OLCUM_PAYI` %0,5, `GIZLI_EN_FAZLA`
%25, `SPREAD_FRAC` %4, `MUREKKEP_ESIK` %0,1. Sentetik sahnelerle seçildi; gerçek sahnelerle ayarlanmadı.

**K-16 · 2026-10-12 · Dikey ölçek: kumaş sahnede kısa görünürse tasarım SIKIŞTIRILMAZ.**
Bağımsız inceleme (quality-reviewer B1) sonrası. Asılı boy ürün boyundan kısa ise ölçek fizikseldir, görünmeyen alt kısım
gizli bölge sayılır ve mürekkep denetimine girer; %3'ten fazla kısa ve birikme yoksa sahne "havada bitiyor" diye reddedilir.
Ürün boyundan en fazla %3 uzun ise tasarım görünen boya sığdırılır ve bu kullanıcıya UYARI olarak yazılır (sessiz değil);
daha uzunsa red. Gerekçe: "yazıyı yapay olarak yukarı taşıma" ve "oranı bozarak esnetme yok" kuralları.

**K-15 · 2026-10-12 · Zemindeki birikmede baskı varsa sahne başarılı sayılmaz (`birikme_cozulemedi`).**
Birikmedeki kıvrımların üzerinde baskı doğru çizilemiyor. Gizli bölge baskısızsa kabul + uyarı + gizli kısım önizlemesi.

**K-14 · 2026-10-12 · Fotoğraf hattında sahne esnetme (`proportion.widen`) kapalı; algılamada kumaş zorunlu.**
Sahne `bd.detect(hint={"kind":"fabric"})` ile alınır; otomatik sert/kumaş sınıflandırması yerleşimi değiştirmez.
Eski yollar (`compositor` mode=None) video modülleri ve eski işler için korunur.

**K-13 · 2026-10-12 · Fotoğraf kadrajı sabit 1:1.** `auto_video_kind` kadrajı etkilemez (önceki: canlı video seçiliyken
9:16). Video koduna yeni 9:16 zorunluluğu eklenmedi; video oranı sonraki aşamada belirlenecek.

**K-12 · 2026-10-12 · Ürün profili `product.UrunProfili` ve örnek ölçü `Settings.ornek_olcu` = 75×200.**
Ölçü kimlikle seçilir (aynı oranlılar ayrı); ölçü cm değerleri rapora kaydedilir; görünür fiyonk (`gorunur_fiyonk`) ile
fiziksel bağlantı (`fiziksel_baglanti.kusgozu`) ayrı; bilinmeyenler None. Profil her işin `rapor.json`'una kopyalanır.

**K-11 · 2026-10-12 · Tam kumaş modu: PNG tuvali = kumaşın tamamı.** (kullanıcı kararı) Kenar payı, içeri küçültme,
kırpma, ortalama ve oran bozan esneme yok. Yatayda kumaşın gerçek kenarları, dikeyde fiziksel ölçek (px/cm = en).

**K-10 · 2026-10-12 · Oran uyuşmazlığında üretim BEKLETİLİR.** (kullanıcı kararı) Uyarı + önizleme; hiç ücretli çağrı
yapılmaz (arayüz/app ve orkestratör iki katmanda). **Önceki öneri "(A) sahne esnetmeyi kapat / (B) %15 esnetme" ve
CLAUDE.md'deki "baskı alanına oranı koruyarak sığdır" kuralının yerine geçti.**

### 2026-10-12 — Aşama 1

**K-09 · 2026-10-12 · Aşama sonu belgeleri: `docs/durum.md` ve `docs/kararlar.md`.**
Kullanıcı projeyi Codex ile de değerlendiriyor; iki araç aynı klasörü okuyor. Her aşama sonunda durum belgesi
güncellenir, önemli kararlar buraya eklenir.

**K-08 · 2026-10-12 · Aşama 2, fiziksel ürün soruları yanıtlanmadan başlamaz.**
Baskı alanı, kuşgözü ve üst kenar yapısı yerleştirmeyi doğrudan belirliyor; uydurulmamalı (`CLAUDE.md`).
Sorular: `docs/durum.md` §4.

**K-07 · 2026-10-12 · Ajan dosyaları `ajanlar_kurulum/` klasörüne konur, kullanıcı `ajanlari_kur.bat` ile kurar.**
Uzaktan bağlantı `.claude/` klasörüne yazmaya izin vermiyor. Kurulumdan sonra Claude Code yeniden açılmalı.

**K-06 · 2026-10-12 · Yedekleme: Git yerine `_yedek/` (zip + Git bundle).**
Kullanıcının klasöründe Git yok ve uzaktan komut çalıştırılamıyor. Çalışma Claude'un alanındaki Git deposunda
yapılıyor; değişiklikten önce kaynak zip'i, sonra bundle bilgisayara yazıldı. `ayarlar.json`, log, karne, iş
çıktıları yedeğe ve Git'e girmez (`.gitignore`).

**K-05 · 2026-10-12 · Selector düzeltmesinde `SELECTOR_VERSION` artırılmadı.**
`save()` yalnız `hist`'i yazdığı için `servis_karnesi.json`'da çift sayım hiç oluşmamıştı. Sürümü artırmak
kullanıcının doğru öğrenilmiş servis verisini sıfırlardı. quality-reviewer onayladı.

**K-04 · 2026-10-12 · Selector seçim hesabı yalnız `hist` kullanır; `run` raporlama içindir.**
`hist` zaten "kalıcı karne + bu iş" toplamı. Thompson formülü, keşif oranı, ardışık hata sınırı, kayıt biçimi
değiştirilmedi (kapsam dışı davranış değişikliği yok). Test eşiği 380 → 330 (doğru beklenen ≈ 358/400).
Geri alma: `_yedek/` zip'indeki `selector.py`.

**K-03 · 2026-10-12 · Mevcut çatı korunur: `app.py` (`http.server`) + `ui.html` + `baslat.bat`.**
Gereksiz framework değişikliği yok; yeni sorumluluklar ince modüllerle eklenir (`product.py`, `scene_plan.py`,
`package.py`, ileride `scenelib.py`).

**K-02 · 2026-10-12 · Güncel gereksinimler `CLAUDE.md`'dedir; `PROJE_NOTLARI.md` geçmiş kaydıdır.**
Çelişkiler sessizce silinmez, `docs/architecture.md` §2'de tabloya yazılır (kuşgözü, kurdelesiz seçenek,
duvar/stand, 9:16 kadraj, fotoğraf başına video, ölçünün PNG'den türetilmesi).

**K-01 · 2026-10-12 · Hedef mimari: sahne hazırlama ile günlük ürün hazırlama ayrılır; ürün türü etkinlik
kategorisinden ayrıdır.**
Onaylı sahneler kütüphanede tekrar kullanılır, günlük üretimde gereksiz ücretli çağrı olmaz. Gelecek ürünler
(tişört, saat, davetiye, menü) için yalnız yerleştirme motoru ve kalite profili türe özel olur.

### Aşama 2 için önerilen kararlar (Aşama 1'de yazılmıştı) — durum
- Fotoğraf kadrajı sabit 1:1 → **K-13 ile uygulandı** (9:16 video kırpması yerine "video oranı sonra belirlenecek").
- Kumaş ürününde yerleşim her zaman kumaş yolundan → **K-14 ile uygulandı**; "baskı alanı profilden" yerine tam kumaş (K-11).
- Oran uyuşmazlığında (A)/(B) seçimi → **yanıtlandı: K-10** (ne esnetme ne sığdırma; üretim bekletilir).
