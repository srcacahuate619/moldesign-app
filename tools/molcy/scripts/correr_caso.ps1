param(
    [Parameter(Mandatory=$true)][string]$Pdb,
    [Parameter(Mandatory=$true)][string]$Sufijo,
    [Parameter(Mandatory=$true)][string]$Carpeta,
    [string]$Formato = 'biblioteca',
    [ValidateSet('cpu','gpu')][string]$Renderizador = 'gpu',
    # El guion x conserva su sujeto de busqueda. Para sitio_activo, MolDesign
    # puede pasar pose_evaluada o receptor_solo; el valor por defecto mantiene
    # la interfaz original con ligando_cocristal.
    [string]$Guion = 'sitio_activo',
    [string]$Sujeto = 'ligando_cocristal',
    # La interfaz pasa las dos rutas desde `nucleo/rutas.py`. Los valores por
    # defecto son para lanzarlo a mano (Root: la carpeta padre de scripts\).
    [string]$Root = '',
    # Sin ruta fija: MolDesign pasa -Blender; a mano, la variable MOLCY_BLENDER.
    [string]$Blender = $env:MOLCY_BLENDER,
    [string]$Python = 'python',
    # JSON con los mandos de la interfaz (variables/controles.py). Vacio =
    # produccion tal cual.
    [string]$Ajustes = '',
    # Solo QC + .blend + acta, sin render (validacion barata).
    [switch]$SoloConstruir
)
# Codigos de salida: 0 = OK, 1 = FALLO, 3 = OMITIDO (el MP4 ya existia).
$ErrorActionPreference = 'Continue'
# En PowerShell 5.1 `$PSScriptRoot` aun esta vacio al evaluar los valores por
# defecto del param(): se resuelve aqui.
if (-not $Root) { $Root = Split-Path -Parent $PSScriptRoot }
$addon = 'bl_ext.blender_org.molecularnodes'
$estado = Join-Path $Carpeta '_molcy_estado.log'
# Log y marca de fallo PROPIOS de este job. Antes eran uno por caso
# (`v4_run.log`, `FALLO_v4.txt`) y dos formatos del mismo receptor leian las
# lineas del otro: un ENCODE_VERIFICADO ajeno daba por buena una codificacion,
# y el arranque de uno borraba el FALLO del otro.
$log = "$Carpeta\run_${Formato}_$Sufijo.log"
$marcaFallo = "$Carpeta\FALLO_${Formato}_$Sufijo.txt"
$render = "$Carpeta\render_${Formato}_$Sufijo"
$over = "$Carpeta\render_${Formato}_${Sufijo}_titulo"
$mp4 = "$Carpeta\${Pdb}_${Guion}_${Formato}_$Sufijo.mp4"
$build = "$Carpeta\build_${Formato}_$Sufijo.json"
$maestro = Join-Path $Root 'scripts\maestro.py'
$codificar = Join-Path $Root 'scripts\salida\codificar.py'
$sellar = Join-Path $Root 'scripts\salida\sellar_mp4.py'
$postcheck = Join-Path $Root 'scripts\salida\postcheck_nitidez.py'

function Estado($m) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') [$Pdb/$Formato/$Sufijo] $m" | Out-File -FilePath $estado -Append -Encoding utf8
}
function Log($m) {
    "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') $m" | Out-File -FilePath $log -Append -Encoding utf8
}
function Fallo($motivo) {
    "FALLO $Pdb | $Formato | $Sufijo | $motivo | $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" |
        Out-File -FilePath $marcaFallo -Encoding utf8
    Log "FALLO $motivo"
    Estado "FALLO $motivo"
    exit 1
}
function Lineas() { return (Get-Content $log -ErrorAction SilentlyContinue | Measure-Object).Count }
function Nuevas($desde) { return @(Get-Content $log -ErrorAction SilentlyContinue | Select-Object -Skip $desde) }

Estado 'INICIO'
Remove-Item $marcaFallo -ErrorAction SilentlyContinue
if ((-not $Blender) -or (-not (Test-Path $Blender))) { Fallo "SIN_BLENDER($Blender)" }
# Un video existente nunca se pisa: se omite antes de gastar un render.
if ((-not $SoloConstruir) -and (Test-Path $mp4)) {
    Log 'VIDEO_YA_EXISTE: no se sobrescribe (usa otro --sufijo)'
    Estado 'OMITIDO video ya existe'
    exit 3
}
Log 'RUN_START'
$antes = Lineas
$extra = @()
if ($SoloConstruir) { $extra += @('--solo-construir') }
if ($Ajustes) {
    if (-not (Test-Path $Ajustes)) { Fallo "SIN_AJUSTES($Ajustes)" }
    $extra += @('--ajustes', $Ajustes)
}
& $Blender -b --factory-startup --addons $addon --python $maestro -- $Pdb --guion $Guion --sujeto $Sujeto --formato $Formato --renderizador $Renderizador --sufijo $Sufijo --experimental-look @extra *>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$codigo = $LASTEXITCODE
$nuevas = Nuevas $antes
if ($nuevas | Select-String -Pattern 'QC_ABORTADO' -Quiet) { Fallo 'QC_ABORTADO' }
if ($codigo -ne 0) { Fallo ("MAESTRO_EXIT_" + $codigo) }
if ($nuevas | Select-String -Pattern 'Traceback' -Quiet) { Fallo 'TRACEBACK_MAESTRO' }

if ($SoloConstruir) {
    if (-not ($nuevas | Select-String -Pattern 'CONSTRUIDO_OK' -Quiet)) { Fallo 'SIN_CONSTRUIDO_OK' }
    Log 'RUN_DONE (solo construir)'
    Estado 'OK solo construir'
    exit 0
}

