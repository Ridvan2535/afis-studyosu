"""
Çoklu sahne akışı:  tasarım + sahne klasörü -> N adet gerçekçi mockup + kontrol raporu.

  python pipeline.py --design tasarim.png --scenes sahneler/ --out cikti/ [--n 6] [--backend auto]

Her sahne için:
  1) afiş otomatik bulunur (banner_detect), sert/kumaş ayrılır
  2) kalite kapısı: bulunamayan, kadraja taşan, boş olmayan, en-boy uyumsuz sahneler elenir
  3) geçerli sahnelere tasarım yerleştirilir (compositor)
N adet geçerli sahne dolunca durur. Kaç sahne eksik kaldığı raporlanır (yeni sahne üretilmeli).

Sahne yanına sahne.json koyarak ipucu verebilirsin:  {"point":[0.5,0.55]}  {"kind":"fabric"}  {"polygon":[[x,y],...]}
"""
import argparse
import json
import os
import sys

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

import banner_detect as bd
import compositor as cp
import cvio

EXT = (".jpg", ".jpeg", ".png", ".webp")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def contact_sheet(items, path, cols=3, cw=520, ch=640):
    """Her görsel sabit boyutlu bir hücreye sığdırılır (oran korunur)."""
    if not items:
        return
    font = ImageFont.truetype(FONT, 22) if os.path.exists(FONT) else ImageFont.load_default()
    rows = (len(items) + cols - 1) // cols
    gap, cap = 18, 40
    sheet = Image.new("RGB", (cols * (cw + gap) + gap, rows * (ch + cap + gap) + gap), (250, 250, 250))
    d = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(items):
        im = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
        f = min(cw / im.width, ch / im.height)
        im = im.resize((max(1, int(im.width * f)), max(1, int(im.height * f))), Image.LANCZOS)
        x0 = gap + (i % cols) * (cw + gap)
        y0 = gap + (i // cols) * (ch + cap + gap)
        sheet.paste(im, (x0 + (cw - im.width) // 2, y0 + cap + (ch - im.height) // 2))
        d.text((x0, y0 + 6), f"{i + 1}. {name}", fill=(40, 40, 40), font=font)
    sheet.save(path, quality=92)


def run(design_path, scenes_dir, out_dir, n=6, backend="auto"):
    os.makedirs(os.path.join(out_dir, "debug"), exist_ok=True)
    design = cp.load_design(design_path)
    files = sorted(f for f in os.listdir(scenes_dir) if f.lower().endswith(EXT))
    report, done = [], []
    for f in files:
        if len(done) >= n:
            report.append({"scene": f, "status": "atlandı", "reason": f"{n} geçerli sahne tamamlandı"})
            continue
        path = os.path.join(scenes_dir, f)
        img = cvio.imread(path)
        if img is None:
            report.append({"scene": f, "status": "elendi", "reason": "okunamadı"})
            continue
        det = bd.detect(img, bd.load_hint(path), backend)
        fit = cp.check_fit(det, design) if det.ok else None
        if fit:
            det.reject.append(fit)
        stem = os.path.splitext(f)[0]
        cvio.imwrite(os.path.join(out_dir, "debug", f"{stem}.jpg"), bd.overlay(img, det),
                    [cv2.IMWRITE_JPEG_QUALITY, 85])
        entry = {"scene": f, "kind": det.kind if det.ok else None, "backend": det.backend,
                 "metrics": {k: round(v, 3) for k, v in det.metrics.items() if isinstance(v, (int, float))},
                 "warn": det.warn}
        if not det.ok:
            entry.update(status="elendi", reason="; ".join(det.reject))
            report.append(entry)
            continue
        out, info = cp.composite(img, design, det, paper="auto")
        name = f"{len(done) + 1:02d}_{stem}.jpg"
        cvio.imwrite(os.path.join(out_dir, name), out, [cv2.IMWRITE_JPEG_QUALITY, 95])
        entry.update(status="hazır", output=name, placement=info)
        report.append(entry)
        done.append((stem, out))

    contact_sheet(done, os.path.join(out_dir, "_overview.jpg"))
    summary = {"hedef": n, "hazır": len(done), "eksik": max(0, n - len(done)), "sahneler": report}
    with open(os.path.join(out_dir, "report.json"), "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    return summary


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", required=True)
    ap.add_argument("--scenes", required=True)
    ap.add_argument("--out", default="cikti")
    ap.add_argument("--n", type=int, default=6)
    ap.add_argument("--backend", default="auto", choices=["auto", "classical", "sam2"])
    a = ap.parse_args()
    s = run(a.design, a.scenes, a.out, a.n, a.backend)
    print(f"Hedef {s['hedef']}, hazır {s['hazır']}, eksik {s['eksik']}")
    for e in s["sahneler"]:
        extra = e.get("output") or e.get("reason", "")
        w = f"  [uyarı: {', '.join(e['warn'])}]" if e.get("warn") else ""
        print(f"  {e['scene']:<24} {e['status']:<7} {e.get('kind') or '-':<7} {extra}{w}")
    if s["eksik"]:
        print(f"-> {s['eksik']} sahne daha gerekiyor (yeni sahne üretilmeli).")
