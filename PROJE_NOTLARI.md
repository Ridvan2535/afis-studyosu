# Afiş Stüdyosu — proje notları (yeni bir konuşmaya geçilirse buradan devam edilir)

## Ne yapıyor
Kullanıcının gerçek tasarım PNG'sinden Etsy için hambez (krem, baskılı) afiş mockup fotoğrafları ve kısa videolar üretir.
Sahne (boş afişli) yapay zekâdan gelir; tasarım HER ZAMAN kodla basılır, yapay zekâ yazıyı çizmez. Başlatma: `baslat.bat`.
Çalışma biçimi: kod değişiklikleri doğrudan bu klasöre yazılır; kullanıcı `baslat.bat`'ı kapatıp açar. `ayarlar.json` ve `tasarim.*` dosyalarına dokunulmaz.

## Satılan ölçüler (cm, en x boy)
50x100, 50x150, 75x200, 150x300, 150x400. Çoğunlukla **75x200**. Afiş oranı tasarımdan gelir, sahnedeki afiş bu orandan
daha geniş/farklı olmamalı (istem gerçek ölçüyü birebir ister; fazla ince çizilirse yatayda genişletilip tam orana getirilir).
Ölçü tablosu görseli yalnızca referanstır.

## Onaylanan ayarlar (kaybolmasın)
- Kamera videosu: **"Yaklaşırken sağa doğru dön (yay çizerek)"** (`yakinlas_saga`), el sallantısı **Doğal el** (`yuruyus`, k=0.35),
  6 sn, yaklaşma ~2.0x, kamera ~24° yay, adım sıklığı 1.4-1.6 Hz, video kaynağı 1.6x büyütülüp tasarım yeniden basılır.
