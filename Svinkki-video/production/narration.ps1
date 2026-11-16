param(
  [Parameter(Mandatory=$true)][string]$Text,
  [Parameter(Mandatory=$true)][string]$Output,
  [int]$Rate = 2
)
$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.Rate = $Rate
$synth.Volume = 100
$synth.SelectVoice("Microsoft Hazel Desktop")
$synth.SetOutputToWaveFile($Output)
$synth.Speak($Text)
$synth.Dispose()
