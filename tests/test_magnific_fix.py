# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import providers as P

calls = []
class R:
    def __init__(self, j): self._j = j
    def json(self): return self._j
def fake_http(method, url, **kw):
    calls.append((method, url, kw.get("json")))
    if method == "POST":
        return R({"data": {"task_id": "T1", "status": "CREATED"}})
    if url.endswith("kling-v2-6-pro/T1"):
        raise P.ProviderError("HTTP 404: Not found")
    return R({"data": {"status": "COMPLETED", "generated": ["http://x/y.png"]}})
P._http = fake_http
P._download = lambda u: b"IMG"
png = b"\x89PNG\r\n\x1a\n" + b"0" * 20

m = P.MagnificEdit("k", log=lambda *a: None, variant="magnific-edit-pro", poll_every=0)
m.scene("p", 9, 16, guide=png)
post = [c for c in calls if c[0] == "POST"][-1]
assert post[1].endswith("seedream-v5-pro-edit"), post[1]
assert post[2]["reference_images"][0].startswith("data:image/png;base64,"), post[2]["reference_images"][0][:30]

m4 = P.MagnificEdit("k", log=lambda *a: None, variant="magnific-edit", poll_every=0)
m4.scene("p", 9, 16, guide=png)
post = [c for c in calls if c[0] == "POST"][-1]
assert not post[2]["reference_images"][0].startswith("data:"), "4.5 Edit ham base64 kalmalı"

calls.clear()
v = P.Magnific("k", log=lambda *a: None, poll_every=0)
v.video(b"jpg", "p", model="kling-pro")
post = [c for c in calls if c[0] == "POST"][0]
assert post[1].endswith("/image-to-video/kling-v2-6-pro") and post[2]["aspect_ratio"] == "social_story_9_16", post
gets = [c[1] for c in calls if c[0] == "GET"]
assert gets[-1].endswith("kling-v2-6/T1"), gets
assert "runway-4-5" not in P.VIDEO_ORDER
print("OK magnific düzeltmeleri")
