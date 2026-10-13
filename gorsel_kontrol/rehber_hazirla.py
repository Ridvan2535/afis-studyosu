# -*- coding: utf-8 -*-
"""Rehber (öğretim) görsellerini üretir: 5 sentetik sahne (geometrisi KESİN bilinir) + 3 gerçek örnek (005509).
  python gorsel_kontrol/rehber_hazirla.py <isler_klasoru>
Rehber örnekleri başarı ölçümünde KULLANILMAZ (ornek_plani.json). AĞ YOK."""
from __future__ import annotations

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import banner_detect as bd     # noqa: E402
import geri_cevir              # noqa: E402
import mock_provider as mp     # noqa: E402

UZUN = 768


def kucult(img):
    h, w = img.shape[:2]
    f = UZUN / max(h, w)
    return cv2.resize(img, (int(w * f), int(h * f)), interpolation=cv2.INTER_AREA)


def main(isler):
    plan = json.load(open(os.path.join(HERE, "ornek_plani.json"), encoding="utf-8"))
    out = os.path.join(HERE, "rehber")
    os.makedirs(out, exist_ok=True)
    for r in plan["rehber"]:
        if r["kaynak"] == "sentetik":
            img, t = mp.square_scene(1536, r["oran"], r["tur"], seed=7)
            m = bd.detect(img, hint={"kind": "fabric"}).mask
        else:
            p = os.path.join(isler, r["is"], r["dosya"])
            v = cv2.imread(p)
            if r["dosya"].endswith(".png"):
                img, m = v, bd.detect(v, hint={"kind": "fabric"}).mask
            else:
                img, m1, _ = geri_cevir.yaklasik_sahne(v)
                m = m1 * 255
        cv2.imwrite(os.path.join(out, r["ad"] + "_sahne.jpg"), kucult(img), [cv2.IMWRITE_JPEG_QUALITY, 90])
        cv2.imwrite(os.path.join(out, r["ad"] + "_maske.png"), kucult(((m > 0) * 255).astype(np.uint8)))
    print("rehber görselleri:", out)


if __name__ == "__main__":
    main(sys.argv[1])
