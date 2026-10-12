"""
SADECE TEST İÇİN: boş sert afişli sentetik sahneler üretir.
Gerçek akışta sahneler fotoğraf ya da görsel modelinden gelir; bu betik pipeline'ı sınamak için var.
"""
import os
import sys

import cv2
import numpy as np

import cvio

rng = np.random.default_rng(7)


def wall(w, h, rgb, tex=1.5):
    base = np.ones((h, w, 3), np.float32) * np.array(rgb[::-1], np.float32)
    n = cv2.resize(rng.normal(0, 1, (h // 40 + 2, w // 40 + 2)).astype(np.float32), (w, h), interpolation=cv2.INTER_CUBIC)
    base *= (1 + 0.025 * n)[..., None]
    base += rng.normal(0, tex, (h, w, 1)).astype(np.float32)
    yy, xx = np.mgrid[0:h, 0:w]
    r = np.hypot((xx - w / 2) / w, (yy - h / 2) / h)
    return base * (1 - 0.35 * r ** 2)[..., None]


def poly_mask(h, w, pts):
    m = np.zeros((h, w), np.float32)
    cv2.fillPoly(m, [np.round(np.array(pts) * 16).astype(np.int32)], 1.0, lineType=cv2.LINE_AA, shift=4)
    return m


def add_poster(img, quad, paper_rgb, frame_rgb, frame_w, light=(0.12, 0.08), shadow=0.35):
    h, w = img.shape[:2]
    quad = np.array(quad, np.float32)
    c = quad.mean(0)
    if shadow:
        sh = cv2.GaussianBlur(poly_mask(h, w, quad + [12, 16]), (0, 0), 14) * shadow
        img *= (1 - sh)[..., None]
    outer = quad + (quad - c) / np.linalg.norm(quad - c, axis=1, keepdims=True) * frame_w * 1.41
    mo = poly_mask(h, w, outer)[..., None]
    fcol = np.array(frame_rgb[::-1], np.float32) * (1 + rng.normal(0, 0.015, (h, w, 1)))
    img[:] = img * (1 - mo) + fcol * mo
    mp = poly_mask(h, w, quad)[..., None]
    yy, xx = np.mgrid[0:h, 0:w]
    grad = 1 - light[0] * (xx - c[0]) / w - light[1] * (yy - c[1]) / h
    pcol = np.array(paper_rgb[::-1], np.float32) * grad[..., None] + rng.normal(0, 1.0, (h, w, 1))
    img[:] = img * (1 - mp) + pcol * mp


def save(img, path):
    cvio.imwrite(path, np.clip(img, 0, 255).astype(np.uint8), [cv2.IMWRITE_JPEG_QUALITY, 94])


def main(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    # A: adaçayı duvar, hafif perspektif, ahşap çerçeve, en-boy ~0.40
    img = wall(1200, 1700, (136, 158, 128))
    add_poster(img, [(400, 300), (810, 322), (800, 1322), (392, 1296)], (238, 235, 229), (150, 110, 70), 16)
    save(img, f"{out_dir}/A_sage_wall.jpg")
    # B: bej duvar, karşıdan, ince siyah çerçeve, en-boy ~0.40
    img = wall(1200, 1700, (222, 205, 182))
    add_poster(img, [(430, 330), (832, 330), (832, 1335), (430, 1335)], (240, 240, 238), (32, 32, 32), 9, light=(0.2, 0.05))
    save(img, f"{out_dir}/B_beige_studio.jpg")
    # C: koyu teal duvar, yatay kadraj, afiş sağda ve perspektifli
    img = wall(1700, 1200, (30, 70, 78))
    add_poster(img, [(930, 170), (1300, 215), (1280, 1120), (925, 1080)], (232, 230, 222), (190, 150, 70), 14, shadow=0.5)
    save(img, f"{out_dir}/C_teal_landscape.jpg")
    # D: en-boy uyumsuz (geniş afiş) -> en-boy kapısında elenmeli
    img = wall(1200, 1700, (190, 170, 160))
    add_poster(img, [(250, 500), (960, 505), (955, 1180), (245, 1175)], (235, 235, 235), (60, 50, 45), 12)
    save(img, f"{out_dir}/D_wide_mismatch.jpg")
    # E: afişsiz sahne (sadece duvar + bitki lekeleri) -> elenmeli
    img = wall(1200, 1700, (170, 175, 165))
    for _ in range(6):
        cx, cy, r = int(rng.integers(100, 1100)), int(rng.integers(1200, 1650)), int(rng.integers(50, 120))
        cv2.circle(img, (cx, cy), r, (60, 110, 70), -1, cv2.LINE_AA)
    img[1500:] *= 0.55
    save(img, f"{out_dir}/E_no_banner.jpg")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "tests/scenes")
