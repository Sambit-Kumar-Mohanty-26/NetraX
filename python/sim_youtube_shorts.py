import os
import json
import time
from google.cloud import pubsub_v1
from db import db

os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "serviceAccountKey.json"
project_id = "bwai-solution-challenge"
topic_id = "video-frames" 

publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path(project_id, topic_id)

print("🔴 INITIALIZING YOUTUBE SHORTS SCRAPER...")

docs = db.collection("official_hashes").limit(1).get()
valid_hash = docs[0].to_dict()["hash"] if docs else "1010101010101010"

payload = {
    "hash": valid_hash, 
    "video_id": "yt_shorts_viral_edit_01",
    "source": "YouTube Shorts"
}

data_str = json.dumps(payload)
data_bytes = data_str.encode("utf-8")

print(f"📡 Pushing suspected YouTube Short to NetraX Core...")
future = publisher.publish(topic_path, data=data_bytes)
print(f"✅ Published message ID: {future.result()}")