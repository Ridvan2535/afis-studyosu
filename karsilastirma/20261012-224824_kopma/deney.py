# -*- coding: utf-8 -*-
"""Kopma kök neden deneyi: kayıtlı boş sahne + aynı tasarım; her seferinde TEK değişken değiştirilir.
V0 mevcut hat · V1 fold_shift=0 · V2 satır bazlı kenarlar düzgünleştirilmiş · V3 kurdele geri koyma yok.
Ücretli çağrı yok. Orijinal iş dosyalarına dokunmaz (kopyadan okur)."""
import json, os, sys
import cv2, numpy as np
sys.path.insert(0, "/home/claude/afis")
import banner_detect as bd, compositor as cp, product, ribbon as ribbon_mod, cvio
from orchestrator import DESIGN_CAP

JOB = "/home/claude/kars/is"
OUT = "/home/claude/kars/sonuc"
os.makedirs(OUT, exist_ok=True)
rap = json.load(open(f"{JOB}/rapor.json", encoding="utf-8"))
prof = product.UrunProfili.from_dict(rap["urun_profili"])
d = cp.load_design(f"{JOB}/tasarim.png")
if max(d.shape[:2]) > DESIGN_CAP:
    f = DESIGN_CAP / max(d.shape[:2]); d = cv2.resize(d, None, fx=f, fy=f, interpolation=cv2.INTER_AREA)

_orig_geom = cp.fabric_geometry
def geom_smooth(*a, **k):
    g = _orig_geom(*a, **k)
    n = len(g["L"]); s = max(3.0, 0.02 * n)
    from scipy.ndimage import gaussian_filter1d
    g["L"] = gaussian_filter1d(g["L"], s, mode="nearest"); g["R"] = gaussian_filter1d(g["R"], s, mode="nearest")
    return g

def run(scene, det, hexv, fold=0.01, smooth=False, ribbon=True):
    cp.fabric_geometry = geom_smooth if smooth else _orig_geom
    try:
        out, info, model = cp.composite(scene, d, det, mode="tam_kumas", profile=prof, fold_shift=fold, return_model=True)
    finally:
        cp.fabric_geometry = _orig_geom
    if ribbon and hexv:
        out = ribbon_mod.restore(scene, out, hexv)
    return out, info, model

def map_metrics(model, det):
    """Dönüşüm sürekliliği: satırdan satıra yatay sıçrama (çıktı pikseli cinsinden) ve katlanma (du/dx <= 0)."""
    u, v, a = model["u"], model["v"], model["alpha"]
    x0, y0, x1, y1 = model["bbox"]
    W0 = float(np.median((a > 0.5).sum(1)[(a > 0.5).sum(1) > 0]))
    inside = a > 0.95
    ux = u * W0
    dy = np.abs(np.diff(ux, axis=0)); m = inside[1:] & inside[:-1]
    d2 = np.abs(np.diff(ux, n=2, axis=0)); m2 = inside[2:] & inside[1:-1] & inside[:-2]
    dx = np.diff(u, axis=1); mx = inside[:, 1:] & inside[:, :-1]
    return {"satir_kayma_maks_px": round(float(dy[m].max()), 3), "satir_kayma_p999_px": round(float(np.percentile(dy[m], 99.9)), 3),
            "ikinci_turev_maks_px": round(float(d2[m2].max()), 3), "katlanma_piksel": int(((dx <= 0) & mx).sum())}

res = {}
for p in rap["fotograflar"]:
    stem, ad = p["stem"], p["ad"]
    scene = cvio.imread(f"{JOB}/sahneler_bos/{stem}.png", cv2.IMREAD_COLOR)
    det = bd.detect(scene, hint={"kind": "fabric"})
    hexv = p.get("kurdele")
    orig = cvio.imread(f"{JOB}/foto/{ad}", cv2.IMREAD_COLOR)
    rs = {}
    for name, kw in (("V0_mevcut", {}), ("V1_fold0", {"fold": 0.0}), ("V2_kenar_duz", {"smooth": True}), ("V3_kurdele_yok", {"ribbon": False})):
        out, info, model = run(scene, det, hexv, **kw)
        cvio.imwrite(f"{OUT}/{stem}_{name}.png", out)
        diff_orig = float(np.abs(out.astype(int) - orig.astype(int)).mean())
        rs[name] = dict(map_metrics(model, det), fark_orijinal_ort=round(diff_orig, 2),
                        fark_V0=None)
        if name == "V0_mevcut":
            v0 = out
        else:
            rs[name]["fark_V0"] = round(float(np.abs(out.astype(int) - v0.astype(int)).mean()), 3)
            rs[name]["fark_V0_degisen_piksel"] = int((np.abs(out.astype(int) - v0.astype(int)).max(2) > 8).sum())
    res[stem] = rs
json.dump(res, open(f"{OUT}/metrikler.json", "w"), indent=1, ensure_ascii=False)
for s, rs in res.items():
    print(s)
    for k, v in rs.items():
        print("  ", k, v)
