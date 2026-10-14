# -*- coding: utf-8 -*-
"""Manuel sınır düzenleyicisi — GERÇEK TARAYICI etkileşim testi (K-55). Ağ yok, ücret yok, yeni üretim yok.

Uygulama (app.py) geçici bir kopya klasörde başlatılır; içine iş 053942'nin kayıtlı ham sahnesi + tasarımı konur.
Chromium (Playwright) ile: işi aç -> elenen kartında "manuel sınır" -> 4 nokta tıkla (biri yanlış, "son noktayı sil" ile
düzelt) -> Uygula -> yeni sonuç otomatik açılır -> foto kartını büyüt. Doğrulananlar:
  1. Önizleme KÜÇÜLTÜLMÜŞKEN (iki farklı pencere genişliği) tıklanan noktalar orijinal görsel oranına doğru aktarılır
     (sunucuya giden 0-1 oranları, beklenen noktadan en fazla 1 ekran pikseli sapar).
  2. Yeni sonuç ayrı işte; kaynak iş klasörü bayt bayt değişmez.
  3. Ürün çıktısında (foto/*.jpg) işaret çizgisi yok ve tanı yazıları yok: tasarım alanı dışındaki pikseller sahneyle aynı.
  4. Dört köşe modunda köşeler kumaşla örtüşmüyorsa baskı yapılmaz, açık uyarı gösterilir, foto/ boş kalır.
  5. "Elenen ham görüntüleri de dene" kutusu (ham görüntüsü olan işte görünür) varsayılan İŞARETSİZ; işaretsizken
     /api/yeniden_birlestir gövdesinde elenen_ham false, işaretlenince true gider (istek tarayıcıda yakalanır,
     sunucuya ulaşmaz: kaynak iş değişmez, yeni üretim yok).
Playwright yoksa test ATLANIR (Windows kurulumunda gerekmez). Çalıştır: python tests/test_manuel_sinir_tarayici.py
"""
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
KOK = os.path.dirname(HERE)
try:
    from playwright.sync_api import sync_playwright
except Exception:
    print("test_manuel_sinir_tarayici: ATLANDI (playwright yok)")
    sys.exit(0)
import cv2
import numpy as np

KAYNAK_IS = "20261013-053942_Baby-shower"
HAM = os.path.join(HERE, "kontrol_ornekleri", "is_053942", "ham.jpg")
MAN = json.load(open(os.path.join(HERE, "kontrol_ornekleri", "is_053942", "kontrol.json"), encoding="utf-8"))
CIKTI = os.environ.get("MANUEL_TEST_CIKTI")          # ekran görüntüleri (isteğe bağlı)


def md5_klasor(d):
    h = {}
    for r, _, fs in os.walk(d):
        for f in fs:
            p = os.path.join(r, f)
            h[os.path.relpath(p, d)] = hashlib.md5(open(p, "rb").read()).hexdigest()
    return h


def bos_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


def kur(tdir):
    app_dir = os.path.join(tdir, "afis")
    os.makedirs(app_dir)
    for f in os.listdir(KOK):
        if f.endswith((".py", ".html")):
            shutil.copy(os.path.join(KOK, f), app_dir)
    src = os.path.join(app_dir, "isler", KAYNAK_IS)
    os.makedirs(os.path.join(src, "sahneler_bos"))
    shutil.copy(HAM, os.path.join(src, "sahneler_bos", "elenen_01_01_ham.jpg"))
    rgba = np.zeros((2000, 750, 4), np.uint8)                 # test tasarımı: üst yazı + ALT yazı (v≈0,88-0,92)
    rgba[350:450, 150:600] = (30, 30, 30, 255)
    rgba[1760:1840, 200:550] = (30, 30, 30, 255)
    cv2.imwrite(os.path.join(src, "tasarim.png"), rgba)
    rap = {"kategori": "Baby shower", "urun_profili": {"olcu_id": "75x200"}, "fotograflar": [],
           "elenenler": [{"cagri": 1, "servis": "test", "tur": "kalite_kapisi", "neden": "test kaydı",
                          "ham_dosya": "sahneler_bos/elenen_01_01_ham.jpg"}]}
    json.dump(rap, open(os.path.join(src, "rapor.json"), "w", encoding="utf-8"), ensure_ascii=False)
    return app_dir, src


def ekran(page, ad):
    if CIKTI:
        os.makedirs(CIKTI, exist_ok=True)
        page.screenshot(path=os.path.join(CIKTI, ad), full_page=False)


def bekle_bitti(base, onceki, sure=600):
    t0 = time.time()
    while time.time() - t0 < sure:
        st = json.load(urllib.request.urlopen(base + "api/state"))
        if not st.get("running") and st.get("finished") != onceki:
            return st
        time.sleep(0.5)
    raise AssertionError("işlem bitmedi")


