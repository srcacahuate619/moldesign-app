# Genera las 20 frases del guion con la voz española de Windows (16 kHz, mono, 16 bits).
#
# SÓLO para probar la cadena y dar una cota optimista: una voz sintética no tiene
# acento, ruido ni titubeos. La medida que vale es la de `grabar.md`.
#
# Uso: powershell -File sintetizar.ps1 -Salida D:\moldesign-dev-data\molchat-lab\dictado\sintetico
param([Parameter(Mandatory = $true)][string]$Salida)

Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Force -Path $Salida | Out-Null
$frases = & python -c "import sys, json; sys.path.insert(0, r'$PSScriptRoot'); from guion import FRASES; print(json.dumps(FRASES))" | ConvertFrom-Json
$formato = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo(16000, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
$voz = New-Object System.Speech.Synthesis.SpeechSynthesizer
$voz.SelectVoice("Microsoft Sabina Desktop")
foreach ($f in $frases) {
    $voz.SetOutputToWaveFile((Join-Path $Salida "$($f[0]).wav"), $formato)
    $voz.Speak($f[1])
}
$voz.SetOutputToNull()
"$($frases.Count) frases en $Salida"
