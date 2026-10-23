"""Rebuild the case-study image set from the HTML mockups.

Usage:
    python tools/build_assets.py

The case study is anonymised: none of the images are screenshots of the
client's sites. Every screen is an illustrative mockup built in
tools/mockups/*.html, rendered with headless Chrome at an exact size, and
then encoded to AVIF/WebP (or an animated WebP for the store tour).
Docs previews and the Open Graph card are rebuilt in the same pass, so the
whole image set is reproducible from source.

Requirements: Pillow with AVIF support, and Chrome/Edge on Windows.
Override the browser with CHROME_PATH if needed.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MOCKUPS = ROOT / "tools" / "mockups"
OUT = ROOT / "assets" / "img"
DOCS = ROOT / "docs"
SHOTS = ROOT / "_screens"

CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
]

# (output stem, mockup page, width, height, transparent, output widths)
STATIC_JOBS = [
    ("hero-designer", "hero-designer.html", 859, 549, True, [480, 645, 859]),
    ("hero-factory", "hero-factory.html", 273, 505, True, [273]),
    ("admin-discounts", "admin-discounts.html", 1586, 992, False, [800, 1200, 1586]),
    ("collections-travy", "collections-travy.html", 1536, 1024, False, [760, 1140, 1536]),
    ("lookbook-ss22", "lookbook-ss22.html", 1536, 1024, False, [760, 1140, 1536]),
    ("cart", "cart.html", 535, 381, False, [380, 535]),
    ("checkout", "checkout.html", 1586, 992, False, [800, 1200, 1586]),
]

TOUR_PAGES = ["tour-1.html", "tour-2.html", "tour-3.html", "tour-4.html"]

OBSOLETE = ["collections-dostoevsky-*.avif", "collections-dostoevsky-*.webp"]


def find_chrome() -> Path:
    env = os.environ.get("CHROME_PATH")
    candidates = ([Path(env)] if env else []) + CHROME_CANDIDATES
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    raise SystemExit(
        "Chrome/Edge not found. Set CHROME_PATH to the executable "
        "or install Google Chrome."
    )


def render(page: Path, png: Path, width: int, height: int, transparent: bool = False) -> None:
    png.parent.mkdir(parents=True, exist_ok=True)
    last_error = ""

    for _ in range(3):
        if png.exists():
            png.unlink()

        # A fresh profile per run: Chrome may keep the previous one locked for a
        # moment after exit, which makes back-to-back captures fail silently.
        profile = Path(tempfile.mkdtemp(prefix="dsh-chrome-"))
        args = [
            str(find_chrome()),
            "--headless=new",
            "--no-sandbox",
            "--disable-gpu",
            "--hide-scrollbars",
            "--no-first-run",
            "--no-default-browser-check",
            "--allow-file-access-from-files",
            "--log-level=3",
            "--force-device-scale-factor=1",
            f"--window-size={width},{height}",
            "--virtual-time-budget=3000",
            f"--user-data-dir={profile}",
            f"--screenshot={png}",
        ]
        if transparent:
            args.append("--default-background-color=00000000")
        args.append(page.as_uri())

        try:
            result = subprocess.run(args, capture_output=True, text=True)
        finally:
            shutil.rmtree(profile, ignore_errors=True)

        # The screenshot can land a few milliseconds after the browser exits.
        deadline = time.time() + 3
        while time.time() < deadline:
            if png.is_file() and png.stat().st_size > 0:
                return
            time.sleep(0.05)

        last_error = (result.stderr or "").strip()
        time.sleep(0.5)

    raise SystemExit(f"render failed for {page.name}:\n{last_error[-2000:]}")


def _kb(path: Path) -> str:
    return f"{path.stat().st_size / 1024:.0f}K"


def save_static(stem: str, source: Path, widths: list[int]) -> None:
    image = Image.open(source)
    has_alpha = image.mode in ("RGBA", "LA") or "transparency" in image.info
    base = image.convert("RGBA" if has_alpha else "RGB")

    for width in widths:
        height = round(base.height * width / base.width)
        frame = base if width == base.width else base.resize((width, height), Image.LANCZOS)
        suffix = "" if len(widths) == 1 else f"-{width}"
        name = f"{stem}{suffix}"

        frame.save(OUT / f"{name}.avif", "AVIF", quality=52, speed=6)
        frame.save(OUT / f"{name}.webp", "WEBP", quality=82, method=6)
        print(
            f"  {name}: {width}x{height} "
            f"avif={_kb(OUT / (name + '.avif'))} webp={_kb(OUT / (name + '.webp'))}"
        )


def build_tour() -> None:
    frames = []
    for page in TOUR_PAGES:
        png = SHOTS / page.replace(".html", ".png")
        render(MOCKUPS / page, png, 746, 458)
        frames.append(Image.open(png).convert("RGB"))

    sequence: list[Image.Image] = []
    durations: list[int] = []
    for index, frame in enumerate(frames):
        sequence.append(frame)
        durations.append(2200)
        following = frames[(index + 1) % len(frames)]
        for alpha in (0.25, 0.5, 0.75):
            sequence.append(Image.blend(frame, following, alpha))
            durations.append(80)

    output = OUT / "site-tour.webp"
    sequence[0].save(
        output,
        "WEBP",
        save_all=True,
        append_images=sequence[1:],
        duration=durations,
        loop=0,
        quality=78,
        method=6,
    )
    print(f"  site-tour: 746x458, {len(sequence)} frames, webp={_kb(output)}")


def build_og() -> None:
    png = SHOTS / "og-card.png"
    render(ROOT / "tools" / "og-card.html", png, 1200, 630)
    Image.open(png).convert("RGB").save(OUT / "og.jpg", "JPEG", quality=88, optimize=True)
    print(f"  og.jpg: 1200x630, {_kb(OUT / 'og.jpg')}")


def save_webp(source: Path, target: Path, quality: int = 84) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    Image.open(source).convert("RGB").save(target, "WEBP", quality=quality, method=6)
    print(f"  {target.name}: {Image.open(target).size[0]}x{Image.open(target).size[1]}, {_kb(target)}")


def build_docs() -> None:
    # Pin the theme before app.js runs: the headless browser may follow the
    # host's dark colour scheme, which would make both previews dark.
    source = (ROOT / "index.html").read_text(encoding="utf-8")
    light_copy = ROOT / "_preview-light.html"
    dark_copy = ROOT / "_preview-dark.html"
    mobile_wrapper = ROOT / "_preview-mobile.html"
    light_copy.write_text(
        source.replace('<html lang="ru">', '<html lang="ru" data-theme="light">', 1),
        encoding="utf-8",
    )
    dark_copy.write_text(
        source.replace('<html lang="ru">', '<html lang="ru" data-theme="dark">', 1),
        encoding="utf-8",
    )
    # Chrome enforces a minimum window width on Windows, so a 390 px capture
    # would crop a wider layout. An iframe renders the page at a true 390 px
    # viewport; the extra 110 px of canvas is cropped afterwards.
    mobile_wrapper.write_text(
        """<!DOCTYPE html>
