"""Render a self-contained, product-led Svinkki video from supplied app screenshots.

Requires Pillow, NumPy and FFmpeg on PATH. No internet or paid services.
Run: python production/render.py [--preview] [--scene INDEX] [--audio-only]
Output: output/Svinkki-demo-1080p.mp4, plus poster, captions and contact sheet.
The screenshots and repository source are read-only inputs.
"""
from __future__ import annotations

import argparse
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

from story import SCENES, SHOTS, TOTAL, ROOT

OUT = ROOT.parent / "output"
OUT.mkdir(exist_ok=True)
BUILD = ROOT / "build"
W, H, FPS = 1920, 1080, 30
if not (ROOT / "frames-count.txt").exists():
    pass
TOTAL_FRAMES = round(TOTAL * FPS)
DARK = (5, 66, 50)
INK = (20, 40, 33)
MUTED = (94, 115, 102)
LIME = (186, 250, 101)
MINT = (215, 247, 187)
WHITE = (251, 253, 248)
FONTS = Path(r"C:\Windows\Fonts")
FONT_REGULAR = FONTS / "segoeui.ttf"
FONT_BOLD = FONTS / "segoeuib.ttf"


def font(size, bold=False):
    return ImageFont.truetype(str(FONT_BOLD if bold else FONT_REGULAR), round(size))


def ease(t):
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def ease_out(t):
    return 1.0 - (1.0 - max(0.0, min(1.0, t))) ** 3


def enter(t):
    return ease_out(t / 0.70)


def rounded_mask(size, radius):
    m = Image.new("L", size)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), radius, fill=255)
    return m.convert("RGBA")


def fit_lines(draw, text, fnt, width, max_lines=4):
    lines, current = [], ""
    for word in text.split():
        test = (current + " " + word).strip()
        if current and draw.textlength(test, font=fnt) > width:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines[:max_lines]


def multiline(base, text, xy, fnt, fill, width, line_height):
    draw = ImageDraw.Draw(base)
    x, y = xy
    lines = fit_lines(draw, text, fnt, width)
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += line_height
    return y


