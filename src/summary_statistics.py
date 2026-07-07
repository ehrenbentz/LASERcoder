import sys
import os
import csv
import json


def compute_summary_rows(annotations_path, use_whole_video=False):
    """Compute per-event summary rows from annotation data.

    annotations_path may be a per-video chunked directory or a legacy CSV file.
    When use_whole_video is True the coding-start / coding-duration
    session parameters are ignored and the full data span is used instead.
    """
    from annotation_store import read_all_annotation_rows

    if os.path.isdir(annotations_path):
        basename = os.path.basename(annotations_path)
        video_name = (os.path.basename(os.path.dirname(annotations_path))
                      if basename == "Chunks" else basename)
    else:
        base_name = os.path.basename(annotations_path)
        video_name = base_name.removesuffix("_Annotations.csv")

    rows = read_all_annotation_rows(annotations_path)

    if not rows:
        return None

    # coding parameters from session state
    coding_start = 0.0
    coding_duration = None

    if not use_whole_video:
        if os.path.isdir(annotations_path):
            # Chunked: path is Session/VideoName/Chunks/
            # Session state is in Session/VideoName/
            session_state_file = os.path.join(
                os.path.dirname(annotations_path),
                f"{video_name}_session_state.json")
        else:
            # Full CSV: path is Annotations/VideoName_Annotations.csv
            base_dir = os.path.dirname(os.path.dirname(annotations_path))
            session_state_file = os.path.join(
                base_dir, "Session", video_name,
                f"{video_name}_session_state.json")

        if os.path.exists(session_state_file):
            try:
                with open(session_state_file, "r") as fh:
                    state = json.load(fh)
                    coding_start = float(state.get("coding_start", 0))
                    if state.get("coding_duration") is not None:
                        coding_duration = float(state["coding_duration"])
                    elif state.get("coding_end") is not None:
                        coding_duration = (float(state["coding_end"])
                                           - coding_start)
            except (json.JSONDecodeError, ValueError, OSError):
                pass

    coding_end = (coding_start + coding_duration
                  if coding_duration is not None and coding_duration > 0
                  else None)

    # total duration from the data
    total_duration_seconds = 0.0
    for row in rows:
        for col in ("End", "Start"):
            raw = row.get(col, "").strip()
            if raw and raw != "NA":
                try:
                    total_duration_seconds = max(
                        total_duration_seconds, float(raw))
                except ValueError:
                    pass

    analysis_duration = (coding_duration
                         if coding_duration is not None and coding_duration > 0
                         else total_duration_seconds)
    analysis_minutes = analysis_duration / 60 if analysis_duration else 0

    # group rows by (event name, subject), restricted to the coding
    # window when one is defined: point events must fall inside it,
    # state events must overlap it (their durations are clipped to the
    # window in _sum_state_durations)
    rows_by_key = {}
    for row in rows:
        name = row.get("Event", "").strip()
        subject = row.get("Subject", "NA").strip()
        if not subject:
            subject = "NA"
        if not name:
            continue
        if (coding_end is not None
                and not _row_in_window(row, coding_start, coding_end)):
            continue
        key = (name, subject)
        rows_by_key.setdefault(key, []).append(row)

    # per-event-per-subject stats
    summary_rows = []

    for (name, subject), brows in rows_by_key.items():
        btype = _infer_type(brows)
        count = len(brows)
        frequency = count / analysis_minutes if analysis_minutes > 0 else 0

        if btype == "State":
            total_dur = _sum_state_durations(
                brows, coding_start, coding_end)
            pct = (total_dur / analysis_duration * 100
                   if analysis_duration > 0 else 0)
            summary_rows.append({
                "Video": video_name,
                "Event": name,
                "Subject": subject,
                "Type": "State",
                "Count": count,
                "Observations_per_minute": round(frequency, 3),
                "Total_Duration_seconds": round(total_dur, 3),
                "Percent_Time": round(pct, 3),
            })
        else:
            summary_rows.append({
                "Video": video_name,
                "Event": name,
                "Subject": subject,
                "Type": "Point",
                "Count": count,
                "Observations_per_minute": round(frequency, 3),
                "Total_Duration_seconds": "",
                "Percent_Time": "",
            })

    summary_rows.sort(key=lambda r: (r["Type"], r["Event"], r.get("Subject", "")))
    return summary_rows


