import os
import sys
import ctypes
import ctypes.util


# Shipped beside the executable in portable packages only
PORTABLE_MARKER = "portable.txt"


def portable_dir():
    """Return the application folder for a portable package, else None.

    A portable package keeps its settings and logs in its own folder so
    it can run from an external drive without writing to the host. App
    bundles must stay unmodified, so macOS never runs in this mode.
    """
    if sys.platform == "darwin":
        return None
    if getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS"):
        app_dir = os.path.dirname(sys.executable)
    elif "__compiled__" in globals():
        app_dir = os.path.dirname(os.path.abspath(sys.argv[0]))
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))
    if os.path.isfile(os.path.join(app_dir, PORTABLE_MARKER)):
        return app_dir
    return None


def _get_nsapp():
    """Get the NSApplication shared instance via the Objective-C runtime"""
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
    """Hide dock and menu bar on macOS. No-op on other platforms"""
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


def is_network_drive(path):
    """Check if a path is on a network drive.

    Returns True for SMB/CIFS/NFS/sshfs mounts.
    Returns False for local drives and on detection failure.
    """
    try:
        path = os.path.realpath(path)
    except (OSError, ValueError):
        return False

    if sys.platform == "win32":
        try:
            # UNC paths are always network
            if path.startswith("\\\\"):
                return True
            # GetDriveTypeW returns 4 for DRIVE_REMOTE
            drive = os.path.splitdrive(path)[0]
            if drive:
                drive_with_slash = drive + "\\"
                return ctypes.windll.kernel32.GetDriveTypeW(drive_with_slash) == 4
        except Exception:
            pass
        return False

    if sys.platform == "darwin":
        try:
            import subprocess
            result = subprocess.run(
                ["mount"], capture_output=True, text=True, timeout=5)
            network_fs = {"smbfs", "nfs", "afpfs", "webdav", "fuse.sshfs"}
            for line in result.stdout.splitlines():
                parts = line.split()
                # format: device on /mount/point (fstype, options)
                if len(parts) >= 5 and parts[1] == "on":
                    mount_point = parts[2]
                    fs_type = parts[3].strip("(,)")
                    if path == mount_point or path.startswith(mount_point + "/"):
                        if fs_type in network_fs:
                            return True
        except Exception:
            pass
        return False

    # Linux
    try:
        network_fs = {"nfs", "nfs4", "cifs", "smbfs", "fuse.sshfs",
                       "ncpfs", "9p", "afs", "ceph", "glusterfs",
                       "lustre", "gpfs", "pvfs2", "orangefs"}
        best_mount = ""
        best_fs = ""
        with open("/proc/mounts", "r") as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 3:
                    mount_point = parts[1]
                    fs_type = parts[2]
                    if (path == mount_point
                            or path.startswith(mount_point + "/")):
                        if len(mount_point) > len(best_mount):
                            best_mount = mount_point
                            best_fs = fs_type
        return best_fs in network_fs
    except Exception:
        return False


def set_presentation_options(mask):
    """Set NSApplication.presentationOptions to an arbitrary mask on macOS.

    Useful bits:
      AutoHideDock        = 1
      HideDock            = 2
      AutoHideMenuBar     = 4   (requires HideDock or AutoHideDock)
      HideMenuBar         = 8   (requires HideDock)

    Examples:
      0      -> Default (dock + menu always visible)
      1 | 4  -> Auto-hide both; OS reveals each on edge approach
      2 | 8  -> Hard-hide both; OS NEVER reveals
      4 | 2  -> Menu auto-reveals on top edge, dock stays hard-hidden
      8 | 1  -> Dock auto-reveals on bottom edge, menu stays hard-hidden

    No-op on other platforms.
    """
    if sys.platform != "darwin":
        return
    try:
        objc, NSApp = _get_nsapp()
        sel = objc.sel_registerName(b"setPresentationOptions:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulonglong,
        ]
        objc.objc_msgSend(NSApp, sel, int(mask))
    except Exception:
        pass


def exit_fullscreen_platform():
    """Restore dock and menu bar on macOS. No-op on other platforms"""
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


