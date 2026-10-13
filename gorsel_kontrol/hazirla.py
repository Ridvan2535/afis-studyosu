# -*- coding: utf-8 -*-
"""
Görsel Kontrol değerlendirme paketini hazırlar (AĞ YOK, sağlayıcı/model çağrısı YOK).

  python gorsel_kontrol/hazirla.py <isler_klasoru> [--cikti gorsel_kontrol]

Üretilen:
  paket/<kod>/sahne.jpg, maske.png, ust.jpg, alt.jpg, bilgi.json   -> ajana verilen (program kararı/gerekçesi YOK)
  rehber/<ad>.jpg + rehber/rehber.md                               -> açıklamalı öğretim örnekleri
  cevaplar_GIZLI/anahtar.json                                      -> program kararı, otomatik kontrol, insan etiketi
                                                                     (ajana VERİLMEZ; yalnız karsilastir.py okur)
Kaynak iş dosyaları yalnız OKUNUR. Eski kayıtlarda ham görüntü yoksa geri_cevir ile YAKLAŞIK görüntü üretilir ve
'goruntu_turu: yaklasik' olarak işaretlenir.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import banner_detect as bd     # noqa: E402
import deneme_kayit as dk      # noqa: E402
import geri_cevir              # noqa: E402

SAHNE_UZUN_KENAR = 1904        # Claude yüksek çözünürlük sınırının (4784 görsel jeton) altında: ceil(1904/28)^2 = 4624
MASKE_UZUN_KENAR = 1024
KESIT_GENISLIK = 1200

SINIR = {
    "ham": "Ham görüntü (servisten gelen, gerekirse küçültüldü). Fotoğraftan kesin santimetre çıkarılamaz.",
    "yaklasik": ("YAKLAŞIK görüntü: eski kayıt yalnız algılama katmanlı görseli saklamıştı; katman cebirsel olarak geri "
                 "alındı. Ham değildir; maske kenarı çevresindeki renk ve ince ayrıntı güvenilmez. Orijinal sahne kurtarılamaz."),
    "isaretsiz_jpeg": "Eski kayıtta katmansız ama JPEG %80 kayıplı kaydedilmiş görüntü; ince ayrıntı kaybı olabilir.",
}


def kod_uret(*parca) -> str:
    return "g" + hashlib.sha256("|".join(parca).encode("utf-8")).hexdigest()[:6]


def _boyut(img, uzun):
    h, w = img.shape[:2]
    f = uzun / max(h, w)
    return cv2.resize(img, (int(round(w * f)), int(round(h * f))), interpolation=cv2.INTER_AREA) if f < 1 else img


def _kesitler(img, m):
    ys, xs = np.where(m > 0)
    if len(ys) < 100:
        return None, None
    y0, y1, x0, x1 = ys.min(), ys.max(), xs.min(), xs.max()
    h, w = img.shape[:2]
    pad_x = int(0.2 * (x1 - x0)); band = int(0.10 * (y1 - y0))
    xa, xb = max(0, x0 - pad_x), min(w, x1 + pad_x)
    ust = img[max(0, y0 - band):min(h, y0 + band), xa:xb]
    alt = img[max(0, y1 - band):min(h, y1 + band), xa:xb]
    return _boyut(ust, KESIT_GENISLIK), _boyut(alt, KESIT_GENISLIK)


def ornek_goruntu(is_dir, rap, ref):
    """(sahne, maske, goruntu_turu, kayit) — ref: 'cN' (elenen çağrı N) ya da 'sNN' (kabul edilen sahne)."""
    if ref.startswith("c"):
        c = int(ref[1:])
        e = next(x for x in rap.get("elenenler", []) if int(x.get("cagri") or 0) == c)
        if e.get("ham_dosya"):
            img = cv2.imread(os.path.join(is_dir, e["ham_dosya"]))
            m = bd.detect(img, hint={"kind": "fabric"}).mask
            return img, m, "ham", e
        vis = cv2.imread(os.path.join(is_dir, e["dosya"]))
        img, m, renk = geri_cevir.yaklasik_sahne(vis)
        if renk == "yok":
            return img, bd.detect(img, hint={"kind": "fabric"}).mask, "isaretsiz_jpeg", e
        return img, m * 255, "yaklasik", e
    img = cv2.imread(os.path.join(is_dir, "sahneler_bos", ref + ".png"))
    m = bd.detect(img, hint={"kind": "fabric"}).mask
    foto = next((p for p in rap.get("fotograflar", []) if p.get("stem") == ref), None)
    return img, m, "ham", foto


def paket_yaz(hedef, kod, img, m, tur, urun):
    os.makedirs(hedef, exist_ok=True)
    cv2.imwrite(os.path.join(hedef, "sahne.jpg"), _boyut(img, SAHNE_UZUN_KENAR), [cv2.IMWRITE_JPEG_QUALITY, 92])
    mm = ((m > 0) * 255).astype(np.uint8)
    cv2.imwrite(os.path.join(hedef, "maske.png"), _boyut(mm, MASKE_UZUN_KENAR))
    ust, alt = _kesitler(img, mm)
    if ust is not None:
        cv2.imwrite(os.path.join(hedef, "ust.jpg"), ust, [cv2.IMWRITE_JPEG_QUALITY, 92])
        cv2.imwrite(os.path.join(hedef, "alt.jpg"), alt, [cv2.IMWRITE_JPEG_QUALITY, 92])
    bilgi = {"kod": kod, "urun": {"olcu": urun["olcu"], "en_cm": urun["en_cm"], "boy_cm": urun["boy_cm"],
                                  "en_boy_orani": round(urun["en_cm"] / urun["boy_cm"], 4)},
             "goruntu_turu": tur, "degerlendirme_siniri": SINIR[tur],
             "maske_kaynagi": ("programın o üretimdeki maskesi (katmandan çıkarıldı)" if tur == "yaklasik"
                               else "programın bugünkü algılaması")}
    with open(os.path.join(hedef, "bilgi.json"), "w", encoding="utf-8") as f:
        json.dump(bilgi, f, ensure_ascii=False, indent=1)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("isler")
    ap.add_argument("--cikti", default=HERE)
    ap.add_argument("--plan", default=os.path.join(HERE, "ornek_plani.json"))
    ap.add_argument("--kume", choices=("degerlendirme", "ilk_deneme"), default="degerlendirme",
                    help="ilk_deneme: yalnız plandaki 6-8 örnek (önerilen çıktı klasörü gorsel_kontrol/ilk_deneme)")
    a = ap.parse_args(argv)
    plan = json.load(open(a.plan, encoding="utf-8"))
    if a.kume == "ilk_deneme":
        bloklar = {}
        for o in plan["ilk_deneme"]["ornekler"]:
            bloklar.setdefault(o["is"], []).append(o["ornek"])
        plan = dict(plan, degerlendirme=[{"is": i, "grup": "ilk_deneme", "ornekler": r} for i, r in bloklar.items()])
    urun = plan["urun"]
    oran = urun["en_cm"] / urun["boy_cm"]
    anahtar, sayac = {}, {}
    for blok in plan["degerlendirme"]:
        is_dir = os.path.join(a.isler, blok["is"])
        rap = json.load(open(os.path.join(is_dir, "rapor.json"), encoding="utf-8"))
        insan = dk.insan_oku(is_dir)
        for ref in blok["ornekler"]:
            kod = kod_uret(blok["is"], ref)
            img, m, tur, kayit = ornek_goruntu(is_dir, rap, ref)
            paket_yaz(os.path.join(a.cikti, "paket", kod), kod, img, m, tur, urun)
            if ref.startswith("c"):
                ks = dk.kontrol_sonucu(kayit, oran, urun["boy_cm"])
                prog = {"karar": "ret", "tur": kayit.get("tur"), "neden": kayit.get("neden"), "kontrol": ks["durum"],
                        "guven": ks.get("guven")}
                ins = (insan.get("elenenler") or {}).get(dk.elenen_anahtari(kayit))
            else:
                prog = {"karar": "kabul", "kontrol": "uygun"}
                ins = (insan.get("fotograflar") or {}).get((kayit or {}).get("ad", ""))
            anahtar[kod] = {"is": blok["is"], "ornek": ref, "grup": blok["grup"], "goruntu_turu": tur, "program": prog,
                            "insan": ins}
            sayac[tur] = sayac.get(tur, 0) + 1
    os.makedirs(os.path.join(a.cikti, "cevaplar_GIZLI"), exist_ok=True)
    with open(os.path.join(a.cikti, "cevaplar_GIZLI", "anahtar.json"), "w", encoding="utf-8") as f:
        json.dump({"uyari": "AJANA VERİLMEZ. Program kararı ve insan etiketi doğru cevap değildir; karşılaştırma içindir.",
                   "ornekler": anahtar}, f, ensure_ascii=False, indent=1)
    print(f"paket: {len(anahtar)} örnek {sayac}; anahtar: cevaplar_GIZLI/anahtar.json")
    return anahtar


if __name__ == "__main__":
    main()
