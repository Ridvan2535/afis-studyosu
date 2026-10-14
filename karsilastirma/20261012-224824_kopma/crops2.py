import cv2, numpy as np, sys, json
sys.path.insert(0,"/home/claude/afis")
O="sonuc"
regs={"s02":{"y_kuyrugu":(1180,1340,1380,1520),"BABY_SHOWER":(840,1500,1600,1620)},
      "s01":{"WELCOME":(780,470,1650,700),"ayicik":(1000,820,1450,1250),"alt_BABY":(1100,2050,1340,2170)}}
for stem,rr in regs.items():
    for nm,(x0,y0,x1,y1) in rr.items():
        tiles=[]
        for v,lab in [("V0_mevcut","ONCE (mevcut)"),("V4_duzeltilmis","SONRA (duzeltilmis)")]:
            im=cv2.imread(f"{O}/{stem}_{v}.png")[y0:y1,x0:x1]
            s=min(2.0, 900/(x1-x0)); im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_CUBIC)
            cv2.rectangle(im,(0,0),(300,30),(255,255,255),-1); cv2.putText(im,lab,(5,22),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,200),2)
            tiles.append(im)
        cv2.imwrite(f"{O}/once_sonra_{stem}_{nm}.png", np.vstack(tiles))
# yerleşim koordinatı farkı (kopma satırları dışında): u haritaları
import banner_detect as bd, compositor as cp, product, cvio
exec(open("deney.py").read().split("_orig_geom =")[0])
for p in rap["fotograflar"]:
    stem=p["stem"]; sc=cvio.imread(f"{JOB}/sahneler_bos/{stem}.png", cv2.IMREAD_COLOR); det=bd.detect(sc, hint={"kind":"fabric"})
    _,i0,m0=cp.composite(sc,d,det,mode="tam_kumas",profile=prof,fold_shift=0.01,return_model=True)
    # eski kenar (ham) ile: yumuşatmayı geçici kapat
    keep=cp.KENAR_YUMUSATMA; cp.KENAR_YUMUSATMA=1e-9
    g_old=cp.fabric_geometry; 
    def raw(*a,**k):
        g=g_old(*a,**k); g["L"],g["R"]=g["L_ham"],g["R_ham"]; return g
    cp.fabric_geometry=raw
    _,ia,ma=cp.composite(sc,d,det,mode="tam_kumas",profile=prof,fold_shift=0.01,return_model=True)
    cp.fabric_geometry=g_old; cp.KENAR_YUMUSATMA=keep
    _,i1,m1=cp.composite(sc,d,det,mode="tam_kumas",profile=prof,return_model=True)
    X0=max(ma["bbox"][0],m1["bbox"][0]); Y0=max(ma["bbox"][1],m1["bbox"][1]); X1=min(ma["bbox"][2],m1["bbox"][2]); Y1=min(ma["bbox"][3],m1["bbox"][3])
    cut=lambda m,k: m[k][Y0-m["bbox"][1]:Y1-m["bbox"][1], X0-m["bbox"][0]:X1-m["bbox"][0]]
    a=(cut(ma,"alpha")>0.95)&(cut(m1,"alpha")>0.95)
    du=np.abs(cut(ma,"u")-cut(m1,"u"))[a]*i1["genislik_px"]; dv=np.abs(cut(ma,"v")-cut(m1,"v"))[a]
    print(stem,"eski->yeni yatay konum farki px: medyan",round(float(np.median(du)),2),"p95",round(float(np.percentile(du,95)),2),
          "| dikey v farki maks", round(float(dv.max()),5))
