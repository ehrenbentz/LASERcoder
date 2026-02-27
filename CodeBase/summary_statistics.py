import sys
import os
import csv
import json


def generate_summary_statistics(annotations_file, custom_output_file=None):
    """
    Generate summary statistics from an annotation CSV file.

    """
    base_name = os.path.basename(annotations_file)
    video_name = base_name.replace("_Annotations.csv", "")

    # Read annotation rows
    with open(annotations_file, "r", newline="") as fh:
        rows = list(csv.DictReader(fh))

    if not rows:
        return None

    # --- coding parameters from session state ----------------------------
    coding_start = 0.0
    coding_duration = None

    annotations_dir = os.path.dirname(annotations_file)
    base_dir = os.path.dirname(annotations_dir)
    session_state_file = os.path.join(
        base_dir, "Resume", f"{video_name}_session_state.json")

    if os.path.exists(session_state_file):
        try:
            with open(session_state_file, "r") as fh:
                state = json.load(fh)
                coding_start = float(state.get("coding_start", 0))
                if state.get("coding_duration") is not None:
                    coding_duration = float(state["coding_duration"])
                elif state.get("coding_end") is not None:
                    coding_duration = float(state["coding_end"]) - coding_start
        except (json.JSONDecodeError, ValueError, OSError):
            pass

    # --- total duration from the data ------------------------------------
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

    # --- group rows by behaviour name ------------------------------------
    rows_by_name = {}
    for row in rows:
        name = row.get("Event", "").strip()
        if name:
            rows_by_name.setdefault(name, []).append(row)

    # --- compute per-behaviour stats -------------------------------------
    summary_rows = []

    for name, brows in rows_by_name.items():
        btype = _infer_type(brows)
        count = len(brows)
        frequency = count / analysis_minutes if analysis_minutes > 0 else 0

        if btype == "State":
            total_dur = _sum_state_durations(
                brows, coding_start, coding_duration)
            pct = (total_dur / analysis_duration * 100
                   if analysis_duration > 0 else 0)
            summary_rows.append({
                "Video": video_name,
                "Event": name,
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
                "Type": "Point",
                "Count": count,
                "Observations_per_minute": round(frequency, 3),
                "Total_Duration_seconds": "",
                "Percent_Time": "",
            })

    summary_rows.sort(key=lambda r: (r["Type"], r["Event"]))

    # --- write output CSV ------------------------------------------------
    if custom_output_file is None:
        summary_dir = os.path.join(base_dir, "Summary")
        os.makedirs(summary_dir, exist_ok=True)
        output_file = os.path.join(summary_dir, f"{video_name}_Summary.csv")
    else:
        output_file = custom_output_file

    fieldnames = [
        "Video", "Event", "Type", "Count",
        "Observations_per_minute", "Total_Duration_seconds", "Percent_Time",
    ]

    with open(output_file, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    return output_file


def combine_summaries(summary_files, output_file):
    """
    Combine multiple per-video summary CSVs into an aggregate summary.

    """
    all_rows = []
    for path in summary_files:
        try:
            with open(path, "r", newline="") as fh:
                all_rows.extend(csv.DictReader(fh))
        except OSError:
            pass

    if not all_rows:
        return None

    # Group by (Event, Type)
    groups = {}
    for row in all_rows:
        key = (row.get("Event", ""), row.get("Type", ""))
        groups.setdefault(key, []).append(row)

    summary_rows = []
    for (event, btype), group in sorted(groups.items()):
        counts = [int(r["Count"]) for r in group]
        obs_rates = [float(r["Observations_per_minute"]) for r in group
                     if r.get("Observations_per_minute")]

        entry = {
            "Event": event,
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
        "Event", "Type", "Count", "Mean_Count_per_video", "Total_videos",
        "Total_Duration_seconds", "Mean_Duration_per_video",
        "Mean_Percent_Time", "Mean_Observations_per_minute",
    ]

    with open(output_file, "w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(summary_rows)

    return output_file


# ======================================================================
# Internal helpers
# ======================================================================

def _mean(values):
    """Return the arithmetic mean of *values*, or 0 when empty."""
    return sum(values) / len(values) if values else 0


def _safe_float(raw):
    """Convert *raw* to float, returning *None* on failure."""
    if not raw or raw == "NA":
        return None
    try:
        return float(raw)
    except (ValueError, TypeError):
        return None


def _infer_type(rows):
    """Infer whether a set of annotation rows represents a State or Point."""
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


def _sum_state_durations(rows, coding_start, coding_duration):
    """Sum durations for state-behaviour rows, clipping to the coding period."""
    total = 0.0
    coding_end = (coding_start + coding_duration
                  if coding_duration is not None else None)

    for row in rows:
        # Prefer the explicit Duration column when available
        dur_raw = row.get("Duration", "").strip()
        if dur_raw and dur_raw != "NA":
            dur_val = _safe_float(dur_raw)
            if dur_val is not None:
                total += dur_val
                continue

        # Fall back to Start/End
        start = _safe_float(row.get("Start", ""))
        end = _safe_float(row.get("End", ""))
        if start is None or end is None:
            continue

        if coding_end is not None:
            if end < coding_start or start > coding_end:
                continue
            start = max(start, coding_start)
            end = min(end, coding_end)

        total += end - start

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
