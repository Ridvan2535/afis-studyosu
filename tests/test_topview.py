# -*- coding: utf-8 -*-
"""TopView sağlayıcısı: sahte HTTP ile akış (yükleme -> gönder -> sorgula -> indir)."""
import os, sys
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, HERE)
import providers as P

calls = []
class R:
    def __init__(s, j=None, code=200, content=b""):
        s._j, s.status_code, s.content, s.text = j, code, content, ""
    def json(s): return s._j

def fake_http(method, url, **kw):
    calls.append((method, url.replace(P.TopViewVideo.BASE, ""), kw.get("params"), kw.get("json")))
    if "upload/credential" in url:
        return R({"code": "200", "result": {"fileId": "F1", "uploadUrl": "https://up/x"}})
    if "upload/check" in url:
        return R({"code": "200", "result": "true"})
    if url.endswith("/task/submit"):
        return R({"code": "200", "result": {"taskId": "T1", "status": "init"}})
    if url.endswith("/task/query"):
        n = sum(1 for c in calls if c[1].endswith("/task/query"))
        if n < 2:
            return R({"code": "200", "result": {"status": "running"}})
        return R({"code": "200", "result": {"status": "success", "videos": [{"filePath": "https://cdn/v.mp4"}]}})
    raise AssertionError(url)

P._http = fake_http
P.requests.put = lambda url, data=None, timeout=0: R(code=200)
P._download = lambda url: b"VIDEO"
P.time.sleep = lambda s: None
s = P.Settings(); s.topview_key, s.topview_uid = "k" * 12, "u1"
assert P.available_video(s) == list(P.TOPVIEW_ORDER)
pv = P.make_video_provider(s, name="tv-veo")
assert pv.video(b"jpg", "move", seconds=7) == b"VIDEO"
sub = next(c for c in calls if c[1].endswith("/task/submit"))
assert sub[3]["model"] == "Veo 3.1" and sub[3]["firstFrameFileId"] == "F1" and sub[3]["duration"] in (6, 8), sub
try:
    P.TopViewVideo("", "")
    raise SystemExit("anahtarsız TopView reddedilmeliydi")
except P.AuthError:
    pass
print("test_topview: TAMAM")
