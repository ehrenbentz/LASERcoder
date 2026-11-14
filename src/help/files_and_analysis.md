## Where your data is saved

Everything is in the project directory, as plain files:

- **Annotations**: *VideoName*_Annotations.csv, the complete annotation file for each video, and the **Summaries** folder.
- **Keys**: the Event_Keys and Subject_Keys folders.
- **Session**: working copies saved while you annotate, and your position in each video. Do not edit these.
- **Debug**: diagnostic logs. Include these when reporting a problem.

## The annotation file

Each row is one annotation. Use **Start**, **End**, and **Duration** (seconds) for analysis; **H_Start** and **H_End** are the same times in readable form. **Subject** is NA when no subject was active, and **Manual_Edit** is True for edited rows.

You may edit *VideoName*_Annotations.csv in Excel or a text editor. The next time the video is opened, LASERcoder shows what changed and asks whether to apply or discard the edits.

## Tools on the start screen

- **View Annotations**: view a video's annotations as a table or timeline, or delete them.
- **Import Annotations**: add annotations from a CSV in LASERcoder format, merged with or replacing the existing ones.
- **Export Annotations**: save the annotations of any or all videos to a location you choose, as one combined CSV or one file per video.
- **Summary Statistics**: tick the videos of an experiment, click **Generate Summary**, and name it. View the results as tables or box plots. Right-click an experiment, or press Delete, to remove it.
- **Backup Project**: copy the whole project to another location.
- **Move Project**: move the project to a new location.

## More information

Full documentation, downloads, and bug reports: <https://github.com/ehrenbentz/LASERcoder>