<html lang="ru">
<head><meta charset="utf-8">
<style>
  html, body { margin: 0; padding: 0; background: #f7f4ef; }
  iframe { display: block; width: 390px; height: 844px; border: 0; }
</style></head>
<body><iframe src="_preview-light.html" scrolling="no"></iframe></body>
</html>
""",
        encoding="utf-8",
    )

    try:
        light_png = SHOTS / "preview-light.png"
        dark_png = SHOTS / "preview-dark.png"
        mobile_png = SHOTS / "preview-mobile.png"
        render(ROOT / "_preview-light.html", light_png, 1440, 900)
        render(ROOT / "_preview-dark.html", dark_png, 1440, 900)
        render(mobile_wrapper, mobile_png, 500, 844)
        save_webp(light_png, DOCS / "preview-light.webp")
        save_webp(dark_png, DOCS / "preview-dark.webp")
        Image.open(mobile_png).crop((0, 0, 390, 844)).save(
            DOCS / "preview-mobile.webp", "WEBP", quality=84, method=6
        )
        print(f"  preview-mobile.webp: 390x844, {_kb(DOCS / 'preview-mobile.webp')}")
    finally:
        light_copy.unlink(missing_ok=True)
        dark_copy.unlink(missing_ok=True)
        mobile_wrapper.unlink(missing_ok=True)


def clean() -> None:
    for pattern in OBSOLETE:
        for path in OUT.glob(pattern):
            path.unlink()
            print(f"  removed {path.name}")


def main() -> int:
    if not MOCKUPS.is_dir():
        print(f"missing mockups directory: {MOCKUPS}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    SHOTS.mkdir(parents=True, exist_ok=True)
    clean()

    print("mockup renders")
    for stem, page, width, height, transparent, widths in STATIC_JOBS:
        png = SHOTS / f"{stem}.png"
        render(MOCKUPS / page, png, width, height, transparent)
        save_static(stem, png, widths)

    print("store tour")
    build_tour()

    print("open graph")
    build_og()

    print("docs previews")
    build_docs()

    total = sum(item.stat().st_size for item in OUT.iterdir())
    print(f"total assets/img: {total / 1024:.0f}K")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