def tikla(page, fx, fy):
    b = page.locator("#msImg").bounding_box()
    page.mouse.click(b["x"] + fx * b["width"], b["y"] + fy * b["height"])
    return b


def elenen_ham_kutusu(br, base):
    page = br.new_page(viewport={"width": 1100, "height": 900})
    giden = []

    def yakala(route):
        giden.append(json.loads(route.request.post_data))
        route.fulfill(status=200, content_type="application/json", body='{"ok": true}')
    page.route("**/api/yeniden_birlestir", yakala)
    page.goto(base)
    page.wait_for_function("document.querySelector('#jobSel') && document.querySelector('#jobSel').options.length > 0")
    page.select_option("#jobSel", KAYNAK_IS)
    page.wait_for_selector("#elenenHam", state="visible", timeout=20000)
    assert page.is_visible("#btnRecomp"), "yeniden birleştir düğmesi görünmüyor"
    assert not page.is_checked("#elenenHam"), "'elenen ham' kutusu varsayılan olarak işaretli"
    ekran(page, "0_elenen_ham_kutusu.png")
    page.click("#btnRecomp")
    for _ in range(40):
        if giden:
            break
        page.wait_for_timeout(100)
    assert giden and giden[-1].get("elenen_ham") is False, f"işaretsiz kutuyla gövde: {giden}"
    page.check("#elenenHam")
    page.click("#btnRecomp")
    for _ in range(40):
        if len(giden) >= 2:
            break
        page.wait_for_timeout(100)
    assert len(giden) >= 2 and giden[-1].get("elenen_ham") is True, f"işaretli kutuyla gövde: {giden}"
    assert giden[-1].get("job") == KAYNAK_IS, giden[-1]
    page.close()
    print("elenen ham kutusu: varsayılan işaretsiz; gönderilen gövdeler", giden)


