#!/usr/bin/env python3
"""Break the frame like a pane of glass to reveal what is behind it.

Three phases:
  hold  - the incoming clip plays untouched
  crack - fracture lines race outward from the impact point, the frame shakes
  fly   - the pane comes apart and the shards fall away, revealing the next scene

The fracture pattern is radial-plus-concentric, which is how struck glass
actually fails. Voronoi cells look random; real glass throws spokes out from the
impact and rings around it.
"""

import argparse
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw


# ---------------------------------------------------------------- geometry ---

def build_fracture(w, h, ix, iy, rays, rings, rng):
    """Return (cells, vertices) for a radial/concentric fracture pattern.

    Adjacent cells are built from a shared vertex table, so the pane comes apart
    with no gaps between pieces.
    """
    # Reach past the far corner so the pattern covers the whole frame.
    corners = [(0, 0), (w, 0), (0, h), (w, h)]
    max_r = max(math.hypot(cx - ix, cy - iy) for cx, cy in corners) * 1.08

    angles = np.sort(rng.uniform(0, 2 * math.pi, rays))
    # Nudge apart any two spokes that landed almost on top of each other.
    for i in range(1, len(angles)):
        if angles[i] - angles[i - 1] < 0.12:
            angles[i] = angles[i - 1] + 0.12
    angles = np.concatenate([angles, [angles[0] + 2 * math.pi]])

    # Ring radii grow geometrically: fragments are small near the strike and
    # large out at the edges, which is what the eye expects.
    base = np.array([(k / rings) ** 1.7 for k in range(rings + 1)])
    radii = base * max_r
    radii[0] = max_r * 0.012

    # One jittered vertex per (ring, spoke), shared by the four cells that meet there.
    verts = np.zeros((rings + 1, len(angles), 2))
    for ri, r in enumerate(radii):
        for ai, a in enumerate(angles):
            jr = r * (1.0 + rng.uniform(-0.16, 0.16)) if 0 < ri < rings else r
            ja = a + (rng.uniform(-0.045, 0.045) if 0 < ri < rings else 0.0)
            verts[ri, ai] = (ix + jr * math.cos(ja), iy + jr * math.sin(ja))
    # Close the ring exactly, so the seam is not a visible crack.
    verts[:, -1] = verts[:, 0]

    cells = []
    # Innermost pieces: a fan of triangles around the impact point.
    for ai in range(len(angles) - 1):
        cells.append([(ix, iy), tuple(verts[0, ai]), tuple(verts[0, ai + 1])])
    # Everything outward: quads between consecutive rings and spokes.
    for ri in range(rings):
        for ai in range(len(angles) - 1):
            cells.append([tuple(verts[ri, ai]), tuple(verts[ri, ai + 1]),
                          tuple(verts[ri + 1, ai + 1]), tuple(verts[ri + 1, ai])])

    return cells, verts, radii, angles, max_r


def centroid(poly):
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    return sum(xs) / len(xs), sum(ys) / len(ys)


# ------------------------------------------------------------------ shards ---

