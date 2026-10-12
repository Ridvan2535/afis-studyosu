# -*- coding: utf-8 -*-
"""
Kare (1:1) fotoğraf kadrajı ve ürün profili — SAHTE SERVİS testi (mock_provider; ağ yok, ücretli çağrı yok).

Doğrulananlar:
  1. auto_video_kind "canli" ve "kamera" iken sağlayıcıya giden kadraj oranı 1.0, kılavuz kare, foto/*.jpg kare.
  2. 50x100 ve 150x300 (AYNI oran) profilleri prompt'ta ayrı ölçü olarak gider (50 cm / 150 cm).
  3. Oranı uyuşmayan tasarımda sağlayıcı HİÇ çağrılmaz; onizleme_oran.png yazılır; rapor "beklemede".
  4. Uyumlu tasarımda üretim olur; kayıtlar yeni alanları taşır (yerlesim_modu, tam_kumas, tur), eski alanlar durur.
  5. Elenen kayıtlarında hata türü (tur) ayrı: sahne_geometri / kalite_kapisi / birikme_cozulemedi / servis_hatasi.
  6. Eski rapor (urun_profili yok) okunur; üretim Settings.ornek_olcu ile yapılır.
Çalıştır:  python tests/test_kare_kadraj.py
"""
import glob
import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import cv2                      # noqa: E402
import numpy as np              # noqa: E402

import mock_provider as mp      # noqa: E402
import orchestrator as orch     # noqa: E402
import product                  # noqa: E402
from providers import SceneProvider, Settings   # noqa: E402

tmp = tempfile.mkdtemp(prefix="afis_kare_")
orch.JOBS_DIR = os.path.join(tmp, "isler")
orch.REPORT_DIR = os.path.join(tmp, "raporlar")
orch.LOG_PATH = os.path.join(tmp, "kayit.log")
orch.STATS_PATH = os.path.join(tmp, "karne.json")

CALLS = []


class Spy:
    """Sağlayıcıya giden her çağrıyı kaydeden sahte servis (içeride mock_provider.MockScenes)."""
    supports_guide = True

    def __init__(self, variant):
        self.inner = mp.MockScenes(variant if variant in ("mock", "mock_err", "mock_bad", "mock_thin") else "mock")
        if variant in mp.MockScenes.FORCED:
            self.inner.kind = variant
        self.variant = variant

    def scene(self, prompt, aw, ah, refs=None, seed=None, guide=None):
        g = cv2.imdecode(np.frombuffer(guide, np.uint8), cv2.IMREAD_COLOR) if guide else None
        CALLS.append({"servis": self.variant, "aw": aw, "ah": ah, "prompt": prompt, "guide": None if g is None else g.shape[:2]})
        return self.inner.scene(prompt, aw, ah, refs, seed, guide)


orch.make_scene_provider = lambda s, log=print, name=None: SceneProvider(Spy(name or s.scene_provider))


