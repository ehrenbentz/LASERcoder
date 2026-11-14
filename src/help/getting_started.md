## Getting started

LASERcoder keeps everything for one project in a **project directory** and reads your videos from wherever they already are. Your videos are never modified.

### 1. Choose a project directory

Click **Select Project Directory**. In the folder window, create a new folder (the New Folder button, or right-click), select it, and click **Select Folder**. LASERcoder creates its **Keys**, **Annotations**, and **Session** folders inside it.

- Use a new, empty folder for each project. Your home folder or the top of a drive is not accepted.
- To reopen a project, select its existing folder.
- In the path fields, type part of a folder name and press `Tab` to complete it.

### 2. Choose the video directory

Click **Select Video Directory** and pick the folder that holds your videos. They are listed with their length, size, date, and the position you last reached. Click a column header to sort, and drag a header edge to resize a column.

- A yellow dot marks a video in progress and a green check marks a completed one. Right-click a video to change its status.
- If a recording is split into several files, put each recording's files in their own subfolder and tick **My videos are split into multiple parts**. Each subfolder is then listed as one video, and its parts play back to back in file name order.

### 3. Open a video

Double-click a video, or select it and press `Enter`.

### 4. Event key

The first time, create an **event key**: the list of behaviors you score. Each event has a name, a shortcut key, and a type:

- **Point**: an instant. One key press records one time.
- **State**: a behavior with a duration. Press once to start and again to end.

Events in the same **mutually exclusive (ME) group** cannot overlap: starting one ends the other. Event keys are saved in the project and can be reused. Then click **Start Video**.

### 5. Subject key (optional)

If you score more than one individual, click **Subjects** in the annotator and create a subject key. Each subject gets a shortcut key and optionally a color and an ME group. Every annotation records which subjects were active.

### Names

Event, subject, and group names may contain letters, numbers, spaces, and `_ - . ( )`. The name `NA` is reserved.
