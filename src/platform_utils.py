import os
import sys
import ctypes
import ctypes.util


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
