# Actividad-3-Primera-parcial

## Actividad 3

Aplicación de escritorio para Windows. La interfaz está implementada con
Tkinter y los métodos Simplex, Gran M y Dos Fases se ejecutan con el solver
manual de `app.py`; no se usan bibliotecas de optimización.

### Ejecutar desde Python

Requiere Python 3.10 o posterior con Tcl/Tk. Desde la carpeta del proyecto:

```powershell
python app.py
```

### Pruebas

```powershell
python -m unittest discover -s tests -v
```

### Compilar instalador de Windows x64

Instala Inno Setup 6 y asegúrate de que `ISCC.exe` esté en `PATH` o en la
carpeta estándar de instalación. El script también detecta el compilador en
`build\tools\Inno Setup 6\ISCC.exe`. Luego ejecuta:

```powershell
powershell -ExecutionPolicy Bypass -File .\build.ps1
```

El script instala PyInstaller desde `requirements-build.txt`, corre las
pruebas, crea una aplicación independiente con ventana y genera
`build\installer\Actividad3-Setup-x64.exe`. El instalador crea accesos
directos en el escritorio y en el menú Inicio. El equipo de destino no necesita
Python.