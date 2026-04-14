"""
Ingest Official Video from File Path
Accepts path via environment variable or command line
Used for judge upload demo
"""
import os
import sys
from extract_frames import extract_frames
from hash import generate_hash
from store import store_hash
import datetime

def ingest_video_from_path(video_path, video_id):
    print(f"🎬 Ingesting OFFICIAL video: {video_id}")
    print(f"📁 Path: {video_path}")
    
    if not os.path.exists(video_path):
        print(f"❌ Error: Video file not found at {video_path}")
        return False
    
    try:
        # Extract frames from video
        print("🎞️ Extracting frames...")
        frames = extract_frames(video_path)
        print(f"✅ Extracted {len(frames)} frames")

        # Generate and store hashes for each frame
        print("🔐 Generating perceptual hashes...")
        for frame_id, frame in frames:
            hash_value = generate_hash(frame)
            timestamp = datetime.datetime.utcnow().isoformat()

            store_hash(video_id, frame_id, hash_value, timestamp)
            
            if frame_id % 5 == 0:  # Progress update every 5 frames
                print(f"   ✅ Processed frame {frame_id}")

        print(f"🎉 Official video fully ingested! ({len(frames)} reference hashes created)")
        print(f"📊 Video ID: {video_id}")
        print(f"✅ Ready for detection - upload a test video to see matches!")
        return True
        
    except Exception as e:
        print(f"❌ Error ingesting video: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Priority 1: Environment variables (from backend)
    video_path = os.environ.get("VIDEO_PATH")
    video_id = os.environ.get("VIDEO_ID")
    
    # Priority 2: Command line arguments
    if not video_path and len(sys.argv) > 1:
        video_path = sys.argv[1]
        video_id = sys.argv[2] if len(sys.argv) > 2 else f"official_{int(datetime.datetime.now().timestamp())}"
    
    # Priority 3: Interactive input
    if not video_path:
        video_path = input("Enter official video path (e.g., test.mp4): ")
        video_id = input("Enter a name for this video (e.g., official_match_1): ")
    
    success = ingest_video_from_path(video_path, video_id)
    sys.exit(0 if success else 1)
