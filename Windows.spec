# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['Windows.py'],
    pathex=[],
    binaries=[('C:/Program Files/Tesseract-OCR/tesseract.exe', 'Tesseract-OCR')],
    datas=[
        ('uploads', 'uploads'),
        ('processed', 'processed'), 
        ('unrenamed', 'unrenamed'),
        ('templates/*.html', 'templates'),  # Inclure les templates
        ('static/css/*', 'static/css')     # Inclure les fichiers CSS
    ],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='Nomminator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
app = BUNDLE(
    exe,
    name='Nomminator.app',
    icon=None,
    bundle_identifier=None,
)
