from db import db
from datetime import datetime

def store_alert(video_id, confidence):
    db.collection("alerts").add({
        "video_id": video_id,
        "confidence": confidence,
        "timestamp": datetime.utcnow().isoformat(),
        "status": "MATCH",
        "source": "Simulated Stream"
    })