# LaserTAG

**Lightweight Application for Scoring Ethology Recordings and Tracking Animals Gooder**

LaserTAG is a free, open-source desktop application for behavioral annotation of video recordings. Built for researchers and students in ethology, animal behavior, ecology, psychology, and related fields who need to score behaviors from video quickly and reliably.

Runs natively on **Windows**, **macOS**, and **Linux**.

<!-- TODO: Add screenshot of main annotation window here -->
<!-- ![LaserTAG Main Window](docs/images/screenshot.png) -->


## Features

- **No save button.** Annotations are written to disk in real time using atomic write operations. Your data is safe even if the app crashes, your laptop dies, or you accidentally close the window.
- **Clean CSV output.** Annotation files are properly formatted `.csv` ready for direct import into R, Python, or whatever you use. No reformatting, no export step.
- **Point and state behaviors.** Score instantaneous events and behaviors with duration from the same interface.
- **Mutually exclusive groups.** Starting one state behavior automatically ends the others in its group, so your annotations stay logically consistent without extra effort.
- **Keyboard shortcuts and on-screen buttons.** Use hotkeys for speed or floating buttons for mouse/touchscreen workflows.
- **Annotation timelines.** Visualize all annotated behaviors on a timeline and export as high-resolution images (JPG/PNG, 100-900 DPI).
- **Summary statistics.** Generate per-video and per-experiment summaries and combined annotation files for batch analysis.
- **Resume anywhere.** Stop and restart coding sessions without losing your place.
- **Coding windows.** Define a start time and duration to standardize observation periods across videos without editing video files.


## Installation

### Pre-built Installers (Recommended)

Download the latest release for your platform from the [Releases](../../releases) page:

