# -*- coding: utf-8 -*-
"""
Tam kumaş yerleşimi (Aşama 2A) — YEREL test (ağ yok, sağlayıcı yok; sahneler mock_provider.square_scene ile sentetik).

Doğrulananlar:
  1. PNG tuvali kumaşın TAMAMI: tuvalin köşe/merkez/çeyrek/kenar işaretleri kumaşta beklenen fiziksel konumda (±%1.5).
     Sol-üst işaret kumaşın sol-üst köşesinde: kenar payı / içeri alma / küçültüp ortalama YOK.
  2. Şeffaf alan = baskısız kumaş: işaretlerin dışında sahne pikselleri DEĞİŞMEZ.
  3. Sert (rigid) görünen sahnede de tam kumaş yolu kullanılır (det.kind yerleşimi değiştirmez).
  4. Eski kumaş yolunun %10 içeri alması tam kumaşta yok (eski yol hâlâ eski çağrılar için duruyor).
  5. Birikmeli sahne: temasın üstündeki işaretler fiziksel ölçekte doğru yerde; temasın altı basılmaz; alt bölge
     mürekkepliyse "birikme_cozulemedi", mürekkepsizse sorun yok (yalnız uyarı).
  6. Ürün boyundan uzun ya da kısa (havada biten) kumaş: "sahne_geometri".
Çalıştır:  python tests/test_tam_kumas.py
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cv2                      # noqa: E402
import numpy as np              # noqa: E402

import banner_detect as bd      # noqa: E402
import compositor as cp         # noqa: E402
import mock_provider as mp      # noqa: E402
import product                  # noqa: E402

PROF = product.profil_olustur("75x200")
DW, DH, RAD = 750, 2000, 22
MARKERS = {                      # ad: (u, v, BGR)
    "sol_ust": (0.04, 0.015, (30, 30, 220)),
    "sag_ust": (0.96, 0.015, (30, 200, 30)),
    "ust_ceyrek": (0.50, 0.25, (220, 40, 30)),
    "merkez": (0.50, 0.50, (200, 40, 200)),
    "sol_kenar": (0.03, 0.50, (200, 200, 30)),
    "alt_ceyrek": (0.50, 0.75, (30, 140, 240)),
    "sol_alt": (0.04, 0.985, (40, 40, 40)),
    "sag_alt": (0.96, 0.985, (120, 30, 110)),
}
TOL = 0.015


def make_design(names=None):
    """Şeffaf 750x2000 PNG (75x200 ile TAM oranlı) + renkli işaretler. float BGR (load_design ile aynı biçim) ve RGBA döner."""
    rgba = np.zeros((DH, DW, 4), np.uint8)
    for k, (u, v, c) in MARKERS.items():
        if names is None or k in names:
            cv2.circle(rgba, (int(round(u * DW - 0.5)), int(round(v * DH - 0.5))), RAD, (*c, 255), -1, cv2.LINE_AA)
    f = rgba.astype(np.float32) / 255.0
    a = f[..., 3:4]
    return np.clip(f[..., :3] * a + (1 - a), 0, 1).astype(np.float32), rgba


def ratio(out, scene):
    return out.astype(np.float32) / np.maximum(scene.astype(np.float32), 1.0)


def marker_centroid(out, scene, exp_xy, color, win):
    """Beklenen konum çevresindeki pencerede, işaret renginin oluşturduğu çarpan oranına yakın piksellerin ağırlık merkezi."""
    r = ratio(out, scene)
    want = 1.0 - 0.93 * (1.0 - np.array(color, np.float32) / 255.0)
    x, y = exp_xy
    x0, x1 = int(max(0, x - win[0])), int(min(out.shape[1], x + win[0]))
    y0, y1 = int(max(0, y - win[1])), int(min(out.shape[0], y + win[1]))
    sub = r[y0:y1, x0:x1]
    sel = np.linalg.norm(sub - want, axis=2) < 0.18
    if sel.sum() < 20:
        return None, int(sel.sum())
    yy, xx = np.nonzero(sel)
    return (x0 + xx.mean() + 0.5, y0 + yy.mean() + 0.5), int(sel.sum())


def check_markers(out, scene, truth, total_px, visible, label):
    w = truth["x1"] - truth["x0"]
    win = (0.06 * w, 0.03 * total_px)
    res = {}
    for k, (u, v, c) in MARKERS.items():
        ex = (truth["x0"] + u * w, truth["top"] + v * total_px)
        cen, n = marker_centroid(out, scene, ex, c, win)
        if k in visible:
            assert cen is not None, f"[{label}] {k}: işaret bulunamadı (piksel {n})"
            dx, dy = (cen[0] - ex[0]) / w, (cen[1] - ex[1]) / total_px
            res[k] = (round(dx * 100, 2), round(dy * 100, 2))
            assert abs(dx) <= TOL and abs(dy) <= TOL, f"[{label}] {k}: sapma en %{dx * 100:.2f}, boy %{dy * 100:.2f}"
        else:
            assert cen is None, f"[{label}] {k}: gizli olması gereken işaret görünüyor ({n} piksel)"
    print(f"  [{label}] işaret sapmaları (en %, boy %):", res)
    return res


def changed_outside_markers(out, scene, truth, total_px):
    """İşaret çevrelerinin DIŞINDA değişen piksel sayısı (şeffaf alan sahneyi değiştirmemeli)."""
    diff = np.abs(out.astype(np.int16) - scene.astype(np.int16)).max(2) > 2
    allow = np.zeros(diff.shape, np.uint8)
    w = truth["x1"] - truth["x0"]
    rpx = int(RAD / DW * w * 1.25 + 6)
    for (u, v, _) in MARKERS.values():
        cv2.circle(allow, (int(truth["x0"] + u * w), int(truth["top"] + v * total_px)), rpx, 1, -1)
    return int((diff & (allow == 0)).sum())


design, rgba = make_design()

# ---------------------------------------------------------------- 1-3: tam zemine değen, sert görünen sahne
scene, t = mp.square_scene(1536, PROF.oran, "dokunan", seed=1)
det_auto = bd.detect(scene)                                   # ipucusuz: düz dikdörtgen -> "rigid" sınıflanır
assert det_auto.ok, det_auto.reject
print("ipucusuz algılama türü:", det_auto.kind)
assert det_auto.kind == "rigid", "test sahnesi sert görünmeliydi (rigid yolunu sınamak için)"
for label, det in (("ipucusuz/rigid", det_auto), ("ipucu=fabric", bd.detect(scene, hint={"kind": "fabric"}))):
    out, info = cp.composite(scene, design, det, mode="tam_kumas", profile=PROF)
    assert info["mod"] == "tam_kumas"
    assert info["sorunlar"] == [], info["sorunlar"]
    assert info["birikme"] is False and info["v_gizli"] == 1.0 and info["temas_yontemi"] == "maske_alti", info
    assert abs(info["px_per_cm"] / (t["width_px"] / 75) - 1) < 0.02, (info["px_per_cm"], t["width_px"] / 75)
    assert abs(info["asili_cm"] - 200) < 200 * 0.03, info["asili_cm"]
    check_markers(out, scene, t, t["total_px"], set(MARKERS), label)
    n_out = changed_outside_markers(out, scene, t, t["total_px"])
    assert n_out == 0, f"[{label}] şeffaf alanda sahne değişti: {n_out} piksel"
    # sol-üst işaret kumaşın sol-üst köşesinde: işaretin sol/üst kenarı kumaş kenarından en fazla ~%1.5 içeride
    r = ratio(out, scene)
    want = 1.0 - 0.93 * (1.0 - np.array(MARKERS["sol_ust"][2], np.float32) / 255.0)
    yy, xx = np.nonzero(np.linalg.norm(r - want, axis=2) < 0.18)
    w = t["x1"] - t["x0"]
    lx = (np.percentile(xx, 1) - t["x0"]) / w
    ty = (np.percentile(yy, 1) - t["top"]) / t["total_px"]
    print(f"  [{label}] sol-üst işaretin kumaş köşesine uzaklığı: en %{lx * 100:.2f}, boy %{ty * 100:.2f}")
    assert lx < 0.025 and ty < 0.012, (lx, ty)

# şeffaf piksellerde sahne birebir aynı mı? (baskı modeli: model u,v ile şeffaf noktalar)
_, info_m, model = cp.composite(scene, design, bd.detect(scene, hint={"kind": "fabric"}), mode="tam_kumas", profile=PROF,
                                return_model=True)
x0, y0, x1, y1 = model["bbox"]
assert model["u"].shape == (y1 - y0, x1 - x0) and model["alpha"].max() > 0.99
print("baskı modeli (video onarımı için) üretildi:", model["bbox"], "kind", model["kind"])

# ---------------------------------------------------------------- 4: eski kumaş yolu %10 içeri alır, tam kumaş almaz
det_f = bd.detect(scene, hint={"kind": "fabric"})
old, _ = cp.composite(scene, design, det_f)                   # eski çağrı (mode yok) aynen çalışmalı
w = t["x1"] - t["x0"]
ex = (t["x0"] + 0.04 * w, t["top"] + 0.015 * t["total_px"])
cen_old, _ = marker_centroid(old, scene, ex, MARKERS["sol_ust"][2], (0.25 * w, 0.12 * t["total_px"]))
assert cen_old is not None
print(f"eski kumaş yolu: sol-üst işaret {(cen_old[0] - ex[0]) / w * 100:.1f}% en, {(cen_old[1] - ex[1]) / t['total_px'] * 100:.1f}% boy kaymış")
assert (cen_old[0] - ex[0]) / w > 0.06 and (cen_old[1] - ex[1]) / t["total_px"] > 0.03, "eski yolun içeri alması beklenirdi"

# ---------------------------------------------------------------- 5: birikmeli sahne
scene_p, tp = mp.square_scene(1536, PROF.oran, "birikmeli", seed=2, pool_frac=0.10)
det_p = bd.detect(scene_p, hint={"kind": "fabric"})
assert det_p.ok, det_p.reject
out_p, info_p = cp.composite(scene_p, design, det_p, mode="tam_kumas", profile=PROF)
print("birikmeli:", {k: info_p[k] for k in ("px_per_cm", "asili_cm", "gizli_cm", "v_gizli", "temas_y", "birikme", "temas_yontemi")})
assert info_p["birikme"] and info_p["temas_yontemi"] == "kenar_yayilmasi"
assert abs(info_p["temas_y"] - tp["contact"]) <= 0.01 * tp["total_px"], (info_p["temas_y"], tp["contact"])
assert abs(info_p["v_gizli"] - 0.90) < 0.02, info_p["v_gizli"]
visible = {k for k, (u, v, c) in MARKERS.items() if v < 0.88}
check_markers(out_p, scene_p, tp, tp["total_px"], visible, "birikmeli")
c = int(tp["contact"]) + 3
assert np.abs(out_p[c:].astype(int) - scene_p[c:].astype(int)).max() <= 2, "temas çizgisinin altına baskı yapılmış"
# alt %12'si tam genişlikte mürekkepli tasarım: temasın altındaki birikmeye HİÇ basılmamalı, üstündeki kısım basılmalı
band = np.ones((DH, DW, 3), np.float32)
band[int(0.88 * DH):] = (0.2, 0.3, 0.7)
out_b, info_b = cp.composite(scene_p, band, det_p, mode="tam_kumas", profile=PROF)
assert np.abs(out_b[c:].astype(int) - scene_p[c:].astype(int)).max() <= 2, "temas çizgisinin altına (birikmeye) baskı yapılmış"
yb = int(tp["top"] + 0.89 * tp["total_px"])
assert np.abs(out_b[yb, int(tp["x0"]) + 20:int(tp["x1"]) - 20].astype(int) - scene_p[yb, int(tp["x0"]) + 20:int(tp["x1"]) - 20].astype(int)).min() > 20, \
    "temasın hemen üstündeki bant basılmalıydı"
assert [s["tur"] for s in info_b["sorunlar"]] == ["birikme_cozulemedi"]
turler = [s["tur"] for s in info_p["sorunlar"]]
assert turler == ["birikme_cozulemedi"], info_p["sorunlar"]
print("  alt bölge mürekkepli ->", turler, "| mürekkep oranı", info_p["gizli_murekkep"])
# aynı sahne, alt %15'i mürekkepsiz tasarım: sorun yok, yalnız uyarı
design_top, _ = make_design({k for k, (u, v, c) in MARKERS.items() if v < 0.85})
out_q, info_q = cp.composite(scene_p, design_top, det_p, mode="tam_kumas", profile=PROF)
assert info_q["sorunlar"] == [] and any("baskı yok" in u for u in info_q["uyarilar"]), info_q
print("  alt bölge mürekkepsiz -> sorun yok; uyarı:", info_q["uyarilar"])

# ---------------------------------------------------------------- 6: sahne geometrisi uyuşmazlığı
for kind in ("uzun", "havada"):
    sc, tt = mp.square_scene(1536, PROF.oran, kind, seed=3)
    dd = bd.detect(sc, hint={"kind": "fabric"})
    assert dd.ok, (kind, dd.reject)
    _, inf = cp.composite(sc, design, dd, mode="tam_kumas", profile=PROF)
    turler = [s["tur"] for s in inf["sorunlar"]]
    print(f"{kind}: asılı ≈{inf['asili_cm']:.0f} cm ->", turler)
    assert turler == ["sahne_geometri"], inf

# ---------------------------------------------------------------- 7: dikey ölçek politikası (K-54; K-16'nın yerine)
# Tasarım HER ZAMAN fiziksel ölçekle yerleşir; ölçüm toleransı (±%3) deformasyon izni DEĞİLDİR.
# Biraz KISA: alt kısım görünmez (gizli bölge). Biraz UZUN: tasarım SIKIŞTIRILMAZ, altta ölçüm farkı kadar baskısız kumaş kalır
# ve bu UYARI olarak yazılır. Her iki durumda işaretler fiziksel konumdadır (top + v * boy_px).
for k in (0.98, 1.02):
    sc, tt = mp.square_scene(1536, PROF.oran / k, "dokunan", seed=4)      # en geniş/dar çizilir -> asılı boy = ürün boyu x k
    dd = bd.detect(sc, hint={"kind": "fabric"})
    design_u, _ = make_design({"ust_ceyrek", "merkez", "alt_ceyrek"})
    o, inf = cp.composite(sc, design_u, dd, mode="tam_kumas", profile=PROF)
    assert inf["sorunlar"] == [] and inf["dikey_olcek"] == "fiziksel", (k, inf)
    hang = tt["hang_px"]
    boy_px = hang / k
    for name in ("ust_ceyrek", "merkez", "alt_ceyrek"):
        u, v, c = MARKERS[name]
        exp = (tt["x0"] + u * (tt["x1"] - tt["x0"]), tt["top"] + v * boy_px)
        got, n = marker_centroid(o, sc, exp, c, (0.06 * (tt["x1"] - tt["x0"]), 0.03 * hang))
        assert got is not None and abs(got[1] - exp[1]) < 0.004 * hang, (k, name, got, exp)
    if k < 1:
        assert inf["v_gizli"] < 0.995, inf
    else:
        assert inf["v_gizli"] == 1.0 and any("SIKIŞTIRILMADI" in w for w in inf["uyarilar"]), inf
        assert not any("dikeyde" in w and "sıkıştı" in w for w in inf["uyarilar"]), inf
    print(f"asılı/ürün {k}: dikey ölçek {inf['dikey_olcek']}, olcek_farki {inf['olcek_farki']}, uyarı: {inf['uyarilar'][:1]}")

# ---------------------------------------------------------------- 8: ölçüm payı bandı ve birikmesiz gizli bölge metni (G5b)
# (a) |fark| ≤ OLCUM_PAYI (≈1 cm kısa): karar değişmez (ret yok, v_gizli 1.0), AMA fiziksel ölçekte en alttaki ≈1 cm temas
#     çizgisinin altına düşer -> görünen mürekkep GERÇEK orandan (<1) raporlanır, bu banttaki baskı ölçülür ve uyarı yazılır.
#     (Eski kod gorunen_murekkep=1.0 yazıp bu bandı hiç denetlemiyordu.)
alt_serit = np.ones((DH, DW, 3), np.float32)
alt_serit[int(0.9925 * DH):] = (0.2, 0.3, 0.7)                      # yalnız en alttaki ≈1,5 cm mürekkepli
sc, tt = mp.square_scene(1536, PROF.oran / 0.997, "dokunan", seed=4)
dd = bd.detect(sc, hint={"kind": "fabric"})
_, inf = cp.composite(sc, alt_serit, dd, mode="tam_kumas", profile=PROF)
assert -cp.OLCUM_PAYI <= inf["olcek_farki"] < 0, inf["olcek_farki"]
assert inf["sorunlar"] == [] and inf["v_gizli"] == 1.0, inf
assert inf["gorunen_murekkep"] < 0.95, inf["gorunen_murekkep"]
assert inf["olcum_payi_gizli_cm"] > 0.3 and inf["olcum_payi_murekkep"] > cp.MUREKKEP_ESIK, inf
assert any("ölçüm payı" in w for w in inf["uyarilar"]), inf["uyarilar"]
print(f"ölçüm payı bandı: fark {inf['olcek_farki']}, gizli ≈{inf['olcum_payi_gizli_cm']} cm, görünen mürekkep "
      f"{inf['gorunen_murekkep']} -> uyarı, ret yok")
# aynı sahne, alt kenarı boş tasarım: uyarı yok, görünen mürekkep 1.0
_, inf0 = cp.composite(sc, make_design({"merkez"})[0], dd, mode="tam_kumas", profile=PROF)
assert inf0["sorunlar"] == [] and inf0["gorunen_murekkep"] == 1.0 and not any("ölçüm payı" in w for w in inf0["uyarilar"]), inf0
# (b) birikmesiz %2 kısa kumaş: gizli bölgede baskı -> tür yine birikme_cozulemedi, ama metin "zeminde biriken" DEMEZ
sc, tt = mp.square_scene(1536, PROF.oran / 0.98, "dokunan", seed=4)
dd = bd.detect(sc, hint={"kind": "fabric"})
_, inf = cp.composite(sc, band, dd, mode="tam_kumas", profile=PROF)
assert not inf["birikme"] and [s["tur"] for s in inf["sorunlar"]] == ["birikme_cozulemedi"], inf
msg = inf["sorunlar"][0]["mesaj"]
assert "birik" not in msg.replace("birikme görünmüyor", "") and "görünen alt kenar" in msg, msg
_, inf = cp.composite(sc, make_design({"merkez"})[0], dd, mode="tam_kumas", profile=PROF)
assert inf["sorunlar"] == [] and not any("zeminde birik" in w for w in inf["uyarilar"]), inf["uyarilar"]
print("birikmesiz kısa kumaş: tür birikme_cozulemedi, metin:", msg[:80], "...")

# ---------------------------------------------------------------- 9: sinir_kaniti kod alanı ve 0 değeri (G5b)
import sinir_kaniti as sk       # noqa: E402
for kind, kod in (("dokunan", "uygun"), ("uzun", "geometri")):
    sc, _ = mp.square_scene(1536, PROF.oran, kind, seed=3)
    r = sk.olc(sc, 75, 200)
    assert r["kaynak_kodu"] == kod and r["kaynak"].startswith(kod), (kind, r["kaynak_kodu"], r["kaynak"])
rec0 = {"tam_kumas": {"asili_cm": 140.0, "temas_belirsiz": True},
        "temas_karsilastirma": {"yayilma": {"asili_cm": 140.0, "gorunen_murekkep": 0.0}, "etek_ucu": {"asili_cm": 200.0}}}
assert "%100'i gizlenir" in sk.kalan_sorunlar(rec0)[0], sk.kalan_sorunlar(rec0)[0]   # eski `or 1` burada %0 yazıyordu
rec1 = {"tam_kumas": {"asili_cm": 190.0}, "sinir_araligi": {"asili_min": 185, "asili_max": 199, "kaynak": "sinir"}}
assert any("Sınır seçimine göre" in s for s in sk.kalan_sorunlar(rec1)), sk.kalan_sorunlar(rec1)
print("sinir_kaniti: kaynak_kodu uygun/geometri; görünen mürekkep 0 -> %100 gizli yazılır")

# profil zorunlu, bilinmeyen mod reddedilir
for kw in ({"mode": "tam_kumas"}, {"mode": "baska", "profile": PROF}):
    try:
        cp.composite(scene, design, det_f, **kw)
        raise SystemExit(f"hata bekleniyordu: {kw}")
    except ValueError:
        pass

print("test_tam_kumas: TAMAM")
