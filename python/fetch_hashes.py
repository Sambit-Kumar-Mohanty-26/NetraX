from db import db

def fetch_hashes():
    docs = db.collection("official_hashes").stream()

    hashes = []

    for doc in docs:
        data = doc.to_dict()
        hashes.append(data["hash"])

    return hashes