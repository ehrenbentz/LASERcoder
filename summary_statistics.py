# summary_statistics.py

import pandas as pd
import sys
import os
import json
from collections import defaultdict

def generate_summary_statistics(annotations_file, custom_output_file=None):
    """
    Generate summary statistics from annotation file.
    
    Parameters:
    -----------
    annotations_file : str
        Path to the _Annotations.csv file
    custom_output_file : str, optional
        Path to save the summary output. If None, a default is generated based on the input filename.
        
    Returns:
    --------
    Path to the created summary file or None if the file is empty
    """
    # Extract video file name from annotations filename
    base_name = os.path.basename(annotations_file)
    video_name = base_name.replace("_Annotations.csv", "")
    
    # Read annotation data
    df = pd.read_csv(annotations_file)
    
    # Skip empty files - make sure we return None to indicate empty file
    if df.empty:
        print(f"Warning: {video_name} contained no observations. Skipping.")
        return None
    
    # Calculate total video duration (max timestamp in the data)
    try:
        total_duration_seconds = max(
            df['End'].dropna().max() if not df['End'].dropna().empty else 0,
            df['Start'].dropna().max() if not df['Start'].dropna().empty else 0
        )
    except:
        print(f"Warning: Could not determine duration for {video_name}. Using 0.")
        total_duration_seconds = 0
    
    # Check for coding start/duration from the session state file
    coding_start = 0
    coding_duration = None
    
    # Determine directories for the session state file
    annotations_dir = os.path.dirname(annotations_file)
    base_dir = os.path.dirname(annotations_dir)
    resume_dir = os.path.join(base_dir, "Resume")
    session_state_file = os.path.join(resume_dir, f"{video_name}_session_state.json")
    
    # Load coding parameters if available
    if os.path.exists(session_state_file):
        try:
            with open(session_state_file, "r") as f:
                session_state = json.load(f)
                coding_start = float(session_state.get("coding_start", 0))
                
                # Try to get coding duration from the file
                if "coding_duration" in session_state and session_state["coding_duration"] is not None:
                    coding_duration = float(session_state["coding_duration"])
                # If no coding_duration but we have coding_end, calculate it
                elif "coding_end" in session_state and session_state["coding_end"] is not None:
                    coding_end = float(session_state["coding_end"])
                    coding_duration = coding_end - coding_start
                    
            print(f"Loaded coding parameters: start={coding_start}, duration={coding_duration}")
        except Exception as e:
            print(f"Warning: Error loading session state: {e}")
    
    # Determine what time range to use for calculations
    analysis_duration = total_duration_seconds
    if coding_duration is not None and coding_duration > 0:
        analysis_duration = coding_duration
        print(f"Using coding duration {analysis_duration} seconds for percentage calculations")
    
    total_duration_minutes = analysis_duration / 60
    
    # Group behaviors by Name
    behaviors = {}
    
    # Collect unique behavior names
    unique_behaviors = df['Name'].unique()
    
    for behavior in unique_behaviors:
        behavior_df = df[df['Name'] == behavior]
        
        # Handle case where Type might be missing
        if 'Type' not in behavior_df.columns or behavior_df['Type'].isnull().all():
            # Try to infer type from other columns
            if 'Duration' in behavior_df.columns and not behavior_df['Duration'].isnull().all():
                behavior_type = 'State'
            else:
                behavior_type = 'Point'
        else:
            behavior_type = behavior_df['Type'].iloc[0]
        
        # Count instances
        count = len(behavior_df)
        
        # Calculate frequency (Observations per minute)
        frequency = count / total_duration_minutes if total_duration_minutes > 0 else 0
        
        if behavior_type == 'State':
            try:
                # Sum durations for state behaviors
                if 'Duration' in behavior_df.columns:
                    total_duration = behavior_df['Duration'].fillna(0).sum()
                else:
                    # Try to calculate duration from Start and End
                    total_duration = 0
                    
                    # Filter for behaviors that fall within coding period if it exists
                    for _, row in behavior_df.iterrows():
                        if pd.notnull(row.get('Start')) and pd.notnull(row.get('End')):
                            start_time = row['Start']
                            end_time = row['End']
                            
                            # If coding period defined, adjust state behavior times
                            if coding_duration is not None:
                                # Skip behaviors that end before coding start or start after coding end
                                if end_time < coding_start or start_time > coding_start + coding_duration:
                                    continue
                                    
                                # Clip start and end times to the coding period
                                start_time = max(start_time, coding_start)
                                end_time = min(end_time, coding_start + coding_duration)
                            
                            # Add the (potentially adjusted) duration
                            total_duration += (end_time - start_time)
                
                # Calculate percentage of total time based on analysis duration
                percent_time = (total_duration / analysis_duration) * 100 if analysis_duration > 0 else 0
            except Exception as e:
                print(f"Warning: Error calculating durations for {behavior}: {e}")
                total_duration = 0
                percent_time = 0
            
            behaviors[behavior] = {
                'Type': 'State',
                'Count': count,
                'Frequency': frequency,
                'Total_Duration': total_duration,
                'Percent_Time': percent_time
            }
        else:  # Point behavior
            behaviors[behavior] = {
                'Type': 'Point',
                'Count': count,
                'Frequency': frequency,
                'Total_Duration': None,
                'Percent_Time': None
            }
    
    # Create summary dataframe
    summary_data = []
    for behavior, stats in behaviors.items():
        summary_data.append({
            'Video': video_name,
            'Behavior': behavior,
            'Type': stats['Type'],
            'Count': stats['Count'],
            'Observations_per_minute': round(stats['Frequency'], 3),
            'Total_Duration_seconds': round(stats['Total_Duration'], 3) if stats['Total_Duration'] is not None else None,
            'Percent_Time': round(stats['Percent_Time'], 3) if stats['Percent_Time'] is not None else None
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    # Add video metadata to the summary
    summary_df = summary_df.sort_values(by=['Type', 'Behavior'])
    
    # Create output filename
    if custom_output_file is None:
        # First, determine whether we need to put it in a Summary folder
        parent_dir = os.path.dirname(annotations_file)
        base_dir = os.path.dirname(parent_dir)
        summary_dir = os.path.join(base_dir, "Summary")
        
        # Create the directory if it doesn't exist
        os.makedirs(summary_dir, exist_ok=True)
        
        output_file = os.path.join(summary_dir, f"{video_name}_Summary.csv")
    else:
        output_file = custom_output_file
    
    # Write summary to CSV
    summary_df.to_csv(output_file, index=False, float_format='%.3f')
    
    # Include coding information in the console output
    if coding_duration is not None:
        print(f"Summary statistics saved to {output_file}")
        print(f"Video duration: {total_duration_seconds:.2f} seconds ({total_duration_seconds/60:.2f} minutes)")
        print(f"Coding period: {coding_start:.2f} to {coding_start + coding_duration:.2f} seconds ({coding_duration:.2f} seconds, {coding_duration/60:.2f} minutes)")
    else:
        print(f"Summary statistics saved to {output_file}")
        print(f"Video duration: {total_duration_seconds:.2f} seconds ({total_duration_minutes:.2f} minutes)")
    
    return output_file

def combine_summaries(summary_files, output_file):
    """
    Combine multiple summary files into a single summary file.
    
    Parameters:
    -----------
    summary_files : list
        List of paths to summary CSV files
    output_file : str
        Path to save the combined summary
        
    Returns:
    --------
    Path to the created combined summary file
    """
    all_data = []
    
    # Read all summary files
    for file_path in summary_files:
        try:
            df = pd.read_csv(file_path)
            all_data.append(df)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    if not all_data:
        print("No valid summary files found")
        return None
    
    # Combine all data
    combined_df = pd.concat(all_data, ignore_index=True)
    
    # Group by behavior and calculate aggregated statistics
    grouped = combined_df.groupby(['Behavior', 'Type'])
    
    summary_data = []
    for (behavior, btype), group in grouped:
        # Common statistics for all behavior types (removing Video column)
        data = {
            'Behavior': behavior,
            'Type': btype,
            'Count': group['Count'].sum(),
            'Mean_Count_per_video': round(group['Count'].mean(), 3),
            'Total_videos': len(group)
        }
        
        # Add type-specific statistics
        if btype == 'State':
            # For state behaviors, we aggregate durations and percentages
            data.update({
                'Total_Duration_seconds': round(group['Total_Duration_seconds'].sum(), 3),
                'Mean_Duration_per_video': round(group['Total_Duration_seconds'].mean(), 3),
                'Mean_Percent_Time': round(group['Percent_Time'].mean(), 3)
            })
        
        # Add frequency data
        data['Mean_Observations_per_minute'] = round(group['Observations_per_minute'].mean(), 3)
        
        summary_data.append(data)
    
    # Create the combined summary dataframe
    combined_summary = pd.DataFrame(summary_data)
    
    # Sort by type and behavior
    combined_summary = combined_summary.sort_values(by=['Type', 'Behavior'])
    
    # Save the combined summary
    combined_summary.to_csv(output_file, index=False)
    print(f"Combined summary saved to {output_file}")
    
    return output_file

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python summary_statistics.py <annotations_file>")
        sys.exit(1)
    
    annotations_file = sys.argv[1]
    
    if not os.path.exists(annotations_file):
        print(f"Error: File {annotations_file} not found")
        sys.exit(1)
        
    if not annotations_file.endswith("_Annotations.csv"):
        print("Warning: Input file does not follow the expected naming convention: <Video_File>_Annotations.csv")
    
    generate_summary_statistics(annotations_file)