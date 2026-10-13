# -*- coding: utf-8 -*-
"""
Kayıtlı sahnelerden yeniden birleştirme — SAHTE SERVİS testi (ağ yok, ücretli çağrı yok).

Doğrulananlar:
  1. Kaynak iş sahte servisle üretilir (kurdeleli, birikmeli ve zemine değen sahneler).
  2. recompose_from_scenes: sağlayıcı fabrikası ve sahne çağrısı HİÇ kullanılmaz (çağrılırsa test düşer).
  3. Kaynak işin TÜM dosyaları bayt bayt aynı kalır (yeni dosya da eklenmez).
  4. Yeni iş ayrı klasörde; rapor: islem, kaynak_is, saglayici_cagrisi=0, ürün profili 75x200, her fotoğraf kare,
     yerlesim_modu tam_kumas, kaynak (is/stem/foto) bilgisi; asılı boy/gizli bölge kaynakla aynı (aynı kod, aynı sahne).
  5. Yeni yerleşim generate_photos ile AYNI ortak fonksiyonlardan geçer: aynı sahneye doğrudan _evaluate_scene ile
     bakıldığında sonuç piksel piksel aynıdır.
  6. Kaynakta kayıtlı sahne yoksa açık hata verir; oranı uyuşmayan tasarımda yeni iş "beklemede" kalır, çağrı yine 0.
Çalıştır:  python tests/test_yeniden_birlestir.py
"""
import glob
import hashlib
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cv2                      # noqa: E402
import numpy as np              # noqa: E402

import cvio                     # noqa: E402
import mock_provider as mp      # noqa: E402
import orchestrator as orch     # noqa: E402
from providers import ProviderError, SceneProvider, Settings   # noqa: E402

tmp = tempfile.mkdtemp(prefix="afis_yb_")
orch.JOBS_DIR = os.path.join(tmp, "isler")
orch.REPORT_DIR = os.path.join(tmp, "raporlar")
orch.LOG_PATH = os.path.join(tmp, "kayit.log")
orch.STATS_PATH = os.path.join(tmp, "karne.json")


class Mock:
    supports_guide = True

    def __init__(self, v):
        self.inner = mp.MockScenes("mock")
        self.inner.kind = v

    def scene(self, *a, **k):
        return self.inner.scene(*a, **k)


arms = iter(["mock_touch", "mock_pool"])
orch.make_scene_provider = lambda s, log=print, name=None: SceneProvider(Mock(name))


def settings():
    return Settings(scene_provider="mock", video_provider="mock", max_scene_calls=6, photo_long_side=1200, auto_video=False)


rgba = np.zeros((2000, 750, 4), np.uint8)                       # 75x200 ile tam oranlı, şeffaf zeminli
cv2.putText(rgba, "Candy", (90, 700), cv2.FONT_HERSHEY_SCRIPT_COMPLEX, 4.2, (30, 30, 30, 255), 6, cv2.LINE_AA)
cv2.putText(rgba, "BABY SHOWER", (40, 900), cv2.FONT_HERSHEY_SIMPLEX, 1.9, (30, 30, 30, 255), 4, cv2.LINE_AA)
design_path = os.path.join(tmp, "tasarim_test.png")
cv2.imwrite(design_path, rgba)

o = orch.Orchestrator(settings(), log=lambda m: None, progress=lambda f, t: None)
o.arms_override = {"scene": ["mock_touch", "mock_pool"]}
o.rng_seed = 3
src = o.new_job(design_path, "Baby shower", "kaynak")
r = o.generate_photos(src, 2, ribbon={"hex": "#E8B4BC"})
assert r["uretilen"] == 2, r
src_rap = o.report_of(src)


def snapshot(folder):
    out = {}
    for p in glob.glob(os.path.join(folder, "**", "*"), recursive=True):
        if os.path.isfile(p):
            out[os.path.relpath(p, folder)] = hashlib.md5(open(p, "rb").read()).hexdigest()
    return out


before = snapshot(src)

# 2) sağlayıcı yasak: çağrılırsa test düşer
CALLED = []
def forbidden(*a, **k):
    CALLED.append(1)
    raise AssertionError("yeniden birleştirmede sağlayıcı fabrikası çağrıldı")
