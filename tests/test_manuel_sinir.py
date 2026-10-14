# -*- coding: utf-8 -*-
"""Manuel sınır — dört köşe modu (K-55). YEREL test; ağ yok, ücret yok, yeni üretim yok. Örnek: iş 053942 ham sahnesi.
  1. Köşeler kumaşın üzerinde: bölge = dörtgen ∩ otomatik kumaş maskesi -> kabul; kurdele pikselleri DEĞİŞMEZ.
  2. Tasarım kenarında mürekkep var ve kurdele kumaş kenarını örtüyor: kurdelenin üstüne basılmaz; mürekkep sığmadığı için
     kabul edilmez (sahne_kivrim), foto/ boş.
  3. Köşeler kumaşla örtüşmüyor (duvar): dörtgene otomatik baskı YOK -> manuel_maske_zayif, foto/ boş, açık uyarı.
  4. Kaynak iş klasörü bayt bayt değişmez; her sonuç ayrı yeni işte.
  5. G5a olumsuz durumlar: görsel olmayan dosya, sahneler_bos/ dışındaki dosya (tasarım görseli dahil), üst dizine kaçış,
     üst çizgi alt çizginin altında, köşe sırası ters -> ProviderError ve HİÇ iş klasörü açılmaz (yarım iş kalmaz).
"""
import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import cv2                       # noqa: E402
import numpy as np               # noqa: E402

import orchestrator as orch      # noqa: E402
from providers import Settings   # noqa: E402

HAM = os.path.join(HERE, "kontrol_ornekleri", "is_053942", "ham.jpg")
KUMAS = [[0.19, 0.12], [0.53, 0.12], [0.53, 0.95], [0.19, 0.95]]
DUVAR = [[0.60, 0.20], [0.95, 0.20], [0.95, 0.90], [0.60, 0.90]]


def md5_klasor(d):
    return {os.path.relpath(os.path.join(r, f), d): hashlib.md5(open(os.path.join(r, f), "rb").read()).hexdigest()
            for r, _, fs in os.walk(d) for f in fs}


def kaynak(t, kenar_murekkep=False):
    src = os.path.join(t, "kaynak" + ("_kenar" if kenar_murekkep else ""))
    os.makedirs(os.path.join(src, "sahneler_bos"))
    shutil.copy(HAM, os.path.join(src, "sahneler_bos", "ham.jpg"))
    rgba = np.zeros((2000, 750, 4), np.uint8)
    rgba[350:450, 150:600] = (30, 30, 30, 255)
    rgba[1760:1840, 200:550] = (30, 30, 30, 255)
    if kenar_murekkep:
        rgba[100:1900, 10:40] = (30, 30, 200, 255)
    cv2.imwrite(os.path.join(src, "tasarim.png"), rgba)
    with open(os.path.join(src, "sahneler_bos", "bozuk.jpg"), "w", encoding="utf-8") as f:
        f.write("bu bir görsel değil")
    json.dump({"urun_profili": {"olcu_id": "75x200"}}, open(os.path.join(src, "rapor.json"), "w"))
    return src


