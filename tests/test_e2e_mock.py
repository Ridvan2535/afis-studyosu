"""
Uçtan uca sınama SAHTE sağlayıcılarla (gerçek servis yok): sahne üretimi -> kalite kapısı -> yerleştirme ->
video -> yazı onarımı -> kalite kontrol -> hata raporu.
Çalıştır:  python tests/test_e2e_mock.py [tasarim_yolu]
"""
import json
import os
import sys
import tempfile
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("MOCK_FRAMES", "16")

import orchestrator as orch          # noqa: E402
from providers import Settings        # noqa: E402

design = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "design_candy.jpg")
tmp = tempfile.mkdtemp(prefix="afis_e2e_")
orch.JOBS_DIR = os.path.join(tmp, "isler")
orch.REPORT_DIR = os.path.join(tmp, "raporlar")
orch.LOG_PATH = os.path.join(tmp, "kayit.log")

s = Settings(scene_provider="mock", video_provider="mock", max_scene_calls=14, max_video_tries=2,
             photo_long_side=1600, seconds=4, auto_video=False, magnific_key="SECRET-KEY-123456")
msgs = []
o = orch.Orchestrator(s, log=msgs.append, progress=lambda f, t: None)

t0 = time.time()
job = o.new_job(design, "Doğum günü / Baby shower", "test")
res = o.generate_photos(job, 6)
rap = o.report_of(job)
print(f"FOTOĞRAF: {res}  ({time.time() - t0:.0f}s)")
for p in rap["fotograflar"]:
    print("  kabul:", p["ad"], p["tur"], p["olcu"], p["uyari"])
for e in rap["elenenler"]:
    print("  elendi: çağrı", e["cagri"], "-", e["neden"][:110])
assert res["uretilen"] == 6, "6 geçerli fotoğraf bekleniyordu"
assert os.path.exists(os.path.join(job, "foto", "_ozet.jpg"))

# video: önce sert afişli bir fotoğraf, sonra kumaşlı
pick = next(p for p in rap["fotograflar"] if p["tur"] == "rigid")
t1 = time.time()
v = o.generate_video(job, pick["ad"])
print(f"\nVİDEO ({pick['ad']}): kontrol_gecti={v['kontrol_gecti']} deneme={v['secilen_deneme']} nedenler={v['nedenler']} "
      f"({time.time() - t1:.0f}s)")
for d in v["denemeler"]:
    print("  ", d)
final = os.path.join(job, v["dosya"])
assert os.path.getsize(final) > 10_000, "final.mp4 boş"

# kamera hareketi (yapay zekasız): "hepsi" -> 3 video
import camera_move as cm              # noqa: E402
t2 = time.time()
cv = o.generate_camera_videos(job, pick["ad"], cm.expand("hepsi"))
print(f"\nKAMERA: {[v['hareket'] for v in cv['videolar']]} ({time.time() - t2:.0f}s)")
assert len(cv["videolar"]) == 3
import video_repair as vr            # noqa: E402
for v in cv["videolar"]:
    fr, fps = vr.read_video(os.path.join(job, v["dosya"]))
    assert len(fr) >= 100 and abs(fps - 30) < 1, (v["dosya"], len(fr), fps)
rap2 = o.report_of(job)
assert sum(1 for v in rap2["videolar"] if v.get("tur") == "kamera") == 3

