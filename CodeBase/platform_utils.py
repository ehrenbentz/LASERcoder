"""Platform-specific fullscreen helpers."""
import sys
import ctypes
import ctypes.util


def _get_nsapp():
    """Get the NSApplication shared instance via the Objective-C runtime."""
    objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
    objc.objc_getClass.restype = ctypes.c_void_p
    objc.sel_registerName.restype = ctypes.c_void_p
    objc.objc_msgSend.restype = ctypes.c_void_p
    objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]

    NSApp = objc.objc_msgSend(
        objc.objc_getClass(b"NSApplication"),
        objc.sel_registerName(b"sharedApplication"),
    )
    return objc, NSApp


def enter_fullscreen_platform():
    """Hide dock and menu bar on macOS. No-op on other platforms."""
    if sys.platform != "darwin":
        return
    try:
        objc, NSApp = _get_nsapp()
        # NSApplicationPresentationAutoHideDock = 1
        # NSApplicationPresentationAutoHideMenuBar = 4
        sel = objc.sel_registerName(b"setPresentationOptions:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulonglong,
        ]
        objc.objc_msgSend(NSApp, sel, 1 | 4)
    except Exception:
        pass


def exit_fullscreen_platform():
    """Restore dock and menu bar on macOS. No-op on other platforms."""
    if sys.platform != "darwin":
        return
    try:
        objc, NSApp = _get_nsapp()
        # NSApplicationPresentationDefault = 0
        sel = objc.sel_registerName(b"setPresentationOptions:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulonglong,
        ]
        objc.objc_msgSend(NSApp, sel, 0)
    except Exception:
        pass
