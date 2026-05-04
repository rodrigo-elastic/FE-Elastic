"""
GIF builder for FE Copilot README hero animations.

Strategy: Option B (PIL-based, no ffmpeg required).
- Resizes source PNGs to a max width of 1280 px (preserves aspect).
- Builds three styles of frames:
    * crossfade(a, b)         smooth A -> B blend
    * ken_burns(img)          slow zoom + pan within a viewport
    * sequence(a, b, c, d)    chained crossfades A -> B -> C -> D
- Output: 4 looping GIFs, 6 to 8 seconds each, total combined under 20 MB.

Run once:
    python3 docs/gifs/_build.py

The script is idempotent. Re-running overwrites the GIFs deterministically.
"""

from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "docs" / "screenshots"
OUT = ROOT / "docs" / "gifs"
OUT.mkdir(parents=True, exist_ok=True)

MAX_W = 960
# Viewport is the visible window of the GIF. Source screenshots are full-page
# (1440 x 2400). For the README hero we crop to a 16:10 viewport so the GIF
# reads at glance, then pan inside that viewport for Ken-Burns shots.
VIEWPORT_W = MAX_W
VIEWPORT_H = 600  # 960 x 600 keeps a comfortable hero ratio and shrinks bytes.

# GIF tuning: 8 fps reads smooth on screenshots without paying for redundant
# frames. 64-color adaptive palette is enough for UI mocks and keeps each GIF
# safely under ~5 MB.
FPS = 8
HOLD_FRAMES = 6  # ~0.75 s hold on a static frame
CROSSFADE_FRAMES = 8  # ~1.0 s crossfade
KEN_BURNS_FRAMES = 40  # ~5 s pan + zoom
PALETTE_COLORS = 56


def load_resized(name: str) -> Image.Image:
    """Load a source PNG and resize so width == MAX_W."""
    img = Image.open(SRC / name).convert("RGB")
    w, h = img.size
    new_h = int(h * (MAX_W / w))
    return img.resize((MAX_W, new_h), Image.LANCZOS)


def viewport_top(img: Image.Image) -> Image.Image:
    """Crop the top viewport from a tall screenshot."""
    return img.crop((0, 0, VIEWPORT_W, min(VIEWPORT_H, img.size[1])))


def crossfade_pair(a: Image.Image, b: Image.Image, frames: int) -> List[Image.Image]:
    """Linear crossfade from a to b across `frames` frames."""
    out = []
    for i in range(frames):
        alpha = (i + 1) / frames
        out.append(Image.blend(a, b, alpha))
    return out


def ken_burns(img: Image.Image, frames: int, zoom_from: float = 1.0, zoom_to: float = 1.08,
              pan_from: Tuple[float, float] = (0.0, 0.0),
              pan_to: Tuple[float, float] = (0.0, 0.25)) -> List[Image.Image]:
    """Generate a slow zoom and pan inside a fixed viewport.

    pan values are normalized (0..1) over the available scroll range.
    Default pans down 25% of the page height while zooming in 8%.
    """
    out = []
    iw, ih = img.size
    for i in range(frames):
        t = i / max(frames - 1, 1)
        z = zoom_from + (zoom_to - zoom_from) * t
        # Compute the cropped viewport size at zoom z.
        vw = int(VIEWPORT_W / z)
        vh = int(VIEWPORT_H / z)
        # Pan: linear interp over normalized range.
        px = pan_from[0] + (pan_to[0] - pan_from[0]) * t
        py = pan_from[1] + (pan_to[1] - pan_from[1]) * t
        max_x = max(iw - vw, 0)
        max_y = max(ih - vh, 0)
        x = int(max_x * px)
        y = int(max_y * py)
        crop = img.crop((x, y, x + vw, y + vh))
        out.append(crop.resize((VIEWPORT_W, VIEWPORT_H), Image.LANCZOS))
    return out


def hold(img: Image.Image, frames: int) -> List[Image.Image]:
    return [img.copy() for _ in range(frames)]


