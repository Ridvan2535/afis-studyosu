# -*- coding: utf-8 -*-
"""Magnific (veya başka bir sitede) elle model denemesi için paket hazırlar:
kılavuz görsel + her sahne için hazır prompt + kısa talimat. Kullanım: test_paketi.bat"""
import io
import os
import sys
import time
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import guide as guide_mod
import prompts

SIZES = {"50x100": (50, 100), "50x150": (50, 150), "75x200": (75, 200), "150x300": (150, 300), "150x400": (150, 400)}


def build(category="Düğün", size="75x200", n=3, out_dir=None):
    aw, ah = SIZES[size]
    out_dir = out_dir or os.path.join(HERE, "isler", time.strftime("%Y%m%d-%H%M%S") + "_test_paketi")
    os.makedirs(out_dir, exist_ok=True)
    png, _ = guide_mod.make_guide(9 / 16, aw / ah)
    with open(os.path.join(out_dir, "kilavuz.png"), "wb") as f:
        f.write(png)
    lines = []
    for i in range(n):
        p = prompts.build_scene_prompt(category, i, aw, ah, False, 0, guided=True, people=prompts.default_people(category))
        with open(os.path.join(out_dir, f"prompt_{i + 1}.txt"), "w", encoding="utf-8") as f:
            f.write(p)
        lines.append(f"- prompt_{i + 1}.txt")
    # rakip / örnek fotoğraf ile kullanım için iki varyant
    base = prompts.build_scene_prompt(category, 0, aw, ah, False, 0, guided=False, people=prompts.default_people(category))
    head_a = ("Image 1 is a photo of a hanging fabric banner at a real event. Recreate THE SAME photograph: keep the composition, camera angle, "
              "banner position, size and proportions, the venue, people and lighting. Change ONE thing: the banner must be completely BLANK cream "
              "raw canvas. Remove all printing, artwork, text, lettering, logos, brand marks and watermarks from the banner and from the whole image; "
              "leave no ghost of the old design. Keep the real fabric folds, grommets, ribbons and the floor-length hem resting on the ground. ")
    with open(os.path.join(out_dir, "prompt_rakip_A_ayni_sahne.txt"), "w", encoding="utf-8") as f:
        f.write(head_a)
    with open(os.path.join(out_dir, "prompt_rakip_B_yeni_sahne.txt"), "w", encoding="utf-8") as f:
        f.write(base + prompts.REFERENCE_NOTE)
    readme = f"""TEST PAKETİ ({category}, {size} cm)

1) Magnific sitesinde görsel üretme (image) bölümünü aç. Modeli seç: GPT 2, Nano Banana 2, Seedream 5 Pro (sırayla).
2) "Referans / görsel ekle" ile kilavuz.png dosyasını yükle. En-boy oranı: 9:16 (dikey).
3) prompt_1.txt içindeki yazıyı komple kopyalayıp prompt kutusuna yapıştır, üret.
4) Aynısını her model için prompt_1, prompt_2, prompt_3 ile tekrarla ({', '.join(l[2:] for l in lines)}).
5) Sonuçları şöyle adlandır: gpt_1.png, nano_1.png, seedream5_1.png ... ve bana gönder.
RAKİP / ÖRNEK FOTOĞRAFLA DENEME (kilavuz.png yerine):
 - prompt_rakip_A_ayni_sahne.txt : örnek fotoğrafı yükle, aynı sahneyi BOŞ afişle yeniden yapar (kadrajı birebir korur).
 - prompt_rakip_B_yeni_sahne.txt : örnek fotoğrafı yükle, benzer yapıda ama YENİ bir sahne üretir (afiş boş).
 Önemli: rakip görselindeki tasarım/logo kopyalanmamalı; sonuçta afiş boş olmalı. Satışta kullanmadan önce rakip fotoğrafının kendisini değil sonucu kullan.

Not: Bu sahnelerde afiş BOŞ çıkmalı. Tasarımı program sonra yerleştirir.
"""
    with open(os.path.join(out_dir, "OKU.txt"), "w", encoding="utf-8") as f:
        f.write(readme)
    zp = out_dir + ".zip"
    with zipfile.ZipFile(zp, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in os.listdir(out_dir):
            z.write(os.path.join(out_dir, fn), fn)
    return out_dir


if __name__ == "__main__":
    cat = sys.argv[1] if len(sys.argv) > 1 else "Düğün"
    size = sys.argv[2] if len(sys.argv) > 2 else "75x200"
    d = build(cat, size)
    print("Hazır:", d)
