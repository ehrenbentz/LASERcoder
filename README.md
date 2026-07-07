# LASERcoder

**Lightweight Annotation Software for Ethology Research**

LASERcoder is an open-source desktop application for behavioral annotation of video recordings. Built for researchers and students in ethology, animal behavior, ecology, psychology, and related fields who need to score behaviors from video quickly and reliably.

Runs natively on **Windows**, **macOS** (Apple Silicon and Intel), and **Linux**.

<!-- TODO: Add screenshot of main annotation window here -->
<!-- ![LASERcoder Main Window](docs/images/screenshot.png) -->


## Features

**Annotation**
- **No save button.** Annotations are written to disk in real time using atomic write operations. Your data is safe even if the app crashes or you close the window mid-session.
- **Point and state events.** Score instantaneous (point) events and events with duration (state) from the same interface.
- **Mutually exclusive groups.** Starting one state event automatically ends the others in its group, so your annotations stay logically consistent without extra effort.
- **Subjects.** Score multiple individuals in the same video. Toggle active subjects with hotkeys or on-screen buttons; every annotation records which subject(s) it applies to.
- **Keyboard shortcuts and on-screen buttons.** Use hotkeys for speed or movable floating buttons for mouse/touchscreen workflows.
- **Notes and editing.** Attach notes to any annotation, edit timestamps, delete, and undo, all tracked in the output file.

**Playback**
- **Frame-accurate control.** Variable playback speed (0.5x–10x, up to 25x optional), frame stepping, configurable skip intervals, and click-to-zoom.
- **Audio tools.** Waveform overview and live spectrogram displays, volume/mute, audio delay adjustment, and pitch correction at altered speeds.
- **Video adjustments.** Per-video brightness, contrast, gamma, saturation, and hue.
- **Multi-part videos.** Score a recording split across multiple files as a single continuous video.

**Workflow**
- **Resume anywhere.** Stop and restart coding sessions without losing your place. Videos are flagged as in-progress or complete in the file browser.
- **Coding windows.** Define per-video observation windows to standardize scoring periods across videos without editing video files. Statistics are computed within the window.
- **Annotation timelines.** Visualize all annotated behaviors on a timeline and export as high-resolution images (JPG/PNG, 100–900 DPI).
- **Summary statistics.** Generate per-video and per-experiment summaries and box plots, plus combined annotation files formatted for downstream statistical analysis.
- **Project backup.** Back up an entire project directory from within the app.
- **Light and dark themes** with customizable interface colors.


## Installation

Download the installer for your platform from the [Releases](../../releases) page and run it. The installers bundle everything LASERcoder needs, including its own media playback libraries.