def quantize(frames: List[Image.Image]) -> List[Image.Image]:
    """Quantize to a shared adaptive palette derived from the median frame."""
    # Use the middle frame to derive a palette so motion stays consistent.
    base = frames[len(frames) // 2].convert(
        "P", palette=Image.ADAPTIVE, colors=PALETTE_COLORS
    )
    return [f.quantize(palette=base, dither=Image.FLOYDSTEINBERG) for f in frames]


def save_gif(frames: List[Image.Image], path: Path) -> int:
    """Save a looping GIF and return its byte size."""
    duration_ms = int(1000 / FPS)
    qframes = quantize(frames)
    qframes[0].save(
        path,
        save_all=True,
        append_images=qframes[1:],
        duration=duration_ms,
        loop=0,
        optimize=True,
        disposal=2,
    )
    return path.stat().st_size


# ---------- Per-GIF builders ----------

def build_pre_meeting() -> Path:
    """dashboard.png -> meeting_revolut.png with hold + crossfade + hold."""
    a = viewport_top(load_resized("dashboard.png"))
    b = viewport_top(load_resized("meeting_revolut.png"))
    frames = (
        hold(a, HOLD_FRAMES * 2)
        + crossfade_pair(a, b, CROSSFADE_FRAMES)
        + hold(b, HOLD_FRAMES * 2)
    )
    out = OUT / "pre-meeting.gif"
    size = save_gif(frames, out)
    print(f"pre-meeting.gif: {len(frames)} frames, {size/1024:.0f} KB")
    return out


def build_agent_builder() -> Path:
    """Solo agent_builder.png with a slow Ken-Burns pan down the page."""
    img = load_resized("agent_builder.png")
    frames = ken_burns(
        img,
        KEN_BURNS_FRAMES,
        zoom_from=1.02,
        zoom_to=1.10,
        pan_from=(0.0, 0.0),
        pan_to=(0.0, 0.55),
    )
    out = OUT / "agent-builder.gif"
    size = save_gif(frames, out)
    print(f"agent-builder.gif: {len(frames)} frames, {size/1024:.0f} KB")
    return out


def build_demo_data() -> Path:
    """demo_data.png -> three meeting screenshots as proxy dashboards."""
    a = viewport_top(load_resized("demo_data.png"))
    b = viewport_top(load_resized("meeting_meli.png"))
    c = viewport_top(load_resized("meeting_santander.png"))
    d = viewport_top(load_resized("meeting_revolut.png"))
    frames = (
        hold(a, HOLD_FRAMES)
        + crossfade_pair(a, b, CROSSFADE_FRAMES)
        + hold(b, HOLD_FRAMES // 2)
        + crossfade_pair(b, c, CROSSFADE_FRAMES)
        + hold(c, HOLD_FRAMES // 2)
        + crossfade_pair(c, d, CROSSFADE_FRAMES)
        + hold(d, HOLD_FRAMES)
    )
    out = OUT / "demo-data.gif"
    size = save_gif(frames, out)
    print(f"demo-data.gif: {len(frames)} frames, {size/1024:.0f} KB")
    return out


def build_workflow() -> Path:
    """Solo workflow_demo.png with Ken-Burns covering the four-step diagram."""
    img = load_resized("workflow_demo.png")
    frames = ken_burns(
        img,
        KEN_BURNS_FRAMES,
        zoom_from=1.04,
        zoom_to=1.12,
        pan_from=(0.0, 0.0),
        pan_to=(0.0, 0.45),
    )
    out = OUT / "workflow.gif"
    size = save_gif(frames, out)
    print(f"workflow.gif: {len(frames)} frames, {size/1024:.0f} KB")
    return out


def main() -> None:
    paths = [
        build_pre_meeting(),
        build_agent_builder(),
        build_demo_data(),
        build_workflow(),
    ]
    total = sum(p.stat().st_size for p in paths)
    print(f"total: {total/1024/1024:.2f} MB across {len(paths)} GIFs")


if __name__ == "__main__":
    main()