def generate_summary_statistics(annotations_path, custom_output_file=None):
    """
    Generate summary statistics from annotation data.

    annotations_path may be a per-video chunked directory or a legacy CSV file.
    """
    summary_rows = compute_summary_rows(annotations_path)
    if summary_rows is None:
        return None

    if os.path.isdir(annotations_path):
        basename = os.path.basename(annotations_path)
        video_name = (os.path.basename(os.path.dirname(annotations_path))
                      if basename == "Chunks" else basename)
        # Chunks dir: Session/VideoName/Chunks → output root 3 up
        if basename == "Chunks":
            base_dir = os.path.dirname(
                os.path.dirname(os.path.dirname(annotations_path)))
        else:
            base_dir = os.path.dirname(os.path.dirname(annotations_path))
    else:
        base_name = os.path.basename(annotations_path)
        video_name = base_name.removesuffix("_Annotations.csv")
        base_dir = os.path.dirname(os.path.dirname(annotations_path))

    if custom_output_file is None:
        summary_dir = os.path.join(
            base_dir, "Annotations", "Summaries")
        os.makedirs(summary_dir, exist_ok=True)
        output_file = os.path.join(summary_dir, f"{video_name}_Summary.csv")
    else:
        output_file = custom_output_file

    fieldnames = [
        "Video", "Event", "Subject", "Type", "Count",
        "Observations_per_minute", "Total_Duration_seconds", "Percent_Time",
    ]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    # Generate complete (non-chunked) annotations file alongside the summary
    if custom_output_file is None:
        from annotation_store import read_all_annotation_rows, AnnotationStore
        all_rows = read_all_annotation_rows(annotations_path)
        if all_rows:
            complete_file = os.path.join(
                summary_dir, f"{video_name}_Annotations.csv")
            with open(complete_file, "w", newline="",
                      encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(
                    fh, fieldnames=AnnotationStore.CSV_HEADERS)
                writer.writeheader()
                writer.writerows(all_rows)

    return output_file


def combine_summaries(summary_files, output_file):
    """
    Combine multiple per-video summary CSVs into an aggregate summary

    """
    all_rows = []
    for path in summary_files:
        try:
            with open(path, "r", newline="", encoding="utf-8-sig") as fh:
                all_rows.extend(csv.DictReader(fh))
        except OSError:
            pass

    if not all_rows:
        return None

    # Group by (Event, Subject, Type)
    groups = {}
    for row in all_rows:
        key = (row.get("Event", ""),
               row.get("Subject", "NA"),
               row.get("Type", ""))
        groups.setdefault(key, []).append(row)

    summary_rows = []
    for (event, subject, btype), group in sorted(groups.items()):
        counts = [int(r["Count"]) for r in group]
        obs_rates = [float(r["Observations_per_minute"]) for r in group
                     if r.get("Observations_per_minute")]

        entry = {
            "Event": event,
            "Subject": subject,
            "Type": btype,
            "Count": sum(counts),
            "Mean_Count_per_video": round(_mean(counts), 3),
            "Total_videos": len(group),
        }

        if btype == "State":
            durations = [float(r["Total_Duration_seconds"]) for r in group
                         if r.get("Total_Duration_seconds")]
            percents = [float(r["Percent_Time"]) for r in group
                        if r.get("Percent_Time")]
            entry["Total_Duration_seconds"] = round(sum(durations), 3)
            entry["Mean_Duration_per_video"] = round(_mean(durations), 3)
            entry["Mean_Percent_Time"] = round(_mean(percents), 3)
        else:
            entry["Total_Duration_seconds"] = ""
            entry["Mean_Duration_per_video"] = ""
            entry["Mean_Percent_Time"] = ""

        entry["Mean_Observations_per_minute"] = round(_mean(obs_rates), 3)
        summary_rows.append(entry)

    fieldnames = [
        "Event", "Subject", "Type", "Count", "Mean_Count_per_video",
        "Total_videos", "Total_Duration_seconds", "Mean_Duration_per_video",
        "Mean_Percent_Time", "Mean_Observations_per_minute",
    ]

    with open(output_file, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    return output_file


# Internal helpers

def _mean(values):
    """Return the arithmetic mean of *values*, or 0 when empty"""
    return sum(values) / len(values) if values else 0


def _safe_float(raw):
    """Convert raw to float"""
    if not raw or raw == "NA":
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _infer_type(rows):
    """Infer whether a set of annotation rows represents a State or Point"""
    for row in rows:
        raw = row.get("Type", "").strip()
        if raw:
            return raw.capitalize()
    # Fallback: if any row has a non-empty Duration, treat as State
    for row in rows:
        dur = row.get("Duration", "").strip()
        if dur and dur != "NA":
            return "State"
    return "Point"


def _row_is_state(row):
    """Best-effort per-row State/Point classification."""
    raw = row.get("Type", "").strip().lower()
    if raw:
        return raw == "state"
    dur = row.get("Duration", "").strip()
    end = row.get("End", "").strip()
    return bool((dur and dur != "NA") or (end and end != "NA"))


def _row_in_window(row, coding_start, coding_end):
    """Return True if an annotation belongs to the coding window.

    Point events: timestamp inside the window.
    State events: any overlap with the window (still-open events count
    as extending to the end of the video).
    Rows whose timestamps cannot be parsed are kept.
    """
    start = _safe_float(row.get("Start", ""))
    if _row_is_state(row):
        if start is None:
            return True
        if start > coding_end:
            return False
        end = _safe_float(row.get("End", ""))
        if end is not None and end < coding_start:
            return False
        return True
    if start is None:
        return True
    return coding_start <= start <= coding_end


def _sum_state_durations(rows, coding_start, coding_end):
    """Sum durations for state-event rows, clipped to the coding window.

    Start/End timestamps are preferred so events crossing a window
    boundary contribute only their in-window portion. The Duration
    column is used only when timestamps are missing or unparsable
    (it cannot be clipped in that case).
    """
    total = 0.0
    for row in rows:
        start = _safe_float(row.get("Start", ""))
        end = _safe_float(row.get("End", ""))

        if start is not None and end is not None:
            if coding_end is not None:
                if end < coding_start or start > coding_end:
                    continue
                start = max(start, coding_start)
                end = min(end, coding_end)
            total += max(0.0, end - start)
            continue

        # Fall back to the explicit Duration column
        dur_val = _safe_float(row.get("Duration", "").strip())
        if dur_val is not None:
            total += max(0.0, dur_val)

    return total


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python summary_statistics.py <annotations_file>")
        sys.exit(1)

    path = sys.argv[1]
    if not os.path.exists(path):
        print(f"Error: File {path} not found")
        sys.exit(1)

    result = generate_summary_statistics(path)
    if result:
        print(f"Summary saved to {result}")
    else:
        print("No annotations found — nothing to summarise.")
