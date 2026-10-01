$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ProjectRoot

try {
    $Architecture = python -c "import struct; print(struct.calcsize('P') * 8)"
    if ($LASTEXITCODE -ne 0 -or $Architecture.Trim() -ne "64") {
        throw "La compilación requiere Python de 64 bits."
    }

    python -m unittest discover -s tests -v
    if ($LASTEXITCODE -ne 0) {
        throw "Fallaron las pruebas; se cancela la compilación."
    }

    python -m pip install -r requirements-build.txt
    if ($LASTEXITCODE -ne 0) {
        throw "No se pudieron instalar las dependencias de compilación."
    }

    $BuildRoot = Join-Path $ProjectRoot "build"
    $DistPath = Join-Path $BuildRoot "dist"
    $WorkPath = Join-Path $BuildRoot "pyinstaller-work"
    New-Item -ItemType Directory -Force -Path $DistPath, $WorkPath | Out-Null

    python -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name Actividad3 --distpath $DistPath --workpath $WorkPath `
        --specpath $BuildRoot (Join-Path $ProjectRoot "app.py")
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller no pudo crear la aplicación de escritorio."
    }

    $Compiler = Get-Command ISCC.exe -ErrorAction SilentlyContinue
    if (-not $Compiler) {
        $Candidates = @(
            (Join-Path $BuildRoot "tools\Inno Setup 6\ISCC.exe"),
            "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe",
            "$env:ProgramFiles\Inno Setup 6\ISCC.exe"
        )
        $CompilerPath = $Candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    } else {
        $CompilerPath = $Compiler.Source
    }

    if (-not $CompilerPath) {
        throw "No se encontro ISCC.exe. Instala Inno Setup 6 y vuelve a ejecutar build.ps1."
    }

    & $CompilerPath (Join-Path $ProjectRoot "installer.iss")
    if ($LASTEXITCODE -ne 0) {
        throw "Inno Setup no pudo generar el instalador."
    }

    Write-Host "Instalador generado: build\installer\Actividad3-Setup-x64.exe"
}
finally {
    Pop-Location
}