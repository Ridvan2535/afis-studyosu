# -*- coding: utf-8 -*-
"""
İZLEME (test değil; başarısız olmaz): görüntü küçültülünce program kararının değişmesi — açık algılama sorunu A-01.

Kontrol örneklerinin kabul edilen ham sahnelerini (s01, s02) farklı çözünürlüklere küçültüp yeniden büyütür ve kararı
(kabul/ret), asılı boyu ve temas yöntemini yazdırır. Sorun çözülünce tüm satırlar aynı kararı vermeli; o zaman bu dosya
gerçek bir regresyon testine (tests/test_...) dönüştürülür. Servis çağrısı yok.
Çalıştır: python tests/izle_kucultme_kararliligi.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import orchestrator as orch    # noqa: E402
import product                 # noqa: E402
from providers import Settings  # noqa: E402

D = os.path.join(HERE, "kontrol_ornekleri", "is_005509")
prof = product.profil_olustur("75x200")
o = orch.Orchestrator(Settings(photo_long_side=2400), log=lambda m: None, progress=lambda f, t: None)
design = np.ones((2000, 750, 3), np.float32)
design[300:1700, 150:600] = 0.25
degisen = 0
for ad in ("kabul_s01_ham.png", "kabul_s02_ham.png"):
    raw = cv2.imread(os.path.join(D, ad))
    satir, kararlar = [], set()
    for s in (2400, 2000, 1600, 1536, 1280):
        img = raw if s == raw.shape[0] else o._upscale(cv2.resize(raw, (s, s), interpolation=cv2.INTER_AREA))
        ev = o._evaluate_scene(img, design, prof, f"{ad}@{s}", kararlilik=False)
        tk = ev.get("tk_info") or (ev.get("extra") or {}).get("tam_kumas") or {}
        kararlar.add(ev["ok"])
        satir.append(f"{s}px:{'KABUL' if ev['ok'] else 'RET'} {tk.get('asili_cm', 0):.0f}cm {tk.get('temas_yontemi')}")
    degisen += len(kararlar) > 1
    print(ad, " | ".join(satir), "-> KARAR DEĞİŞİYOR" if len(kararlar) > 1 else "-> kararlı")
print(f"A-01 durumu: {degisen}/2 kabul edilen sahnede küçültme kararı değiştiriyor" + (" (AÇIK)" if degisen else " (çözülmüş görünüyor)"))
