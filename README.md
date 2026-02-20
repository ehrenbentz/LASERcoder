# LaserTAG

**Lightweight Application for Scoring Ethology Recordings and Tracking Animals Gooder**

LaserTAG is a free, open-source desktop application for behavioral annotation of video recordings. It is designed for researchers and students in ethology, animal behavior, ecology, psychology, or related fields who need to score behaviors from video data quickly and reliably.

LaserTAG runs natively on **Windows** and **macOS** with pre-built installers or may be run from source.

<!-- TODO: Add screenshot of main annotation window here -->
<!-- ![LaserTAG Main Window](docs/images/screenshot.png) -->

## Key Features

- **No save button**: Annotations are saved in real time using atomic write operations. Your data is protected even during accidental closures, power outages, crashes.
- **Simple CSV output**: Annotation files are clean, properly formatted `.csv` files ready for direct import into R, Python, or any statistics software. No reformatting required.
- **Point and state behaviors**: Annotate instantaneous events (point behaviors) and behaviors with duration (state behaviors) using the same intuitive interface.
- **Mutually exclusive groups**: Define groups of state behaviors where starting one automatically ends the others, ensuring logically consistent annotations.
- **Keyboard shortcuts and on-screen buttons**: Code behaviors using hotkeys for speed, or floating buttons for mouse/touchscreen workflows.
- **Annotation visualization**: Generate timeline visualizations of all annotated behaviors and export them as high-resolution images (JPG/PNG, 100–900 DPI).
- **Summary statistics**: Generate per-video and per-experiment summary statistics and combined annotation files for batch analysis.
- **Resume coding sessions**: Stop and restart coding at any time without losing your place.
- **Set coding windows**: Define a start time and duration to standardize observation periods across videos without editing video files.
- **Cross-platform**: Native builds for Windows and macOS with platform-optimized video playback.

## Installation

### Pre-built Installers (Recommended)

Download the latest release for your platform from the [Releases](../../releases) page:

| Platform | Download | Notes |
|----------|----------|-------|
| **Windows** | `LaserTAGSetup.exe` | Installer adds Start Menu/Desktop shortcuts and PATH entry |
| **Windows** | `LaserTAG.zip` | Portable version — extract and run LaserTAG.exe, no installation needed |
| **macOS** | `LaserTAGInstaller.dmg` | Drag to Applications folder (see [Gatekeeper note](#macos-gatekeeper)) |

### macOS Gatekeeper

LaserTAG is not signed with an Apple Developer ID. On first launch, macOS may block the application. To open it:

1. Right-click `LaserTAG.app` and choose **Open**, then click **Open** in the dialog, **or**
2. Run `xattr -cr /Applications/LaserTAG.app` in Terminal, **or**
3. Go to **System Settings > Privacy & Security** and click **Open Anyway**

This is only required once per machine.

### Running from Source

Requires Python 3.10+ and a working installation or prebuilt libraries for [MPV](https://mpv.io/) (Windows) or Homebrew mpv (macOS).

```bash
pip install PySide6 python-mpv
cd CodeBase
python LaserTAG.py
```

### Building from Source

Full build instructions for manually creating standalone executables and installers:

- [Windows Build Guide](build_Windows/build_LaserTAG_Windows.MD)
- [macOS Build Guide](build_MacOS/build_LaserTAG_MacOS.MD)

Automated build scripts are provided for both platforms (`build_LaserTAG_Windows.bat` and `build_LaserTAG_MacOS.sh`).

## Quick Start

1. **Launch LaserTAG** and select an output directory (subdirectories for annotations, behaviors, resume files, and summaries are created automatically).
2. **Select a video directory** and choose a video file to annotate.
3. **Create or load a behavior key** — define behaviors with names, keyboard shortcuts, and types (Point or State). Assign mutually exclusive groups as needed.
4. **Annotate** — Use keyboard shortcuts or floating buttons to add annotations as the video plays. Navigate with standard controls (see table below).
5. **Generate summary statistics** from the file selection screen when you have finished annotating.

### Keyboard Controls

| Function | Key |
|----------|-----|
| Play / Pause | `Space` |
| Increase speed | `+` or `=` |
| Decrease speed | `-` or `_` |
| Reset speed to 1x | `Backspace` (`Delete` on macOS) |
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
| Return to file selection | `Escape` |

## Output Format

Annotation files are saved as `VideoName_Annotations.csv` with 11 columns:

| Column | Description |
|--------|-------------|
| `Video` | Video filename |
| `Name` | Behavior name |
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
├── CodeBase/                 Python source code
│   ├── LaserTAG.py           Main entry point
│   ├── video_annotator.py    Core annotation engine
│   ├── annotation_store.py   Atomic file I/O
│   ├── behavior_key_editor.py
│   ├── setup_manager.py      File/directory selection UI
│   ├── annotations_visualizer.py
│   ├── summary_statistics.py
│   ├── summary_statistics_manager.py
│   ├── config_manager.py
│   ├── dialogs.py
│   ├── display_utils.py
│   ├── files_manager.py
│   ├── floating_controls.py
│   └── progress_bar.py
├── build_Windows/            Windows build scripts and resources
├── build_MacOS/              macOS build scripts and resources
├── LaserTAG_Manual.txt       User manual
├── LICENSE                   GPL-3.0 license
└── README.md                 This file
```

## Citation

If you use LaserTAG in your research, please cite:

<!-- TODO: Update with JOSS DOI once published -->

> Bentz, E.J., Laser, R.S., Ophir, A.G. (2026). LaserTAG: Lightweight Application for Scoring Ethology Recordings and Tracking Animals Gooder. *Journal of Open Source Software*. (in preparation)

See [CITATION.cff](CITATION.cff) for machine-readable citation information.

## Contributing

Contributions are welcome. Please open an [issue](../../issues) to report bugs or suggest features before submitting a pull request.

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/ehrenbentz/LaserTAG.git
   cd LaserTAG
   ```
2. Install dependencies:
   ```bash
   pip install PySide6 python-mpv
   ```
3. Run from source:
   ```bash
   cd CodeBase
   python LaserTAG.py
   ```

## License

LaserTAG is licensed under the [GNU General Public License v3.0](LICENSE).

## Acknowledgments

LaserTAG was developed in the [Ophir Lab of Integrative Neuroethology](https://www.ophirlab.com/) in the Cornell University department of Psychology.

<!-- TODO: Add specific acknowledgments (lab, funding, contributors) -->
