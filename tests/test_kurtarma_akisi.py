# -*- coding: utf-8 -*-
"""G5a — kurtarma akışı, video yeniden yerleşim tutarlılığı ve görsel kontrol bütçesi (YEREL + SAHTE servis; ağ yok,
ücret yok, gerçek API çağrısı yok). Sahibi: pipeline-engineer.

1) Kurtarma döngüsü (K-52 "kararlı ≠ doğru"): 2. aday KARARLI RET, 3. aday KABUL -> 3. seçilir; kararlı ret kayıtta görünür.
   Hiçbir aday kabul edilmezse ilk değerlendirmenin tanısı korunur (yanlış adayın ret nedeni yerine geçmez) ve kayıtta
   denenen adaylar görünür. Görsel kontrol önerisi kararlı ret verirse de ilk tanı korunur.
2) Video: kayıtlı fotoğraf eski K-16 kuralıyla ("temas_cizgisine_kadar") ya da güncel yeniden yerleşim sorunluysa kamera
   videosu KAYITLI fotoğrafı kullanır; ücretli video yolunda (_video_start -> generate_video) kullanıcıya görünen uyarı.
3) Bütçe: servis istisna verirse ya da yanıt çözülemezse de çağrı sayılır (en az tahmini tutar); ClaudeServis JSON
   çözülemese de kullanım bilgisini döndürür (sahte `requests`, ağ yok).
Düzeltmeler geri alınırsa (HEAD sürümü) 1, 2 ve 3'teki testler başarısız olur (rapor: ekip/raporlar/pipeline-engineer.md).
"""
import contextlib
import os
import sys
import tempfile
import types
from types import SimpleNamespace

import cv2
import numpy as np

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import banner_detect as bd            # noqa: E402
import gorsel_kontrol_servisi as gks  # noqa: E402
import orchestrator                   # noqa: E402
from providers import Settings        # noqa: E402

PROF = SimpleNamespace(oran=0.37, boy_cm=180)
IMG = np.full((200, 200, 3), 120, np.uint8)


