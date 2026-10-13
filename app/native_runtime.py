"""Prefer installed Windows CRT over old Conda DLLs, without modifying either."""
import os
import sys
from pathlib import Path

_handles = []
if os.name == 'nt' and (Path(sys.base_prefix)/'conda-meta').is_dir():
    import ctypes
    buffer = ctypes.create_unicode_buffer(32768)
    if not ctypes.windll.kernel32.GetSystemDirectoryW(buffer, len(buffer)):
        raise OSError('Cannot resolve Windows system directory')
    for name in ('msvcp140.dll', 'vcruntime140_1.dll'):
        _handles.append(ctypes.WinDLL(str(Path(buffer.value)/name)))
