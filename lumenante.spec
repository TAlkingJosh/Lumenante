# lumenante.spec
import sys
from pathlib import Path

# This file tells PyInstaller how to build your application.

# This function helps find the correct path for data files,
# especially when the script is bundled into a one-file exe.
def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = Path(__file__).resolve().parent

    return str(Path(base_path) / relative_path)

# The block_cipher must be defined at the top before it is used.
# For most applications, encryption is not needed, so we set it to None.
block_cipher = None

a = Analysis(
    ['lumenante_main.py'],
    pathex=[],
    binaries=[],
    # --- THIS IS THE MOST IMPORTANT PART ---
    # This list tells PyInstaller what non-Python files to include.
    # The format is a list of tuples: `('source_path', 'destination_in_build')`
    datas=[
        ('themes', 'themes'),          # Copy the 'themes' folder to a 'themes' folder in the build
        ('plugins', 'plugins'),        # Copy the 'plugins' folder to a 'plugins' folder in the build
        ('splash_logo.png', '.'),      # Copy splash_logo.png to the root of the build folder
        ('app_icon.ico', '.')          # Copy app_icon.ico to the root
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='lumenante',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,           # Set to False for a GUI application (no console window)
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # This is where you set the .exe icon.
    icon='app_icon.ico',
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='lumenante',
)