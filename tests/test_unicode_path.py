"""
Windows'ta OpenCV, adında Türkçe karakter (ü, ş, ı...) olan klasörlerdeki dosyaları (ör. ...\\Masaüstü\\...) okuyup
yazamaz. Bu sınama OpenCV'nin dosya yolu işlevlerini ASCII dışı yolda BAŞARISIZ olacak şekilde değiştirir
(Windows davranışını taklit eder) ve bütün akışı Türkçe karakterli bir klasörde çalıştırır.
Çalıştır:  python tests/test_unicode_path.py
"""
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
os.environ.setdefault("MOCK_FRAMES", "12")

import cv2  # noqa: E402

bad_calls = []


def _ascii(p):
    try:
        return isinstance(p, str) and p.isascii()
    except Exception:
        return True


_imread, _imwrite, _VC, _VW = cv2.imread, cv2.imwrite, cv2.VideoCapture, cv2.VideoWriter


def imread(path, *a, **k):
    if not _ascii(path):
        bad_calls.append(("imread", path)); return None
    return _imread(path, *a, **k)


def imwrite(path, *a, **k):
    if not _ascii(path):
        bad_calls.append(("imwrite", path)); return False
    return _imwrite(path, *a, **k)


def VC(path, *a, **k):
    if not _ascii(path):
        bad_calls.append(("VideoCapture", path)); return _VC("/yok/yok.mp4")
    return _VC(path, *a, **k)


def VW(path, *a, **k):
    if not _ascii(path):
        bad_calls.append(("VideoWriter", path)); return _VW("/yok/yok.mp4", *a, **k)
    return _VW(path, *a, **k)


cv2.imread, cv2.imwrite, cv2.VideoCapture, cv2.VideoWriter = imread, imwrite, VC, VW

import orchestrator as orch          # noqa: E402
from providers import Settings        # noqa: E402

base = os.path.join(tempfile.mkdtemp(prefix="afis_u_"), "Masaüstü", "afiş_stüdyosu")
os.makedirs(base)
orch.JOBS_DIR = os.path.join(base, "işler")
orch.REPORT_DIR = os.path.join(base, "raporlar")
orch.LOG_PATH = os.path.join(base, "kayıt.log")
design = os.path.join(base, "tasarım.jpg")
shutil.copy(os.path.join(ROOT, "design_candy.jpg"), design)

s = Settings(scene_provider="mock", video_provider="mock", photo_long_side=1200, seconds=2, auto_video=False, max_video_tries=1)
o = orch.Orchestrator(s, log=lambda m: None, progress=lambda f, t: None)
job = o.new_job(design, "Doğum günü / Baby shower", "türkçe")
res = o.generate_photos(job, 3)
print("fotoğraf:", res)
assert res["uretilen"] == 3, "Türkçe karakterli klasörde fotoğraf üretilemedi"
rap = o.report_of(job)
pick = rap["fotograflar"][0]["ad"]
v = o.generate_video(job, pick)
print("video:", v["kontrol_gecti"], v["dosya"])
final = os.path.join(job, v["dosya"])
assert os.path.getsize(final) > 10_000
frames, fps = __import__("video_repair").read_video(final)
assert len(frames) >= 10, f"final video okunamadı ({len(frames)} kare)"
o.make_report(job)
assert not bad_calls, f"ASCII dışı yola OpenCV çağrısı yapıldı: {bad_calls[:3]}"
print("TAMAM: Türkçe karakterli klasörde bütün akış çalıştı;", base)
