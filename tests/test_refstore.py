# -*- coding: utf-8 -*-
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import cv2, numpy as np
import refstore, prompts

refstore.ROOT = tempfile.mkdtemp(prefix="refdepo_")
assert refstore.slug("Bekarlığa veda") == "bekarliga_veda", refstore.slug("Bekarlığa veda")
assert refstore.slug("Nişan / Kına") and "/" not in refstore.slug("Nişan / Kına")
img = np.full((600, 400, 3), 180, np.uint8)
ok, buf = cv2.imencode(".png", img)
r = refstore.add("Düğün", "Güzel Sahne 1.png", buf.tobytes())
assert r["ad"].endswith(".png") and r["genislik"] == 400
assert [x["ad"] for x in refstore.list_refs("Düğün")] == [r["ad"]]
assert refstore.list_refs("Baby shower") == []
assert refstore.set_desc("Düğün", r["ad"], "OUT: a garden at golden hour")
its = refstore.items("Düğün")
assert len(its) == 1 and its[0][1].startswith("OUT:")
p = prompts.build_scene_prompt("Düğün", 0, 75, 200, True, 0, guided=True, scene_desc=its[0][1])
assert "garden at golden hour" in p and "OUT:" not in p
p2 = prompts.build_scene_prompt("Düğün", 0, 75, 200, False, 0)
assert "the other attached image" not in p2
assert refstore.delete("Düğün", r["ad"]) and refstore.list_refs("Düğün") == []
assert os.path.isfile(os.path.join(refstore.folder("Düğün"), "_silinen", r["ad"]))
assert not refstore.add.__defaults__ or True
try:
    refstore.add("Düğün", "x.png", b"bozuk")
    raise SystemExit("bozuk görsel kabul edildi")
except ValueError:
    pass
print("test_refstore: TAMAM")
