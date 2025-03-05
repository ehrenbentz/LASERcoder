import pandas as pd
import sys
import os
from collections import defaultdict

def generate_summary_statistics(annotations_file):
    """
    Generate summary statistics from annotation file.
    
    Parameters:
    -----------
    annotations_file : str
        Path to the _Annotations.csv file
        
    Returns:
    --------
    None, but writes a _Summary.csv file
    """
    # Extract video file name from annotations filename
    base_name = os.path.basename(annotations_file)
    video_name = base_name.replace("_Annotations.csv", "")
    
    # Read annotation data
    df = pd.read_csv(annotations_file)
    
    # Calculate total video duration (max timestamp in the data)
    total_duration_seconds = max(
        df['End'].max() if not pd.isna(df['End']).all() else 0,
        df['Start'].max() if not pd.isna(df['Start']).all() else 0
    )
    
    total_duration_minutes = total_duration_seconds / 60
    
    # Group behaviors by Name
    behaviors = {}
    
    # Collect unique behavior names
    unique_behaviors = df['Name'].unique()
    
    for behavior in unique_behaviors:
        behavior_df = df[df['Name'] == behavior]
        behavior_type = behavior_df['Type'].iloc[0]
        
        # Count instances
        count = len(behavior_df)
        
        # Calculate frequency (instances per minute)
        frequency = count / total_duration_minutes if total_duration_minutes > 0 else 0
        
        if behavior_type == 'State':
            # Sum durations for state behaviors
            total_duration = behavior_df['Duration'].sum()
            # Calculate percentage of total time
            percent_time = (total_duration / total_duration_seconds) * 100 if total_duration_seconds > 0 else 0
            
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
            'Behavior': behavior,
            'Type': stats['Type'],
            'Count': stats['Count'],
            'Frequency_per_minute': round(stats['Frequency'], 2),
            'Total_Duration_seconds': round(stats['Total_Duration'], 2) if stats['Total_Duration'] is not None else None,
            'Percent_Time': round(stats['Percent_Time'], 2) if stats['Percent_Time'] is not None else None
        })
    
    summary_df = pd.DataFrame(summary_data)
    
    # Add video metadata to the summary
    summary_df = summary_df.sort_values(by=['Type', 'Behavior'])
    
    # Create output filename
    output_file = annotations_file.replace("_Annotations.csv", "_Summary.csv")
    
    # Write summary to CSV
    summary_df.to_csv(output_file, index=False)
    
    print(f"Summary statistics saved to {output_file}")
    print(f"Video duration: {total_duration_seconds:.2f} seconds ({total_duration_minutes:.2f} minutes)")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python annotation_summary.py <annotations_file>")
        sys.exit(1)
    
    annotations_file = sys.argv[1]
    
    if not os.path.exists(annotations_file):
        print(f"Error: File {annotations_file} not found")
        sys.exit(1)
        
    if not annotations_file.endswith("_Annotations.csv"):
        print("Warning: Input file does not follow the expected naming convention: <Video_File>_Annotations.csv")
    
    generate_summary_statistics(annotations_file)