def calistir():
    tdir = tempfile.mkdtemp(prefix="manuel_tarayici_")
    app_dir, src = kur(tdir)
    once = md5_klasor(src)
    port = bos_port()
    env = dict(os.environ, AFIS_PORT=str(port))
    # PORT_RANGE'i bu test için tek porta indir (app.py değişmeden)
    boot = ("import sys, app; app.PORT_RANGE = range(%d, %d); sys.argv.append('--no-browser'); app.main()" % (port, port + 1))
    proc = subprocess.Popen([sys.executable, "-c", boot], cwd=app_dir, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    base = f"http://127.0.0.1:{port}/"
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(base + "api/state", timeout=1)
                break
            except Exception:
                time.sleep(0.3)
        with sync_playwright() as p:
            br = p.chromium.launch()
            elenen_ham_kutusu(br, base)                       # 5) önce: kaynak iş henüz el değmemişken
            sonuc = {}
            for genislik in (1280, 700):                       # iki farklı küçültme
                page = br.new_page(viewport={"width": genislik, "height": 900})
                giden = []
                page.on("request", lambda r: giden.append(json.loads(r.post_data)) if r.url.endswith("/api/manuel_sinir") else None)
                page.goto(base)
                page.wait_for_function("document.querySelector('#jobSel') && document.querySelector('#jobSel').options.length > 0")
                page.select_option("#jobSel", KAYNAK_IS)
                page.wait_for_selector("[data-ms]", timeout=20000)
                page.click("[data-ms]")
                page.wait_for_function("document.querySelector('#msImg').complete && document.querySelector('#msImg').naturalWidth > 0")
                nat = page.evaluate("[document.querySelector('#msImg').naturalWidth, document.querySelector('#msImg').clientWidth]")
                assert nat[1] < nat[0], f"önizleme küçültülmemiş: {nat}"
                u, a = MAN["elle_sinir"]["ust"], MAN["elle_sinir"]["alt"]
                hedef = [u[0], u[1], a[0], a[1]]
                tikla(page, *hedef[0])
                tikla(page, 0.80, 0.50)                       # YANLIŞ nokta (duvar)
                assert "2/4" in page.inner_text("#msDurum")
                page.click("#msGeri")                         # düzelt
                assert "1/4" in page.inner_text("#msDurum")
                for q in hedef[1:]:
                    b = tikla(page, *q)
                assert "4 nokta hazır" in page.inner_text("#msDurum")
                ekran(page, f"1_noktalar_{genislik}.png")
                onceki = json.load(urllib.request.urlopen(base + "api/state")).get("finished")
                page.click("#msUygula")
                st = bekle_bitti(base, onceki)
                assert giden, "istek gitmedi"
                g = giden[-1]
                tol = 1.0 / b["width"] + 1e-6                # en fazla 1 ekran pikseli
                for (gx, gy), (ex, ey) in zip(g["ust"] + g["alt"], hedef):
                    assert abs(gx - ex) <= tol and abs(gy - ey) <= 1.0 / b["height"] + 1e-6, (genislik, g, hedef)
                assert st["result"]["sonuc"] == "kabul", st["result"]
                yeni = st["result"]["job"]
                page.wait_for_function(f"document.querySelector('#jobSel').value === {json.dumps(yeni)}", timeout=20000)
                page.wait_for_selector("#photoGrid img, .pgrid img, [data-zoom]", timeout=20000)
                ekran(page, f"2_yeni_sonuc_{genislik}.png")
                zb = page.locator("button.zoom[data-zoom]").first
                zb.click()
                page.wait_for_selector("#lb.on")
                ekran(page, f"3_buyutulmus_{genislik}.png")
                sonuc[genislik] = (yeni, g)
                page.close()

            # 4) dört köşe modu, köşeler kumaşla örtüşmüyor -> baskı yok, açık uyarı
            page = br.new_page(viewport={"width": 1000, "height": 900})
            page.goto(base)
            page.wait_for_function("document.querySelector('#jobSel') && document.querySelector('#jobSel').options.length > 1")
            page.select_option("#jobSel", KAYNAK_IS)
            page.wait_for_selector("[data-ms]", timeout=20000)
            page.click("[data-ms]")
            page.wait_for_function("document.querySelector('#msImg').complete && document.querySelector('#msImg').naturalWidth > 0")
            page.check("input[name=msMod][value=kose]")
            for q in ((0.60, 0.20), (0.95, 0.20), (0.95, 0.90), (0.60, 0.90)):     # duvar/kemer bölgesi
                tikla(page, *q)
            onceki = json.load(urllib.request.urlopen(base + "api/state")).get("finished")
            page.click("#msUygula")
            st = bekle_bitti(base, onceki)
            assert st["result"]["sonuc"] == "inceleme" and st["result"]["tur"] == "manuel_maske_zayif", st["result"]
            page.wait_for_function("document.querySelector('#toast') && document.querySelector('#toast').textContent.includes('UYGULANMADI')",
                                   timeout=20000)
            ekran(page, "4_kose_zayif_uyari.png")
            kose_is = st["result"]["job"]
            br.close()
    finally:
        proc.terminate()
        proc.wait(10)

    # 2) kaynak korunur, sonuçlar ayrı işlerde
    assert md5_klasor(src) == once, "kaynak iş değişti"
    isler = os.path.join(app_dir, "isler")
    for genislik, (yeni, g) in sonuc.items():
        assert yeni != KAYNAK_IS and os.path.isdir(os.path.join(isler, yeni)) and "manuel_" in yeni
        rap = json.load(open(os.path.join(isler, yeni, "rapor.json"), encoding="utf-8"))
        ph = rap["fotograflar"][0]
        assert ph["tam_kumas"]["temas_yontemi"] == "manuel" and ph["tam_kumas"]["gorunen_murekkep"] >= 0.999
        # 3) ürün çıktısında işaret çizgisi / tanı yazısı yok
        out = cv2.imread(os.path.join(isler, yeni, "foto", ph["ad"])).astype(int)
        sc = cv2.imread(os.path.join(isler, yeni, "sahneler_bos", ph["stem"] + ".png")).astype(int)
        q = np.array(ph["tam_kumas"]["dortgen"], float)
        x0, y0 = [int(v) for v in q.min(0)]
        x1, y1 = [int(v) + 1 for v in q.max(0)]
        fark = np.abs(out - sc).max(2)
        dis = np.ones(fark.shape, bool)
        dis[max(0, y0 - 6):y1 + 6, max(0, x0 - 6):x1 + 6] = False
        assert np.percentile(fark[dis], 99.9) <= 12, "tasarım alanı dışında sahne değişmiş (işaret/yazı?)"
        kirmizi = (out[..., 2] > 200) & (out[..., 1] < 60) & (out[..., 0] < 60)
        assert kirmizi.sum() < 50, "ürün çıktısında kırmızı işaret çizgisi var"
        assert not any("TANI" in f for f in os.listdir(os.path.join(isler, yeni, "foto"))), "tanı görseli foto/ içinde"
        print(f"pencere {genislik}px: yeni iş {yeni}; gönderilen noktalar {g['ust'] + g['alt']}")
    assert not os.listdir(os.path.join(isler, kose_is, "foto")), "zayıf köşe modunda ürün çıktısı yazılmış"
    rk = json.load(open(os.path.join(isler, kose_is, "rapor.json"), encoding="utf-8"))
    assert rk["elenenler"][0]["tur"] == "manuel_maske_zayif" and not rk["fotograflar"]
    print("dört köşe (zayıf örtüşme): baskı yok, uyarı:", rk["elenenler"][0]["sade_neden"])
    shutil.rmtree(tdir, ignore_errors=True)
    print("test_manuel_sinir_tarayici: TAMAM")


if __name__ == "__main__":
    calistir()