def disable_native_fullscreen(window):
    """Prevent macOS native fullscreen on a given Qt window.

    The green traffic-light button then zooms (maximizes) instead of
    entering a Mission Control fullscreen space. This keeps floating
    Tool windows visible (they do not follow the main window into a
    native fullscreen space).

    """
    if sys.platform != "darwin":
        return
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p
        sel_window = objc.sel_registerName(b"window")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        nswindow = objc.objc_msgSend(
            ctypes.c_void_p(int(window.winId())), sel_window)
        if not nswindow:
            return
        # NSWindowCollectionBehaviorFullScreenNone = 1 << 9 = 512
        sel_set = objc.sel_registerName(b"setCollectionBehavior:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulonglong,
        ]
        objc.objc_msgSend(nswindow, sel_set, 1 << 9)
    except Exception:
        pass


def set_native_titled(window, titled):
    """Toggle title bar / resize chrome on a Qt window's NSWindow in place.

    Mutates the underlying NSWindow styleMask directly via the Objective-C
    runtime instead of calling Qt's setWindowFlags. This preserves the
    NSWindow identity, so the OpenGL surface backing video playback and the
    native parent-child relationship of floating Tool windows are NOT
    destroyed across the toggle.

    titled=True   -> Titled | Closable | Miniaturizable | Resizable (drag
                     from the title bar, all four edges resize, traffic
                     lights visible).
    titled=False  -> Borderless (no chrome). The window can still cover the
                     menu bar and dock.

    No-op on other platforms.
    """
    if sys.platform != "darwin":
        return
    try:
        objc = ctypes.cdll.LoadLibrary(ctypes.util.find_library("objc"))
        objc.objc_getClass.restype = ctypes.c_void_p
        objc.sel_registerName.restype = ctypes.c_void_p
        objc.objc_msgSend.restype = ctypes.c_void_p
        sel_window = objc.sel_registerName(b"window")
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        nswindow = objc.objc_msgSend(
            ctypes.c_void_p(int(window.winId())), sel_window)
        if not nswindow:
            return

        # Read current styleMask, flip the chrome bits, write back.
        sel_get_mask = objc.sel_registerName(b"styleMask")
        objc.objc_msgSend.restype = ctypes.c_ulonglong
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        current = int(objc.objc_msgSend(nswindow, sel_get_mask))

        # Titled=1, Closable=2, Miniaturizable=4, Resizable=8
        chrome_bits = 1 | 2 | 4 | 8
        if titled:
            new_mask = current | chrome_bits
        else:
            new_mask = current & ~chrome_bits

        objc.objc_msgSend.restype = ctypes.c_void_p
        sel_set_mask = objc.sel_registerName(b"setStyleMask:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulonglong,
        ]
        objc.objc_msgSend(nswindow, sel_set_mask, new_mask)

        # Borderless windows default to non-movable on macOS; force movable
        # so window dragging works regardless of chrome state.
        sel_set_movable = objc.sel_registerName(b"setMovable:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool,
        ]
        objc.objc_msgSend(nswindow, sel_set_movable, True)

        # Force opaque. setStyleMask transitions can leave NSWindow in a
        # transient non-opaque state — during fast resize the GL surface
        # lags the Qt repaint and the desktop behind bleeds through,
        # producing a flicker.
        sel_set_opaque = objc.sel_registerName(b"setOpaque:")
        objc.objc_msgSend.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_bool,
        ]
        objc.objc_msgSend(nswindow, sel_set_opaque, True)

        # Force AppKit to redraw the window chrome. setStyleMask leaves the
        # NSWindow shadow + title bar pixels stale; invalidateShadow +
        # display force a fresh frame including the title bar.
        objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        sel_inv_shadow = objc.sel_registerName(b"invalidateShadow")
        objc.objc_msgSend(nswindow, sel_inv_shadow)
        sel_display = objc.sel_registerName(b"display")
        objc.objc_msgSend(nswindow, sel_display)

        if titled:
            # If the NSWindow is "zoomed" (frame == screen frame), AppKit
            # locks vertical drag and edge resize. Un-zoom defensively.
            class NSSize(ctypes.Structure):
                _fields_ = [("width", ctypes.c_double),
                            ("height", ctypes.c_double)]

            sel_is_zoomed = objc.sel_registerName(b"isZoomed")
            objc.objc_msgSend.restype = ctypes.c_bool
            objc.objc_msgSend.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
            if objc.objc_msgSend(nswindow, sel_is_zoomed):
                objc.objc_msgSend.restype = ctypes.c_void_p
                sel_zoom = objc.sel_registerName(b"zoom:")
                objc.objc_msgSend.argtypes = [
                    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                ]
                objc.objc_msgSend(nswindow, sel_zoom, None)

            # Reset min/max content sizes to wide-open bounds so nothing
            # left over from a previous mode pins the window.
            objc.objc_msgSend.restype = ctypes.c_void_p
            sel_set_min = objc.sel_registerName(b"setMinSize:")
            sel_set_max = objc.sel_registerName(b"setMaxSize:")
            objc.objc_msgSend.argtypes = [
                ctypes.c_void_p, ctypes.c_void_p, NSSize,
            ]
            objc.objc_msgSend(nswindow, sel_set_min, NSSize(200.0, 150.0))
            objc.objc_msgSend(
                nswindow, sel_set_max, NSSize(100000.0, 100000.0))
    except Exception:
        pass


