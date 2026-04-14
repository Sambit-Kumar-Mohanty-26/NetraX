"""
Process Test Video for Piracy Detection
Accepts path via environment variable or command line
Used for judge upload demo - simulates Pub/Sub workflow
"""
import os
import sys
from extract_frames import extract_frames
from hash import generate_hash
from publisher import publish_frame
import datetime
from google.cloud import firestore
import base64
import json

# Initialize Firestore
db = firestore.Client()

def process_video(video_path):
    """Original function for regular workflow"""
    print("📡 Sending frames to Pub/Sub...")
    frames = extract_frames(video_path)
    for _, frame in frames:
        hash_value = generate_hash(frame)
        publish_frame(hash_value)
    print("✅ Done sending frames")

def process_test_video_for_judge(video_path):
    """Enhanced function for judge demo - DIRECT detection without Pub/Sub"""
    print(f"🚨 Processing TEST video for piracy detection")
    print(f"📁 Path: {video_path}")
    
    if not os.path.exists(video_path):
        print(f"❌ Error: Video file not found at {video_path}")
        return False
    
    try:
        # Extract frames
        print("🎞️ Extracting frames...")
        frames = extract_frames(video_path)
        print(f"✅ Extracted {len(frames)} frames")

        # Process each frame DIRECTLY (bypass Pub/Sub for judge demo)
        for frame_id, frame in frames[:3]:  # First 3 frames for demo
            print(f"\n🔍 Processing frame {frame_id}...")
            
            # Generate hash
            hash_value = generate_hash(frame)
            
            # Check for matches in official_hashes
            matches = db.collection("official_hashes").where("hash", "==", hash_value).limit(1).stream()
            
            match_found = False
            for match in matches:
                match_found = True
                match_data = match.to_dict()
                print(f"   ⚠️ MATCH FOUND! Hash: {hash_value}")
                print(f"   📌 Official Video ID: {match_data.get('video_id')}")
                
                # DIRECT DETECTION: Call the full pipeline synchronously
                print(f"   🚀 Running DIRECT detection pipeline...")
                
                # Convert frame to base64
                from PIL import Image
                import io
                pil_img = Image.fromarray(frame)
                buffer = io.BytesIO()
                pil_img.save(buffer, format='JPEG')
                frame_base64 = base64.b64encode(buffer.getvalue()).decode()
                
                # Create detection payload
                video_id = f"judge_upload_{int(datetime.datetime.now().timestamp())}"
                payload = {
                    "video_id": video_id,
                    "frame_id": frame_id,
                    "frame_data": frame_base64,
                    "original_hash": hash_value,
                    "timestamp": datetime.datetime.utcnow().isoformat(),
                    "source": "Judge Upload",
                    "url": os.path.basename(video_path),
                    "matched_official_id": match_data.get("video_id")
                }
                
                # Run the FULL detection pipeline (what subscriber.py does)
                try:
                    # Import detection functions
                    from gemini_vision import analyze_frame_with_gemini_vision
                    from deepfake_detector import detect_deepfake
                    
                    print(f"   🤖 Stage 3: Gemini Vision + Deepfake analysis...")
                    
                    # Run Gemini Vision analysis
                    gemini_result = analyze_frame_with_gemini_vision(frame_base64, payload)
                    
                    if gemini_result:
                        # Calculate risk score
                        base_score = gemini_result.get('embedding_score', 88)
                        misuse_category = gemini_result.get('misuse_category', 'Unknown')
                        
                        # Apply multipliers
                        multiplier = 1.0
                        if gemini_result.get('is_deepfake'):
                            multiplier = 1.3
                        elif misuse_category == "Raw Piracy":
                            multiplier = 1.15
                        elif misuse_category == "Meme":
                            multiplier = 0.8
                        elif misuse_category == "Fair Use":
                            multiplier = 0.5
                        
                        risk_score = min(base_score * multiplier, 100)
                        
                        # Store alert to Firestore
                        alert_data = {
                            "video_id": video_id,
                            "source": "Judge Upload",
                            "timestamp": firestore.SERVER_TIMESTAMP,
                            "confidence": base_score,
                            "risk_score": risk_score,
                            "misuse_category": misuse_category,
                            "misuse_reasoning": gemini_result.get('misuse_reasoning', 'Detected from uploaded video'),
                            "matched_official_id": match_data.get("video_id"),
                            "alert_type": "HIGH_RISK" if risk_score > 85 else "MEDIUM_RISK" if risk_score > 50 else "LOW_RISK"
                        }
                        
                        # Add to piracy_alerts collection
                        alert_ref = db.collection("piracy_alerts").add(alert_data)
                        print(f"   ✅ Alert stored to Firestore: {alert_ref[1].id}")
                        print(f"   ⚡ Risk Score: {risk_score:.1f}%")
                        print(f"   🔍 Classification: {misuse_category}")
                        
                        # Also publish to Pub/Sub for propagation tracking
                        try:
                            publish_frame(hash_value)
                        except:
                            print(f"   ℹ️ Pub/Sub publish skipped (not critical for demo)")
                        
                except Exception as e:
                    print(f"   ⚠️ AI analysis error: {e}")
                    import traceback
                    traceback.print_exc()
                
            if not match_found:
                print(f"   ℹ️ No match found for frame {frame_id}")
                print(f"   💡 TIP: Upload an official video first to create reference hashes")

        print(f"\n🎉 Test video processing complete!")
        print(f"📊 Check your NetraX dashboard for real-time alerts!")
        return True
        
    except Exception as e:
        print(f"❌ Error processing video: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    # Priority 1: Environment variable (from backend)
    video_path = os.environ.get("VIDEO_PATH")
    
    # Priority 2: Command line argument
    if not video_path and len(sys.argv) > 1:
        video_path = sys.argv[1]
    
    # Priority 3: Interactive input (legacy)
    if not video_path:
        video_path = input("Enter video name: ")
    
    # If called from upload endpoint, use enhanced version
    if os.environ.get("VIDEO_PATH"):
        success = process_test_video_for_judge(video_path)
        sys.exit(0 if success else 1)
    else:
        # Regular workflow
        process_video(video_path)
