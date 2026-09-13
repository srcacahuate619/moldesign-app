# =============================================================================
# Rasteriza un PDF a PNG usando el motor de Windows (Windows.Data.Pdf).
#
# Por qué esta vía y no Poppler: este equipo no tiene `pdftoppm`, `pdftocairo`,
# Ghostscript, PyMuPDF ni pdf2image, y el sprint prohíbe instalar dependencias
# sin justificarlo. `Windows.Data.Pdf` viene con el sistema operativo, es el
# mismo motor que usa el visor de Edge, y no requiere red ni instalación.
#
# Uso:
#   powershell -File scripts/render_pdf_pages.ps1 -Pdf <ruta.pdf> -OutDir <dir> [-Scale 2]
#
# Salida: <OutDir>/<nombre>_p01.png, _p02.png, …
# =============================================================================
param(
  [Parameter(Mandatory = $true)][string]$Pdf,
  [Parameter(Mandatory = $true)][string]$OutDir,
  [int]$Scale = 2
)

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Runtime.WindowsRuntime | Out-Null

# WinRT expone IAsyncOperation<T>; .NET necesita convertirlo a Task<T> para
# poder esperarlo de forma síncrona. Sin este puente, cada llamada devolvería
# un objeto asíncrono a medio resolver.
$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
  Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1'
  })[0]

function Await-Op($op, $tipo) {
  $asTask = $asTaskGeneric.MakeGenericMethod($tipo)
  $task = $asTask.Invoke($null, @($op))
  $task.Wait(-1) | Out-Null
  $task.Result
}

# `RenderToStreamAsync` devuelve IAsyncAction (sin resultado), y su `AsTask` es
# otra sobrecarga distinta de la genérica de arriba. Se resuelve por reflexión
# igual: dejar que PowerShell elija la sobrecarga falla con
# "no se encuentra ninguna sobrecarga para AsTask".
$asTaskAction = ([System.WindowsRuntimeSystemExtensions].GetMethods() |
  Where-Object {
    $_.Name -eq 'AsTask' -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.FullName -eq 'Windows.Foundation.IAsyncAction'
  })[0]

function Await-Action($action) {
  $task = $asTaskAction.Invoke($null, @($action))
  $task.Wait(-1) | Out-Null
}

[Windows.Storage.StorageFile, Windows.Storage, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Pdf.PdfDocument, Windows.Data.Pdf, ContentType = WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType = WindowsRuntime] | Out-Null

$rutaPdf = (Resolve-Path $Pdf).Path
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir -Force | Out-Null }
$base = [System.IO.Path]::GetFileNameWithoutExtension($rutaPdf)

$archivo = Await-Op ([Windows.Storage.StorageFile]::GetFileFromPathAsync($rutaPdf)) ([Windows.Storage.StorageFile])
$doc = Await-Op ([Windows.Data.Pdf.PdfDocument]::LoadFromFileAsync($archivo)) ([Windows.Data.Pdf.PdfDocument])

Write-Output "$base : $($doc.PageCount) paginas"

for ($i = 0; $i -lt $doc.PageCount; $i++) {
  $pagina = $doc.GetPage([uint32]$i)
  $opciones = New-Object Windows.Data.Pdf.PdfPageRenderOptions
  $opciones.DestinationWidth = [uint32]([Math]::Round($pagina.Size.Width * $Scale))

  $stream = New-Object Windows.Storage.Streams.InMemoryRandomAccessStream
  Await-Action ($pagina.RenderToStreamAsync($stream, $opciones))

  $destino = Join-Path $OutDir ("{0}_p{1:d2}.png" -f $base, ($i + 1))
  $lector = New-Object Windows.Storage.Streams.DataReader($stream.GetInputStreamAt(0))
  Await-Op ($lector.LoadAsync([uint32]$stream.Size)) ([uint32]) | Out-Null
  $bytes = New-Object byte[] $stream.Size
  $lector.ReadBytes($bytes)
  [System.IO.File]::WriteAllBytes($destino, $bytes)
  $lector.Dispose()
  $stream.Dispose()
  # `PdfPage` implementa IDisposable, no `Close()`.
  if ($pagina -is [System.IDisposable]) { $pagina.Dispose() }

  Write-Output ("  {0}  ({1} bytes)" -f (Split-Path $destino -Leaf), $bytes.Length)
}