def kutu(x0, y0, x1, y1, H=200, W=200):
    m = np.zeros((H, W), bool)
    m[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = True
    return m


def det(mask):
    return bd.Detection(mask=mask.astype(np.uint8) * 255, kind="fabric", metrics={"lightness": 200, "area_ratio": 0.2},
                        reject=[])


ILK = kutu(0.02, 0.1, 0.12, 0.7)        # ilk (şüpheli) algılama: soldaki şerit
A2 = kutu(0.70, 0.1, 0.95, 0.9)         # 2. aday: kararlı RET verecek (yanlış bölge)
A3 = kutu(0.35, 0.1, 0.65, 0.9)         # 3. aday: KABUL
A4 = kutu(0.20, 0.5, 0.30, 0.95)


@contextlib.contextmanager
def yama(nesne, **degerler):
    """Modül özniteliklerini yalnız blok içinde değiştirir; çıkışta (hata olsa da) geri yükler."""
    asil = {k: getattr(nesne, k) for k in degerler}
    for k, v in degerler.items():
        setattr(nesne, k, v)
    try:
        yield
    finally:
        for k, v in asil.items():
            setattr(nesne, k, v)


def sahte_orc(sonuclar, servis=None, butce=None):
    """sonuclar: maske kimliği -> (ok, kararli, neden). _aday_degerlendir yalnız bunu döndürür (gerçek ölçüm yok)."""
    o = object.__new__(orchestrator.Orchestrator)
    o.loglar = []
    o.log = o.loglar.append
    o.gk_servis = servis or gks.KapaliServis()
    o.gk_butce = butce
    o.s = SimpleNamespace(kurtarma_etkin=True)
    o.denenen = []

    def aday(img, design, prof, label, d, hint):
        anahtar = next(k for k, m in (("A2", A2), ("A3", A3), ("A4", A4), ("ILK", ILK)) if np.array_equal(d.mask > 0, m))
        o.denenen.append(anahtar)
        ok, kararli, neden = sonuclar[anahtar]
        return {"ok": ok, "tur": None if ok else "sahne_geometri", "neden": neden, "det": d, "lay": {},
                "extra": {}}, kararli
    o._aday_degerlendir = aday
    return o


ILK_EV = {"ok": False, "tur": "kalite_kapisi", "neden": "İLK TANI: bulunan bölge açık renkli/nötr değil", "det": det(ILK),
          "lay": {}, "extra": {"algilama": {}}}


# ---- 1) kurtarma döngüsü -----------------------------------------------------------------------------------------
def test_kararli_ret_aramayi_bitirmez_kabul_secilir():
    adaylar = [det(ILK), det(A2), det(A3)]               # 1. aday ilk algılamayla aynı bölge (atlanır)
    o = sahte_orc({"A2": (False, True, "A2 asılı ≈120 cm, ürün 200 cm"), "A3": (True, True, None)})
    with yama(bd, detect_candidates=lambda img, hint, en_fazla=4, **k: adaylar):
        ev, bilgi = o._kurtar(IMG, None, PROF, "s", dict(ILK_EV))
    assert ev is not None and ev["ok"], f"kararlı ret aramayı bitirdi: {bilgi}"
    assert bilgi["sonuc"] == "yerel_aday_kabul" and bilgi["secilen"]["aday"] == 3, bilgi
    assert o.denenen == ["A2", "A3"], o.denenen
    ya = bilgi["yerel_adaylar"]
    assert [y["aday"] for y in ya] == [2, 3] and ya[0]["sonuc"].startswith("ret: A2") and ya[0]["kararli"], ya
    print("1a) 2. aday kararlı ret, 3. aday kabul -> 3. seçildi; ret kayıtta:", ya[0]["sonuc"])


def test_hicbiri_kabul_degil_ilk_tani_korunur():
    adaylar = [det(A2), det(A4)]
    o = sahte_orc({"A2": (False, True, "A2 YANLIŞ ADAY RET NEDENİ"), "A4": (False, False, "A4 kararsız ret")})
    o._evaluate_scene = lambda img, design, prof, label: {**ILK_EV, "extra": {"algilama": {}}}
    o._supheli_mi = lambda ev, prof: True
    with yama(bd, detect_candidates=lambda img, hint, en_fazla=4, **k: adaylar):
        ev = o._degerlendir_kurtar(IMG, None, PROF, "s")
    assert not ev["ok"] and ev["neden"] == ILK_EV["neden"] and ev["tur"] == "kalite_kapisi", \
        f"ilk tanı yanlış adayın ret nedeniyle değişti: {ev['neden']}"
    k = ev["extra"]["kurtarma"]
    assert k["sonuc"] == "dogrulanamadi" and "secilen" not in k, k
    assert [(y["aday"], y["kararli"]) for y in k["yerel_adaylar"]] == [(1, True), (2, False)], k["yerel_adaylar"]
    assert "A2 YANLIŞ" in k["yerel_adaylar"][0]["sonuc"]
    print("1b) hiçbir aday kabul edilmedi -> ilk tanı korundu; denenen adaylar kayıtta:",
          [y["sonuc"] for y in k["yerel_adaylar"]])


def test_servis_onerisi_kararli_ret_ilk_taniyi_degistirmez():
    servis = gks.SahteServis([{"durum": "uygun", "kumas_kutusu": [0.70, 0.1, 0.95, 0.9]}])
    o = sahte_orc({"A2": (False, True, "ÖNERİ BÖLGESİ RET")}, servis=servis)
    o._evaluate_scene = lambda img, design, prof, label: {**ILK_EV, "extra": {"algilama": {}}}
    o._supheli_mi = lambda ev, prof: True
    with yama(bd, detect_candidates=lambda img, hint, en_fazla=4, **k: [], detect=lambda img, hint, **k: det(A2)):
        ev = o._degerlendir_kurtar(IMG, None, PROF, "s")
    assert ev["neden"] == ILK_EV["neden"], ev["neden"]
    k = ev["extra"]["kurtarma"]
    assert k["sonuc"] == "dogrulanamadi" and k["servis"]["yeniden_algilama"].startswith("ret: ÖNERİ") and k["servis"]["kararli"], k
    print("1c) görsel kontrol önerisi kararlı ret -> ilk tanı korundu:", k["servis"]["yeniden_algilama"])


# ---- 3) bütçe ------------------------------------------------------------------------------------------------------
def butce(t, en_fazla=5):
    return gks.Butce(SimpleNamespace(gorsel_kontrol_is_basina_en_fazla=en_fazla, gorsel_kontrol_gunluk_tavan_usd=5.0,
                                     gorsel_kontrol_modeli="claude-sonnet-5-5"), t)


def test_butce_hata_ve_bozuk_yanit_sayilir():
    tahmin = gks.tahmini_cagri_usd("claude-sonnet-5-5")
    with tempfile.TemporaryDirectory() as t:
        b = butce(t, en_fazla=2)
        s = gks.SahteServis([RuntimeError("görsel kontrol servisi HTTP 500"), "model düz metin döndürdü, JSON yok"])
        o = sahte_orc({}, servis=s, butce=b)
        with yama(bd, detect_candidates=lambda img, hint, en_fazla=4, **k: []):
            ev1, b1 = o._kurtar(IMG, None, PROF, "s", dict(ILK_EV))
            ev2, b2 = o._kurtar(IMG, None, PROF, "s", dict(ILK_EV))
            ev3, b3 = o._kurtar(IMG, None, PROF, "s", dict(ILK_EV))
        assert ev1 is None and b1["servis"]["durum"] == "hata", b1
        assert ev2 is None and b2["servis"]["durum"] == "gecersiz_yanit" and b2["servis"]["kullanim"]["input_tokens"], b2
        assert b.is_cagri == 2, f"hata/bozuk yanıt çağrı sayılmadı: {b.is_cagri}"
        gun = b._oku()[__import__("datetime").date.today().isoformat()]
        assert b2["servis"]["tahmini_usd"] > 0                          # gerçek kullanım (usage) yanıtla geldi
        beklenen = round(tahmin + b2["servis"]["tahmini_usd"], 5)        # istisna: tahmin; bozuk yanıt: kullanımdan
        assert gun["cagri"] == 2 and abs(gun["usd"] - beklenen) < 1e-6, (gun, beklenen)
        assert ev3 is None and b3["servis"]["durum"] == "butce" and s.cagri == 2, (b3, s.cagri)   # iş sınırı korunur
    print(f"3a) istisna + çözülemeyen yanıt sayıldı: 2 çağrı, {gun['usd']} $ (tahmin {tahmin:.4f} $); 3. çağrı bütçede durdu")


def test_claude_servis_bozuk_json_kullanim_doner():
    sahte = types.ModuleType("requests")
    sahte.cagri = []

    def post(url, json=None, timeout=None, headers=None):
        sahte.cagri.append(url)
        return SimpleNamespace(status_code=200, json=lambda: {
            "content": [{"type": "text", "text": "Üzgünüm, kumaşı göremiyorum."}],
            "usage": {"input_tokens": 3000, "output_tokens": 40}})
    sahte.post = post
    eski = sys.modules.get("requests")
    sys.modules["requests"] = sahte                                       # ağ yok: incele() içindeki import bunu alır
    try:
        res = gks.ClaudeServis("sahte-anahtar-yok").incele(IMG, [], 0.37)
    finally:
        if eski is not None:
            sys.modules["requests"] = eski
        else:
            sys.modules.pop("requests", None)
    assert res is not None and res.durum == gks.GECERSIZ, res
    assert res.kullanim == {"input_tokens": 3000, "output_tokens": 40} and abs(res.tahmini_usd - 0.0064) < 1e-9, res
    assert gks.harcanan_usd(res, 0.0126) == res.tahmini_usd and gks.harcanan_usd(None, 0.0126) == 0.0126
    assert len(sahte.cagri) == 1                                          # tek POST, kör yeniden deneme yok
    print("3b) ClaudeServis (sahte requests): JSON çözülemedi -> durum", res.durum, "kullanım", res.kullanim)


def test_servis_varsayilan_kapali():
    assert Settings().gorsel_kontrol_servisi == "kapali" and isinstance(gks.servis_olustur(Settings()), gks.KapaliServis)


# ---- 2) video yeniden yerleşim tutarlılığı --------------------------------------------------------------------------
def video_orc(t, info_sorunlar, entry_tk):
    orchestrator.STATS_PATH = os.path.join(t, "s.json")
    o = orchestrator.Orchestrator(Settings(max_video_tries=1), log=None, progress=None)
    o.loglar, o.ilerleme = [], []
    o.log = o.loglar.append
    o.progress = lambda f, m: o.ilerleme.append(m)
    job = os.path.join(t, "is")
    os.makedirs(os.path.join(job, "sahneler_bos"), exist_ok=True)
    os.makedirs(os.path.join(job, "foto"), exist_ok=True)
    blank = np.full((600, 600, 3), 90, np.uint8)
    blank[60:560, 230:370] = 225
    cv2.imwrite(os.path.join(job, "sahneler_bos", "s01.png"), blank)
    foto = blank.copy()
    foto[200:300, 250:350] = (20, 20, 20)                                  # "kayıtlı fotoğraf" (tasarım basılı)
    cv2.imwrite(os.path.join(job, "foto", "01_kumas.png"), foto)
    entry = {"ad": "01_kumas.png", "stem": "s01", "yerlesim_modu": "tam_kumas", "olcu_id": "75x200", "tam_kumas": entry_tk}
    rap = {"urun_profili": {"olcu_id": "75x200"}, "fotograflar": [entry]}
    o.report_of = lambda job_: rap
    o._design = lambda job_: np.zeros((2000, 750, 4), np.uint8)
    yeniden = []

    def comp(scene, design, d, profile, **kw):
        yeniden.append(scene.shape)
        out = np.full_like(scene, 7)                                       # güncel kurallarla "farklı" yerleşim
        info = {"sorunlar": info_sorunlar, "uyarilar": []}
        return (out, info, {"model": 1}) if kw.get("return_model") else (out, info)
    o._composite_for = comp
    return o, job, entry, foto, yeniden


def maske_det(img, hint=None, **k):
    H, W = img.shape[:2]
    m = np.zeros((H, W), bool)
    m[int(H * .1):int(H * .93), int(W * .38):int(W * .62)] = True
    return det(m)


def test_video_kaynagi_eski_kayitta_kayitli_foto():
    with tempfile.TemporaryDirectory() as t, yama(bd, detect=maske_det):
        o, job, entry, foto, yeniden = video_orc(t, [], {"dikey_olcek": "temas_cizgisine_kadar"})
        out = o._video_source(job, entry, foto)
        assert out is foto, "eski K-16 kaydında video kaynağı yeniden basıldı (fotoğrafla tutarsız)"
        assert any("temas çizgisine kadar" in m and "Kayıtlı fotoğraf kullanılıyor" in m for m in o.loglar), o.loglar
        o2, job2, entry2, foto2, _ = video_orc(t, [{"tur": "temas_belirsiz", "mesaj": "zemine temas belirsiz"}],
                                               {"dikey_olcek": "fiziksel"})
        out2 = o2._video_source(job2, entry2, foto2)
        assert out2 is foto2, "güncel yerleşim sorunluyken video kaynağı yeniden basıldı"
        assert any("zemine temas belirsiz" in m for m in o2.loglar), o2.loglar
        o3, job3, entry3, foto3, y3 = video_orc(t, [], {"dikey_olcek": "fiziksel"})
        out3 = o3._video_source(job3, entry3, foto3)
        assert out3 is not foto3 and out3.shape[0] > foto3.shape[0] and y3, "tutarlı durumda yüksek çözünürlük kaynağı yapılmadı"
    print("2a) kamera videosu: eski kayıt / sorunlu yeniden yerleşim -> kayıtlı fotoğraf; tutarlıda yeniden basım")


def test_ucretli_video_yolunda_gorunen_uyari():
    with tempfile.TemporaryDirectory() as t, yama(bd, detect=maske_det):
        o, job, entry, foto, _ = video_orc(t, [{"tur": "sahne_geometri", "mesaj": "asılı ≈150 cm"}], {"dikey_olcek": "fiziksel"})
        st = o._video_start(cv2.imread(os.path.join(job, "sahneler_bos", "s01.png")), None, profile=o._profile(
            {"urun_profili": {"olcu_id": "75x200"}}), entry=entry)
        assert st["uyari"] and "asılı ≈150 cm" in st["uyari"][0], st.get("uyari")
        # generate_video: sahte video sağlayıcı + sahte onarım (ağ yok, ücret yok)
        o.arms_override = {"video": ["mock_video"]}
        gonderilen = []
        saglayici = SimpleNamespace(video=lambda jpg, prompt, sec, seed=None, **k: gonderilen.append(len(jpg)) or b"mp4")
        def onarim(ai, out, ref, blank, design, model, size, progress=None):
            open(out, "wb").write(b"mp4")
            return {"ok": True, "reasons": [], "ncc_mean": 0.9, "frames": 3}, []
        with yama(orchestrator, make_video_provider=lambda s, log, name=None: saglayici), \
                yama(orchestrator.vr, repair_video=onarim):
            res = o.generate_video(job, "01_kumas.png")
        assert gonderilen and res.get("uyari") and "asılı ≈150 cm" in res["uyari"][0], res
        assert any(m.startswith("UYARI (video)") for m in o.loglar), o.loglar
        assert any(m.startswith("UYARI:") for m in o.ilerleme), o.ilerleme
        o2, job2, entry2, _, _ = video_orc(t, [], {"dikey_olcek": "fiziksel"})
        st2 = o2._video_start(cv2.imread(os.path.join(job2, "sahneler_bos", "s01.png")), None,
                              profile=o2._profile({"urun_profili": {"olcu_id": "75x200"}}), entry=entry2)
        assert st2["uyari"] == [], st2["uyari"]
    print("2b) ücretli video yolu: tutarsızlık uyarısı günlükte, ilerlemede ve video kaydında:", res["uyari"][0][:80], "...")


if __name__ == "__main__":
    hatalar = []
    for ad, f in list(globals().items()):
        if ad.startswith("test_") and callable(f):
            try:
                f()
                print("geçti:", ad)
            except Exception as e:                      # bütün testler çalışsın; hangi düzeltmenin eksik olduğu görünsün
                hatalar.append(ad)
                print(f"BAŞARISIZ: {ad}: {e.__class__.__name__}: {str(e)[:300]}")
    if hatalar:
        print("BAŞARISIZ testler:", ", ".join(hatalar))
        sys.exit(1)
    print("TAMAM")
