"""Platform-specific fullscreen helpers"""
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