- Her fotoğraf için otomatik video: AÇIK (Ayarlar > Otomatik video).
- Otomatik servis seçimi (sahne ve video): AÇIK; karne `servis_karnesi.json`.
- ÜRÜN/SAHNE (güncel, referans görsellere göre): afiş ince açık ahşap yuvarlak çubuğa asılır; çubuk, afişin hemen arkasındaki ince ahşap serbest çerçevenin (iki dikme + ayaklar) üst çubuğudur. İki üst köşede yumuşak kurdele rahat bir fiyonkla bağlanır, uzun kuyruklar afişin dış yan kenarlarından aşağı (boyun ~%35-45'i) sarkar. Tavana/ağaca asılı sürüm İSTENMİYOR. Müşteriye stand satılmıyor; stand yalnızca sahne dekoru. Gerçekte afişte köşelerde metal halka (kuş gözü) bulunur.
- Kurdele rengi: Ayarlar > Kurdele renkleri (ad + renk; kullanıcı kendi renklerini ekler), fotoğraf ekranında sadece renk seçilir. İlham görsellerindeki kurdele rengi yok sayılır. "Kurdelesiz" seçeneği düz çubuk. Kurdele kuyruğu tasarıma binerse (renkli kurdelelerde) `ribbon.py` kurdele piksellerini geri koyar.
- Varsayılan sahne: duvara asılı, boş, yere kadar uzanan, karşıdan çekilmiş afiş.

## Servis durumu (son bilinen)
- Çalışan: Magnific Seedream 4.5 Edit (kılavuz görselli). Seedream 5 Pro Edit hata veriyordu (nedeni bilinmiyor).
- OpenAI: hesapta kredi yok. Gemini: kota/faturalandırma kapalı. Düzelince otomatik denenir.

## Açık konular
- Kurdeleli/halkalı yeni sahne isteminin algılama ve yerleştirme davranışı gerçek görselle denenmedi.
- Hareketli sahne (kompozit) videosu gerçek yapay zekâ videosunda denenmedi; Runway uç noktası, Windows .bat, TopView denemesi bekliyor.
- Stand satılmıyor; stand'li görünüm yapılmayacak.

## Kutlama türüne göre arka planlar (v9)
- `prompts.CATEGORIES`: Düğün, Nişan / Kına, Bekarlığa veda, Baby shower, Cinsiyet partisi, Çocuk doğum günü, Yetişkin doğum günü, Mezuniyet, Yılbaşı (her biri 6-9 zengin sahne; "OUT:" açık hava, "IN:" iç mekan).
- Işık/saat sahneden bağımsız seçilir (LIGHTS_OUT/IN); her iş rastgele bir sahneden başlar (`sahne_baslangic`).
- Düğün, nişan, mezuniyet, yılbaşı vb. için arkada misafirler otomatik (`PEOPLE_DEFAULT`).
- Eski "Doğum günü / Baby shower" adı Baby shower'a eşlenir (ALIASES). SELECTOR_VERSION = 9.

## Gerçek hareketli video + TopView (v10)
- Kullanıcı şikayeti: düz fotoğrafa yaklaşma hissi; kurdele/çocuk hareket etmiyor; yay çizerken arka plan değişmiyor.
- Çözüm: `Orchestrator.generate_live_video`: YZ video modeli (Veo 3.1 / Kling / TopView modelleri) TASARIMSIZ sahnede kamerayı yürütür (`prompts.MOTION_LIVE`), `video_track.compose_tracked` afiş düzlemini (afiş+dikmeler+çubuk) optik akış+RANSAC+ECC ile izleyip tasarımı her kareye basar; önüne giren şey (kurdele ucu, kişi) bastırılır. Kalite kontrol geçmezse kamera videosuna döner.
- Ayar: `auto_video_kind` = "canli" (varsayılan, ücretli, otomatik videoda 1 deneme) | "kamera" (ücretsiz). UI: Ayarlar > Otomatik video; video türü listesinde "Gerçek hareketli sahne".
- TopView: `providers.TopViewVideo` (tv-kling, tv-veo, tv-seedance); ayarlar `topview_key`, `topview_uid`. Dokümandan yazıldı, gerçek anahtarla DENENMEDİ.
- Stand/kurdele: afiş çubuktan serbest sarkar, dikmeler görünür, kurdele kuyrukları afişin DIŞINDA, kenar şeridi/püskül yok, etek zemine yatar.

## v11 (gerçek Veo videosu üzerinden düzeltmeler)
- Kullanıcının gerçek Veo videosunda (canli_ai_1.mp4) takip, yürüyen insanlar yüzünden kopuyordu → `video_track.track`: tüm karede çoğunluk hareketi (RANSAC) + düzlem noktaları, sıçrama kapısı, ilk kareye karşı çok ölçekli ECC (önüne girenler maskelenir), düzlem-only yedek. Gerçek videoda baskı artık kare boyunca afişte kalıyor, insanlar önünden geçerken gizleniyor.
- Veo kamerayı neredeyse hiç oynatmamıştı → `MOTION_LIVE` yeniden yazıldı (kamera talimatı en başta, dolly-in + sağa yay, parallax, kimse kamerayla afiş arasından geçmesin). DOĞRULANMADI: gerçek Veo yeni istemle denenmeli. Hâlâ durağan kalırsa: Kling/Seedance (TopView), ya da bitiş karesi (start/end frame) ile hareket zorlama.
- Canlı video açıkken sahneler baştan 9:16 üretilir (video 9:16 kırpmaya sığmıyordu).

## v12 – Magnific araştırması ve test paketi
- Magnific API dokümanında düzenleme (referans görselli) tarafında yalnızca Seedream 4.5 Edit ve Flux Kontext var; GPT Image / Nano Banana sitede var, API'de belgelenmemiş.
- `test_paketi.bat` (test_paketi.py): kılavuz görsel + hazır promptlar üretir; kullanıcı Magnific sitesinde GPT 2 / Nano Banana 2 / Seedream 5 Pro'yu elle dener. Sonuca göre servis listesi sadeleştirilecek.
- Seedream 5 Pro Edit hatasının nedeni hâlâ doğrulanmadı (görsel URL isteyebilir; yerel URL barındırma yok).

## v13 – log'dan düzeltmeler (12 Ekim)
- Seedream 5 Pro Edit: Magnific hatası "invalid url specified: iVBOR..." -> görsel `data:image/png;base64,...` biçiminde gönderiliyor (providers._data_uri). Gerçek anahtarla doğrulanacak. 4.5 Edit ham base64 ile çalışıyor, değişmedi.
- Kling: eski adres "kling-pro" 404 veriyordu -> `kling-v2-6-pro` (+ social_story_9_16). Sorgu adresi dokümanda yok; 404 olursa `kling-v2-6` denenir.
- Runway "400 Validation error": uç nokta adı/parametreleri doğrulanmadı, otomatik listeden çıkarıldı (VIDEO_ORDER). Elle seçim hâlâ var.
- Kullanıcı testi: prompt 2 (yeni sahne, referans stil) + Seedream 5 Pro sahnesi programdan sorunsuz geçti (afiş algılandı, baskı yerleşti). Rakip fotoğrafıyla "aynı sahne" üretimi hem hukuki risk hem algılama sorunu (kurdeleler kenara biniyor).

## v14 – referans deposu, video kapalı (12 Ekim)
- Seedream 5 Pro Edit artık çalışıyor (data URI düzeltmesi doğrulandı: 2/2 sahne kabul, kalite 83). Kling Pro 404'ü giderildi ama videoda izleme koptu (kalite kontrolü geçmedi). Runway hâlâ doğrulanmadı.
- Otomatik video varsayılan KAPALI (ayarlar servis_surumu 3'te bir kez kapatılır; kullanıcı Ayarlar'dan açabilir). Video yalnız "Video üret" ile başlar. Canlı video türü seçiliyken sahne yine 9:16 üretilir.
- Referans deposu: `refstore.py`, klasör `referanslar/<kategori_slug>/` (görseller + isteğe bağlı aynı adlı .txt "sahne tarifi"; .thumb küçük resimler; silinenler _silinen'e taşınır). Arayüzde Üret sekmesinde kategoriye göre liste/ekle/sil/tarif. Üretimde her sahne sırayla depodaki bir referansı alır (tek referans/çağrı); tarifi varsa kategori havuzu yerine o tarif kullanılır (prompts.build_scene_prompt scene_desc). Depo boşsa eski davranış.
- Prompt stratejisi (kullanıcı fikri): referans görsel görünümü, sahne tarifi (.txt) niyeti taşır; sabit kurallar (boş afiş, çerçeve, kurdele, zemin) kodda kalır. Tarifleri Claude referans görsellere bakarak yazar.
- Bilinen: model afişi tasarımdan ince çiziyor (oran 0.36-0.40, tasarım 0.51) -> yatay genişletme x1.28-1.45; ölçüler 50x100 gibi geniş afişlerde kılavuz görsele rağmen ince kalıyor.