class Shard:
    """One piece of the pane, with the motion it takes after the break."""

    def __init__(self, poly, source, w, h, ix, iy, rng):
        self.poly = poly
        cx, cy = centroid(poly)
        self.cx, self.cy = cx, cy

        dx, dy = cx - ix, cy - iy
        dist = math.hypot(dx, dy) or 1.0
        self.dist = dist

        xs = [p[0] for p in poly]
        ys = [p[1] for p in poly]
        pad = 2
        self.x0 = max(0, int(min(xs)) - pad)
        self.y0 = max(0, int(min(ys)) - pad)
        self.x1 = min(w, int(max(xs)) + pad)
        self.y1 = min(h, int(max(ys)) + pad)
        # A cell can fall entirely outside the frame; it has nothing to draw.
        if self.x1 <= self.x0 or self.y1 <= self.y0:
            self.image = None
            return

        mask = Image.new("L", (self.x1 - self.x0, self.y1 - self.y0), 0)
        ImageDraw.Draw(mask).polygon(
            [(px - self.x0, py - self.y0) for px, py in poly], fill=255)

        piece = source.crop((self.x0, self.y0, self.x1, self.y1)).convert("RGBA")
        piece.putalpha(mask)

        # A bright rim along each fracture edge. Without it the pieces read as
        # flat cutouts; with it they catch the light like real glass.
        local = [(px - self.x0, py - self.y0) for px, py in poly]
        rim = ImageDraw.Draw(piece, "RGBA")
        rim.line(local + [local[0]], fill=(235, 245, 255, 165), width=2)
        # Clip the rim back to the shard so it cannot bleed outside the polygon.
        piece.putalpha(Image.composite(piece.getchannel("A"),
                                       Image.new("L", piece.size, 0), mask))
        self.image = piece

        ux, uy = dx / dist, dy / dist

        # Pieces near the strike carry the most energy and leave fastest.
        near = math.exp(-dist / (0.42 * math.hypot(w, h)))
        speed = (0.16 + 1.05 * near) * (1.0 + rng.uniform(-0.3, 0.3))
        self.vx = ux * speed * w * 0.55
        self.vy = uy * speed * h * 0.55 - rng.uniform(0.02, 0.14) * h

        self.gravity = h * rng.uniform(1.5, 2.6)
        self.spin = rng.uniform(-190, 190) * (0.4 + near)
        # Near shards come toward the camera, far ones recede: cheap depth.
        self.scale_rate = rng.uniform(0.05, 0.42) * (1.0 if near > 0.45 else -1.0)
        self.delay = (1.0 - near) * rng.uniform(0.0, 0.20)
        self.near = near

    def draw(self, canvas, t):
        """Composite this shard onto `canvas` at time t (0..1 through the fly phase)."""
        if self.image is None:
            return
        tt = max(0.0, t - self.delay)
        if tt <= 0.0:
            canvas.alpha_composite(self.image, (self.x0, self.y0))
            return

        dx = self.vx * tt
        dy = self.vy * tt + 0.5 * self.gravity * tt * tt
        scale = max(0.05, 1.0 + self.scale_rate * tt)
        angle = self.spin * tt

        img = self.image
        if abs(scale - 1.0) > 0.01:
            nw = max(1, int(img.width * scale))
            nh = max(1, int(img.height * scale))
            img = img.resize((nw, nh), Image.BILINEAR)
        if abs(angle) > 0.5:
            img = img.rotate(angle, resample=Image.BILINEAR, expand=True)

        # Hold full opacity while the motion still reads, then let them go.
        alpha = 1.0 if tt < 0.62 else max(0.0, 1.0 - (tt - 0.62) / 0.38)
        if alpha <= 0.01:
            return
        if alpha < 0.999:
            a = img.getchannel("A").point(lambda v: int(v * alpha))
            img = img.copy()
            img.putalpha(a)

        px = int(self.x0 + (self.x1 - self.x0 - img.width) / 2 + dx)
        py = int(self.y0 + (self.y1 - self.y0 - img.height) / 2 + dy)
        canvas.alpha_composite(img, (px, py))


# ------------------------------------------------------------------- input ---

def read_frames(path, w, h, fps):
    """Decode a clip to RGB frames at the target size and rate."""
    cmd = ["ffmpeg", "-v", "error", "-i", str(path),
           "-vf", f"scale={w}:{h}:force_original_aspect_ratio=increase,"
                  f"crop={w}:{h},fps={fps}",
           "-pix_fmt", "rgb24", "-f", "rawvideo", "-"]
    raw = subprocess.run(cmd, capture_output=True).stdout
    if not raw:
        sys.exit(f"Could not decode any video from {path}")
    return np.frombuffer(raw, dtype=np.uint8).reshape(-1, h, w, 3)


def solid_frames(color, w, h, count):
    rgb = color.lstrip("#")
    if len(rgb) == 3:
        rgb = "".join(c * 2 for c in rgb)
    val = tuple(int(rgb[i:i + 2], 16) for i in (0, 2, 4))
    one = np.full((h, w, 3), val, dtype=np.uint8)
    return np.repeat(one[None, ...], count, axis=0)


