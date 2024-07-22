import argparse
import subprocess
import re

def parse_arguments():
    parser = argparse.ArgumentParser(description='Cut silences from a video.')
    parser.add_argument('infile', type=str, help='Input video file')
    parser.add_argument('outfile', type=str, help='Output video file')
    parser.add_argument('silence_dB', type=float, help='Silence dB threshold')
    parser.add_argument('min_silence_duration', type=int, help='Minimum silence duration to cut in seconds')
    return parser.parse_args()

def get_video_duration(infile):
    command = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', infile
    ]
    result = subprocess.run(command, stdout=subprocess.PIPE, universal_newlines=True)
    return float(result.stdout.strip())

def findSilences(infile, silence_dB, min_silence_duration):
    command = [
        'ffmpeg', '-i', infile, '-af',
        f'silencedetect=noise={silence_dB}dB:d={min_silence_duration}', 
        '-f', 'null', '-'
    ]
    result = subprocess.run(command, stderr=subprocess.PIPE, universal_newlines=True)
    output = result.stderr

    silence_starts = []
    silence_ends = []

    for line in output.split('\n'):
        if 'silence_start' in line:
            silence_start = float(re.search(r'silence_start: (\d+(\.\d+)?)', line).group(1))
            silence_starts.append(silence_start)
        elif 'silence_end' in line:
            silence_end = float(re.search(r'silence_end: (\d+(\.\d+)?)', line).group(1))
            silence_ends.append(silence_end)

    return list(zip(silence_starts, silence_ends))

def cut_silences(infile, outfile, silence_dB, min_silence_duration):
    silences = findSilences(infile, silence_dB, min_silence_duration)
    duration = get_video_duration(infile)

    segments = []
    last_end = 0
    for start, end in silences:
        if start > last_end:
            segments.append((last_end, start))
        last_end = end
    if last_end < duration:
        segments.append((last_end, duration))

    filters = []
    for i, (start, end) in enumerate(segments):
        filters.append(f"[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{i}];")
        filters.append(f"[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{i}];")

    filter_complex = ''.join(filters)
    concat_filter = ''.join([f"[v{i}][a{i}]" for i in range(len(segments))])
    concat_filter += f"concat=n={len(segments)}:v=1:a=1[v][a]"

    command = [
        'ffmpeg', '-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda', '-i', infile, 
        '-filter_complex', filter_complex + concat_filter,
        '-map', '[v]', '-map', '[a]', '-c:v', 'h264_nvenc', outfile
    ]

    subprocess.run(command)

def main():
    args = parse_arguments()
    cut_silences(args.infile, args.outfile, args.silence_dB, args.min_silence_duration)

if __name__ == "__main__":
    main()