# Windows: fullscreen OpenGL window and audio device helpers
#
# Everything below is a no-op on macOS and Linux.

# Qt's Windows platform plugin reads this QWindow property when it
# creates the native window, and then gives the window a 1-pixel
# WS_BORDER whenever it is full screen.
_FULLSCREEN_BORDER_PROPERTY = "_q_has_border_in_fullscreen"
_WS_BORDER = 0x00800000
_GWL_STYLE = -16


def request_fullscreen_border(widget):
    """Ask Qt to keep a 1-pixel border on *widget* when it is full screen.

    Windows stops compositing an OpenGL window that exactly covers the
    primary screen, and the application's own dialogs and menus are
    then not drawn on top of it (they open, but stay invisible until
    something such as the Start menu forces a recomposite).  The border
    makes the window one pixel short of "exactly the screen", which
    keeps composition on.

    Must be called before the widget is first shown: the property is
    only read when the native window is created.  WA_NativeWindow makes
    the QWindow exist before that happens.
    """
    if sys.platform != "win32":
        return False
    try:
        from PySide6.QtCore import Qt
        widget.setAttribute(Qt.WidgetAttribute.WA_NativeWindow, True)
        handle = widget.windowHandle()
        if handle is None:
            return False
        handle.setProperty(_FULLSCREEN_BORDER_PROPERTY, True)
        return True
    except Exception:
        return False


def ensure_fullscreen_border(widget):
    """Check that a full-screen *widget* really has the border, and add
    it through the Win32 API if Qt did not.

    Returns "qt" (Qt applied it), "win32" (added here), "missing"
    (could not be added), or None when not applicable (not Windows, or
    the window is not full screen).  The caller logs the result.
    """
    if sys.platform != "win32":
        return None
    try:
        if not widget.isFullScreen():
            return None
        hwnd = int(widget.winId())
        user32 = ctypes.windll.user32
        get_style = getattr(user32, "GetWindowLongPtrW", None)
        set_style = getattr(user32, "SetWindowLongPtrW", None)
        if get_style is None or set_style is None:
            # 32-bit Windows exports only the non-"Ptr" names
            get_style = user32.GetWindowLongW
            set_style = user32.SetWindowLongW
        get_style.restype = ctypes.c_ssize_t
        get_style.argtypes = [ctypes.c_void_p, ctypes.c_int]
        set_style.restype = ctypes.c_ssize_t
        set_style.argtypes = [ctypes.c_void_p, ctypes.c_int,
                              ctypes.c_ssize_t]

        style = get_style(hwnd, _GWL_STYLE)
        if style & _WS_BORDER:
            return "qt"

        set_style(hwnd, _GWL_STYLE, style | _WS_BORDER)
        # SWP_NOSIZE | SWP_NOMOVE | SWP_NOZORDER | SWP_NOACTIVATE |
        # SWP_FRAMECHANGED: only make Windows re-read the frame style.
        user32.SetWindowPos.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        user32.SetWindowPos(hwnd, None, 0, 0, 0, 0,
                            0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020)
        return ("win32" if get_style(hwnd, _GWL_STYLE) & _WS_BORDER
                else "missing")
    except Exception:
        return "missing"


def audio_output_available():
    """False only when Windows reports that the PC has no audio output
    device at all.  Always True on macOS and Linux, and whenever the
    question cannot be answered."""
    if sys.platform != "win32":
        return True
    try:
        return int(ctypes.windll.winmm.waveOutGetNumDevs()) > 0
    except Exception:
        return True