class Renderer:
    def __init__(self):
        OUT.mkdir(exist_ok=True)
        BUILD.mkdir(exist_ok=True)
        self.images = {name: Image.open(SHOTS / name).convert("RGB")
                       for name in (s["screen"] for s in SCENES if s["screen"])}
        self.images["14-what-if-i-spent-less.png"] = Image.open(SHOTS / "14-what-if-i-spent-less.png").convert("RGB")
        self.images["16-daily-quiz.png"] = Image.open(SHOTS / "16-daily-quiz.png").convert("RGB")
        self.images["01-welcome-your-choices.png"] = Image.open(SHOTS / "01-welcome-your-choices.png").convert("RGB")
        self.ttf_cache = {}
        scene = self.images["02-home-page.png"]
        big = scene.resize((480, round(scene.height * 480 / scene.width)), Image.Resampling.LANCZOS)
        crop = big.crop((18, 2, 115, 57))
        mask = Image.new("L", crop.size)
        for x in range(crop.width):
            for y in range(crop.height):
                pixel = crop.getpixel((x, y))
                if pixel[1] > 75 and pixel[1] > pixel[0] * 1.04 and pixel[1] > pixel[2] * 1.04:
                    mask.putpixel((x, y), 255)
        self.mark = self.s_mark = mask
        self.phone_body = rounded_mask((540, 1134), 64)
        self.tap_ring = None
        self.base_cache = {}
        self.last_frame = None
        for i, scene in enumerate(SCENES):
            self.base_cache[i] = self.static_scene(i, scene)

    def static_scene(self, i, scene):
        special = scene["screen"] is None
        image = Image.new("RGB", (W, H), DARK if scene["accent"] == "lime" else WHITE)
        draw = ImageDraw.Draw(image)
        if scene["accent"] == "lime":
            draw.rectangle((0, 0, 18, H), fill=LIME)
            draw.line((64, 184, W - 68, 184), fill=(62, 98, 79), width=1)
            draw.line((864, 205, 864, 866), fill=(62, 98, 79), width=1)
            draw.ellipse((1550, 675, 2100, 1225), fill=(9, 80, 56))
            draw.ellipse((1660, 785, 1950, 1075), fill=(13, 95, 60))
        else:
            draw.line((64, 184, W - 68, 184), fill=(215, 225, 214), width=2)
            draw.line((864, 205, 864, 866), fill=(215, 225, 214), width=1)
            draw.ellipse((1610, 725, 2050, 1165), fill=(228, 246, 209))
            for y in range(236, 1020, 88):
                draw.line((916, y, 1885, y), fill=(231, 238, 227), width=1)
            draw.rectangle((0, 0, 18, H), fill=MINT)

        if self.s_mark.getbbox():
            mark = self.s_mark.resize((58, 60), Image.Resampling.LANCZOS)
            image.paste(LIME if scene["accent"] == "lime" else DARK, (66, 54), mark)
        draw.text((146, 63), "Vinkki", font=font(41, True), fill=LIME if scene["accent"] == "lime" else DARK)
        label = "PERSONAL ECONOMIC TRAINER"
        draw.text((428, 77), label, font=font(19), fill=(168, 195, 175) if scene["accent"] == "lime" else MUTED)
        end = "S-PANKKI  /  JUNCTION 2026"
        draw.text((W - 75 - draw.textlength(end, font=font(18, True)), 75), end, font=font(18, True),
                  fill=LIME if scene["accent"] == "lime" else MUTED)
        ink = (248, 253, 244) if scene["accent"] == "lime" else DARK
        muted = (190, 214, 193) if scene["accent"] == "lime" else MUTED
        normal = font(29)
        if special:
            if scene["id"] == "12-features":
                feature_text_scene(draw, ink, muted)
            else:
                title_font = font(84 if scene["id"] != "01-hook" else 92, True)
                y = 277
                for line in scene["heading"].split("\n"):
                    draw.text((66, y), line, font=title_font, fill=ink)
                    y += round(title_font.size * 1.07)
                draw.line((70, y + 23, 440, y + 23), fill=LIME, width=8)
                if scene["id"] == "01-hook":
                    draw.text((68, y + 72), "ASK.  PLAN.  ACT.", font=font(28, True), fill=LIME)
                    multiline(image, "An AI coach that turns your questions into a plan — and your plan into action.",
                              (68, 650), font(30), muted, 696, 44)
                if scene["id"] == "13-close":
                    draw.text((69, y + 71), "UNDERSTAND   →   PLAN   →   ACT", font=font(24, True), fill=LIME)
                    multiline(image, "Your money. Your plan. Your next step.", (69, y + 134), normal, muted, 725, 42)
        else:
            kicker_font = font(19, True)
            kicker_width = draw.textlength(scene["kicker"], font=kicker_font)
            badge = Image.new("RGBA", (round(kicker_width + 33), 37))
            ImageDraw.Draw(badge).rounded_rectangle((0, 0, badge.width, 37), 18,
                                                     fill=LIME if scene["accent"] == "lime" else MINT)
            ImageDraw.Draw(badge).text((16, 7), scene["kicker"], font=kicker_font, fill=DARK)
            image.paste(badge, (66, 234), badge)
            y = 307
            for line in scene["heading"].split("\n"):
                draw.text((66, y), line, font=font(67, True), fill=ink)
                y += 77
            multiline(image, scene["tagline"], (70, 642), normal, muted, 733, 43)
            if scene["id"] == "07-widget":
                draw.rounded_rectangle((68, 774, 793, 844), 18, fill=(232, 250, 207) if scene["accent"] != "lime" else (20, 108, 65))
                draw.text((88, 794), "CHAT  →  CUSTOM WIDGET  →  NEXT MOVE", font=font(23, True), fill=ink)
        draw.text((68, 1040), "SVINKKI  /  HACKATHON PROTOTYPE · SYNTHETIC DATA", font=font(15, True), fill=muted)
        draw.text((1822, 1038), f"{i + 1:02d}", font=font(17, True), fill=muted)
        draw.line((68, 1013, 1850, 1013), fill=(67, 105, 84) if scene["accent"] == "lime" else (213, 225, 211), width=2)
        return image

    def phone(self, screen_name, t, scene, width=500, x=1388, y=526, yaw=0.0, pitch=0.0, roll=0.0, detail=1.0):
        """A readable 2.5D phone: perspective is on the whole device, not the UI."""
        src = self.images[screen_name]
        progress = ease(t)
        zoom = 1.0 + (scene.get("crop", (1.12,))[0] - 1.0) * progress
        sw, sh = src.size
        target_w = round(sw / zoom)
        target_h = round(target_w * 1100 / 506)
        focus_x, focus_y = scene.get("crop", (1.1, 0.5, 0.50))[1:3]
        drift_y = scene.get("crop", (1.1, 0.5, 0.5, 0.0))[3]
        cx = sw * focus_x
        cy = sh * (focus_y + drift_y * (progress - 0.5))
        left = max(0, min(sw - target_w, round(cx - target_w / 2)))
        top = max(0, min(sh - target_h, round(cy - target_h / 2)))
        crop = src.crop((left, top, left + target_w, top + target_h))
        shot = crop.resize((506, 1100), Image.Resampling.LANCZOS)
        height_factor = 1.0 - 0.28 * abs(yaw) / 0.30
        angle = yaw * 170
        body = Image.new("RGBA", (556, round(1150 * height_factor)))
        h = body.height
        d = ImageDraw.Draw(body)
        radius = round(width * 0.1)
        # Extruded edge in the direction the device is facing.
        edge_shift = 19 if yaw < 0 else 0
        if yaw < 0:
            corners = [(32, 0), (524, 44), (524, h - 14), (32, h)]
        else:
            corners = [(14, 45), (516, 0), (516, h), (14, h - 13)]
        for iy in range(body.height):
            d.line((0, iy, body.width, iy), fill=(0, 0, 0, 0))
        body = Image.new("RGBA", (556, h))
        d = ImageDraw.Draw(body)
        dir_sign = -1 if yaw < 0 else 1
        for e in range(18, -1, -1):
            offset = round(e * dir_sign)
            pts = [(xx + offset, yy + e * 0.35) for xx, yy in corners]
            shade = round(24 + (18 - e) * 1.65)
            d.polygon(pts, fill=(shade, shade + 37, shade + 26, 255))
        # Alpha-masked front surface, including a matching device border.
        front_width = 506
        front_height = round(1100 * height_factor)
        face_x, face_y = (32, 0) if yaw < 0 else (14, 46)
        shell = Image.new("RGBA", (556, h))
        sm = Image.new("L", (556, h))
        sd = ImageDraw.Draw(shell)
        md = ImageDraw.Draw(sm)
        for layer in [(shell, sd), (sm, md)]:
            canvas, pen = layer
            pen.rounded_rectangle((1, 1, 554, h-2), radius=54, fill=(30,78,57,255) if canvas is shell else 255)
        sd.text((0, 0), "", fill=(30, 78, 57))
        shot = shot.resize((506, front_height), Image.Resampling.LANCZOS)
        shell.paste(shot, (24, 24), clean_screen_mask((506, front_height), 30))
        # The border lives on the same alpha surface as the phone frame.
        shell.putalpha(Image.fromarray(np.maximum(np.asarray(shell.getchannel("A")), np.asarray(sm))))
        body.paste(shell, (face_x, face_y), shell)
        d = ImageDraw.Draw(body)
        notch_w, notch_h = round(front_width * 0.20), 9
        d.rounded_rectangle((face_x + 158, face_y + 13, face_x + 158 + notch_w, face_y + 13 + notch_h), 6, fill=(3, 22, 17))
        # A tiny edge seam and physical button (no distorted text).
        d.line((face_x + 9, face_y + 60, face_x + 9, face_y + front_height - 42), fill=(93, 145, 109), width=2)
        if yaw >= 0:
            d.rounded_rectangle((1, face_y + 221, 8, face_y + 291), 4, fill=(89, 132, 104))
        else:
            d.rounded_rectangle((546, 221, 553, 291), 4, fill=(89, 132, 104))
        body = body.rotate(angle, Image.Resampling.BICUBIC, expand=True)
        desired_width = width + round(abs(yaw) * 370)
        factor = desired_width / body.width
        body = body.resize((desired_width, round(body.height * factor)), Image.Resampling.LANCZOS)
        result = Image.new("RGBA", (W, H))
        result.alpha_composite(body, (round(x - body.width / 2), round(y - body.height / 2)))
        return result

    def phone_shadow(self, t, accent):
        layer = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(layer)
        d.ellipse((1040, 979, 1790, 1059), fill=(2, 29, 17, 100))
        d.ellipse((1170, 995, 1670, 1047), fill=(0, 23, 12, 140))
        return layer.filter(ImageFilter.GaussianBlur(28))

    def triple_phones(self, t, final=False):
        result = Image.new("RGBA", (W, H))
        p = ease_out(t / 1.5)
        for i, name in enumerate(["01-welcome-your-choices.png", "02-home-page.png", "03-home-savings-plan-and-suggestions.png"]):
            x = 1060 + i * 290
            y = 600 + abs(i - 1) * 9
            yaw = 0.24 if i == 0 else (0.0 if i == 1 else -0.24)
            fake = {"crop": (1.0, 0.5, 0.5, 0.0)}
            layer = self.phone(name, t * 0.35, fake, width=358, x=x, y=y,
                               yaw=yaw, pitch=0, roll=0.014 if i == 0 else -0.014)
            offset = round((1.0 - p) * (160 + i * 90))
            moved = Image.new("RGBA", (W, H))
            moved.alpha_composite(layer, (offset, round((1.0 - p) * 80)))
            result.alpha_composite(moved)
        return result

    def feature_montage(self, t):
        result = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(result)
        names = [("03-home-savings-plan-and-suggestions.png", "Your Japan plan", "A widget from your own conversation"),
                 ("14-what-if-i-spent-less.png", "What if…?", "See what a small change could mean"),
                 ("16-daily-quiz.png", "A personal quiz", "Learn from your own month")]
        p = ease_out(t / 1.1)
        for i, (name, title, description) in enumerate(names):
            x = 930 + i * 325
            y = 216 + (i % 2) * 22
            card = Image.new("RGBA", (297, 711))
            dc = ImageDraw.Draw(card)
            dc.rounded_rectangle((0, 0, 296, 710), 26, fill=WHITE)
            src = self.images[name]
            # Showcase the interface, with animated gentle vertical scrolling.
            scroll = round((0.20 + 0.10 * math.sin(t * 0.75 + i)) * src.height)
            crop = src.crop((0, min(scroll, src.height - 1990), src.width, min(scroll, src.height - 1990) + 1990))
            crop = crop.resize((266, 453), Image.Resampling.LANCZOS)
            card.paste(crop, (16, 16), rounded_mask((266, 453), 14))
            dc.text((16, 495), title, font=font(22, True), fill=DARK)
            multiline(card, description, (16, 540), font(17), MUTED, 263, 27)
            dc.text((16, 656), f"0{i+1}", font=font(17, True), fill=DARK)
            moved = Image.new("RGBA", (W, H))
            moved.alpha_composite(card, (x, round(y + (1 - p) * 100)))
            result.alpha_composite(moved)
        return result

    def caption(self, scene, t):
        layer = Image.new("RGBA", (W, H))
        draw = ImageDraw.Draw(layer)
        text = scene["voice"]
        voice_font = font(25)
        lines = fit_lines(draw, text, voice_font, 740)
        lines = lines[:3]
        height = len(lines) * 35 + 18
        y = 991 - height
        alpha = ease(min(t / 0.40, (scene["duration"] - t) / 0.35))
        if t < 0.38:
            text = ""
        draw.rounded_rectangle((59, y - 15, 834, 987), radius=18,
                               fill=(11, 67, 46, round(220 * alpha)) if scene["accent"] != "lime" else (4, 54, 38, round(235 * alpha)))
        for line in lines:
            draw.text((80, y), line, font=voice_font, fill=(247, 253, 238, round(255 * alpha)))
            y += 35
        return layer

    def frame(self, scene_index, local_t):
        scene = SCENES[scene_index]
        p = max(0.0, min(1.0, local_t / scene["duration"]))
        image = self.base_cache[scene_index].copy()
        text_alpha = enter(local_t)
        content = Image.new("RGBA", (W, H))
        d = ImageDraw.Draw(content)
        if scene["accent"] != "lime":
            d.line((69, 1091, 69 + int(text_alpha * 690), 1091), fill=LIME, width=6)
            d.ellipse((951 + math.sin(p * 3) * 40, 196, 969 + math.sin(p * 3) * 40, 214), fill=LIME)
        if scene["screen"]:
            shadow = self.phone_shadow(p, scene["accent"])
            image.paste(shadow, (0, 0), shadow)
            float_y = math.sin(p * math.pi * 2) * 7
            slide_x = (1.0 - text_alpha) * 115 * (1 if scene_index % 2 else -1)
            yaw0 = scene.get("yaw", 0)
            yaw = yaw0 * (1.25 - 0.6 * ease_out(p / 0.75))
            layer = self.phone(scene["screen"], p, scene, width=465,
                               x=1427 + slide_x, y=585 + (1.0 - enter(local_t)) * 28 + float_y, yaw=yaw,
                               pitch=scene.get("pitch", 0), roll=scene.get("roll", 0))
            image.paste(layer, (0, 0), layer)
            # A restrained badge highlights the customer benefit, outside the app screen.
            if local_t > 1.2:
                label = {"02-personal": "MADE FOR VEETI", "07-widget": "ACHIEVABLE. VISIBLE. YOURS.",
                         "08-proactive": "MADE FOR JOONAS", "05-afford": "YES — IT FITS"}.get(scene["id"])
                if label:
                    opacity = ease((local_t - 1.2) / 0.45)
                    d = ImageDraw.Draw(content)
                    tw = d.textlength(label, font=font(19, True))
                    draw = ImageDraw.Draw(content)
                    draw.rounded_rectangle((1538, 856, 1554 + tw + 28, 909), 15, fill=LIME + (round(opacity * 255),))
                    draw.text((1552, 870), label, font=font(19, True), fill=DARK)
        elif scene["id"] == "12-features":
            layer = self.feature_montage(p)
            image.paste(layer, (0, 0), layer)
        else:
            layer = self.triple_phones(p, scene["id"] == "13-close")
            image.paste(layer, (0, 0), layer)

        if scene_index == 0 and local_t < 1.65:
            # Slight lime field reveals the first frame without a hard flash.
            a = 1 - ease(local_t / 1.5)
        else:
            a = 0.0
        if scene["screen"] or scene["id"] == "12-features":
            caption = self.caption(scene, local_t)
            image.paste(caption, (0, 0), caption)
        if a > 0:
            lime_bg = Image.new("RGBA", (W, H), (222, 253, 183, round(110 * a)))
            image.paste(lime_bg, (0, 0), lime_bg)
        draw = ImageDraw.Draw(image)
        total = scene["start"] + local_t
        progress = total / TOTAL
        draw.line((68, 1013, 68 + 1782 * progress, 1013), fill=LIME if scene["accent"] == "lime" else (117, 188, 90), width=3)
        if scene_index != len(SCENES) - 1 and local_t < 0.16 and self.last_frame:
            blend = ease(local_t / 0.16) * 0.90 + 0.10
            image = Image.blend(self.last_frame, image, blend)
        return image

    def render_scene(self, index, fps=FPS, output=None, preview=False):
        scene = SCENES[index]
        frames = round(scene["duration"] * fps)
        output = output or (BUILD / f"{index:02d}.mp4")
        if output.exists():
            output.unlink()
        cmd = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo",
               "-pixel_format", "rgb24", "-video_size", f"{W}x{H}", "-framerate", str(fps), "-i", "-",
               "-an", "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
               "-threads", "4", "-movflags", "+faststart", str(output)]
        process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        start = time.time()
        try:
            for frame in range(frames):
                i = self.frame(index, frame / fps)
                process.stdin.write(i.tobytes())
        finally:
            if process.stdin:
                process.stdin.close()
        code = process.wait()
        if code:
            raise RuntimeError(f"FFmpeg returned {code} for {scene['id']}")
        print(f"Rendered {scene['id']}: {frames} frames in {time.time()-start:.1f}s", flush=True)
        self.last_frame = i
        return output


