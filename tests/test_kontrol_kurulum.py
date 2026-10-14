# -*- coding: utf-8 -*-
"""kontrol.py (kur.bat sonrası kendini sınama) — afiş bulunamayınca hata mesajı regresyon testi (M-architecture-reviewer-11).

Eskiden `"...: " + det.reject` (liste) yüzünden kullanıcı asıl neden yerine yanıltıcı bir
"TypeError: can only concatenate str (not "list") to str" görüyordu. Bu test, kontrol.py'nin ağır kurulum adımlarını
(paket/ffmpeg/kamera) ÇALIŞTIRMADAN yalnız `yerlestirme()` fonksiyonunu afişsiz düz bir sahneyle çağırır ve
  1. RuntimeError yükseldiğini, mesajın "afiş bulunamadı" + algılamanın gerçek nedenlerini içerdiğini,
  2. `adim()` çıktısında TypeError görünmediğini doğrular.
Yerel test (ağ yok, ücretli çağrı yok). Çalıştır: python tests/test_kontrol_kurulum.py
"""
import contextlib
import io
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cv2                     # noqa: E402
import numpy as np             # noqa: E402

import banner_detect as bd     # noqa: E402
import kontrol                 # noqa: E402  (içe aktarınca kurulum adımları ÇALIŞMAMALI)

assert not kontrol.fails, "kontrol.py içe aktarılırken adımlar çalıştı"

tmp = tempfile.mkdtemp(prefix="kontrol_kurulum_")
try:
    sahne = os.path.join(tmp, "bos_sahne.jpg")
    cv2.imwrite(sahne, np.full((900, 900, 3), 70, np.uint8))         # düz koyu gri: afiş yok
    det = bd.detect(cv2.imread(sahne))
    assert isinstance(det.reject, list) and det.reject, f"ön koşul: boş sahne reddedilmeli ({det.reject!r})"

    # 1) doğrudan çağrı
    try:
        kontrol.yerlestirme(sahne)
        raise AssertionError("afişsiz sahnede hata yükselmedi")
    except RuntimeError as e:
        msg = str(e)
    except TypeError as e:                                             # düzeltme geri alınınca buraya düşer
        raise AssertionError(f"yanıltıcı TypeError (det.reject listesi metne eklenmiş): {e}")
    assert "afiş bulunamadı" in msg, msg
    for neden in det.reject:
        assert neden in msg, (neden, msg)
    print("hata mesajı:", msg)

    # 2) kullanıcının gördüğü satır (adim)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        kontrol.adim("Afiş bulma + tasarım yerleştirme", lambda: kontrol.yerlestirme(sahne))
    satir = buf.getvalue().strip()
    assert "[HATA ]" in satir and "RuntimeError" in satir and "TypeError" not in satir, satir
    kontrol.fails.clear()
finally:
    shutil.rmtree(tmp, ignore_errors=True)
print("test_kontrol_kurulum: TAMAM")