def load_source(spec, w, h, fps, needed):
    """Accept a video, a still image, or a #RRGGBB colour."""
    if spec is None:
        return solid_frames("#000000", w, h, needed)
    if spec.startswith("#") or spec in ("black", "white"):
        color = {"black": "#000000", "white": "#FFFFFF"}.get(spec, spec)
        return solid_frames(color, w, h, needed)

    path = Path(spec).expanduser()
    if not path.exists():
        sys.exit(f"No such file: {path}")
    if path.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}:
        img = Image.open(path).convert("RGB")
        scale = max(w / img.width, h / img.height)
        img = img.resize((max(w, int(img.width * scale)), max(h, int(img.height * scale))),
                         Image.LANCZOS)
        left = (img.width - w) // 2
        top = (img.height - h) // 2
        arr = np.asarray(img.crop((left, top, left + w, top + h)))
        return np.repeat(arr[None, ...], needed, axis=0)
    return read_frames(path, w, h, fps)


def frame_at(frames, index):
    return frames[min(index, len(frames) - 1)]


# ------------------------------------------------------------------ cracks ---

def draw_cracks(base, verts, radii, angles, ix, iy, progress, max_r):
    """Fracture lines racing outward, drawn over the intact frame."""
    img = base.copy()
    d = ImageDraw.Draw(img, "RGBA")
    reach = progress * max_r

    def visible(p):
        return math.hypot(p[0] - ix, p[1] - iy) <= reach

    # Spokes first - they outrun the rings in real glass.
    for ai in range(len(angles) - 1):
        pts = [(ix, iy)] + [tuple(verts[ri, ai]) for ri in range(len(radii))]
        for a, b in zip(pts, pts[1:]):
            if not visible(a):
                continue
            if not visible(b):
                # Stop the line partway rather than snapping to the next vertex.
                seg = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
                covered = max(0.0, reach - math.hypot(a[0] - ix, a[1] - iy))
                f = min(1.0, covered / seg)
                b = (a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f)
            d.line([a, b], fill=(255, 255, 255, 210), width=3)
            d.line([a, b], fill=(160, 205, 235, 130), width=1)

    # Concentric rings, revealed as the fracture front passes them.
    for ri in range(len(radii)):
        if radii[ri] > reach:
            break
        ring = [tuple(verts[ri, ai]) for ai in range(len(angles))]
        d.line(ring, fill=(255, 255, 255, 150), width=2)

    return img


# ------------------------------------------------------------------- main ---

