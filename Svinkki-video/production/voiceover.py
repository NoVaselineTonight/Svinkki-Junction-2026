from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import subprocess
import wave
from story import SCENES, ROOT

POWERSHELL = r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe"
(ROOT / "audio").mkdir(exist_ok=True)


def generate(item):
    i, scene = item
    output = ROOT / "audio" / f"{i:02d}-{scene['id']}.wav"
    command = (
        "$ErrorActionPreference = 'Stop'; Add-Type -AssemblyName System.Speech; "
        "$s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        "$s.Rate = 3; $s.Volume = 100; $s.SelectVoice('Microsoft Hazel Desktop'); "
        f"$s.SetOutputToWaveFile('{output}'); $speak = @'\n{scene['voice']}\n'@; "
        "$s.Speak($speak); $s.Dispose()"
    )
    result = subprocess.run([POWERSHELL, "-NoProfile", "-NonInteractive", "-Command", command], capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(f"Narration {i} failed: {result.stderr}")
    with wave.open(str(output), "rb") as wav:
        length = wav.getnframes() / wav.getframerate()
    status = "OK" if length <= scene["duration"] - 0.22 else "SPEED UP"
    print(f"{status:8s} {scene['id']}: scene {scene['duration']:.1f}s; voice {length:.2f}s", flush=True)


if __name__ == "__main__":
    with ThreadPoolExecutor(max_workers=4) as executor:
        list(executor.map(generate, enumerate(SCENES)))
