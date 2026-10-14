import cv2, numpy as np, os
O="sonuc"
regs={"s02":{"y_kuyrugu":(1180,1340,1380,1520),"BABY_SHOWER":(840,1500,1600,1620)},
      "s01":{"WELCOME":(780,470,1650,700),"ayicik":(1000,820,1450,1250),"alt_BABY":(1100,2050,1340,2170)}}
for stem,rr in regs.items():
    for nm,(x0,y0,x1,y1) in rr.items():
        tiles=[]
        for v in ["V0_mevcut","V1_fold0","V2_kenar_duz","V3_kurdele_yok"]:
            im=cv2.imread(f"{O}/{stem}_{v}.png")[y0:y1,x0:x1]
            s=min(2.0, 900/(x1-x0)); im=cv2.resize(im,None,fx=s,fy=s,interpolation=cv2.INTER_CUBIC)
            cv2.rectangle(im,(0,0),(260,30),(255,255,255),-1); cv2.putText(im,v,(5,22),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,200),2)
            tiles.append(im)
        cv2.imwrite(f"{O}/yakin_{stem}_{nm}.png", np.vstack(tiles))
print(sorted(os.listdir(O)))