# El acta final solo existe si el render termino: mientras rinde se llama
# `.parcial.json`. Resolucion, fps y fotogramas salen de ella y no de una tabla
# repetida aqui, que se desincronizaba con cada formato nuevo.
if (-not (Test-Path $build)) { Fallo 'SIN_ACTA_FINAL' }
try {
    $acta = Get-Content $build -Raw -Encoding UTF8 | ConvertFrom-Json
    # Con pausas, el video tiene mas fotogramas que PNG: una pausa repite uno ya
    # rendido. Lo que tiene que haber en disco son los fotogramas distintos.
    $esperados = if ($null -ne $acta.fotogramas_render_unicos) { [int]$acta.fotogramas_render_unicos } else { [int]$acta.fotogramas }
    $fps = [int]$acta.formato.fps
    $ancho = [int]$acta.formato.ancho
    $alto = [int]$acta.formato.alto
} catch { Fallo 'ACTA_ILEGIBLE' }
$pngs = if (Test-Path $render) { (Get-ChildItem "$render\*.png" -ErrorAction SilentlyContinue).Count } else { 0 }
if ($pngs -lt $esperados) { Fallo "MAESTRO_SIN_RENDER($pngs/$esperados)" }
Estado 'MAESTRO_OK'

# El cierre de marca: se rinde la primera vez por formato (unos minutos) y se
# reutiliza mientras su huella no cambie. Es OBLIGATORIO en todo video: no hay
# interruptor que lo quite, y un acta que no lo declare (cierre_s < 3 s) no se
# codifica ni se entrega.
$idioma = if ($env:MOLCY_IDIOMA -ceq 'en') { 'en' } else { 'es' }
$cierreDir = ''
$cierreManifiesto = ''
$cierreS = 0.0
try { $cierreS = [double]$acta.formato.cierre_s } catch { $cierreS = 0.0 }
if ($cierreS -lt 3.0) { Fallo 'SIN_CIERRE' }
if ($cierreS -gt 0) {
    $cierreDir = if ($env:MOLCY_BRAND_CACHE_DIR) {
        Join-Path $env:MOLCY_BRAND_CACHE_DIR "${Formato}_${Renderizador}_${idioma}"
    } else {
        Join-Path $Root "moldesign\assets\marca\cierre\${Formato}_${Renderizador}_${idioma}"
    }
    $antes = Lineas
    & $Blender -b --factory-startup --python (Join-Path $Root 'scripts\marca\cierre.py') -- --formato $Formato --renderizador $Renderizador --salida $cierreDir --si-falta *>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
    $nuevas = Nuevas $antes
    if (-not ($nuevas | Select-String -Pattern 'CIERRE_AL_DIA|CIERRE_LISTO' -Quiet)) { Fallo 'CIERRE_FALLO' }
    $cierreManifiesto = Join-Path $cierreDir 'manifiesto.json'
    Estado 'CIERRE_OK'
}

$antes = Lineas
$argsCodificar = @($render, $mp4, $fps, 0, 0)
if ((Test-Path $over) -and ((Get-ChildItem "$over\*.png" -ErrorAction SilentlyContinue).Count -ge 1)) {
    # Halo y placa oscura detras de cada etiqueta, en la capa (nunca en la escena).
    & $Python (Join-Path $Root 'scripts\salida\contraste.py') $over $build *>&1 |
        Out-File -FilePath $log -Append -Encoding utf8
    if ($LASTEXITCODE -ne 0) { Fallo 'CONTRASTE_FALLO' }
    $argsCodificar += $over
} else {
    Log 'SIN_CAPA_TITULO'
}
if (-not $cierreDir -or -not $cierreManifiesto) { Fallo 'SIN_CIERRE' }
$argsCodificar += @('--cierre', $cierreDir)
& $Blender -b --factory-startup --python $codificar -- @argsCodificar *>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
$codigo = $LASTEXITCODE
$nuevas = Nuevas $antes
if ($codigo -ne 0) { Fallo ("CODIFICAR_EXIT_" + $codigo) }
if ($nuevas | Select-String -Pattern 'Traceback|ENCODE_MAL|ENCODE_SIN_VERIFICAR|NO_SOBREESCRIBO' -Quiet) { Fallo 'CODIFICAR_FALLO' }
if (-not (Test-Path $mp4)) { Fallo 'SIN_MP4' }
if (-not ($nuevas | Select-String -Pattern 'ENCODE_VERIFICADO' -Quiet)) { Fallo 'ENCODE_SIN_VERIFICAR' }
Estado 'ENCODE_OK'

$argsSellar = @($mp4, $build, '--cierre', $cierreManifiesto)
& $Python $sellar @argsSellar *>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { Fallo ("SELLAR_EXIT_" + $LASTEXITCODE) }
if (Test-Path "${mp4}.sha256") { Log 'SELLO_OK' } else { Fallo 'SELLO_FALLO' }

# Nitidez del titulo en el video final (no fatal): a mitad de su ventana.
$cuadro = 60
if ($acta.capa_titulo -and $acta.capa_titulo.cuadro_nitidez) {
    $cuadro = [int]$acta.capa_titulo.cuadro_nitidez
} elseif ($acta.capa_titulo -and $acta.capa_titulo.ventana) {
    $cuadro = [int](($acta.capa_titulo.ventana[0] + $acta.capa_titulo.ventana[1]) / 2)
}
& $Blender -b --factory-startup --python $postcheck -- $mp4 $cuadro $ancho $alto *>&1 |
    Out-File -FilePath $log -Append -Encoding utf8
Log 'RUN_DONE'
Estado 'OK'
exit 0