| Platform | Download | Notes |
|----------|----------|-------|
| **Windows** | `LaserTAG_v*_windows_x64_setup.exe` | Installer with Start Menu shortcuts |
| **Windows** | `LaserTAG_v*_windows_x64_portable.zip` | Portable version, no installation needed |
| **macOS (Apple Silicon)** | `LaserTAG_v*_macOS_arm64.dmg` | Drag to Applications (see [Gatekeeper note](#macos-gatekeeper)) |
| **macOS (Apple Silicon)** | `LaserTAG_v*_macOS_arm64.pkg` | Installer, clears Gatekeeper automatically |
| **macOS (Intel)** | `LaserTAG_v*_macOS_x86_64.dmg` | Drag to Applications (see [Gatekeeper note](#macos-gatekeeper)) |
| **macOS (Intel)** | `LaserTAG_v*_macOS_x86_64.pkg` | Installer, clears Gatekeeper automatically |
| **Linux** | `LaserTAG_v*_linux_amd64.deb` | Debian/Ubuntu package, installs to `/opt/LaserTAG` |
| **Linux** | `LaserTAG_v*_linux_amd64_portable.tar.gz` | Portable tarball, extract and run |


### macOS Gatekeeper

LaserTAG is not signed with an Apple Developer ID, so macOS will block it on first launch. To get around this:

1. Right-click `LaserTAG.app`, choose **Open**, then click **Open** in the dialog, **or**
2. Run `xattr -cr /Applications/LaserTAG.app` in Terminal, **or**
3. Go to **System Settings > Privacy & Security** and click **Open Anyway**

Only required once. The `.pkg` installer handles this automatically.


### Running from Source

Requires Python 3.10+ and [MPV](https://mpv.io/) (or prebuilt libraries).
```bash
pip install PySide6 python-mpv
cd CodeBase
python LaserTAG.py
```

### Building from Source

Each platform directory (`build_Windows/`, `build_macOS/`, `build_Linux/`) contains a build script that compiles the application, creates installers, and packages portable archives. See the scripts and comments within for details.

**Windows:** Nuitka currently requires Python 3.12 specifically. Builds will fail on 3.11 and 3.13+.

**Linux:** You may need additional system libraries beyond the base install. At minimum:
```bash
sudo apt install libxcb-cursor0
```

## Quick Start

1. **Launch LaserTAG** and pick an output directory. Subdirectories for annotations, behaviors, resume files, and summaries are created automatically.
2. **Select a video directory** and choose a video to annotate.
3. **Create or load a behavior key.** Define behaviors with names, keyboard shortcuts, and types (Point or State). Set up mutually exclusive groups as needed.
4. **Annotate.** Use keyboard shortcuts or floating buttons to record behaviors as the video plays.
5. **Generate summary statistics** from the file selection screen when finished.


### Keyboard Controls

| Function | Key |
|----------|-----|
| Play / Pause | `Space` |
| Increase speed | `+` or `=` |
| Decrease speed | `-` or `_` |
| Reset speed to 1x | `Backspace` (Windows/Linux) or `Delete` (macOS) |
| Skip forward 10s | `W` |
| Skip backward 10s | `S` |
| Skip forward 5s | `D` or `Right Arrow` |
| Skip backward 5s | `A` or `Left Arrow` |
| Skip forward 1s | `Shift+D` or `Shift+Right` |
| Skip backward 1s | `Shift+A` or `Shift+Left` |
| Next annotation | `Up Arrow` |
| Previous annotation | `Down Arrow` |
| Delete annotation | `Delete` |
| Undo delete | `Ctrl+Z` |
| Close video and return to file selection | `Escape` |


## Output Format

Annotation files are saved as `VideoName_Annotations.csv` with 11 columns, formatted for direct import into statistical software:

| Column | Description |
|--------|-------------|
| `Video` | Video filename |
| `Behavior` | Behavior name |
| `Type` | `Point` or `State` |
| `Mutually_Exclusive` | Whether the behavior belongs to an ME group |
| `H_Start` | Human-readable start time (HH:MM:SS) |
| `H_End` | Human-readable end time |
| `Start` | Start time in seconds (use for analysis) |
| `End` | End time in seconds (use for analysis) |
| `Duration` | Duration in seconds (state behaviors only) |
| `Manual_Edit` | `TRUE` if the timestamp was manually edited |
| `Notes` | User-added notes |


## Project Structure
```
LaserTAG/
├── CodeBase/                          Source code
│   ├── LaserTAG.py                    Main entry point
│   ├── video_annotator.py             Core annotation module
│   ├── annotation_store.py            Atomic file I/O
│   ├── behavior_key_editor.py
│   ├── setup_manager.py               File/directory selection UI
│   ├── annotations_visualizer.py
│   ├── summary_statistics.py
│   ├── summary_statistics_manager.py
│   ├── config_manager.py
│   ├── dialogs.py
│   ├── display_utils.py
│   ├── files_manager.py
│   ├── floating_controls.py
│   └── progress_bar.py
├── build_Windows/                     Windows build scripts and resources
├── build_macOS/                       macOS build scripts and resources
├── build_Linux/                       Linux build scripts and resources
├── LICENSE                            GPL-3.0 license
├── CITATION.cff                       Machine-readable citation
└── README.md
```


## Citation

If you use LaserTAG in published research, please cite:

<!-- TODO: Update with DOI once published -->

> Bentz, E.J., Laser, R.S., ...[Other Authors]... Ophir, A.G. (2026). LaserTAG: Lightweight Application for Scoring Ethology Recordings and Tracking Animals Gooder. (in preparation)

See [CITATION.cff](CITATION.cff) for machine-readable citation information.


## Contributing

Contributions are welcome. Please open an [issue](../../issues) to report bugs or suggest features before submitting a pull request.


### Development Setup
```bash
git clone https://github.com/ehrenbentz/LaserTAG.git
cd LaserTAG
pip install PySide6 python-mpv
cd CodeBase
python LaserTAG.py
```


## License

LaserTAG is licensed under the [GNU General Public License v3.0](LICENSE).


## Acknowledgments

LaserTAG was developed in the [Ophir Lab of Integrative Neuroethology](https://www.ophirlab.com/), Department of Psychology, Cornell University.

<!-- TODO: Add specific acknowledgments (funding, contributors) -->