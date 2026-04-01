import os
import json
import time
from google.cloud import pubsub_v1
from db import db

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "serviceAccountKey.json"
project_id = "bwai-solution-challenge"
topic_id = "video-frames" # Ensure this matches your Pub/Sub topic name

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_id)

print("🟣 INITIALIZING TWITCH INGESTION SIMULATOR...")

# Fetch a real hash from your DB so the demo always works
docs = db.collection("official_hashes").limit(1).get()
valid_hash = docs[0].to_dict()["hash"] if docs else "1010101010101010"

payload = {
    "hash": valid_hash,
    "video_id": "twitch_live_capture_992",
    "source": "Twitch (Live Stream)"
}

data_str = json.dumps(payload)
data_bytes = data_str.encode("utf-8")

print(f"📡 Pushing intercepted Twitch frame to NetraX Core...")
future = publisher.publish(topic_path, data=data_bytes)
print(f"✅ Published message ID: {future.result()}")