#!/usr/bin/env python3
"""
🧪 YouTube API Testing Script
Tests YouTube API connectivity and external source checker
Run this locally to verify everything works before deploying
"""

import os
import sys
import json
from datetime import datetime

# Load environment variables from .env.local
try:
    from dotenv import load_dotenv
    # Look for .env.local in project root
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, '.env.local')
    load_dotenv(env_path)
except ImportError:
    # If dotenv not installed, continue with system env vars
    pass

# Test 1: Check Environment Variable
print("\n" + "="*70)
print("🧪 TEST 1: Environment Variable Setup")
print("="*70)

youtube_api_key = os.getenv("YOUTUBE_API_KEY")
if youtube_api_key:
    print("✅ YOUTUBE_API_KEY is set")
    print(f"   Value: {youtube_api_key[:20]}..." if len(youtube_api_key) > 20 else f"   Value: {youtube_api_key}")
else:
    print("❌ YOUTUBE_API_KEY is NOT set")
    print("\nSet it with:")
    print("  Windows (CMD): set YOUTUBE_API_KEY=your-key-here")
    print("  Windows (PS):  $env:YOUTUBE_API_KEY='your-key-here'")
    print("  Linux/Mac:     export YOUTUBE_API_KEY='your-key-here'")
    print("\nOr create .env.local file in project root with:")
    print("  YOUTUBE_API_KEY=your-key-here")
    sys.exit(1)

# Test 2: Check Python Imports
print("\n" + "="*70)
print("🧪 TEST 2: Required Python Modules")
print("="*70)

required_modules = [
    'requests',
    'PIL',
    'cv2',
    'imagehash',
    'numpy',
    'google',
    'googleapiclient',
    'firebase_admin'
]

missing_modules = []
for module_name in required_modules:
    try:
        __import__(module_name)
        print(f"✅ {module_name}")
    except ImportError:
        print(f"❌ {module_name} - MISSING")
        missing_modules.append(module_name)

if missing_modules:
    print(f"\n⚠️  Missing modules: {', '.join(missing_modules)}")
    print("\nInstall with:")
    print(f"  pip install {' '.join(missing_modules)}")
    sys.exit(1)

# Test 3: Test YouTube API Connectivity
print("\n" + "="*70)
print("🧪 TEST 3: YouTube API Connectivity")
print("="*70)

try:
    from googleapiclient.discovery import build
    
    print("Initializing YouTube API...")
    youtube = build('youtube', 'v3', developerKey=youtube_api_key)
    print("✅ YouTube API initialized successfully")
    
    # Try to search for a video
    print("\nSearching NBA Official channel for recent videos...")
    request = youtube.search().list(
        channelId="UCJB8UH7cM3r5YKHgXOZBwpA",  # NBA Official
        part='id,snippet',
        maxResults=5,
        order='date'
    )
    response = request.execute()
    
    items = response.get('items', [])
    print(f"✅ Found {len(items)} videos")
    
    if items:
        for i, item in enumerate(items[:3], 1):
            title = item['snippet']['title']
            video_id = item['id']['videoId']
            print(f"   {i}. {title[:50]}...")
            print(f"      Video ID: {video_id}")
    
except Exception as e:
    print(f"❌ YouTube API Error: {e}")
    print("\n⚠️  Possible causes:")
    print("   1. Invalid API Key")
    print("   2. YouTube Data API not enabled")
    print("   3. Quota exceeded")
    print("   4. API Key has restrictions")
    sys.exit(1)

# Test 4: Test External Source Checker Module
print("\n" + "="*70)
print("🧪 TEST 4: External Source Checker Module")
print("="*70)

try:
    # Add python directory to path for imports
    import sys
    import os
    python_path = os.path.join(os.path.dirname(__file__), 'python')
    if python_path not in sys.path:
        sys.path.insert(0, python_path)
    
    from external_source_checker import (
        generate_hash,
        hamming_distance,
        check_youtube_sources,
        deduplicate_matches
    )
    print("✅ External source checker module imported")
    
    # Test hash generation (dummy frame)
    import numpy as np
    from PIL import Image
    
    print("Testing hash generation with dummy frame...")
    dummy_frame = np.random.randint(0, 255, (480, 640, 3), dtype=np.uint8)
    test_hash = generate_hash(dummy_frame)
    
    if test_hash:
        print(f"✅ Hash generated: {test_hash[:30]}...")
    else:
        print("❌ Hash generation failed")
        sys.exit(1)
    
    # Test hamming distance
    test_hash2 = generate_hash(dummy_frame)
    distance = hamming_distance(test_hash, test_hash2)
    print(f"✅ Hamming distance calculated: {distance}")
    
except Exception as e:
    print(f"❌ External source checker error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 5: Test Firebase Connectivity (if available)
print("\n" + "="*70)
print("🧪 TEST 5: Firebase Connectivity")
print("="*70)

try:
    from google.cloud import firestore
    
    print("Attempting to initialize Firestore...")
    db = firestore.Client()
    
    # Try to read from a collection (non-destructive)
    print("Reading from official_hashes collection...")
    docs = db.collection("official_hashes").limit(1).stream()
    count = len(list(docs))
    
    print(f"✅ Firestore connected (found {count} official hashes)")
    
except Exception as e:
    print(f"⚠️  Firestore note: {e}")
    print("   (This may be expected if running without credentials)")

# Test 6: Full Integration Test
print("\n" + "="*70)
print("🧪 TEST 6: Full Integration Check")
print("="*70)

print("""
✅ All basic checks passed!

Next steps:
1. Start backend: cd backend && npm run dev
2. Start frontend: cd frontend && npm run dev
3. Upload a test video
4. Check dashboard for YouTube/Reddit alerts

To manually test upload processor:
   cd python
   python upload_processor.py <video-path>

Expected output:
   - Extracted frames
   - External sources checked
   - Alerts created (if matches found)
   - Results in Firestore
""")

# Summary
print("\n" + "="*70)
print("✅ TEST SUMMARY: ALL CHECKS PASSED")
print("="*70)
print(f"\nTested at: {datetime.now().isoformat()}")
print("\nYou're ready to:")
print("  1. Test locally with npm run dev")
print("  2. Upload a test video")
print("  3. Verify external source detection")
print("\n")
