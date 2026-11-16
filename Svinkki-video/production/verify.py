from pathlib import Path
import json
import subprocess
from story import TOTAL

ROOT = Path(__file__).resolve().parent.parent
FILE = ROOT / "output" / "Svinkki-demo-1080p.mp4"
report = json.loads(subprocess.check_output([
    "ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate:stream=index,codec_name,codec_type,width,height,avg_frame_rate,sample_rate,channels,duration",
    "-of", "json", str(FILE)
], text=True))
print(json.dumps(report, indent=2))
format_data = report["format"]
assert 107.0 < float(format_data["duration"]) < 120.0, "Must be comfortably under 2 minutes"
video = [s for s in report["streams"] if s["codec_type"] == "video"][0]
audio = [s for s in report["streams"] if s["codec_type"] == "audio"][0]
assert video["width"] == 1920 and video["height"] == 1080
assert video["avg_frame_rate"] == "30/1"
assert video["codec_name"] == "h264"
assert audio["codec_name"] == "aac"
assert audio["channels"] == 2
result = subprocess.run(["ffmpeg", "-v", "error", "-i", str(FILE), "-f", "null", "-"], capture_output=True, text=True)
assert result.returncode == 0 and not result.stderr, result.stderr
print("Full decode: OK; no errors")
levels = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(FILE), "-af", "volumedetect", "-t", "30", "-f", "null", "-"], capture_output=True, text=True)
print("\n".join(line for line in levels.stderr.splitlines() if "mean_volume" in line or "max_volume" in line))
assert "mean_volume" in levels.stderr and "-inf dB" not in levels.stderr, "Audio is silent"
review = ROOT / "output" / "review"
review.mkdir(exist_ok=True)
subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(FILE), "-vf", "fps=1/9,scale=640:-1,tile=4x3", "-frames:v", "1", str(review / "export-contact-sheet.jpg")], check=True)
for f, time in [("start", 1), ("widget", 49), ("finnish", 78), ("end", 103)]:
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(time), "-i", str(FILE), "-frames:v", "1", str(review / f"{f}.png")], check=True)
print(f"Validation complete: {FILE}")
print(f"Size: {int(format_data['size'])/1024/1024:.1f} MiB")