def feature_text_scene(draw, ink, muted):
    draw.text((65, 287), "Small steps.", font=font(75, True), fill=ink)
    draw.text((65, 380), "Better money habits.", font=font(67, True), fill=ink)
    multiline(Image.new("RGB", (1, 1)), "", (0, 0), font(10), INK, 800, 10)
    # Static descriptions in the story column; the three live screens move on the right.
    draw.text((68, 550), "A goal you can see.", font=font(27, True), fill=ink)
    draw.text((68, 591), "A change you can make.", font=font(27), fill=muted)
    draw.text((68, 651), "A habit you can build.", font=font(27), fill=muted)
    draw.line((68, 723, 401, 723), fill=(133, 201, 118), width=7)


def create_audio():
    """Original upbeat backing and timed local voice; normalize at final mux."""
    sample_rate = 48000
    n = round(TOTAL * sample_rate)
    music = np.zeros((n, 2), dtype=np.float64)
    rng = np.random.default_rng(834)
    notes = {0: 0.0, 2: 2.0, 4: 4.0, 5: 5.0, 7: 7.0, 9: 9.0, 11: 11.0}
    def hz(midi):
        return 440.0 * 2 ** ((midi - 69) / 12)

    def tone(at, length, midi, volume=0.18, pan=0.5, kind="pluck"):
        start = round(at * sample_rate)
        num = min(round(length * sample_rate), n - start)
        if num <= 0:
            return
        t = np.arange(num) / sample_rate
        f = hz(midi)
        attack = np.minimum(1.0, t / 0.008)
        env = attack * np.exp(-4.8 * t / length)
        wave_data = np.sin(2 * np.pi * f * t) + 0.30 * np.sin(2 * np.pi * 2 * f * t)
        wave_data += 0.09 * np.sin(2 * np.pi * 3 * f * t)
        wave_data *= env * volume
        music[start:start+num, 0] += wave_data * (1 - pan)
        music[start:start+num, 1] += wave_data * pan

    def kick(at, volume=0.28):
        start = round(at * sample_rate)
        num = min(round(0.24 * sample_rate), n - start)
        t = np.arange(num) / sample_rate
        env = np.exp(-t * 24)
        phase = (130 - 90 * np.minimum(t / 0.14, 1)) * t
        kick = np.sin(phase * 2 * np.pi) * env * volume
        music[start:start+num, 0] += kick
        music[start:start+num, 1] += kick

    def hat(at, volume=0.022):
        start = round(at * sample_rate)
        num = min(round(0.065 * sample_rate), n - start)
        t = np.arange(num) / sample_rate
        noise = rng.normal(0, 1, num)
        noise = noise - np.concatenate(([0.0], noise[:-1]))
        h = noise * np.exp(-t * 75) * volume
        music[start:start+num, 0] += h
        music[start:start+num, 1] += h

    # An original 120 bpm progression, with extra space for spoken words.
    bass_progression = [36, 36, 41, 43, 36, 45, 41, 43]
    for beat in range(round(TOTAL * 2)):
        at = beat / 2
        root = bass_progression[(beat // 8) % len(bass_progression)]
        if beat % 2 == 0:
            kick(at, 0.22)
        hat(at, 0.018 if beat % 4 == 0 else 0.012)
        hat(at + 0.25, 0.007)
        tone(at, 0.38, root + 12, 0.15, 0.47, "bass")
        if beat % 4 in [0, 3, 5, 6]:
            tone(at, 0.65, root + 36 + [0, 4, 7, 2][(beat // 4) % 4], 0.085, 0.30)
            tone(at + 0.02, 0.6, root + 43, 0.052, 0.70)
        if beat % 8 == 0:
            tone(at, 2.5, root + 48, 0.037, 0.25)
            tone(at, 2.5, root + 55, 0.03, 0.75)
    for scene in SCENES[1:]:
        at = scene["start"]
        tone(at, 0.42, 84, 0.12, 0.30)
        tone(at + 0.11, 0.60, 91, 0.08, 0.70)
    music[:sample_rate] *= np.linspace(0, 1, sample_rate)[:, None]
    music[-sample_rate*2:] *= np.linspace(1, 0, sample_rate * 2)[:, None]
    music *= 0.66 / max(1e-6, np.max(np.abs(music)))
    write_wav(BUILD / "music.wav", sample_rate, music)

    # Local Windows narration takes place before this function; normalize/delays in ffmpeg.
    paths = sorted((ROOT / "audio").glob("*.wav"))
    if len(paths) != len(SCENES):
        subprocess.run([sys.executable, str(ROOT / "voiceover.py")], check=True)
        paths = sorted((ROOT / "audio").glob("*.wav"))
    command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
    for file in paths:
        command += ["-i", str(file)]
    filters = []
    labels = []
    offsets = []
    for i, (file, scene) in enumerate(zip(paths, SCENES)):
        start = scene["start"] + 0.24
        with wave.open(str(file), "rb") as wav:
            length = wav.getnframes() / wav.getframerate()
        usable = scene["duration"] - (start - scene["start"]) - 0.16
        speed = max(1.0, length / usable)
        chain = f"[{i}:a]aresample={sample_rate},atempo={speed:.7f}" if speed > 1 else f"[{i}:a]aresample={sample_rate}"
        delay = round(start * 1000)
        command_label = f"v{i}"
        filters.append(chain + f",adelay={delay}|{delay}[{command_label}]")
        labels.append(f"[{command_label}]")
        offsets.append((scene["id"], start, length, speed))
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,apad=whole_dur={TOTAL:.6f}[voice]")
    filters.append(f"[music]volume=0.30[musicquiet]")
    filters.append("[musicquiet][voice]amix=inputs=2:weights=1:normalize=0,alimiter=limit=0.94,"
                   f"afade=t=in:d=0.40,afade=t=out:st={TOTAL-1.4:.3f}:d=1.4[aout]")
    command += ["-i", str(BUILD / "music.wav")]
    # music input is last; rewire the named first occurrence through the split graph.
    filters = [f.replace("[music]volume", f"[{len(paths)}:a]volume") for f in filters]
    command += ["-filter_complex", ";".join(filters), "-map", "[aout]", "-c:a", "aac", "-b:a", "192k",
                "-t", f"{TOTAL:.6f}", str(OUT / "Svinkki-soundtrack.m4a")]
    subprocess.run(command, check=True)
    for name, at, length, speed in offsets:
        print(f"VOICE {name}: {at:.2f}s, {length:.2f}s, speed×{speed:.3f}", flush=True)


def write_wav(path, rate, array):
    path.parent.mkdir(exist_ok=True)
    data = (np.clip(array, -1, 1) * 32767).astype("<i2")
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)
        wav.setframerate(rate)
        wav.writeframes(data.tobytes())


def captions():
    def stamp(seconds):
        h = int(seconds // 3600)
        m = int(seconds / 60 % 60)
        s = seconds % 60
        return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")
    rows = []
    for i, scene in enumerate(SCENES, 1):
        rows.extend([str(i), f"{stamp(scene['start'] + 0.24)} --> {stamp(scene['start'] + scene['duration'] - 0.15)}", scene["voice"], ""])
    (OUT / "Svinkki-demo.srt").write_text("\n".join(rows), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--preview", action="store_true")
    parser.add_argument("--scene", type=int, default=0)
    parser.add_argument("--audio-only", action="store_true")
    args = parser.parse_args()
    if not shutil.which("ffmpeg"):
        raise RuntimeError("FFmpeg must be on PATH")
    captions()
    if args.audio_only:
        create_audio()
        return
    renderer = Renderer()
    if args.preview:
        frames = [(SCENES[args.scene]["start"] + 1.3), (SCENES[args.scene]["start"] + SCENES[args.scene]["duration"] * 0.65)]
        for n, t in enumerate(frames):
            idx = next(i for i, s in enumerate(SCENES) if s["start"] <= t < s["start"] + s["duration"])
            image = renderer.frame(idx, t - SCENES[idx]["start"])
            image.save(OUT / f"preview-{args.scene:02d}-{n}.png")
        renderer.frame(0, 0.6).save(OUT / "Svinkki-demo-poster.png")
        print("Saved two preview frames and poster", flush=True)
        return
    paths = []
    for index in range(len(SCENES)):
        paths.append(renderer.render_scene(index))
    concat = BUILD / "concat.txt"
    concat.write_text("\n".join("file '" + str(p).replace("\\", "/").replace("'", "'\\''") + "'" for p in paths), encoding="utf-8")
    create_audio()
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(concat),
                    "-i", str(OUT / "Svinkki-soundtrack.m4a"), "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "19", "-pix_fmt", "yuv420p", "-threads", "4",
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-metadata",
                    "title=Svinkki — Your money. Your way forward.", "-t", f"{TOTAL:.6f}",
                    str(OUT / "Svinkki-demo-1080p.mp4")], check=True)
    renderer.frame(0, 0.6).save(OUT / "Svinkki-demo-poster.png")
    contact = Image.new("RGB", (1600, 900), DARK)
    for i, scene in enumerate(SCENES):
        frame = renderer.frame(i, min(scene["duration"] * 0.66, scene["duration"] - 0.1))
        frame = frame.resize((320, 180), Image.Resampling.LANCZOS)
        x, y = (i % 5) * 320, (i // 5) * 225
        contact.paste(frame, (x, y))
        ImageDraw.Draw(contact).text((x + 8, y + 184), f"{scene['start']:04.1f}s  {scene['kicker']}", font=font(13, True), fill=WHITE)
    contact.save(OUT / "Svinkki-contact-sheet.jpg", quality=92)
    print(f"DONE: {OUT / 'Svinkki-demo-1080p.mp4'}", flush=True)


if __name__ == "__main__":
    main()
