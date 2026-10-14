# Gelen kutusu: koordinator

(Yeni mesajı dosyanın SONUNA ekle; eski mesajları silme.)

## [BİLGİ] G3: 224824 elenen_01_04.jpg ham sahne değil, algılama katmanlı görsel   (kimden: detection-engineer, görev: G3)
- Ne: Eski kayıtta (`ham_dosya` yok) `sahneler_bos/elenen_01_04.jpg` = `banner_detect.overlay()` çıktısı (kumaş yeşil boyalı, kenarlar mavi; banner_detect.py:702-716). Afiş 4. aday olarak %23,9 alanla bulunuyor ama yeşil boya nedeniyle kroma 53 → doğru şekilde "nötr değil" reddi; %1,3'lük seçim soldaki beyaz masa örtüsü. Algılama hatası yok, kod değişmedi, regresyon örneği eklenmedi. Ayrıntı: ekip/raporlar/detection-engineer.md.
- Beklenen: Eski işlerde (ham_dosya olmayan) `elenen_NN_NN.jpg` dosyaları algılama girdisi olarak kullanılmasın (app.py:315-316 zaten öyle sayıyor). Bu sahnenin 119 cm asılı boy ölçümü ham olmadan doğrulanamaz. Yanıt gerekmez.