def write_design(path, w, h, bottom_ink=False):
    rgba = np.zeros((h, w, 4), np.uint8)
    cv2.putText(rgba, "ADA", (int(0.18 * w), int(0.22 * h)), cv2.FONT_HERSHEY_SIMPLEX, w / 130, (40, 40, 160, 255), max(2, w // 40))
    cv2.circle(rgba, (w // 2, h // 2), w // 6, (60, 120, 40, 255), -1)
    if bottom_ink:
        cv2.rectangle(rgba, (int(0.1 * w), int(0.95 * h)), (int(0.9 * w), int(0.99 * h)), (30, 30, 30, 255), -1)
    cv2.imwrite(path, rgba)
    return path


d75 = write_design(os.path.join(tmp, "t75.png"), 750, 2000)            # 75x200 ile tam oranlı
d50 = write_design(os.path.join(tmp, "t50.png"), 500, 1000)            # 50x100 ve 150x300 ile tam oranlı
d75_ink = write_design(os.path.join(tmp, "t75i.png"), 750, 2000, bottom_ink=True)


def settings(**kw):
    base = dict(scene_provider="mock", video_provider="mock", max_scene_calls=8, photo_long_side=1200, auto_video=False)
    base.update(kw)
    return Settings(**base)


msgs = []

# ---------------------------------------------------------------- 1. kadraj videodan bağımsız kare
for kind in ("canli", "kamera"):
    CALLS.clear()
    o = orch.Orchestrator(settings(auto_video_kind=kind), log=msgs.append, progress=lambda f, t: None)
    job = o.new_job(d75, "Düğün", f"kare_{kind}")
    r = o.generate_photos(job, 2)
    assert r["uretilen"] == 2 and not r["beklemede"], r
    assert CALLS and all(abs(c["aw"] / c["ah"] - 1.0) < 1e-9 for c in CALLS), [(c["aw"], c["ah"]) for c in CALLS]
    assert all(c["guide"] and c["guide"][0] == c["guide"][1] for c in CALLS), [c["guide"] for c in CALLS]
    fotos = [p for p in glob.glob(os.path.join(job, "foto", "*.jpg")) if not p.endswith("_ozet.jpg")]
    assert len(fotos) == 2
    for p in fotos:
        im = cv2.imread(p)
        assert im.shape[0] == im.shape[1], (p, im.shape)
    rap = o.report_of(job)
    for ph in rap["fotograflar"]:
        assert ph["yerlesim_modu"] == "tam_kumas" and ph["ad"].endswith("_kumas.jpg") and ph["olcu_id"] == "75x200", ph
        for k in ("ad", "stem", "tur", "uyari", "olcu", "yerlesim", "servis", "kalite", "kurdele"):     # eski alanlar
            assert k in ph, k
        tk = ph["tam_kumas"]
        assert tk["sorunlar"] == [] and tk["px_per_cm"] > 0 and abs(tk["asili_cm"] - 200) < 25, tk
    print(f"auto_video_kind={kind}: {len(CALLS)} çağrı, hepsi kare (1:1); fotoğraflar", [cv2.imread(p).shape[:2] for p in fotos])

# ---------------------------------------------------------------- 2. aynı oranlı ölçüler prompt'ta ayrışır
prompts_by = {}
for olcu in ("50x100", "150x300"):
    CALLS.clear()
    o = orch.Orchestrator(settings(), log=msgs.append, progress=lambda f, t: None)
    job = o.new_job(d50, "Düğün", f"olcu_{olcu}", profile=product.profil_olustur(olcu))
    r = o.generate_photos(job, 1)
    assert r["uretilen"] == 1, r
    prompts_by[olcu] = CALLS[0]["prompt"]
    assert o.report_of(job)["urun_profili"]["olcu_id"] == olcu
assert "exactly 50 cm wide and 100 cm long" in prompts_by["50x100"], prompts_by["50x100"][:400]
assert "exactly 150 cm wide and 300 cm long" in prompts_by["150x300"]
assert prompts_by["50x100"] != prompts_by["150x300"]
print("50x100 ve 150x300 prompt'ları farklı (50 cm / 150 cm)")

# ---------------------------------------------------------------- 3. oran uyuşmazlığı: hiç çağrı yok, beklemede
CALLS.clear()
o = orch.Orchestrator(settings(), log=msgs.append, progress=lambda f, t: None)
job = o.new_job(os.path.join(ROOT, "design_candy.jpg"), "Düğün", "uyumsuz")         # 4116x8000 (0.51) vs 75x200 (0.375)
rap0 = o.report_of(job)
assert rap0["durum"] == "beklemede" and rap0["bekleme_nedeni"] == "tasarim_oran_uyusmazligi", rap0
r = o.generate_photos(job, 6)
rap = o.report_of(job)
assert len(CALLS) == 0, f"uyumsuz tasarımda sağlayıcı çağrıldı: {len(CALLS)}"
assert r["beklemede"] is True and r["cagri"] == 0 and r["uretilen"] == 0, r
assert os.path.exists(os.path.join(job, "onizleme_oran.png"))
assert rap["durum"] == "beklemede" and rap["bekleme_nedeni"] == "tasarim_oran_uyusmazligi" and rap["tasarim_kontrol"]["uyumlu"] is False
assert rap["fotograflar"] == [] and not glob.glob(os.path.join(job, "foto", "*.jpg"))
assert any("Tasarım oranı kumaşla uyuşmuyor" in m for m in msgs), msgs[-3:]
print("uyumsuz tasarım: 0 çağrı, onizleme_oran.png var, durum beklemede")
# aynı iş, uyumlu ölçüyle (profil açıkça verilince) bekleme kalkar ve üretim olur — design_candy 50x100'e de uymaz (0.51)
r2 = o.generate_photos(job, 1, profile=product.profil_olustur("50x100"))
assert r2["beklemede"] and len(CALLS) == 0, r2

# ---------------------------------------------------------------- 4/5. hata türleri ayrı kaydedilir
CALLS.clear()
o = orch.Orchestrator(settings(max_scene_calls=12), log=msgs.append, progress=lambda f, t: None)
o.arms_override = {"scene": ["mock_long"]}
job = o.new_job(d75, "Düğün", "uzun")
r = o.generate_photos(job, 1)
rap = o.report_of(job)
assert r["uretilen"] == 0 and len(CALLS) > 0
assert {e["tur"] for e in rap["elenenler"]} == {"sahne_geometri"}, [(e["tur"], e["neden"][:60]) for e in rap["elenenler"]]
assert all(e.get("tam_kumas") and e.get("dosya") for e in rap["elenenler"])
print("ürün boyundan uzun sahne -> sahne_geometri:", len(rap["elenenler"]), "kez")

o = orch.Orchestrator(settings(max_scene_calls=3), log=msgs.append, progress=lambda f, t: None)
o.arms_override = {"scene": ["mock_pool"]}
job = o.new_job(d75_ink, "Düğün", "birikme")
r = o.generate_photos(job, 1)
rap = o.report_of(job)
assert r["uretilen"] == 0 and {e["tur"] for e in rap["elenenler"]} == {"birikme_cozulemedi"}, rap["elenenler"]
print("alt kenarı mürekkepli tasarım + birikmeli sahne -> birikme_cozulemedi (başarılı sayılmadı)")

o = orch.Orchestrator(settings(max_scene_calls=3), log=msgs.append, progress=lambda f, t: None)
o.arms_override = {"scene": ["mock_pool"]}
job = o.new_job(d75, "Düğün", "birikme_ok")
r = o.generate_photos(job, 1)
rap = o.report_of(job)
ph = rap["fotograflar"][0]
assert r["uretilen"] == 1 and ph["tam_kumas"]["birikme"] and ph["tam_kumas"]["gizli_cm"] > 5, ph["tam_kumas"]
assert ph["gizli_onizleme"] == "onizleme/01_gizli.jpg" and os.path.exists(os.path.join(job, ph["gizli_onizleme"]))
print("alt kenarı boş tasarım + birikmeli sahne -> kabul; gizli ≈", ph["tam_kumas"]["gizli_cm"], "cm; önizleme", ph["gizli_onizleme"])

o = orch.Orchestrator(settings(max_scene_calls=3), log=msgs.append, progress=lambda f, t: None)
o.arms_override = {"scene": ["mock_air"]}
job = o.new_job(d75, "Düğün", "havada")
r = o.generate_photos(job, 1)
turs = {e["tur"] for e in o.report_of(job)["elenenler"]}
assert r["uretilen"] == 0 and turs == {"sahne_geometri"}, turs
print("havada biten kumaş -> elendi:", turs)

o = orch.Orchestrator(settings(max_scene_calls=3), log=msgs.append, progress=lambda f, t: None)
o.arms_override = {"scene": ["mock_err"]}
job = o.new_job(d75, "Düğün", "hata")
o.generate_photos(job, 1)
assert {e["tur"] for e in o.report_of(job)["elenenler"]} == {"servis_hatasi"}

# ---------------------------------------------------------------- 6. eski rapor (profil yok) okunur ve korunur
o = orch.Orchestrator(settings(ornek_olcu="75x200"), log=msgs.append, progress=lambda f, t: None)
job = o.new_job(d75, "Düğün", "eski")
p = os.path.join(job, "rapor.json")
old = {"surum": "0.7-test", "kategori": "Düğün", "olusturuldu": "20260101-000000", "fotograflar": [
    {"ad": "01_rigid.jpg", "stem": "s01", "tur": "rigid", "uyari": [], "olcu": [1024, 1536], "yerlesim": {}, "servis": "mock",
     "kalite": 80.0, "oran_duzeltme": None, "kurdele": None}], "elenenler": [{"cagri": 1, "servis": "mock", "neden": "x"}], "videolar": []}
with open(p, "w", encoding="utf-8") as f:
    json.dump(old, f)
assert o.report_of(job)["fotograflar"][0]["ad"] == "01_rigid.jpg"
assert o._profile(o.report_of(job)).olcu_id == "75x200"
r = o.generate_photos(job, 1)
rap = o.report_of(job)
eski_foto = {k: v for k, v in rap["fotograflar"][0].items() if k != "en_iyi"}     # en_iyi her üretimde (eskiden de) yeniden hesaplanır
assert r["uretilen"] == 1 and eski_foto == old["fotograflar"][0] and rap["elenenler"][0] == old["elenenler"][0], rap["fotograflar"][0]
assert rap["fotograflar"][1]["ad"] == "02_kumas.jpg" and rap["urun_profili"]["olcu_id"] == "75x200"
print("eski rapor alanları korundu; yeni üretim profil ve tam kumaş alanlarını ekledi")

print("test_kare_kadraj: TAMAM")
