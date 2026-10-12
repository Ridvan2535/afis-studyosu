# -*- coding: utf-8 -*-
"""
Kurulum sonrası hızlı kendini sınama (internet ve ücretli servis KULLANMAZ, birkaç saniye sürer).
  1) paketler yüklü mü   2) video yazma/okuma (ffmpeg) çalışıyor mu   3) afiş bulma + tasarım yerleştirme çalışıyor mu
Hepsi geçerse "HER ŞEY TAMAM" yazar.
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
for st in (sys.stdout, sys.stderr):
    try:
        st.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

fails = []


def adim(ad, fn):
    try:
        sonuc = fn()
        print(f"  [TAMAM] {ad}" + (f"  ({sonuc})" if sonuc else ""))
    except Exception as e:                              # noqa: BLE001
        print(f"  [HATA ] {ad}: {e.__class__.__name__}: {e}")
        fails.append(ad)


def paketler():
    import cv2, numpy, scipy, PIL, requests, imageio_ffmpeg  # noqa: F401,E401
    return f"opencv {cv2.__version__}, numpy {numpy.__version__}"


def video():
    import numpy as np
    import video_repair as vr
    ff = vr.find_ffmpeg()
    if not ff:
        raise RuntimeError("ffmpeg bulunamadı (kur.bat'ı yeniden çalıştır)")
    frames = [np.full((96, 160, 3), 40 + 6 * i, np.uint8) for i in range(12)]
    p = os.path.join(HERE, "_kontrol_video.mp4")          # program klasörünün kendisinde dene (yolda Türkçe karakter olabilir)
    try:
        vr.write_video(frames, p, 24.0)
        n = len(vr.read_video(p)[0])
    finally:
        if os.path.exists(p):
            os.remove(p)
    if n < 10:
        raise RuntimeError(f"yazılan videoda {n} kare okunabildi")
    return f"ffmpeg: {ff}"


def yerlestirme():
    import cv2
    import banner_detect as bd
    import compositor as cp
    import cvio
    scene = cvio.imread(os.path.join(HERE, "scene.jpg"))
    design = cp.load_design(os.path.join(HERE, "design_candy.jpg"))
    det = bd.detect(scene)
    if det.reject:
        raise RuntimeError("örnek sahnede afiş bulunamadı: " + det.reject)
    why = cp.check_fit(det, design)
    if why:
        raise RuntimeError("tasarım örnek sahneye uymadı: " + str(why))
    out, info = cp.composite(scene, design, det)
    if out is None or out.shape != scene.shape:
        raise RuntimeError("yerleştirme çıktısı beklenen boyutta değil")
    return f"afiş türü: {det.kind}"


def kamera():
    import numpy as np
    import camera_move as cm
    import video_composite  # noqa: F401  (içe aktarma hatası varsa burada görünür)
    import cvio
    img = cvio.imread(os.path.join(HERE, "scene.jpg"))
    h, w = img.shape[:2]
    rig = cm.CameraRig(w, h, w // 2 * 2, h // 2 * 2, 2.0, 30, "saga", intensity=1.0)
    fr = [rig.render_frame(img, i) for i in (0, 20, 40)]
    if any(f.shape[:2] != (h // 2 * 2, w // 2 * 2) for f in fr):
        raise RuntimeError("kamera çıktısı beklenen boyutta değil")
    if not (np.abs(fr[0].astype(int) - fr[2].astype(int)).mean() > 0.5):
        raise RuntimeError("kamera hareketi görünmüyor")
    return f"yakınlaştırma payı x{rig.z_extra:.3f}"


def secici():
    import random
    import selector
    import providers
    sel = selector.Selector("scene", ["a", "b"], None, rng=random.Random(1), log=lambda m: None, persist=False)
    if sel.pick() != "a":
        raise RuntimeError("servis seçici beklenen sırayı vermedi")
    sel.record("a", True, 90)
    if sel.pick() != "b":
        raise RuntimeError("servis seçici denenmemiş servisi seçmedi")
    return "otomatik servis seçimi hazır"


print("Afiş Stüdyosu kendini sınıyor…")
adim("Paketler", paketler)
adim("Video yazma/okuma", video)
adim("Afiş bulma + tasarım yerleştirme", yerlestirme)
adim("El kamerası (sanal kamera)", kamera)
adim("Otomatik servis seçimi", secici)
print()
if fails:
    print("SORUN VAR:", ", ".join(fails))
    print("Bu ekranın fotoğrafını ya da yazısını bana gönder.")
    sys.exit(1)
print("HER ŞEY TAMAM. baslat.bat ile programı açabilirsin.")