| Platform | Download | Notes |
|----------|----------|-------|
| **Windows (64-bit)** | `LASERcoder_v*_windows_x64_setup.exe` | Installer with Start Menu shortcuts |
| **Windows (64-bit)** | `LASERcoder_v*_windows_x64_portable.zip` | Portable; extracts to a `LASERcoder` folder, no installation |
| **macOS (Apple Silicon)** | `LASERcoder_v*_macOS_arm64.pkg` | Installer; clears the quarantine flag for you |
| **macOS (Apple Silicon)** | `LASERcoder_v*_macOS_arm64.dmg` | Drag to Applications (see [Gatekeeper note](#note-about-macos-gatekeeper)) |
| **macOS (Intel)** | `LASERcoder_v*_macOS_x86_64.pkg` | Installer; clears the quarantine flag for you |
| **macOS (Intel)** | `LASERcoder_v*_macOS_x86_64.dmg` | Drag to Applications (see [Gatekeeper note](#note-about-macos-gatekeeper)) |
| **Linux** | `LASERcoder_v*_linux_amd64.deb` | Debian/Ubuntu package (see [Linux note](#note-about-linux)) |
| **Linux** | `LASERcoder_v*_linux_amd64_portable.tar.gz` | Portable tarball, extract and run |

**System requirements:** Windows 10/11 (64-bit). Current macOS builds require **macOS 15 (Sequoia) or newer** — the exact minimum for each release is recorded in the app and shown by the installer.

### Note about macOS Gatekeeper

LASERcoder is not signed with an Apple Developer ID, so macOS will warn before the first launch:

- **Using the `.pkg` installer (recommended):** if macOS blocks the installer, right-click the `.pkg`, choose **Open**, and confirm. The installed app then launches normally — the installer clears the quarantine flag for you.
- **Using the `.dmg`:** after dragging to Applications, right-click `LASERcoder.app`, choose **Open**, and confirm — or run `sudo xattr -cr /Applications/LASERcoder.app` in Terminal, or use **System Settings → Privacy & Security → Open Anyway** after a blocked launch.

Either way, this is only required once.

### Note about Linux

The Linux build is currently **alpha**. Installing the `.deb` pulls in the required media libraries automatically (`sudo apt install ./LASERcoder_v*_linux_amd64.deb`); the portable tarball requires `mpv` to be installed via your package manager. Feedback from Linux users is very welcome — please [open an issue](../../issues) if something doesn't work.


## Quick Start

1. **Launch LASERcoder** and select an output directory: This is your project's working directory. All annotations, keys, session files, and summaries for a project live here (see [Where your data goes](#where-your-data-goes)).
2. **Select a video directory** and choose the video to annotate. Colored dots show which videos are already in progress or complete.
3. **Create or load an event key.** Define your behaviors with names, keyboard shortcuts, and types (Point or State), and assign mutually exclusive groups as needed. Optionally load a subject key to score multiple individuals.
4. **Annotate.** Press a behavior's hotkey (or click its button) as the video plays. For state events, press once to start and again to end. Everything is saved as you go.
5. **Press `Escape`** to return to the file selection screen — your position is remembered. From there, mark videos complete, visualize timelines, and **generate summary statistics** for one video or the whole experiment.


## Keyboard Controls

| Function | Key |
|----------|-----|
| Play / Pause | `Space` |
| Skip forward / backward (large, default 5 s) | `→` / `←` (also `D` / `A`) |
| Skip forward / backward (small, default 1 s) | `Shift+→` / `Shift+←` (also `Shift+D` / `Shift+A`) |
| Skip forward / backward 10 s | `W` / `S` |
| Step one frame forward / backward | `.` / `,` |
| Increase / decrease playback speed | `+` / `-` |
| Reset speed to 1x | `Backspace` |
| Navigate the annotation list | `↑` / `↓` |
| Delete selected annotation | `Delete` |
| Undo delete | `Ctrl+Z` (`Cmd+Z` on macOS) |
| Toggle fullscreen / windowed mode | `F11` or `Ctrl+Shift+W` |
| Close video and return to file selection | `Escape` |

Skip intervals are configurable in the settings menu, and the `W`/`A`/`S`/`D` navigation keys can be disabled if you want to use those letters as behavior hotkeys.


## Where your data goes

Everything lives in your chosen output directory, in plain files you can inspect, copy, and version:

```
YourProject/
├── Annotations/
│   ├── VideoName_Annotations.csv       Complete annotation file per video
│   ├── Summaries/                      Per-video summary statistics
│   └── Combined_Annotations/           Merged multi-video annotation files
├── Keys/
│   ├── Event_Keys/                     Behavior definitions (reusable across projects)
│   └── Subject_Keys/                   Subject definitions
├── Session/                            Per-video session state and resume data
└── Debug/                              Diagnostic logs (auto-pruned)
```

While you annotate, data is journaled to small chunk files in `Session/` with atomic writes; the consolidated `VideoName_Annotations.csv` is the file you take to analysis.

## Output format

Annotation CSVs are UTF-8 encoded, open cleanly in Excel, and import directly into R or Python — no reformatting or export step:

| Column | Description |
|--------|-------------|
| `Video` | Video filename |
| `Event` | Behavior name |
| `Subject` | Subject ID(s) the annotation applies to (`NA` if unused) |
| `Type` | `Point` or `State` |
| `Mutually_Exclusive` | Whether the event belongs to an ME group |
| `H_Start`, `H_End` | Human-readable timestamps (e.g. `12m3.50s`) |
| `Start`, `End` | Timestamps in seconds — **use these for analysis** |
| `Duration` | Duration in seconds (state events only) |
| `Manual_Edit` | `True` if the timestamp was edited after scoring |
| `Notes` | User-added notes |


## Citation

If you use LASERcoder in published research, please cite this repository: https://github.com/ehrenbentz/LASERcoder

<!-- TODO: Update with DOI once published -->

A Manuscript is in preparation to provide a stable citation:
> Bentz, E.J., Laser, R.S., ...[Other Authors]... Ophir, A.G. (2026). LASERcoder: Lightweight Annotation Software for Ethology Research. (in preparation)

See [CITATION.cff](CITATION.cff) for machine-readable citation information.


## Contributing

Contributions are welcome. Please open an [issue](../../issues) to report bugs or suggest features before submitting a pull request.


## Running or building from source

**Most users should use the pre-built installers above** — they are self-contained and tested on each platform. Building from source is only needed if you are developing LASERcoder or packaging it for an unsupported platform.

<details>
<summary>Instructions for developers</summary>

Running from source requires Python 3.11+ and [libmpv](https://mpv.io/) (from `brew install mpv`, `apt install libmpv2`, or the prebuilt libraries shipped with releases):

```bash
git clone https://github.com/ehrenbentz/LASERcoder.git
cd LASERcoder
pip install PySide6 python-mpv numpy
cd src
python main.py
```

Release binaries are compiled with [Nuitka](https://nuitka.net/) (`pip install nuitka`). Each platform directory (`build_Windows/`, `build_macOS/`, `build_Linux/`) contains a self-contained build script that compiles the application, creates installers, and packages portable archives. See the comments in each script for prerequisites and details.

Platform notes:
- **Windows:** Nuitka currently compiles successfully on Python 3.12; builds may fail on 3.11 and 3.13+ depending on the Nuitka version.
- **macOS:** the bundled mpv libraries are collected from Homebrew by `collect_dylibs.sh`; the app's minimum macOS version is stamped from those libraries at build time.
- **Linux:** you may need `sudo apt install libxcb-cursor0 patchelf` beyond the base install.

</details>


## License

LASERcoder is licensed under the [GNU General Public License v3.0](LICENSE). You are free to use, study, modify, and share it. If you distribute LASERcoder or any software that incorporates its code, you must release that software under the GPL as well, with full source code. No part of LASERcoder may be used in any part of proprietary, commercial, or closed-source software.


## Acknowledgments

LASERcoder was developed in the [Ophir Lab of Integrative Neuroethology](https://www.ophirlab.com/), Department of Psychology, Cornell University.

<!-- TODO: Add specific acknowledgments (funding, contributors) -->
