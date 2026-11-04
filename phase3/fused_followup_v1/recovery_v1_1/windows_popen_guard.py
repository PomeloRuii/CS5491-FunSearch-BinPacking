"""Normalize Python's Windows Popen audit event without starting a process.

Python3.10 Windows emits executable=None and a list2cmdline string for ordinary
shell=False list invocations. Parse with Windows' own API; reject noncanonical
or unrecognized forms rather than weakening the Docker-only fail-closed guard.
API: https://learn.microsoft.com/en-us/windows/win32/api/shellapi/nf-shellapi-commandlinetoargvw
"""
import ctypes
import os
from pathlib import Path
import subprocess
import sys


def split_windows(command):
    if sys.platform!='win32':raise PermissionError('Windows command-line form on unsupported platform')
    if not isinstance(command,str) or not command or command[0].isspace() or '\0' in command:
        raise PermissionError('Empty/ambiguous Windows command line')
    shell=ctypes.WinDLL('shell32',use_last_error=True)
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    parse=shell.CommandLineToArgvW
    parse.argtypes=[ctypes.c_wchar_p,ctypes.POINTER(ctypes.c_int)]
    parse.restype=ctypes.POINTER(ctypes.c_wchar_p)
    free=kernel.LocalFree;free.argtypes=[ctypes.c_void_p];free.restype=ctypes.c_void_p
    count=ctypes.c_int();pointer=parse(command,ctypes.byref(count))
    if not pointer:raise PermissionError('Windows command-line parsing failed')
    try:args=[pointer[i] for i in range(count.value)]
    finally:free(ctypes.cast(pointer,ctypes.c_void_p))
    # The sealed controller uses Python list invocations. Require precisely that
    # canonical representation; no shell interpretation or custom loose parser.
    if subprocess.list2cmdline(args)!=command:
        raise PermissionError('Noncanonical command line outside sealed controller contract')
    return args


def validate_popen(executable,arguments,expected_docker):
    if isinstance(arguments,str):args=split_windows(arguments)
    elif isinstance(arguments,(list,tuple)):args=list(arguments)
    else:raise PermissionError('Unsupported process argument form')
    if len(args)<2 or any(not isinstance(a,str) or '\0' in a for a in args):
        raise PermissionError('Malformed process arguments')
    def identity(value):
        if not isinstance(value,(str,os.PathLike)) or not str(value) or not Path(value).is_absolute():
            raise PermissionError('Explicit absolute Docker executable required')
        return os.path.normcase(str(Path(value).resolve()))
    expected=identity(expected_docker)
    # None is valid on Windows: CreateProcess then uses the first command token.
    if identity(args[0])!=expected or executable is not None and identity(executable)!=expected:
        raise PermissionError('Process executable is not the resolved controller Docker CLI')
    if args[1] not in ('info','image','create','inspect','start','kill','rm','ps'):
        raise PermissionError('Docker operation outside existing controller allowlist')
    if args[1]=='image' and (len(args)<3 or args[2]!='inspect'):
        raise PermissionError('Only image inspect is permitted')
    return args
