# -*- coding: utf-8 -*-
"""
Türkçe karakterli klasör adlarına (ör. C:\\Users\\ad\\Masaüstü\\...) dayanıklı dosya okuma/yazma.

Windows'ta OpenCV'nin imread/imwrite/VideoCapture/VideoWriter işlevleri adında ü, ş, ı, ğ, ç, ö bulunan yolları
açamaz ("can't open/read file"). Burada görseller Python'un kendi dosya işlemleriyle okunup yazılır;
video işlemleri ise yalnızca ASCII bir geçici klasörde yapılır.
"""
from __future__ import annotations

import os
import shutil
import tempfile

import cv2
import numpy as np


def imread(path, flags=cv2.IMREAD_COLOR):
    try:
        with open(path, "rb") as f:
            data = f.read()
    except OSError:
        return None
    if not data:
        return None
    return cv2.imdecode(np.frombuffer(data, np.uint8), flags)


def imwrite(path, img, params=None):
    ext = os.path.splitext(path)[1] or ".png"
    ok, buf = cv2.imencode(ext, img, params or [])
    if not ok:
        return False
    with open(path, "wb") as f:
        f.write(buf.tobytes())
    return True


# ---------------------------------------------------------------------------------------------------------------
def is_ascii(p) -> bool:
    try:
        str(p).encode("ascii")
        return True
    except UnicodeEncodeError:
        return False


def ascii_tempdir(prefix="afis_") -> str:
    """Yolu yalnızca ASCII karakterden oluşan, yazılabilir yeni bir geçici klasör açar (video işlemleri için)."""
    cands = [os.environ.get("AFIS_TMP", ""), tempfile.gettempdir()]
    if os.name == "nt":
        cands += [os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "Temp"), "C:\\Users\\Public",
                  (os.environ.get("SystemDrive", "C:") + "\\")]
    else:
        cands += ["/tmp"]
    for c in cands:
        if c and is_ascii(c) and os.path.isdir(c):
            try:
                return tempfile.mkdtemp(prefix=prefix, dir=c)
            except OSError:
                continue
    raise RuntimeError("ASCII karakterli yazılabilir bir geçici klasör bulunamadı (AFIS_TMP ortam değişkenine "
                       "C:\\afis_tmp gibi bir klasör yazabilirsin).")


class AsciiCopy:
    """with AsciiCopy(path) as p: ...  -> path ASCII ise kendisi, değilse ASCII geçici klasöre kopyası."""

    def __init__(self, path):
        self.path, self.dir, self.p = path, None, path

    def __enter__(self):
        if self.path and not is_ascii(self.path):
            self.dir = ascii_tempdir()
            self.p = os.path.join(self.dir, "kopya" + (os.path.splitext(self.path)[1] or ".mp4"))
            shutil.copyfile(self.path, self.p)
        return self.p

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self.dir:
            shutil.rmtree(self.dir, ignore_errors=True)
            self.dir = None