# insanlı sahne: istem ve rapor işareti
import prompts                       # noqa: E402
assert "PEOPLE:" in prompts.build_scene_prompt("Düğün", 0, 4116, 8000, people=True)
assert "PEOPLE:" not in prompts.build_scene_prompt("Düğün", 0, 4116, 8000)
assert "REALISM" in prompts.build_scene_prompt("Düğün", 0, 4116, 8000)
assert prompts.default_people("Düğün") and not prompts.default_people("Baby shower")
assert prompts.canon("Doğum günü / Baby shower") == "Baby shower"
assert len({prompts.build_scene_prompt("Yılbaşı", i, 75, 200, round_no=i // 8) for i in range(30)}) == 30
_rb = prompts.build_scene_prompt("Düğün", 0, 4116, 8000, ribbon={"ad": "Pudra", "hex": "#E8B4BC"})
assert "wooden frame" in _rb and "blush pink" in _rb and "#E8B4BC" in _rb and "ribbon tails" in _rb and "NOT hung from the ceiling" in _rb, _rb[:600]
_nr = prompts.build_scene_prompt("Düğün", 0, 4116, 8000)
assert "No ribbons" in _nr and "4 cm wide" not in _nr and "wooden frame" in _nr
assert Settings().ribbon()["hex"] == "#F2C230" and Settings().ribbon("") is None and Settings().ribbon("yok") is None
import guide as _g
import ribbon as _rbn
assert _rbn.mask(__import__("numpy").zeros((8, 8, 3), "uint8"), "#F1E6D2") is None
assert _g.make_guide(2 / 3, 0.375, ribbon_hex="#F2C230")[0][:4] == b"\x89PNG"
assert prompts.size_for(4116 / 8000) == (50, 100) and prompts.size_for(0.375) == (75, 200) and prompts.size_for(1 / 3) == (50, 150)
assert prompts.size_for(0.9) is None
assert "50 cm wide and 100 cm tall" in prompts.build_scene_prompt("Düğün", 0, 4116, 8000)
assert "NOT a thin runner" not in prompts.build_scene_prompt("Düğün", 0, 4116, 8000)

# kompozit video (yapay zekâ videosu + kodla baskı + el kamerası), sahte sabit-kameralı video ile
t3 = time.time()
s.camera_move, s.handheld = "saga", "yuruyus"
o2 = orch.Orchestrator(s, log=msgs.append, progress=lambda f, t: None)
kv = o2.generate_composite_video(job, pick["ad"])
r0 = kv["videolar"][0]
print(f"\nKOMPOZİT: tur={r0['tur']} gecti={r0['kontrol_gecti']} deneme={r0.get('secilen_deneme')} ({time.time() - t3:.0f}s)")
for d in r0["denemeler"]:
    print("  ", d)
assert r0["tur"] == "kompozit" and r0["kontrol_gecti"], r0
fr, fps = vr.read_video(os.path.join(job, r0["dosya"]))
assert len(fr) >= 14 and abs(fps - 24) < 1, (len(fr), fps)

# gerçek hareketli video (kamerayı yapay zekâ yürütür): sahte video + izlenen baskı
t3b = time.time()
lv = o2.generate_live_video(job, pick["ad"])
l0 = lv["videolar"][0]
print(f"\nCANLI: tur={l0['tur']} canli={l0.get('canli')} yedek={l0.get('yedek')} neden={l0.get('yedek_neden')} ({time.time() - t3b:.0f}s)")
for d_ in l0.get("denemeler", []):
    print("  ", d_)
assert l0.get("canli") or l0.get("yedek"), l0
assert os.path.exists(os.path.join(job, l0["dosya"]))

# kompozit video, kamera çok oynayan (kötü) sahte video: otomatik güvenli yedek
os.environ["MOCK_VIDEO"] = "bad"
s.max_video_tries = 1
t4 = time.time()
bv = o2.generate_composite_video(job, pick["ad"])
b0 = bv["videolar"][0]
print(f"\nKOMPOZİT-KÖTÜ: tur={b0['tur']} yedek={b0.get('yedek')} neden={b0.get('yedek_neden')} ({time.time() - t4:.0f}s)")
assert b0["tur"] == "kamera" and b0.get("yedek"), b0
del os.environ["MOCK_VIDEO"]

# --- OTOMATİK SERVİS SEÇİMİ: kötü (yan açılı), hatalı ve iyi sahte servis yarışır ---
orch.STATS_PATH = os.path.join(tmp, "servis_karnesi.json")
s.max_video_tries = 2
s.max_scene_calls = 30          # sahte sahnelerin yarısı zaten kapıdan dönüyor; kötü servislere harcanan çağrıları da karşılasın
o3 = orch.Orchestrator(s, log=msgs.append, progress=lambda f, t: None)
o3.rng_seed = 5
o3.arms_override = {"scene": ["mock_bad", "mock_err", "mock"], "video": ["mock_vbad", "mock"]}
job2 = o3.new_job(design, "Düğün", "oto")
t5 = time.time()
r2 = o3.generate_photos(job2, 4)
rap_a = o3.report_of(job2)
print(f"\nOTO-SAHNE: {r2} ({time.time() - t5:.0f}s)")
print("  servisler:", [(p["ad"], p["servis"], p["kalite"], p.get("en_iyi")) for p in rap_a["fotograflar"]])
k = rap_a["servis_karnesi"][-1]
print("  karne:", [(r["servis"], r["cagri"], r["kabul"], r["hata"]) for r in k["tablo"]], "kazanan:", k["kazanan"])
assert r2["uretilen"] == 4, r2
assert all(p["servis"] == "mock" for p in rap_a["fotograflar"]), "yalnızca iyi servisin sahneleri kabul edilmeliydi"
assert k["kazanan"] == "mock"
assert sum(1 for p in rap_a["fotograflar"] if p.get("en_iyi")) == 1, "tek bir en iyi fotoğraf olmalı"
tab = {r["servis"]: r for r in k["tablo"]}
assert tab["mock_bad"]["cagri"] >= 1 and tab["mock_bad"]["kabul"] == 0
assert tab["mock_err"]["hata"] >= 1 and tab["mock_err"]["kabul"] == 0
assert tab["mock"]["kabul"] == 4
assert all(e.get("servis") for e in rap_a["elenenler"])
# kötü servis sürekli seçilmemeli: iyi servis çağrıların çoğunu almalı
assert tab["mock"]["cagri"] > tab["mock_bad"]["cagri"], tab
assert tab["mock_err"]["cagri"] <= 3, tab                 # 3 üst üste hatadan sonra bırakılmış olmalı
assert any("devre dışı" in m for m in msgs), "hatalı servis devre dışı bırakılmalıydı"

pick2 = next(p for p in rap_a["fotograflar"] if p["tur"] == "rigid")
t6 = time.time()
av = o3.generate_composite_video(job2, pick2["ad"])
a0 = av["videolar"][0]
print(f"OTO-VİDEO: tur={a0['tur']} servis={a0.get('servis')} kalite={a0.get('kalite')} ({time.time() - t6:.0f}s)")
for d in a0["denemeler"]:
    print("   ", {kk: d.get(kk) for kk in ("deneme", "servis", "kontrol_gecti", "kalite", "nedenler", "hata")})
assert a0["tur"] == "kompozit" and a0["servis"] == "mock" and a0["kontrol_gecti"], a0
assert [d["servis"] for d in a0["denemeler"]] == ["mock_vbad", "mock"], a0["denemeler"]
assert a0["denemeler"][0]["kontrol_gecti"] is False and a0["kalite"] is not None
vk = [x for x in o3.report_of(job2)["servis_karnesi"] if x["tur"] == "video"][-1]
assert vk["kazanan"] == "mock", vk
import selector                              # noqa: E402
assert selector.overview(orch.STATS_PATH) == {"scene": [], "video": []}, "sahte servisler kalıcı karneye yazılmamalı"

# ORAN DÜZELTME: servis afişi fazla ince çizerse sahne atılmaz, genişletilip tasarım oranına getirilir
import dataclasses as _dc
o6 = orch.Orchestrator(_dc.replace(s, auto_video_kind="kamera"), log=msgs.append, progress=lambda f, t: None)   # sahte 'ince' servis oranı kadrajdan türetir; 9:16 kadrajda düzeltme sınırını aşar (test yapaylığı)
o6.arms_override = {"scene": ["mock_thin"]}
job6 = o6.new_job(design, "Düğün", "ince")
r6 = o6.generate_photos(job6, 2)
rap6 = o6.report_of(job6)
print(f"ORAN-DÜZELTME: {r6}")
for p_ in rap6["fotograflar"]:
    print("  ", p_["ad"], "oran", (p_["yerlesim"] or {}).get("aspect"), "düzeltme", p_.get("oran_duzeltme"), "kalite", p_["kalite"], "boyut", p_["olcu"])
assert r6["uretilen"] == 2, (r6, rap6["elenenler"])
da_ = 4116 / 8000
for p_ in rap6["fotograflar"]:
    assert p_["oran_duzeltme"] and p_["oran_duzeltme"]["f"] > 1.2, p_
    assert abs(p_["yerlesim"]["aspect"] / da_ - 1) < 0.04, p_["yerlesim"]
    assert p_["kalite"] <= 100 - 5, p_["kalite"]                       # düzeltilmiş sahne, düzeltilmemişten hafif geride
assert any("genişletildi" in m for m in msgs)

# REFERANS DEPOSU: depodaki görseller sırayla sahnelere verilir, tarifli olanın tarifi kullanılır
import cv2 as _cv2, numpy as _np
_ok, _png = _cv2.imencode(".png", _np.full((300, 200, 3), 150, _np.uint8))
msgs7 = []
o7 = orch.Orchestrator(s, log=msgs7.append, progress=lambda f, t: None)
job7 = o7.new_job(design, "Düğün", "depo")
r7 = o7.generate_photos(job7, 2, ref_items=[(_png.tobytes(), "OUT: a test garden"), (_png.tobytes(), "")])
assert r7["uretilen"] == 2, r7
assert any("Referans deposu: 2 görsel" in m for m in msgs7), msgs7[:5]
print("REFERANS DEPOSU: tamam")

# OTOMATİK VİDEO: fotoğraf üretimi bitince her fotoğraf için onaylanan hareketle video da çıkar
s_av = Settings(scene_provider="mock", video_provider="mock", max_scene_calls=14, photo_long_side=1200, seconds=2, auto_video=True)
o7 = orch.Orchestrator(s_av, log=msgs.append, progress=lambda f, t: None)
job7 = o7.new_job(design, "Düğün", "otovideo")
r7 = o7.generate_photos(job7, 2)
rap7 = o7.report_of(job7)
print(f"OTO-VİDEO-FOTO: {r7} videolar={[(v['foto'], v['hareket']) for v in rap7.get('videolar', [])]}")
assert r7["uretilen"] == 2 and len(rap7["videolar"]) == 2, rap7.get("videolar")
assert all(v["hareket"] == "yakinlas_saga" and os.path.getsize(os.path.join(job7, v["dosya"])) > 10_000 for v in rap7["videolar"])
assert (not Settings().auto_video) and Settings().camera_move == "yakinlas_saga"     # kullanıcı isteği: otomatik video varsayılan kapalı

# tüm servisler hatalıysa kredi harcamadan durmalı
o4 = orch.Orchestrator(s, log=msgs.append, progress=lambda f, t: None)
o4.arms_override = {"scene": ["mock_err", "mock_err"]}
job3 = o4.new_job(design, "Düğün", "hata")
r3 = o4.generate_photos(job3, 3)
print(f"OTO-HATA: {r3}")
assert r3["uretilen"] == 0 and r3["cagri"] <= 3, r3                  # 3 üst üste hatada devre dışı: en çok 3 çağrı

# hata raporu: anahtar sızmamalı
rp = o.make_report(job)
with zipfile.ZipFile(rp) as z:
    names = z.namelist()
    blob = b"".join(z.read(n) for n in names if n.endswith((".txt", ".json", ".log")))
print("\nRAPOR:", os.path.basename(rp), "içerik:", names)
assert b"SECRET-KEY-123456" not in blob, "ANAHTAR RAPORA SIZDI"
assert not any(n.startswith("tasarim") for n in names), "tasarım rapora girmiş"
print("anahtar sızıntısı yok, tasarım rapora girmedi")
print("iş klasörü:", job)
