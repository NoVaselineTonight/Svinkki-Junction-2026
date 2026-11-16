# Svinkki demo-video

## Play the finished video

**`output/Svinkki-demo-1080p.mp4`**

- Full HD: 1920 × 1080, 30 fps
- Runtime: about 1 minute 49 seconds
- H.264 video, AAC stereo audio
- English narration, embedded English captions and original electronic music
- Includes a Finnish product moment

## Other outputs

- `output/Svinkki-demo-poster.png` — cover image
- `output/Svinkki-demo.srt` — editable subtitles
- `output/Svinkki-contact-sheet.jpg` — every scene at a glance
- `output/Svinkki-soundtrack.m4a` — separate narration + music mix

## Creative approach

A personal coach, not a technical demo. The key sequence shows an everyday question becoming a Japan savings plan and then a reusable home-page widget. Veeti's and Joonas's differing advice makes personalisation visible. The video finishes with advice becoming action.

## Rebuild

The production scripts are in `production/`. Original screenshots in the parent folder and the GitHub repository are never modified.

Dependencies already available on this machine:

- Python 3.13 with Pillow and NumPy
- FFmpeg on PATH
- Windows PowerShell with `Microsoft Hazel Desktop` voice

Commands:

```bash
# Render all visuals, original music and narration, and assemble the MP4
python production/render.py

# Regenerate speech only (called automatically when missing)
python production/voiceover.py

# Generate only the final audio mix, using existing speech files
python production/render.py --audio-only

# Render preview stills of the widget scene (index 6)
python production/render.py --preview --scene 6
```

Edit `production/story.py` for the shot list, wording, timing, screenshots and framing. `production/render.py` controls typography, composition, camera moves and audio mixing. Fast render settings are used for individual scenes; the final assembled video is re-encoded at H.264 quality 19 for smaller, clean, viewable output.

## Audio note

Narration is a local synthetic Windows voice, not a human spokesperson. It is intentionally energetic and clean, with more headroom around each spoken line. You can replace individual WAV files in `production/audio/` and run the audio-only command above. Music is synthesized from scratch by `production/render.py`, with no stock-music licences or downloaded audio required.

## Script

See [`SCRIPT.md`](SCRIPT.md) for the creative direction. The definitive text includes small pacing edits in [`production/story.py`](production/story.py). The old technical-heavy pitch is not used.

## Accuracy

All app screens are supplied screenshots of the working app on synthetic data. The motion treatment does not simulate taps, invent calculations, or alter the UI within a screen. An app-only widget cannot be confused with a native Android/iOS home-screen widget. S-mobiili is identified as the intended host direction in the script; it is not falsely presented as a production banking integration.

## Validation

`production/verify.py` uses `ffprobe`/`ffmpeg` to inspect duration, video/audio streams, decode health and audio levels. Export frames are saved under `output/review/` for a final visual check.
