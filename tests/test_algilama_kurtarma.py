"""K-49 algılama kurtarma + görsel kontrol servisi (SAHTE servis; ağ yok, ücret yok).

1) İş 054333 kalıcı regresyonu: kumaş krem halıyla birleşip skor 0 alıyordu, koyu duvar boşluğu seçiliyordu.
   Kutular örneğe özel ALGORİTMA değil, yalnız test ölçütüdür (elle işaretlenen bölgeler).
2) sade_neden: algılama hatası "afişte yazı/desen var" diye gösterilmez.
3) _kurtar: yerel aday sırası, servis kapalıyken baskı yok, "uygun" deyip kutu vermeyen yanıt baskıya yol açmaz,
   önerilen kutuyla tutarsız maske reddedilir, tutarlı öneri bütün kontrollerden geçerse kabul edilir, bütçe sınırları.
"""
import os
import sys
import tempfile
from types import SimpleNamespace

import cv2
import numpy as np

KOK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, KOK)
import banner_detect as bd          # noqa: E402
import deneme_kayit                  # noqa: E402
import gorsel_kontrol_servisi as gks  # noqa: E402
import orchestrator                  # noqa: E402

ORNEK = os.path.join(KOK, "tests", "kontrol_ornekleri", "is_054333", "ham.jpg")


def oran(m, kutu):
    h, w = m.shape
    x0, x1, y0, y1 = kutu
    return m[int(y0 * h):int(y1 * h), int(x0 * w):int(x1 * w)].sum() / max(m.sum(), 1)


def test_054333_kumas_secilir():
    img = cv2.imread(ORNEK)
    d = bd.detect(img, {"kind": "fabric"})
    m = d.mask > 0
    assert m.any(), "maske boş"
    assert oran(m, (0.32, 0.69, 0.12, 0.95)) > 0.95, "maske merkezdeki kumaş bölgesinde değil"
    assert oran(m, (0.19, 0.29, 0.20, 0.73)) < 0.01, "soldaki koyu duvar boşluğu seçildi"
    L = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)[..., 0][m].mean()
    assert L > 150, f"seçilen bölge koyu ({L:.0f})"
    assert 0.15 < m.mean() < 0.35, "maske halıya/zemine taştı"


def test_sade_neden_algilama_ayri():
    s = deneme_kayit.sade_neden({"tur": "kalite_kapisi", "neden": "bulunan bölge açık renkli/nötr değil (açıklık 32)"})
    assert "algılama" in s.lower() and "desen olduğu anlamına gelmez" in s, s
    s2 = deneme_kayit.sade_neden({"tur": "kalite_kapisi", "neden": "güvenilir afiş bölgesi bulunamadı"})
    assert "algılama" in s2.lower() and "yazı/desen var" not in s2.lower(), s2
    s3 = deneme_kayit.sade_neden({"tur": "kalite_kapisi", "neden": "afiş boş görünmüyor: yazı/desen benzeri detay var"})
    assert "desen" in s3.lower(), s3


# ---- _kurtar: sahte orkestratör, sahte servis --------------------------------------------------------------
def det(mask, ok=True):
    return bd.Detection(mask=mask.astype(np.uint8) * 255, kind="fabric", metrics={"lightness": 200, "area_ratio": 0.2},
                        reject=[] if ok else ["red"])


def kutu_maske(x0, y0, x1, y1, H=200, W=200):
    m = np.zeros((H, W), bool)
    m[int(y0 * H):int(y1 * H), int(x0 * W):int(x1 * W)] = True
    return m


def sahte_orc(servis=None, butce=None, dogrulayan=None):
    o = object.__new__(orchestrator.Orchestrator)
    o.log = lambda *a, **k: None
    o.gk_servis = servis or gks.KapaliServis()
    o.gk_butce = butce
    o.cagrilar = []

    def aday(img, design, prof, label, d, hint):
        o.cagrilar.append(hint)
        ok = dogrulayan(d) if dogrulayan else True
        return {"ok": ok, "neden": "" if ok else "ret", "tur": "kabul" if ok else "sahne_geometri"}, True
    o._aday_degerlendir = aday
    return o


PROF = SimpleNamespace(oran=0.37, boy_cm=180)
IMG = np.full((200, 200, 3), 120, np.uint8)
YANLIS = kutu_maske(0.05, 0.1, 0.15, 0.7)
DOGRU = kutu_maske(0.35, 0.1, 0.65, 0.9)


def yama(adaylar, yeniden=None):
    bd.detect_candidates = lambda img, hint, en_fazla=4, **k: adaylar
    if yeniden is not None:
        bd.detect = lambda img, hint, **k: yeniden


def test_yerel_aday_ilk_yanlisi_atlar():
    yama([det(YANLIS), det(DOGRU)])
    o = sahte_orc()
    ev, bilgi = o._kurtar(IMG, None, PROF, "s", {"det": det(YANLIS)})
    assert ev is not None and bilgi["sonuc"] == "yerel_aday_kabul" and bilgi["secilen"]["aday"] == 2
    assert len(o.cagrilar) == 1 and abs(o.cagrilar[0]["point"][0] - 0.5) < 0.02