def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--before", required=True, help="Clip or image that breaks")
    ap.add_argument("--after", default="black",
                    help="What is revealed: clip, image, or #RRGGBB (default black)")
    ap.add_argument("--out", default="work/shatter.mp4")
    ap.add_argument("--width", type=int, default=1920)
    ap.add_argument("--height", type=int, default=1080)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--hold", type=float, default=3.0, help="Seconds before the impact")
    ap.add_argument("--crack", type=float, default=0.22, help="Seconds of cracks spreading")
    ap.add_argument("--fly", type=float, default=1.5, help="Seconds of shards falling")
    ap.add_argument("--impact-x", type=float, default=0.5, help="0..1 across the frame")
    ap.add_argument("--impact-y", type=float, default=0.5, help="0..1 down the frame")
    ap.add_argument("--rays", type=int, default=15, help="Radial fracture spokes")
    ap.add_argument("--rings", type=int, default=5, help="Concentric fracture rings")
    ap.add_argument("--seed", type=int, default=None)
    ap.add_argument("--sfx", help="Audio to place at the moment of impact")
    ap.add_argument("--sfx-gain", type=float, default=1.0)
    ap.add_argument("--crf", type=int, default=17)
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args()

    w, h, fps = args.width, args.height, args.fps
    rng = np.random.default_rng(args.seed)

    hold_f = max(0, int(round(args.hold * fps)))
    crack_f = max(1, int(round(args.crack * fps)))
    fly_f = max(2, int(round(args.fly * fps)))
    total_f = hold_f + crack_f + fly_f

    before = load_source(args.before, w, h, fps, hold_f + crack_f + fly_f)
    after = load_source(args.after, w, h, fps, crack_f + fly_f)

    # The pane that breaks is the frame showing at the moment of impact.
    pane_idx = min(hold_f, len(before) - 1)
    pane = Image.fromarray(before[pane_idx]).convert("RGB")

    ix, iy = args.impact_x * w, args.impact_y * h
    cells, verts, radii, angles, max_r = build_fracture(
        w, h, ix, iy, args.rays, args.rings, rng)

    print(f"Fracture: {len(cells)} shards from {args.rays} spokes x {args.rings} rings")
    shards = [Shard(poly, pane, w, h, ix, iy, rng) for poly in cells]
    shards = [s for s in shards if s.image is not None]
    # Draw distant pieces first so near ones pass in front of them.
    shards.sort(key=lambda s: -s.dist)

    out_path = Path(args.out).expanduser()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    enc = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
    if args.sfx:
        # Silence for the hold, then the break exactly on the impact frame.
        enc += ["-f", "lavfi", "-t", f"{total_f / fps:.4f}",
                "-i", "anullsrc=channel_layout=stereo:sample_rate=48000",
                "-i", str(Path(args.sfx).expanduser())]
        delay_ms = int(round(hold_f / fps * 1000))
        enc += ["-filter_complex",
                f"[2:a]volume={args.sfx_gain},adelay={delay_ms}|{delay_ms}[s];"
                f"[1:a][s]amix=inputs=2:duration=first:normalize=0,"
                f"atrim=duration={total_f / fps:.4f}[a]",
                "-map", "0:v", "-map", "[a]",
                "-c:a", "aac", "-b:a", "256k", "-ar", "48000"]
    enc += ["-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
            "-pix_fmt", "yuv420p", "-r", str(fps), "-frames:v", str(total_f),
            "-movflags", "+faststart", str(out_path)]

    proc = subprocess.Popen(enc, stdin=subprocess.PIPE, stderr=subprocess.PIPE)

    try:
        for i in range(hold_f):
            proc.stdin.write(frame_at(before, i).tobytes())

        for i in range(crack_f):
            p = (i + 1) / crack_f
            img = draw_cracks(pane, verts, radii, angles, ix, iy, p, max_r)
            # A single bright frame at the strike, then a decaying shake.
            if i == 0:
                img = Image.blend(img, Image.new("RGB", (w, h), (255, 255, 255)), 0.55)
            shake = (1.0 - p) * 14
            ox = int(rng.uniform(-shake, shake))
            oy = int(rng.uniform(-shake, shake))
            if ox or oy:
                shifted = Image.new("RGB", (w, h), (0, 0, 0))
                shifted.paste(img, (ox, oy))
                img = shifted
            proc.stdin.write(np.asarray(img).tobytes())

        for i in range(fly_f):
            t = (i + 1) / fly_f
            canvas = Image.fromarray(frame_at(after, crack_f + i)).convert("RGBA")
            for shard in shards:
                shard.draw(canvas, t)
            proc.stdin.write(np.asarray(canvas.convert("RGB")).tobytes())
            if (i + 1) % 15 == 0:
                print(f"  shatter {i + 1}/{fly_f}")

        proc.stdin.close()
    except BrokenPipeError:
        pass

    err = proc.stderr.read().decode(errors="replace")
    if proc.wait() != 0:
        print(err[-3000:], file=sys.stderr)
        sys.exit("ffmpeg failed encoding the shatter")

    print(f"Wrote {out_path}  ({total_f} frames, {total_f / fps:.2f}s)")
    print(f"  impact at {hold_f / fps:.2f}s"
          + (", sfx placed there" if args.sfx else ", no sfx (pass --sfx)"))


if __name__ == "__main__":
    main()
