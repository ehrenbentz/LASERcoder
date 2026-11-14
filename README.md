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
- **Frame-accurate control.** Variable playback speed (0.25x–10x, up to 25x optional), frame stepping, configurable skip intervals, and click-to-zoom.
- **Audio tools.** Waveform overview and live spectrogram displays, volume/mute, audio delay adjustment, and pitch correction at altered speeds.
- **Video adjustments.** Per-video brightness, contrast, gamma, saturation, and hue.
- **Multi-part videos.** Score a recording split across multiple files as a single continuous video (one subfolder per recording, enabled with a checkbox in the file picker).

**Workflow**
- **Resume anywhere.** Stop and restart coding sessions without losing your place. Videos are flagged as in-progress or complete in the file browser.
- **Coding windows.** Define per-video observation windows to standardize scoring periods across videos without editing video files. Statistics are computed within the window.
- **Annotation timelines.** Visualize all annotated events on a timeline and export as high-resolution images (JPG/PNG, 100–900 DPI).
- **Summary statistics.** Generate per-video and per-experiment summaries and box plots.
- **Import and export.** Export the annotations of any or all videos as analysis-ready CSV files, and import annotations from other LASERcoder projects.
- **Project backup.** Back up or move an entire project directory from within the app.
- **Built-in help.** Press `F1` or click **?** for a quick guide and a list of all shortcuts, including the event and subject keys of the open video.
- **Light and dark themes** with customizable interface colors.


## Installation

Download the installer for your platform from the [Releases](../../releases) page and run it. The installers bundle everything LASERcoder needs, including its own media playback libraries.

