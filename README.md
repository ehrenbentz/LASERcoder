# LASERcoder

**Lightweight Annotation Software for Ethology Research**

LASERcoder is an open-source desktop application for annotation of video recordings. Built for researchers and students in ethology, animal behavior, ecology, psychology, and related fields who need to manually score video data quickly and reliably.

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
- **Multi-part videos.** Score a recording split across multiple files as a single continuous video (one subfolder per recording, enabled with a checkbox in the file picker).

**Workflow**
- **Resume anywhere.** Stop and restart coding sessions without losing your place. Videos are flagged as in-progress or complete in the file browser.
- **Coding windows.** Define per-video observation windows to standardize scoring periods across videos without editing video files. Statistics are computed within the window.
- **Annotation timelines.** Visualize all annotated events on a timeline and export as high-resolution images (JPG/PNG, 100–900 DPI).
- **Summary statistics.** Generate per-video and per-experiment summaries and box plots, plus combined annotation files formatted for downstream statistical analysis.
- **Project backup.** Back up an entire project directory from within the app.
- **Light and dark themes** with customizable interface colors.


## Installation

Download the installer for your platform from the [Releases](../../releases) page and run it. The installers bundle everything LASERcoder needs, including its own media playback libraries.

| Platform | Download | Notes |
|----------|----------|-------|
| **Windows (64-bit)** | `LASERcoder_v*_windows_x64_setup.exe` | Install on your system |
| **Windows (64-bit)** | `LASERcoder_v*_windows_x64_portable.zip` | Portable; Extract and run without installation |
| **macOS (Apple Silicon)** | `LASERcoder_v*_macOS_arm64.pkg` | Installer; Automatically clears the quarantine flag |
| **macOS (Apple Silicon)** | `LASERcoder_v*_macOS_arm64.dmg` | Drag to Applications (see [Gatekeeper note](#note-about-macos-gatekeeper)) |
| **macOS (Intel)** | `LASERcoder_v*_macOS_x86_64.pkg` | Installer; Automatically clears the quarantine flag |
| **macOS (Intel)** | `LASERcoder_v*_macOS_x86_64.dmg` | Drag to Applications (see [Gatekeeper note](#note-about-macos-gatekeeper)) |
| **Linux** | `LASERcoder_v*_linux_amd64.deb` | Debian/Ubuntu package (see [Linux note](#note-about-linux)) |
| **Linux** | `LASERcoder_v*_linux_amd64_portable.tar.gz` | Portable tarball, extract and run |

**System requirements:** Windows 10/11 (64-bit). Current macOS builds require **macOS 15 (Sequoia) or newer**

### Note about macOS Gatekeeper

LASERcoder is not signed with an Apple Developer ID, so macOS will warn before the first launch:

- **Using the `.pkg` installer (recommended):** if macOS blocks the installer, right-click the `.pkg`, choose **Open**, and confirm. The installed app then launches normally. This installer clears the quarantine flag for you.
- **Using the `.dmg`:** after dragging to Applications, right-click `LASERcoder.app`, choose **Open**, and confirm, or run `sudo xattr -cr /Applications/LASERcoder.app` in Terminal, or use **System Settings → Privacy & Security → Open Anyway** after a blocked launch.

One of these methods should work. This will only be required once.

### Note about Linux

The Linux build is currently **alpha**. Installing the `.deb` pulls in the required media libraries automatically (`sudo apt install ./LASERcoder_v*_linux_amd64.deb`); the portable tarball requires `mpv` to be installed via your package manager. Feedback from Linux users is very welcome. Please [open an issue](../../issues) if something doesn't work.


## Quick Start

LASERcoder keeps everything for a project in one folder, the **working directory**, and reads your videos from wherever they already are. Set up a project once, then open it again from the same screen each time.

### Key concepts

- **Working directory.** A folder you create for the project. LASERcoder writes everything it produces here: annotation files, event and subject keys, session progress, summaries, and logs (see [Where your data goes](#where-your-data-goes)). Choose or create this first; nothing else can be selected until it exists. Use one working directory per project or experiment, and keep it on a local drive rather than a network share.
- **Video folder.** The folder that holds the videos you want to score. LASERcoder only reads from it and never modifies your videos. It can be anywhere, including an external drive.
- **Single vs. multi-part videos.** Most recordings are one file per video. Some cameras split a single recording into several files (for example `trial01_000.mp4`, `trial01_001.mp4`). LASERcoder can play such a set as one continuous video: put each recording's files in their own subfolder of the video folder, and tick **My videos are split into multiple parts** in the file picker. Each such subfolder is then listed as one video, named after the subfolder, alongside any single-file videos in the same folder, and its parts play back to back in filename order.
- **Event key.** The list of behaviors you score: each has a name, a keyboard shortcut, a type (Point for instantaneous events, State for events with a duration), and optionally a mutually exclusive group. Event keys are saved in the working directory and can be reused across projects.
- **Subject key (optional).** The individuals in the video, each with a shortcut. When subjects are active, every annotation records which subject it applies to. Only needed when you score more than one individual.

### Setting up a project

1. **Launch LASERcoder.** The setup screen shows the working directory on the left and the video folder on the right.
2. **Create a working directory.** On the left, browse to where you want the project to live, click **Create Directory**, give it a name, and click **Select Directory**. The chosen folder is confirmed below the list. To reopen an existing project, browse to its folder and click **Select Directory** instead.
3. **Select the folder that holds your videos.** On the right, click **Browse...** and pick the folder. The videos in it are listed. Colored dots mark videos that are already in progress or complete. If some or all recordings are split into parts, tick **My videos are split into multiple parts**: each subfolder is then listed as one video, together with any single-file videos.
4. **Select a video** by double-clicking it or clicking **Select Video**.
5. **Create or load an event key** if the project does not have one yet. Define your events with names, shortcut keys, and types, assign mutually exclusive groups as needed, then **Start Video**. Existing keys are listed in the dropdown.
6. **Optional: create a subject key** if you are scoring more than one individual. Add each subject with a shortcut and, if wanted, a color and mutually exclusive group.

### Annotating

- Press an event's shortcut key or click its on-screen button as the video plays. For state events, press once to start and again to end. For multiple subjects, toggle the active subjects first; each annotation is written once per active subject. Everything is saved in real time.
- Press **`Escape`** at any time to return to the setup screen. Your position in the video is remembered, and the next time the video is opened you resume where you left off.
- **Summary statistics and combined annotations.** From the setup screen, generate per-video summaries, box plots, and a combined annotation file for a whole experiment, pre-formatted for downstream statistical analysis.


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

Skip intervals are configurable in the settings menu, and the `W`/`A`/`S`/`D` navigation keys can be disabled if you want to use those letters for event shortut keys.


## Where your data goes

Everything lives in your working directory, in plain files you can inspect, copy, and edit:

```
YourProject/
├── Annotations/
│   ├── VideoName_Annotations.csv       Complete annotation file per video
│   ├── Summaries/                      Per-video summary statistics
│   └── Combined_Annotations/           Merged multi-video annotation files
├── Keys/
│   ├── Event_Keys/                     List and define events to annotate (reusable across projects)
│   └── Subject_Keys/                   Subject definitions
├── Session/                            Per-video session data
└── Debug/                              Diagnostic logs (for developers)
```

While you annotate, data is journaled to small chunk files in `Session/` with atomic writes; the consolidated `VideoName_Annotations.csv` is the file you take to analysis.

You can also edit `VideoName_Annotations.csv` outside LASERcoder (in Excel, a text editor, or on another computer). The next time that video is opened, LASERcoder compares the file with its working copy, shows a summary of what was added, removed, or changed, and asks whether to apply the edits permanently or discard them. Event key and subject key files are read directly, so edits to those take effect the next time they are loaded. Files saved by Excel on macOS or Windows are read regardless of encoding or line-ending differences.

## Output format

Annotation CSVs are UTF-8 encoded, open cleanly in Excel, and import directly into statistical software (e.g. R) with no reformatting or export step:

| Column | Description |
|--------|-------------|
| `Video` | Video filename |
| `Event` | Event name |
| `Subject` | Subject ID the annotation applies to (`NA` if unused). When several subjects are active, one row is written per subject |
| `Type` | `Point` or `State` |
| `Mutually_Exclusive` | Whether the event belongs to an ME group |
| `H_Start`, `H_End` | Human-readable timestamps (e.g. `12m3.50s`) |
| `Start`, `End` | Timestamps in seconds — *use these for analysis* |
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

**Most users should use the pre-built installers above**. They are self-contained and tested on each platform. Building from source is only needed if you are developing LASERcoder or packaging it for an unsupported platform.

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

Coding assistants (Anthropic; Claude) were used during the creation of LASERcoder source code.

I would like to thank the many researchers at Cornell and beyond who tested LASERcoder and provided feedback during several years of testing.
This project would not have existed without all of you.
