from extract_frames import extract_frames
from hash import generate_hash
from fetch_hashes import fetch_hashes
from compare import hamming_distance

def detect_video(video_path):
    print("🔍 Scanning video...")

    frames = extract_frames(video_path)
    stored_hashes = fetch_hashes()

    match_count = 0

    for frame_id, frame in frames:
        incoming_hash = generate_hash(frame)

        for stored_hash in stored_hashes:
            distance = hamming_distance(incoming_hash, stored_hash)

            if distance < 10:
                match_count += 1
                print(f"🚨 Match found at frame {frame_id} (distance: {distance})")
                break

    # Decision logic
    if match_count > 2:
        print("🔥 PIRACY DETECTED!")
    else:
        print("❌ No significant match")

# TEST
video_path = input("Enter video path: ")
detect_video(video_path)