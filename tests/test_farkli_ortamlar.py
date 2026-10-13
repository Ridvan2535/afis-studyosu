# -*- coding: utf-8 -*-
"""Farklı ortam regresyon örnekleri (YEREL test; ağ yok, ücret yok, servis kapalı).

Örnekler (tests/kontrol_ornekleri/is_*/kontrol.json; hepsi HAM görüntü):
  * is_054333: koyu duvar + krem halı. Kumaş seçilmeli, koyu boşluk seçilmemeli. Elenme nedeni sahne geometrisi: bütün makul
    sınır seçimlerinde asılı boy ±%3 dışında -> fark sınırdan değil sahnedeki kumaştan ("geometri"); otomatik sonuç
    "İnceleme gerekli" (±%30 kaba sınır içinde), kesin hata değil.
  * is_053942: krem duvar. Maske duvara (stand direklerine kadar) TAŞMAMALI ve "afiş boş görünmüyor" (desen) reddi
    çıkmamalı. Ret kalırsa sınır seçimine bağlı olmalı ("sınır") -> güven düşük, kesin hata değil, sahne kullanılmaz.
  * is_224824 s01/s02: önceden kabul edilmiş sahneler kabul kalmalı (s01 kararsız işareti bilinen durumdur).
  * is_005509 s01/s02: tests/test_kontrol_ornekleri.py'de.
Kutular elle işaretlenmiş TEST ölçütüdür; algılama kodu kutu/koordinat kullanmaz. Eşikler gevşetilmedi (7. madde).
Çalıştır: python tests/test_farkli_ortamlar.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import cv2                      # noqa: E402
import numpy as np              # noqa: E402

import banner_detect as bd      # noqa: E402
import compositor as cp         # noqa: E402
import deneme_kayit as dk       # noqa: E402
import layout                   # noqa: E402
import orchestrator as orch     # noqa: E402
import product                  # noqa: E402
from providers import Settings  # noqa: E402

K = os.path.join(HERE, "kontrol_ornekleri")
PROF = product.profil_olustur("75x200")
O = orch.Orchestrator(Settings(photo_long_side=2400, strict_layout=True), log=lambda m: None, progress=lambda f, t: None)
assert isinstance(O.gk_servis, orch.gks.KapaliServis), "görsel kontrol servisi varsayılan olarak kapalı olmalı"
DESIGN = np.ones((2000, 750, 3), np.float32)
DESIGN[300:1700, 150:600] = 0.25

# eşikler değişmedi
assert layout.ASPECT_RATIO_TOL == (0.72, 1.30) and cp.TAM_BOY_TOL == 0.03 and dk.BOY_TOL == 0.03
assert bd.STRONG_REJECT == 0.25 and bd.DETAIL_REJECT == 3.5


def kutu_orani(m, k):
    H, W = m.shape
    x0, y0, x1, y1 = k
    return float(m[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)].mean())


def degerlendir(yol):
    img = O._upscale(cv2.imread(yol))
    ev = O._evaluate_scene(img, DESIGN, PROF, os.path.basename(yol))
    rec = {"tur": ev["tur"], "neden": ev["neden"], "olcum": ev["lay"]}
    rec.update(ev.get("extra") or {})
    oto = dk.kontrol_sonucu(rec, PROF.oran, PROF.boy_cm) if not ev["ok"] else {"durum": "uygun"}
    return img, ev, rec, oto


# ---- 054333 ---------------------------------------------------------------------------------------------------
man = json.load(open(os.path.join(K, "is_054333", "kontrol.json"), encoding="utf-8"))
img, ev, rec, oto = degerlendir(os.path.join(K, "is_054333", "ham.jpg"))
m = ev["det"].mask > 0
assert kutu_orani(m, man["kutular"]["kumas"]) > 0.8, "054333: kumaş seçilmedi"   # kutu kenar payı içerir
assert kutu_orani(m, man["kutular"]["koyu_bosluk"]) < 0.01, "054333: koyu boşluk seçildi"
assert not ev["ok"] and ev["tur"] == "sahne_geometri", (ev["tur"], ev["neden"])
assert rec["sinir_araligi"]["kaynak"] == "geometri", rec["sinir_araligi"]
assert oto["durum"] == "inceleme" and "sahnede çizilen kumaştan" in oto["aciklama"], oto
print("054333: kumaş seçildi; ret = sahne geometrisi;", rec["sinir_araligi"], "->", oto["durum"])

# ---- 053942 ---------------------------------------------------------------------------------------------------
man = json.load(open(os.path.join(K, "is_053942", "kontrol.json"), encoding="utf-8"))
img, ev, rec, oto = degerlendir(os.path.join(K, "is_053942", "ham.jpg"))
det = ev["det"]
m = det.mask > 0
assert kutu_orani(m, man["kutular"]["kumas"]) > 0.95, "053942: kumaş maskede değil"
for k in ("sol_duvar_boslugu", "sag_duvar_boslugu"):
    assert kutu_orani(m, man["kutular"][k]) < 0.02, f"053942: maske duvara taşıyor ({k})"
assert not any("boş görünmüyor" in r for r in det.reject), det.reject
assert (det.metrics.get("yan_kirpilan_oran") or 0) > 0, "yan kırpma kayda geçmeli"
if not ev["ok"]:
    assert ev["tur"] != "kalite_kapisi", ev["neden"]
    assert oto["durum"] == "inceleme" and oto["guven"] == "dusuk", oto
    assert rec.get("sinir_araligi", {}).get("kaynak") == "sınır", rec.get("sinir_araligi")
print("053942: duvara taşma yok, desen reddi yok;", "kabul" if ev["ok"] else f"ret ({ev['tur']}) {rec.get('sinir_araligi')} -> {oto['durum']}/{oto.get('guven')}")

# ---- 224824 kabul edilenler ----------------------------------------------------------------------------------
for ad in ("kabul_s01_ham.png", "kabul_s02_ham.png"):
    img, ev, rec, oto = degerlendir(os.path.join(K, "is_224824", ad))
    assert ev["ok"], f"224824 {ad} artık elenmiş: {ev['neden']}"
    print(f"224824 {ad}: kabul, asılı {ev['tk_info']['asili_cm']:.1f} cm, kararsız={ev['tk_info'].get('kararlilik', {}).get('kararsiz')}")

print("test_farkli_ortamlar: TAMAM")