with tempfile.TemporaryDirectory() as t:
    orch.JOBS_DIR = os.path.join(t, "isler")
    O = orch.Orchestrator(Settings(photo_long_side=2400, strict_layout=True), log=lambda m: None, progress=lambda f, x: None)
    src, src2 = kaynak(t), kaynak(t, True)
    once, once2 = md5_klasor(src), md5_klasor(src2)

    r1 = O.manuel_sinir(src, "sahneler_bos/ham.jpg", koseler=KUMAS)
    assert r1["sonuc"] == "kabul", r1
    j1 = os.path.join(orch.JOBS_DIR, r1["job"])
    ph = json.load(open(os.path.join(j1, "rapor.json"), encoding="utf-8"))["fotograflar"][0]
    out = cv2.imread(os.path.join(j1, "foto", ph["ad"])).astype(int)
    sc = cv2.imread(os.path.join(j1, "sahneler_bos", ph["stem"] + ".png")).astype(int)
    H, W = sc.shape[:2]
    bolge = np.zeros((H, W), bool)
    bolge[int(.12 * H):int(.95 * H), int(.19 * W):int(.53 * W)] = True
    kurdele = (sc[..., 0] > sc[..., 2] + 35) & bolge                   # dörtgenin içine düşen mavi kurdele pikselleri
    assert kurdele.sum() > 5000, kurdele.sum()
    degisen = float((np.abs(out - sc).max(2)[kurdele] > 25).mean())
    assert degisen < 0.005, f"kurdelenin üstüne basılmış: %{degisen * 100:.2f}"
    assert ph["manuel_sinir"]["koseler"] == KUMAS and ph["tam_kumas"]["gorunen_murekkep"] >= 0.999
    print(f"1) köşeler kumaşta: kabul, kurdele piksellerinin %{degisen * 100:.2f}'i değişti, asılı {ph['tam_kumas']['asili_cm']} cm")

    r2 = O.manuel_sinir(src2, "sahneler_bos/ham.jpg", koseler=KUMAS)
    assert r2["sonuc"] == "kabul_edilmedi" and r2["tur"] == "sahne_kivrim", r2
    assert not os.listdir(os.path.join(orch.JOBS_DIR, r2["job"], "foto"))
    print("2) kenarda mürekkep + kurdele:", r2["tur"], "(kurdelenin üstüne basılmadı, kabul yok)")

    r3 = O.manuel_sinir(src, "sahneler_bos/ham.jpg", koseler=DUVAR)
    assert r3["sonuc"] == "inceleme" and r3["tur"] == "manuel_maske_zayif", r3
    j3 = os.path.join(orch.JOBS_DIR, r3["job"])
    assert not os.listdir(os.path.join(j3, "foto")) and not os.path.isdir(os.path.join(j3, "onizleme"))
    e = json.load(open(os.path.join(j3, "rapor.json"), encoding="utf-8"))["elenenler"][0]
    assert "baskı yapılmadı" in e["sade_neden"] and e["siniflama"]["durum"] == "inceleme"
    print("3) köşeler duvarda:", e["sade_neden"])

    # 5) olumsuz durumlar: doğrulama iş klasörü açılmadan yapılır
    from providers import ProviderError       # noqa: E402
    isler_once = sorted(os.listdir(orch.JOBS_DIR))
    olumsuz = [("görsel olmayan dosya", "sahneler_bos/bozuk.jpg", dict(koseler=KUMAS), "görsel olarak okunamadı"),
               ("sahneler_bos dışı (tasarım)", "tasarim.png", dict(koseler=KUMAS), "sahneler_bos"),
               ("üst dizine kaçış", "sahneler_bos/../tasarim.png", dict(koseler=KUMAS), "sahneler_bos"),
               ("var olmayan dosya", "sahneler_bos/yok.jpg", dict(koseler=KUMAS), "bulunamadı"),
               ("üst çizgi altta", "sahneler_bos/ham.jpg", dict(ust=[[0.2, 0.9], [0.5, 0.9]], alt=[[0.2, 0.2], [0.5, 0.2]]),
                "üstünde olmalı"),
               ("çizgiler bir uçta kesişiyor", "sahneler_bos/ham.jpg", dict(ust=[[0.2, 0.1], [0.5, 0.7]], alt=[[0.2, 0.9], [0.5, 0.6]]),
                "üstünde olmalı"),
               ("köşe sırası ters", "sahneler_bos/ham.jpg", dict(koseler=[KUMAS[3], KUMAS[2], KUMAS[1], KUMAS[0]]), "Köşe sırası")]
    for ad, dosya, kw, beklenen in olumsuz:
        try:
            O.manuel_sinir(src, dosya, **kw)
            raise AssertionError(f"{ad}: hata verilmedi")
        except ProviderError as e:
            assert beklenen in str(e), (ad, str(e))
        assert sorted(os.listdir(orch.JOBS_DIR)) == isler_once, f"{ad}: yarım iş klasörü açıldı"
    print(f"5) {len(olumsuz)} olumsuz durum: hepsi reddedildi, iş klasörü açılmadı")
    # Windows ters bölüsüyle verilen yol da kabul edilir; raporda yol "/" ile yazılır
    r4 = O.manuel_sinir(src, "sahneler_bos\\ham.jpg", koseler=KUMAS)
    k4 = json.load(open(os.path.join(orch.JOBS_DIR, r4["job"], "rapor.json"), encoding="utf-8"))["fotograflar"][0]["kaynak"]
    assert r4["sonuc"] == "kabul" and k4["dosya"] == "sahneler_bos/ham.jpg", (r4, k4)

    assert md5_klasor(src) == once and md5_klasor(src2) == once2, "kaynak iş değişti"
    assert len({r1["job"], r2["job"], r3["job"]}) == 3
print("test_manuel_sinir: TAMAM")
