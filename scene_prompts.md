# Boş afişli sahne üretim istemleri

Bu istemleri bir görsel modeline (Gemini görsel, Flux, GPT Image, Midjourney vb.) ver; çıkan görselleri
`sahneler/` klasörüne koy, `pipeline.py` gerisini yapar. Aşağıdaki kurallar **algılamanın çalışması için şart**:

## Her istemin sonuna eklenecek ortak kurallar
- Afiş **tamamen boş**: yazı, desen, logo, süs, kenar çizgisi yok. (Yazı çizilmiş sahneler otomatik elenir.)
- Afiş **beyaz / krem / açık gri** ve **mat** (boyalı/renkli ya da koyu afiş baskıyı bozar).
- Afiş **tam olarak kadrajın içinde**, kesilmemiş, ön planda, görüntünün yaklaşık %10-35'ini kaplıyor.
- Afişin arkası ve çevresi afişten **belirgin biçimde farklı renk/ton** (beyaz duvar önünde beyaz afiş = algılanamaz).
- **Sert afiş** için: düz dikdörtgen, **en-boy oranı tasarımınla aynı** (örn. 2:5 dikey), perspektif hafif.
- İnsan, el, balon, çiçek **afişin önünü kapatmasın** (bu sürüm afişin önündeki nesneleri maskelemiyor).

Ortak ek metin (kopyala-yapıştır):
> blank plain matte off-white banner, completely empty with no text, no pattern, no border, fully visible and
> uncropped, centered, strong contrast against the background, photorealistic, natural light, shot on 85mm lens

## Düğün (tasarımını bitir, bu 6 sahneyi sırayla dene)
1. Bahçe düğünü, ahşap standa asılı **kumaş** afiş, beyaz tül perdeler, yeşil çimen
2. Salon girişi, zemin üstünde **şövale/stand** üzerinde sert beyaz afiş, çiçek aranjmanı yan tarafta (önünü kapatmadan)
3. Rustik duvar önünde ahşap çerçeveli boş poster, loş sıcak ışık, mum ve yeşillik
4. Minimal stüdyo, bej duvar, ince siyah çerçeveli boş poster, yumuşak pencere ışığı
5. Sahil düğünü, bambu/ahşap kemer yanında dikey **kumaş** afiş, hafif rüzgarlı, kum zemin
6. Şık balo salonu, altın çerçeveli büyük boş poster, koyu duvar, vurgulu tek ışık

## Doğum günü
1. Pastel renkli parti masası arkasında duvara asılı boş beyaz afiş, balon demetleri **afişin yanında**
2. Çocuk odası, açık renk duvarda ahşap çerçeveli boş poster
3. Bahçe partisi, kumaş afiş, ip ışıklar, çim zemin
4. Modern salon, koyu duvarda beyaz çerçeveli boş poster, konfeti masada (afişin önünde değil)
5. Kapı girişi karşılama panosu: ahşap stand üstünde boş sert beyaz pano
6. Stüdyo çekimi: düz pastel arka plan, ayakta duran boş karton afiş (easel)

## İpuçları
- Önce 10-12 sahne üret, `pipeline.py` geçerli olanları seçsin; kalan eksik sayıyı rapor eder, onu yeniden üret.
- Afiş çok küçük çıkıyorsa istemde "banner fills about a quarter of the frame" de.
- Tasarımın en-boy oranına göre sahnede afiş oranını belirt ("tall portrait banner, 2:5 ratio").
- Kumaş afişte tasarım kıvrımlara göre hafif bükülür; çok kıvrımlı/dalgalı kumaş yerine hafif asılı kumaş seç.
