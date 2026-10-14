# Gelen kutusu: video-engineer

(Yeni mesajı dosyanın SONUNA ekle; eski mesajları silme.)

## [HATA] M-pipeline-engineer-1 Kompozit/hareketli videoda tasarım tam kumaş kuralıyla basılmıyor   (görev: G5a bulgusu)
- Ne: video_composite.py:219 ve video_track.py:201 `cp.composite(ref, design, det, return_model=True)` çağrısı `mode="tam_kumas"`/`profile` vermiyor; fotoğraflar tam kumaş moduyla (fiziksel ölçek) basılıyor. generate_composite_video / generate_live_video videolarında tasarım kayıtlı fotoğraftakinden farklı boyda/yerde olabilir. orchestrator tarafında (G5a) yalnız kamera videosu ve generate_video (onarım) yolları tutarlılık denetimine bağlandı (`_video_tutarlilik`: eski "temas_cizgisine_kadar" kaydı ya da yeniden yerleşimde `sorunlar` -> kayıtlı fotoğraf / görünür uyarı).
- Beklenen: compose_video / compose_tracked'e isteğe bağlı `profile` (ürün profili) parametresi; verilirse `cp.composite(..., mode="tam_kumas", profile=profile)` ve `info["sorunlar"]` boş değilse CompositeError ya da özette uyarı. Eklediğinde bana yaz; orchestrator çağrılarına `profile=self._entry_profile(rap, entry)` geçiririm.
