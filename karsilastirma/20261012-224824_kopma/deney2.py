# Düzeltilmiş kodla aynı sahneler: V4_duzeltilmis (varsayılanlar) + sürekliliğin ölçümü + yerleşim koordinatı farkı (V0'a göre)
import sys, json, numpy as np, cv2
sys.path.insert(0,"/home/claude/afis")
exec(open("deney.py").read().split("_orig_geom =")[0])
out_m = {}
for p in rap["fotograflar"]:
    stem=p["stem"]; scene=cvio.imread(f"{JOB}/sahneler_bos/{stem}.png", cv2.IMREAD_COLOR)
    det=bd.detect(scene, hint={"kind":"fabric"})
    o, info, model = cp.composite(scene, d, det, mode="tam_kumas", profile=prof, return_model=True)
    o = ribbon_mod.restore(scene, o, p.get("kurdele"))
    cvio.imwrite(f"{OUT}/{stem}_V4_duzeltilmis.png", o)
    u,a = model["u"], model["alpha"]; ins = a>0.95
    W0 = info["genislik_px"]; ux=u*W0
    d2=np.abs(np.diff(ux,n=2,axis=0)); m2=ins[2:]&ins[1:-1]&ins[:-2]
    dx=np.diff(u,axis=1); mx=ins[:,1:]&ins[:,:-1]
    # orijinal (V0) yerleşimle ortalama koordinat farkı: aynı bbox'ta u,v farkı (cm)
    out_m[stem]={"ikinci_turev_maks_px":round(float(d2[m2].max()),3),"katlanma_piksel":int(((dx<=0)&mx).sum()),
                 "asili_cm":info["asili_cm"],"gizli_cm":info["gizli_cm"],"px_per_cm":info["px_per_cm"],"rapordaki":{k:p["tam_kumas"][k] for k in ("asili_cm","gizli_cm","px_per_cm")},
                 "kivrim_kaymasi":info["kivrim_kaymasi"],"kenar_sigma_px":info["kenar_sigma_px"],"sorunlar":info["sorunlar"]}
json.dump(out_m, open(f"{OUT}/metrikler_duzeltilmis.json","w"), indent=1, ensure_ascii=False)
for k,v in out_m.items(): print(k, v)