orch.make_scene_provider = forbidden
o2 = orch.Orchestrator(settings(), log=lambda m: None, progress=lambda f, t: None)
res = o2.recompose_from_scenes(src)
assert not CALLED and res["cagri"] == 0 and res["saglayici_cagrisi"] == 0 and res["uretilen"] == 2, res
new = os.path.join(orch.JOBS_DIR, res["job"])
assert os.path.isdir(new) and os.path.abspath(new) != os.path.abspath(src)

# 3) kaynak iş bayt bayt aynı
after = snapshot(src)
assert after == before, {k for k in set(before) | set(after) if before.get(k) != after.get(k)}

# 4) yeni iş raporu
nr = o2.report_of(new)
assert nr["islem"] == "kayitli_sahnelerden_yeniden_birlestirme" and nr["kaynak_is"] == os.path.basename(src)
assert nr["saglayici_cagrisi"] == 0 and nr["urun_profili"]["olcu_id"] == "75x200" and nr["tasarim_kontrol"]["uyumlu"]
assert "servis_karnesi" not in nr                                   # seçici hiç çalışmadı
for p_new, p_src in zip(nr["fotograflar"], src_rap["fotograflar"]):
    im = cvio.imread(os.path.join(new, "foto", p_new["ad"]), cv2.IMREAD_COLOR)
    assert im.shape[0] == im.shape[1], im.shape
    assert p_new["yerlesim_modu"] == "tam_kumas" and p_new["servis"] == "kayitli_sahne" and p_new["kurdele"] == "#E8B4BC"
    assert p_new["kaynak"] == {"is": os.path.basename(src), "stem": p_src["stem"], "foto": p_src["ad"], "servis": p_src["servis"],
                            "dosya": os.path.join("sahneler_bos", p_src["stem"] + ".png"), "onceki_karar": "kabul"}
    for k in ("asili_cm", "gizli_cm", "px_per_cm", "birikme"):
        assert p_new["tam_kumas"][k] == p_src["tam_kumas"][k], (k, p_new["tam_kumas"][k], p_src["tam_kumas"][k])
    assert p_new["tam_kumas"]["kivrim_kaymasi"] == 0.0
print("yeni iş:", res["job"], "| fotoğraflar:", [p["ad"] for p in nr["fotograflar"]],
      "| asılı cm:", [p["tam_kumas"]["asili_cm"] for p in nr["fotograflar"]])

# 5) ortak akış: aynı sahne + aynı fonksiyon -> aynı piksel (ribbon dahil)
import ribbon as ribbon_mod     # noqa: E402
p0 = nr["fotograflar"][0]
scene = cvio.imread(os.path.join(src, "sahneler_bos", p0["kaynak"]["stem"] + ".png"), cv2.IMREAD_COLOR)
ev = o2._evaluate_scene(o2._upscale(scene), o2._design(new), o2._profile(nr), "test")
direct = ribbon_mod.restore(scene, ev["out"], "#E8B4BC")
saved = cvio.imread(os.path.join(new, "foto", p0["ad"]), cv2.IMREAD_COLOR)
assert ev["ok"] and np.abs(direct.astype(int) - saved.astype(int)).mean() < 1.5           # JPEG kaydı payı

# 6) hata yolları
empty = o2.new_job(design_path, "Baby shower", "bos")
try:
    o2.recompose_from_scenes(empty)
    raise SystemExit("kayıtlı sahnesiz işte hata bekleniyordu")
except ProviderError:
    pass
bad = np.zeros((2000, 1030, 4), np.uint8)                          # 0.515 oranı: 75x200'e uymaz
bad_src = os.path.join(orch.JOBS_DIR, "uyumsuz_kaynak")
os.makedirs(os.path.join(bad_src, "sahneler_bos"))
cv2.imwrite(os.path.join(bad_src, "tasarim.png"), bad)
import shutil, json             # noqa: E401,E402
shutil.copy(os.path.join(src, "sahneler_bos", "s01.png"), os.path.join(bad_src, "sahneler_bos", "s01.png"))
json.dump(dict(src_rap, fotograflar=src_rap["fotograflar"][:1]), open(os.path.join(bad_src, "rapor.json"), "w", encoding="utf-8"))
rb = o2.recompose_from_scenes(bad_src)
assert rb["beklemede"] and rb["uretilen"] == 0 and rb["saglayici_cagrisi"] == 0 and not CALLED, rb
print("test_yeniden_birlestir: TAMAM")
