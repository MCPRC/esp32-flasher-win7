"""Separate process keeps esptool output and cancellation away from Tk."""
import sys


def restore_redirected_streams():
    """Windowed frozen applications have no Python stdout, even with a pipe."""
    if sys.platform != 'win32' or sys.stdout is not None:
        return
    import ctypes
    import io
    import msvcrt
    import os
    from ctypes import wintypes
    get_handle = ctypes.windll.kernel32.GetStdHandle
    get_handle.argtypes = [wintypes.DWORD]
    get_handle.restype = wintypes.HANDLE
    handle = get_handle(wintypes.DWORD(-11))
    if handle in (None, 0, ctypes.c_void_p(-1).value):
        raise RuntimeError('Flash worker did not receive its output pipe')
    fd = msvcrt.open_osfhandle(handle, os.O_WRONLY | os.O_BINARY)
    sys.stdout = io.open(fd, 'w', encoding='utf-8', errors='replace', buffering=1)
    sys.stderr = sys.stdout


def main(args=None):
    restore_redirected_streams()
    import esptool
    try:
        esptool.main(sys.argv[1:] if args is None else args)
    except esptool.FatalError as exc:
        print('A fatal error occurred: %s' % exc, file=sys.stderr, flush=True)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print('Flash cancelled.', file=sys.stderr, flush=True)
        raise SystemExit(130)
    except Exception:
        import traceback
        traceback.print_exc()
        raise SystemExit(1)


if __name__ == '__main__':
    main()