| Platform | Download | Notes |
|----------|----------|-------|
| **Windows (64-bit)** | `LASERcoder_v*_windows_x64_setup.exe` | Installer; No admin rights needed |
| **Windows (64-bit)** | `LASERcoder_v*_windows_x64_portable.zip` | Portable; Extract and run from any folder or external drive. Settings and logs stay in that folder |
| **macOS (Apple Silicon)** | `LASERcoder_v*_macOS_arm64.pkg` | Installer; Automatically clears the quarantine flag |
| **macOS (Apple Silicon)** | `LASERcoder_v*_macOS_arm64.dmg` | Drag to Applications (see [Gatekeeper note](#note-about-macos-gatekeeper)) |
| **macOS (Intel)** | `LASERcoder_v*_macOS_x86_64.pkg` | Installer; Automatically clears the quarantine flag |
| **macOS (Intel)** | `LASERcoder_v*_macOS_x86_64.dmg` | Drag to Applications (see [Gatekeeper note](#note-about-macos-gatekeeper)) |
| **Linux** | `LASERcoder_v*_linux_amd64.deb` | Debian/Ubuntu package (see [Linux note](#note-about-linux)) |
| **Linux** | `LASERcoder_v*_linux_amd64_portable.tar.gz` | Portable tarball, extract and run. Settings and logs stay in that folder |

**System requirements:** Windows 10/11 (64-bit). Current macOS builds require **macOS 15 (Sequoia) or newer**

### Note about macOS Gatekeeper

LASERcoder is not signed with an Apple Developer ID, so macOS will warn before the first launch:

- **Using the `.pkg` installer (recommended):** if macOS blocks the installer, right-click the `.pkg`, choose **Open**, and confirm. The installed app then launches normally. This installer clears the quarantine flag for you.
- **Using the `.dmg`:** after dragging to Applications, right-click `LASERcoder.app`, choose **Open**, and confirm, or run `sudo xattr -cr /Applications/LASERcoder.app` in Terminal, or use **System Settings → Privacy & Security → Open Anyway** after a blocked launch.

One of these methods should work. This will only be required once.

### Note about Linux

The Linux build is currently **alpha**. Installing the `.deb` pulls in the required media libraries automatically (`sudo apt install ./LASERcoder_v*_linux_amd64.deb`); the portable tarball requires `mpv` to be installed via your package manager. Feedback from Linux users is very welcome. Please [open an issue](../../issues) if something doesn't work.


## Quick Start

LASERcoder keeps everything for a project in one folder, the **project directory**, and reads your videos from wherever they already are. Set up a project once, then open it again from the same screen each time.

1. **Launch LASERcoder.** The first time, it asks for a project directory.
2. **Choose a project directory.** Click **Select Project Directory**, create a new folder for the project (right-click, or the New Folder button), select it, and click **Select Folder**.
3. **Choose the video directory.** Click **Select Video Directory** and pick the folder that holds your videos.
4. **Open a video** by double-clicking it, or by selecting it and pressing `Enter`.
5. **Create an event key**: name each behavior, give it a shortcut key and a type (Point or State), then click **Start Video**.
6. **Score.** Press an event's key as the video plays. Press `Escape` to return to the video list; the video reopens where you left off.

Press `F1` or click **?** at any time for the in-app help. The sections below describe every part of LASERcoder in detail.


## Key concepts

- **Project directory.** A folder you create for the project. LASERcoder writes everything it produces here: annotation files, event and subject keys, session progress, summaries, and logs (see [Where your data goes](#where-your-data-goes)). Use one project directory per project or experiment, and keep it on a local drive rather than a network share.
- **Video directory.** The folder that holds the videos you want to score. LASERcoder only reads from it and never modifies your videos. It can be anywhere, including an external drive.
- **Single vs. multi-part videos.** Most recordings are one file per video. Some cameras split a single recording into several files (for example `trial01_000.mp4`, `trial01_001.mp4`). LASERcoder can play such a set as one continuous video (see [Multi-part videos](#multi-part-videos)).
- **Event key.** The list of behaviors you score: each has a name, a keyboard shortcut, a type, and optionally a mutually exclusive group. **Point** events are instantaneous; **State** events have a duration.
- **Mutually exclusive (ME) group.** State events in the same group cannot overlap: starting one ends the others. Subjects can have ME groups too.
- **Subject key (optional).** The individuals in the video, each with a shortcut. When subjects are active, every annotation records which subject it applies to. Only needed when you score more than one individual.
- **Coding segment.** The part of a video you score, set per video. Statistics are computed within it.


## The setup screen

The setup screen opens when LASERcoder starts and whenever you close a video. The project and video directories are shown at the top, the project tools on the left, and the video list on the right. The gear button opens **Appearance** settings, and the **?** button opens the help window.

### Project directory

- The first time LASERcoder starts, it explains the project directory and asks you to choose one. Until a project directory is set, the video list and the project tools are disabled.
- Click **Select Project Directory** to choose or create a folder. The folder window lets you create, rename, and delete empty folders (right-click, or the New Folder button).
- Use a new, empty folder for each project. Your home folder and the top level of a drive are not accepted, and a folder that already contains other files asks for confirmation.
- To reopen a project, select its folder. The last project is reopened automatically on the next start.
- You can also type or paste a path into the **Project Directory** field and press `Enter`. Type part of a folder name and press `Tab` to complete it.

### Video directory and video list

Click **Select Video Directory**, or type a path into the field. The folder window shows the video files in each folder so you can tell you are in the right place.

The video list shows, for each video:

| Column | Meaning |
|--------|---------|
| **Name** | File name. A yellow dot marks a video in progress, a green check a completed one |
| **Length** | Video duration (read in the background the first time and then remembered) |
| **Size** | File size |
| **Date Modified** | When the file last changed |
| **Current Position** | Where you left off in that video |

- Click a column header to sort; click again to reverse. Drag a header edge to resize a column (widths are remembered).
- Right-click a video to mark it **Complete**, **In Progress**, or to **Clear Status**.
- Open a video by double-clicking it, or by selecting it and pressing `Enter`.

### Multi-part videos

Put each recording's files in their own subfolder of the video directory, and tick **My videos are split into multiple parts**. Each such subfolder is then listed as one video, named after the subfolder (with its number of parts), alongside any single-file videos in the same folder. Its parts play back to back in file name order, and its length and size are the totals of its parts. The first time a multi-part video is opened, LASERcoder lists the files it will join, in order, for you to confirm. The checkbox setting is remembered.

### Annotation tools

- **View Annotations.** Choose a video, then **View Spreadsheet** (a sortable table), **Visualize** (a timeline, see [Visualize](#visualize)), or **Delete** its annotations.
- **Import Annotations.** Choose a CSV file in LASERcoder's annotation format (see [Output format](#output-format)), the video to import into (when the file holds several), and whether to **Merge** with the existing annotations (duplicates skipped) or **Replace** them. Files containing event or subject names that LASERcoder does not accept (see [Names](#names)) are refused, with a list of the offending names.
- **Export Annotations.** Tick the videos to export (all are ticked by default), then choose **One combined CSV file** or **One CSV file per video**, and the destination. Exports cannot be saved inside the project directory, which holds LASERcoder's own working files.
- **Summary Statistics.** See [Summary statistics](#summary-statistics).

### Project tools

- **Backup Project.** Copies the whole project directory to a location you choose, as a folder named `Name_BKP_YYYYMMDD`. Backups are marked so they cannot be opened as a project by mistake.
- **Move Project.** Moves the project's folders to a new location and switches to it.


## Event keys and subject keys

### Event key editor

The event key editor opens when you open a video. Choose an existing event key from the drop-down, or create a new one, then fill in one row per event:

- **Name** of the behavior (see [Names](#names)).
- **Key**: one keyboard key. Keys must be unique and must not be `,` or `.` (frame stepping). When **Use W,A,S,D Keys for Video Navigation** is ticked, `W`, `A`, `S`, and `D` are reserved as well; untick it to use those letters for events. An event without a key can still be scored with its on-screen button.
- **Type**: **Point** or **State**.
- **ME group** (state events): any label. State events with the same label are mutually exclusive.

Deleted rows can be restored with **Undo Delete**. Click **Start Video** to begin scoring. The **Event Keys** button in the annotator reopens the editor. Event key files are saved in `Keys/Event_Keys/` and can be copied to other projects.

### Subject key editor

Click **Subjects** in the annotator. Each subject has a **Name**, a **Key**, an optional **ME group**, and an optional **color**. Subject keys cannot reuse an event's key. Tick **All subjects are mutually exclusive** if only one subject can be active at a time. Subject key files are saved in `Keys/Subject_Keys/`, and the subject key in use is remembered for each video.

### Names

Event, subject, and group names may contain letters, numbers, spaces, and `_ - . ( )`. The name `NA` (in any case) is reserved, because LASERcoder writes `NA` to mean "none", and two names that differ only in upper and lower case count as the same name. These rules apply to new names; names already saved in a key file are kept as they are.


## Annotating

### Recording annotations

- Press an event's key, or click its on-screen button, while the video plays or is paused.
- **Point** events record one time per press.
- **State** events start on the first press and end on the second. An active state is highlighted in the event list. Starting a state ends any active state in the same ME group.
- **Subjects.** Press a subject's key, or click its button, to make it active or inactive. Each annotation is written once per active subject (`NA` when none is active). Activating a subject deactivates the others in its ME group. Subjects cannot be changed while a state annotation is open; end the state first.
- Everything is saved immediately; there is no save button. Press `Escape` to return to the setup screen. Your position is remembered, and the video reopens where you left off.

### Coding segment

Click **Coding Segment** to set the part of the video you score: a start time, and either a duration or an end time (**Use Current Position** fills in the current time). **Show only coding segment in timeline** limits the progress bar to that segment. When playback reaches the end of the segment, the video pauses, and if any state is still open LASERcoder offers to end it at that point. **Clear** removes the segment. Summary statistics are computed within the segment.

### The annotation lists

The **State Annotations** and **Point Annotations** lists show every annotation of the video.

- Click a column header to sort by it; click again to reverse, and a third time to return to the order in which the annotations were made. Sorting changes only the display, not the saved files.
- Drag a header edge to resize a column.
- Use `↑` and `↓` to move through a list, and `Delete` to delete the selected annotation. Undo with `Ctrl+Z` (`Cmd+Z` on macOS).
- Right-click an annotation for:
  - **View Details**: see and edit the event, times, and notes. Edited annotations are marked `Manual_Edit = True`.
  - **Skip to Annotation**: move the video to its start.
  - **Reopen State**: clear a state's end time; then press its key at the right moment to end it again.
  - **Delete**, or **Delete Selected** when several rows are selected.

### Visualize

**Visualize** shows all annotations of the video on a timeline. Choose which events to show and their colors, whether to show only the coding segment, and whether to show a title, section headers, and a color legend. **Export** saves the timeline as a PNG or JPEG image at 100 to 900 DPI.

### Mark Video Complete

**Mark Video Complete** marks the video as finished; it then shows a green check in the video list. Click the button again to mark it as in progress.

### On-screen controls

- **Floating playback controls** at the bottom of the video: play and pause, small and large skips, and speed.
- **Events button** (top left of the video): shows a button for each event, for mouse or touchscreen scoring.
- **Subjects button** (below it): shows a button for each subject.
- **Zoom button** (top right of the video): turn it on, then click the video to zoom in on that point; drag to move around, and use the slider to change the zoom level.
- **Audio track** and **spectrogram** below the video. Click either, or the progress bar, to jump to that time; hover to see the time.
- The panel on the right can be collapsed with its arrow button and resized by dragging its edge.

### Settings menu (gear)

The gear button at the top of the annotation panel opens:

| Setting | Effect |
|---------|--------|
| Show Floating Controls | Playback controls below the video |
| Show Audio Track / Show Spectrogram | Audio displays below the video |
| Show Events Toggle / Show Subjects Toggle | The buttons that open the event and subject buttons |
| Show Zoom Button | The zoom button on the video |
| Show Floating Headers | Headers above the event and subject buttons |
| Show Subject Column | The Subject column in the annotation lists |
| Show Video Name | The video's name over the video |
| Number Keys Set Speed | `1` to `9` set the speed to 1x to 9x, `0` to 10x |
| Audio and Video Settings | See below |
| Appearance | Theme (light, dark, or system), interface colors, transparency, and button sizes |

**Audio and Video Settings** contains:

- **Video:** brightness, contrast, gamma, saturation, and hue; **Allow 25x maximum video playback speed**; **Apply video settings to all videos** (otherwise they apply to this video only).
- **Audio:** volume, A/V sync, pitch, **Maintain pitch when speed changes**, and **Apply audio settings to all videos**.
- **Navigation:** the small and large skip intervals (default 1 s and 5 s).
- **Audio Track:** the height of the audio track.

### Fullscreen and windowed mode

On Windows and Linux the annotator opens full screen; on macOS it fills the screen without the menu bar and Dock. Press `F11` or `Ctrl+Shift+W` to switch to a normal window and back.


## Keyboard and mouse controls

These are also listed in the help window (`F1`), together with the event and subject keys of the open video.

| Function | Key |
|----------|-----|
| Play / Pause | `Space` |
| Skip forward / backward (large, default 5 s) | `→` / `←` (also `D` / `A`) |
| Skip forward / backward (small, default 1 s) | `Shift+→` / `Shift+←` (also `Shift+D` / `Shift+A`) |
| Skip forward / backward 10 s | `W` / `S` |
| Step one frame forward / backward | `.` / `,` |
| Increase / decrease playback speed | `+` / `-` |
| Reset speed to 1x | `Backspace` |
| Set speed 1x to 9x / 10x (when enabled in the settings menu) | `1` to `9` / `0` |
| Navigate the annotation list | `↑` / `↓` |
| Delete selected annotation | `Delete` |
| Undo delete | `Ctrl+Z` (`Cmd+Z` on macOS) |
| Toggle fullscreen / windowed mode | `F11` or `Ctrl+Shift+W` |
| Open the help window | `F1` |
| Close video and return to file selection | `Escape` |

Skip intervals are set in **Audio and Video Settings**. The `W`/`A`/`S`/`D` navigation keys can be turned off in the event key editor if you want to use those letters for events. Shortcuts are inactive while a dialog is open.

| Mouse action | Effect |
|--------------|--------|
| Click the progress bar, audio track, or spectrogram | Jump to that time |
| Click the video (zoom on) | Zoom in on that point; drag to move around |
| Right-click an annotation | View Details, Skip to Annotation, Reopen State, Delete |
| Click a list's column header | Sort by that column |
| Right-click a video in the video list | Change its status |
| Right-click an experiment (Summary Statistics) | Delete the experiment |


## Summary statistics

Click **Summary Statistics** on the setup screen.

1. Tick the videos that belong to the experiment (all are ticked by default).
2. Click **Generate Summary** and enter a name for the experiment. To update an existing experiment, select it in the **Experiment** drop-down first; its videos are ticked, and its name is filled in.
3. View the results: choose **Combined** or a single video and click **View Table**, or click **View Box Plots**.

Each run recalculates the per-video summaries from the current annotations, then the combined summary. To delete an experiment, right-click it in the drop-down, or select it and press `Delete`.

**Per-video summary** (`Annotations/Summaries/Individual_Summaries/VideoName_Summary.csv`), one row per event, subject, and type:

| Column | Description |
|--------|-------------|
| `Count` | Number of occurrences |
| `Observations_per_minute` | Occurrences per minute of coded time |
| `Total_Duration_seconds` | Total time in the state (state events) |
| `Percent_Time` | Percentage of coded time in the state (state events) |

**Combined summary** (`Annotations/Summaries/Combined_Summaries/Experiment_Combined_Summary.csv`): `Count`, `Mean_Count_per_video`, `Total_videos`, `Total_Duration_seconds`, `Mean_Duration_per_video`, `Mean_Percent_Time`, and `Mean_Observations_per_minute` across the experiment's videos.

**Box plots** show the distribution across videos for each event. Choose whether to calculate per **Coded Segments** or **Whole Videos**, which events and columns to show, and the event colors; **Export** saves the figure as PNG or JPEG.


## Where your data goes

Everything lives in your project directory, in plain files you can inspect, copy, and edit:

```
YourProject/
├── Annotations/
│   ├── VideoName_Annotations.csv       Complete annotation file per video
│   └── Summaries/
│       ├── Individual_Summaries/       Per-video summary statistics
│       └── Combined_Summaries/         Per-experiment summary statistics
├── Keys/
│   ├── Event_Keys/                     Event keys (reusable across projects)
│   └── Subject_Keys/                   Subject keys
├── Session/                            Per-video session data, working copies, and video lengths
└── Debug/                              Diagnostic logs
```

While you annotate, data is journaled to small chunk files in `Session/` with atomic writes; the consolidated `VideoName_Annotations.csv` is the file you take to analysis. Do not edit the files in `Session/`.

You can also edit `VideoName_Annotations.csv` outside LASERcoder (in Excel, a text editor, or on another computer). The next time that video is opened, LASERcoder compares the file with its working copy, shows a summary of what was added, removed, or changed, and asks whether to apply the edits permanently or discard them. Event key and subject key files are read directly, so edits to those take effect the next time they are loaded. Files saved by Excel on macOS or Windows are read regardless of encoding or line-ending differences.

LASERcoder's own settings (the last project and video directories, display options, colors, and window layout) are kept in `.lasercoder.conf` in your home folder, or in the application folder for the portable versions.


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


## Troubleshooting

- **Diagnostic logs.** Each run writes a log to the project's `Debug/` folder. Before a video is opened, the log is kept in a `LASERcoder_Debug` folder in the system's temporary folder (or the application folder for the portable versions). Include the log when reporting a problem.
- **No sound.** If the computer has no audio output device, videos play silently; this does not affect timing or annotation.
- **Network drives.** LASERcoder warns when the project directory is on a network drive, because its safe-write method is not reliable on network file systems. Keep projects on a local drive and copy them to shared storage with **Backup Project**.
- **Report a problem** by opening an [issue](../../issues) with a description, your operating system, and the log.


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