def test_servis_kapali_baski_yok():
    yama([det(YANLIS)])
    ev, bilgi = sahte_orc()._kurtar(IMG, None, PROF, "s", {"det": det(YANLIS)})
    assert ev is None and bilgi["servis"]["durum"] == "kapali" and bilgi["sonuc"] == "dogrulanamadi"


def test_uygun_ama_kutu_yok_baski_yok():
    yama([det(YANLIS)], yeniden=det(DOGRU))
    s = gks.SahteServis([{"durum": "uygun", "kumas_kutusu": None}])
    o = sahte_orc(servis=s)
    ev, bilgi = o._kurtar(IMG, None, PROF, "s", {"det": det(YANLIS)})
    assert ev is None and s.cagri == 1 and o.cagrilar == [], "kutusuz 'uygun' yanıtıyla değerlendirme/baskı yapıldı"


def test_tutarsiz_maske_reddedilir():
    yama([det(YANLIS)], yeniden=det(YANLIS))          # öneri ortada, yeniden algılama yine solu buluyor
    s = gks.SahteServis([{"durum": "uygun", "kumas_kutusu": [0.33, 0.08, 0.67, 0.92]}])
    o = sahte_orc(servis=s)
    ev, bilgi = o._kurtar(IMG, None, PROF, "s", {"det": det(YANLIS)})
    assert ev is None and "tutarsız" in bilgi["servis"]["yeniden_algilama"] and o.cagrilar == []


def test_tutarli_oneri_kontrollerden_gecer():
    yama([det(YANLIS)], yeniden=det(DOGRU))
    s = gks.SahteServis([{"durum": "inceleme_gerekli", "kumas_kutusu": [0.33, 0.08, 0.67, 0.92]}])
    o = sahte_orc(servis=s)
    ev, bilgi = o._kurtar(IMG, None, PROF, "s", {"det": det(YANLIS)})
    assert ev is not None and bilgi["sonuc"] == "servis_onerisi_kabul" and o.cagrilar == [{"box": [0.33, 0.08, 0.67, 0.92]}]
    # öneri doğru bölgede ama sahne yine kontrolden geçmiyorsa: kabul DEĞİL, doğru bölgede ret
    yama([det(YANLIS)], yeniden=det(DOGRU))
    o2 = sahte_orc(servis=gks.SahteServis([{"durum": "uygun", "kumas_kutusu": [0.33, 0.08, 0.67, 0.92]}]),
                   dogrulayan=lambda d: False)
    ev2, bilgi2 = o2._kurtar(IMG, None, PROF, "s", {"det": det(YANLIS)})
    assert ev2 is not None and not ev2["ok"] and bilgi2["sonuc"] == "servis_onerisi_dogru_bolge_ret"


def test_butce_sinirlari():
    with tempfile.TemporaryDirectory() as t:
        st = SimpleNamespace(gorsel_kontrol_is_basina_en_fazla=1, gorsel_kontrol_gunluk_tavan_usd=0.5,
                             gorsel_kontrol_modeli="claude-sonnet-5-5")
        b = gks.Butce(st, t)
        assert b.izin()[0]
        b.kaydet(0.01)
        ok, neden = b.izin()
        assert not ok and "iş başına" in neden
        st2 = SimpleNamespace(gorsel_kontrol_is_basina_en_fazla=9, gorsel_kontrol_gunluk_tavan_usd=0.02,
                              gorsel_kontrol_modeli="claude-sonnet-5-5")
        b2 = gks.Butce(st2, t)                      # aynı gün dosyası: 0.01 harcandı, tahmin ~0.013 -> tavan aşılır
        ok2, neden2 = b2.izin()
        assert not ok2 and "günlük" in neden2
        # bütçe doluysa servis çağrılmaz
        yama([det(YANLIS)])
        s = gks.SahteServis([{"durum": "uygun", "kumas_kutusu": [0.3, 0.1, 0.7, 0.9]}])
        ev, bilgi = sahte_orc(servis=s, butce=b)._kurtar(IMG, None, PROF, "s", {"det": det(YANLIS)})
        assert ev is None and s.cagri == 0 and bilgi["servis"]["durum"] == "butce"


def test_yanit_coz_dogrular():
    assert gks.yanit_coz("bozuk") is None
    assert gks.yanit_coz('{"durum":"harika"}') is None
    r = gks.yanit_coz('x {"durum":"uygun","kumas_kutusu":[0.3,0.1,0.7,1.4],"aday_no":2} y')
    assert r.durum == "uygun" and r.kumas_kutusu == [0.3, 0.1, 0.7, 1.0] and r.aday_no == 2
    assert gks.yanit_coz('{"durum":"uygun","kumas_kutusu":[0.3,0.1,0.31,0.9]}').kumas_kutusu is None


def test_varsayilan_kapali_ve_anahtar_gizli():
    import providers
    s = providers.Settings()
    assert s.gorsel_kontrol_servisi == "kapali"
    assert isinstance(gks.servis_olustur(s), gks.KapaliServis)
    s.anthropic_key = "sk-ant-GIZLI-123456"
    assert "GIZLI" not in str(s.public())


if __name__ == "__main__":
    asil = (bd.detect_candidates, bd.detect)
    for ad, f in list(globals().items()):
        if ad.startswith("test_") and callable(f):
            f()
            bd.detect_candidates, bd.detect = asil
            print("geçti:", ad)
    print("TAMAM")
