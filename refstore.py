# -*- coding: utf-8 -*-
"""Referans deposu: kategori başına kalıcı klasör (referanslar/<kategori>/).
Her görselin yanında isteğe bağlı aynı adlı .txt dosyası "sahne tarifi" olarak durur;
varsa üretimde o sahne için hazır, ayrıntılı tarif kullanılır."""
from __future__ import annotations

import os
import re
import time

import cv2

import cvio
import prompts

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "referanslar")
EXTS = (".png", ".jpg", ".jpeg", ".webp")
_TR = str.maketrans("çğıöşüÇĞİÖŞÜ ", "cgiosuCGIOSU_")


def slug(category: str) -> str:
    c = prompts.canon(category)
    s = re.sub(r"[^a-z0-9_]+", "", c.translate(_TR).lower().replace("/", "_"))
    return s or "genel"


def folder(category: str, create=False) -> str:
    p = os.path.join(ROOT, slug(category))
    if create:
        os.makedirs(os.path.join(p, ".thumb"), exist_ok=True)
    return p


def _safe_name(name: str) -> str:
    base = os.path.basename(name)
    stem, ext = os.path.splitext(base)
    stem = re.sub(r"[^\w\-.]+", "_", stem, flags=re.UNICODE).strip("._")[:60] or "referans"
    return stem + ext.lower()


def _desc_path(path: str) -> str:
    return os.path.splitext(path)[0] + ".txt"


def list_refs(category: str) -> list[dict]:
    d = folder(category)
    out = []
    if not os.path.isdir(d):
        return out
    for fn in sorted(os.listdir(d)):
        p = os.path.join(d, fn)
        if os.path.isfile(p) and fn.lower().endswith(EXTS):
            desc = ""
            if os.path.isfile(_desc_path(p)):
                with open(_desc_path(p), encoding="utf-8") as f:
                    desc = f.read().strip()
            out.append({"ad": fn, "aciklama": desc, "kucuk": f"/refs/{slug(category)}/.thumb/{fn}.jpg",
                        "buyuk": f"/refs/{slug(category)}/{fn}"})
    return out


def add(category: str, name: str, data: bytes) -> dict:
    import numpy as np
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise ValueError("Görsel okunamadı.")
    d = folder(category, create=True)
    fn = _safe_name(name)
    stem, ext = os.path.splitext(fn)
    if os.path.exists(os.path.join(d, fn)):
        fn = f"{stem}_{time.strftime('%H%M%S')}{ext}"
    p = os.path.join(d, fn)
    with open(p, "wb") as f:
        f.write(data)
    h, w = img.shape[:2]
    f = 360 / max(h, w)
    th = cv2.resize(img, None, fx=f, fy=f, interpolation=cv2.INTER_AREA) if f < 1 else img
    cvio.imwrite(os.path.join(d, ".thumb", fn + ".jpg"), th, [cv2.IMWRITE_JPEG_QUALITY, 82])
    return {"ad": fn, "genislik": w, "yukseklik": h}


def delete(category: str, name: str) -> bool:
    d = folder(category)
    fn = os.path.basename(name)
    p = os.path.join(d, fn)
    if not os.path.isfile(p) or not fn.lower().endswith(EXTS):
        return False
    # silmek yerine _silinen klasörüne taşı: yanlışlıkla silinirse geri alınabilir
    trash = os.path.join(d, "_silinen")
    os.makedirs(trash, exist_ok=True)
    os.replace(p, os.path.join(trash, fn))
    for extra in (_desc_path(p), os.path.join(d, ".thumb", fn + ".jpg")):
        if os.path.isfile(extra):
            if extra.endswith(".txt"):
                os.replace(extra, os.path.join(trash, os.path.basename(extra)))
            else:
                os.remove(extra)
    return True


def set_desc(category: str, name: str, text: str) -> bool:
    d = folder(category)
    p = os.path.join(d, os.path.basename(name))
    if not os.path.isfile(p):
        return False
    text = (text or "").strip()[:3000]
    dp = _desc_path(p)
    if text:
        with open(dp, "w", encoding="utf-8") as f:
            f.write(text)
    elif os.path.isfile(dp):
        os.remove(dp)
    return True


def items(category: str) -> list[tuple[bytes, str]]:
    """Üretim için: [(görsel baytları, sahne tarifi ya da "")]"""
    out = []
    for r in list_refs(category):
        p = os.path.join(folder(category), r["ad"])
        with open(p, "rb") as f:
            out.append((f.read(), r["aciklama"]))
    return out
