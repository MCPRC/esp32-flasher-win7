# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_all

datas, binaries, hiddenimports = collect_all('esptool')
a = Analysis(['app.py'], pathex=[], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports + ['serial.tools.list_ports_windows'],
             hookspath=[], runtime_hooks=[], excludes=[], noarchive=False)

# Use Microsoft's redistributable UCRT, never the build OS's system DLLs.
# Override this path with UCRT_REDIST when using a different Windows SDK.
sdk = Path(os.environ.get('UCRT_REDIST',
    r'C:\Program Files (x86)\Windows Kits\10\Redist\10.0.22621.0\ucrt\DLLs\x86'))
if not (sdk / 'ucrtbase.dll').is_file():
    raise RuntimeError('Install Windows SDK UCRT x86 redistributables or set UCRT_REDIST')
a.binaries = [entry for entry in a.binaries
              if not (Path(entry[0]).name.lower().startswith('api-ms-win-')
                      or Path(entry[0]).name.lower() == 'ucrtbase.dll')]
a.binaries += [(p.name, str(p), 'BINARY') for p in sorted(sdk.glob('*.dll'))]
pyz = PYZ(a.pure, a.zipped_data)
exe = EXE(pyz, a.scripts, a.binaries, a.zipfiles, a.datas, [],
          name='ESP32_Flasher_Win7', console=False, debug=False,
          strip=False, upx=False, disable_windowed_traceback=False)
