"""
Quick Test Script for Judge Upload Feature
Tests the detection pipeline with a simple workflow
"""
from google.cloud import firestore
import datetime

db = firestore.Client()

def check_official_hashes():
    """Check if any official hashes exist"""
    print("🔍 Checking for official reference hashes...")
    hashes = list(db.collection("official_hashes").limit(5).stream())
    
    if len(hashes) == 0:
        print("❌ No official hashes found!")
        print("💡 You need to upload an OFFICIAL video first to create reference hashes")
        print("\nSteps:")
        print("1. Use the upload button to upload a video (any video)")
        print("2. Wait 5 seconds for processing")
        print("3. Upload the SAME video again")
        print("4. You should see 100% match detection\n")
        return False
    else:
        print(f"✅ Found {len(hashes)} official hash entries")
        for hash_doc in hashes:
            data = hash_doc.to_dict()
            print(f"   - Video ID: {data.get('video_id')}, Hash: {data.get('hash')}")
        return True

def check_recent_alerts():
    """Check for recent piracy alerts"""
    print("\n🚨 Checking for recent alerts...")
    alerts = list(db.collection("piracy_alerts").order_by("timestamp", direction=firestore.Query.DESCENDING).limit(5).stream())
    
    if len(alerts) == 0:
        print("⚠️ No alerts found")
        print("💡 This means no matches were detected yet")
    else:
        print(f"✅ Found {len(alerts)} recent alerts")
        for alert_doc in alerts:
            data = alert_doc.to_dict()
            print(f"   - Source: {data.get('source')}, Risk: {data.get('risk_score')}%, Category: {data.get('misuse_category')}")

def create_test_hash(test_hash="test_hash_12345"):
    """Create a test official hash for demo"""
    print(f"\n🎬 Creating test official hash...")
    db.collection("official_hashes").add({
        "video_id": "test_official_video",
        "frame_id": 0,
        "hash": test_hash,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })
    print(f"✅ Created test hash: {test_hash}")
    print("💡 Now you can test by uploading any video that generates this hash")

if __name__ == "__main__":
    print("🎬 NetraX Judge Upload - Diagnostic Tool")
    print("=" * 50)
    
    has_hashes = check_official_hashes()
    check_recent_alerts()
    
    if not has_hashes:
        create_test = input("\n❓ Create a test official hash for testing? (y/n): ")
        if create_test.lower() == 'y':
            create_test_hash()
    
    print("\n" + "=" * 50)
    print("✅ Diagnostic complete!")
    print("\n📝 Next steps:")
    print("1. Upload a video using the dashboard upload button")
    print("2. Check backend terminal for Python execution logs")
    print("3. Re-run this script to see if alerts were created")
