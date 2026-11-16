# Delivery and rebuild status

The definitive final renderer is `production/final_render.py`.

```bash
python production/final_render.py
python production/verify.py
```

The final video is `output/Svinkki-demo-1080p.mp4`. It is 107.1 seconds, with original narration and electronic music.

## Renderer history
- `production/render.py`: scene composition, audio generation, subtitle and image helpers.
- `production/story.py`: definitive scene text, duration, screen selection and voice.
- `production/voiceover.py`: local Windows narration, with four concurrent synthesis workers.
- `production/final_render.py`: final corrected phone compositing, single-alpha phone outline and full-ratio app screenshots. It uses the validated scene/sound helpers in `render.py`.
- `production/verify.py`: stream inspection, complete decode, audio levels and extracted frames.

Two intermediate `corrected_render.py`/experimental scripts are not the build entry point. Treat the documented `final_render.py` entry point as authoritative.

## Motion / UI correctness
- The complete phone rotates gently into side-view style angles and scales; no opaque sk_ewed geometry is laid over the UI.
- App screen aspect ratio is retained and most of each screen is visible. Small central zooms provide camera movement without fabricating interactions.
- The supplied product screenshots are the only UI imagery. Nothing inside the app is rewritten or invented.
- The UI is shown as a synthetic-data hackathon prototype. No native phone-widget or production S-mobiili claim is made.
- The video's small top-left Vinkki icon is a simplified flowing decorative S motif, not the official S-Bank symbol. Actual branded UI only appears untouched inside the phone.

## Sound
Windows Hazel is the synthetic voice. Initial scene audio is narrated at Rate 3 with precise speed fitting up to ~4% so it lands inside the scene cut. The complete 107.1-second H.264/AAC video has 48 kHz stereo audio and comfortable headroom.

## Prior export
A completed first render was produced before phone compositing was improved. The current final-cut process replaces it in-place once the corrected version is ready. A separate sound-only master `Svinkki-soundtrack.m4a` is preserved while rebuilding visuals.
