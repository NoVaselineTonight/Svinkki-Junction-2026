"""Quickly assemble cached video segments without re-rendering unchanged scenes.

Useful after a small phone skin change: run
  python production/assemble.py
It re-renders ordinary phone shots, reuses the opening, feature montage and ending,
then muxes the existing soundtrack with the concatenated scenes.
"""
from pathlib import Path
import subprocess
import render


def main():
    r = render.Renderer()
    paths = []
    for i, scene in enumerate(render.SCENES):
        path = render.BUILD / f"{i:02d}.mp4"
        if scene["screen"]:
            r.render_scene(i, output=path)
        else:
            assert path.exists(), f"Missing existing scene {path}; run render.py first"
        paths.append(path)
    concat = render.BUILD / "assemble-concat.txt"
    concat.write_text("\n".join("file '" + str(p.as_posix()) + "'" for p in paths), encoding="utf-8")
    final = render.OUT / "Svinkki-demo-1080p.mp4"
    subprocess.run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat), "-i", str(render.OUT / "Svinkki-soundtrack.m4a"),
        "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "copy",
        "-movflags", "+faststart", "-t", str(render.TOTAL), str(final),
    ], check=True)
    print(f"Final video: {final}")


if __name__ == "__main__":
    main()
