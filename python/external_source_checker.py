"""
External Source Checker for Video Uploads
Checks YouTube and Reddit for pirated content matching uploaded videos
"""

import os
import json
import requests
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional
import re
from difflib import SequenceMatcher
import imagehash
from PIL import Image
from io import BytesIO
import cv2
import numpy as np

# Load environment variables from .env.local
try:
    from dotenv import load_dotenv
    env_path = os.path.join(os.path.dirname(__file__), '../.env.local')
    print(f"Looking for .env.local at: {env_path}")
    print(f"File exists: {os.path.exists(env_path)}")
    load_dotenv(env_path)
    print("env.local loaded")
except ImportError:
    print("dotenv not installed - using system env vars")
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# API Keys
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
if YOUTUBE_API_KEY:
    print("YOUTUBE_API_KEY loaded")
else:
    print("ERROR: YOUTUBE_API_KEY NOT found!")
REDDIT_USER_AGENT = "NetraX_Piracy_Detector_v1.0"
EXTERNAL_FRAME_LIMIT = int(os.getenv("EXTERNAL_FRAME_LIMIT", "3"))
YOUTUBE_LOOKBACK_DAYS = int(os.getenv("YOUTUBE_LOOKBACK_DAYS", "365"))
EXTERNAL_MATCH_THRESHOLD = float(os.getenv("EXTERNAL_MATCH_THRESHOLD", "40"))
SOCIAL_MATCH_THRESHOLD = float(os.getenv("SOCIAL_MATCH_THRESHOLD", "35"))

# Target channels and subreddits for sports content
YOUTUBE_CHANNELS = {
    "espn": {"id": "UCiWLfSweyRNmLpgEHekhoAg", "handle": "espn"},
    "sports_center": {"id": "UCEgdi0XIXXZ-qJOFPf4JSKw", "handle": "SportsCenter"},
    "nba": {"id": "UCWJ2lWNubArHWmf3FIHbfcQ", "handle": "NBA"},
    "nfl": {"id": "UCDVYQ4Zhbm3S7__I47EB23A", "handle": "NFL"},
    "mlb": {"id": "UCoLrcjPV5PbUrUyXq5mjc_A", "handle": "MLB"}
}

REDDIT_SUBREDDITS = ["sports", "nba", "nfl", "mlb", "CollegeFootball", "soccer"]
X_SEED_POSTS = os.getenv("X_SEED_POSTS_JSON", "[]")
INSTAGRAM_SEED_POSTS = os.getenv("INSTAGRAM_SEED_POSTS_JSON", "[]")
TIKTOK_SEED_POSTS = os.getenv("TIKTOK_SEED_POSTS_JSON", "[]")


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]", " ", (value or "").lower())).strip()


def title_similarity_score(upload_title: str, candidate_title: str) -> float:
    a = normalize_text(upload_title)
    b = normalize_text(candidate_title)
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio() * 100


def temporal_similarity_score(uploaded_at: Optional[datetime], detected_at: Optional[datetime]) -> float:
    if not uploaded_at or not detected_at:
        return 50.0
    delta_hours = abs((uploaded_at - detected_at).total_seconds()) / 3600
    return max(0.0, 100.0 - min(delta_hours, 168) * (100.0 / 168.0))


def optional_embedding_similarity(upload_title: str, candidate_title: str) -> Optional[float]:
    # MVP fallback: lexical embedding proxy until model embeddings are wired.
    if not upload_title or not candidate_title:
        return None
    return title_similarity_score(upload_title, candidate_title)


def multisignal_score(hash_similarity: float, title_similarity: float, temporal_similarity: float, embedding_similarity: Optional[float]) -> float:
    embedding_value = embedding_similarity if embedding_similarity is not None else title_similarity
    return (
        0.55 * hash_similarity
        + 0.20 * title_similarity
        + 0.15 * temporal_similarity
        + 0.10 * embedding_value
    )


def make_asset_id(platform: str, external_id: str) -> str:
    clean_platform = re.sub(r"[^a-z0-9_-]", "", (platform or "unknown").lower())
    clean_id = re.sub(r"[^a-zA-Z0-9_-]", "", (external_id or "unknown"))
    return f"asset_{clean_platform}_{clean_id}"


def parse_seed_posts(seed_json: str, platform: str) -> List[Dict]:
    try:
        raw = json.loads(seed_json or "[]")
        if not isinstance(raw, list):
            return []
        posts = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            external_id = str(item.get("id") or item.get("post_id") or item.get("video_id") or "")
            if not external_id:
                continue
            posts.append({
                "platform": platform,
                "external_id": external_id,
                "title": str(item.get("title", "")),
                "author": str(item.get("author", "")),
                "url": str(item.get("url", "")),
                "published_at": str(item.get("published_at", "")),
                "thumbnail_url": str(item.get("thumbnail_url", "")),
            })
        return posts
    except Exception:
        return []


def hamming_distance(hash1: str, hash2: str) -> int:
    """Calculate hamming distance between two hashes"""
    if not hash1 or not hash2:
        return 100
    try:
        h1 = imagehash.hex_to_hash(hash1)
        h2 = imagehash.hex_to_hash(hash2)
        return h1 - h2
    except:
        return 100


def generate_hash(frame):
    """Generate perceptual hash from frame"""
    try:
        img = Image.fromarray(frame)
        return str(imagehash.phash(img))
    except Exception as e:
        logger.error(f"Error generating hash: {e}")
        return None


def check_youtube_sources(uploaded_hash: str, video_id: str, upload_context: Optional[Dict] = None) -> List[Dict]:
    """
    Check YouTube channels for similar content
    
    Returns list of matching videos found
    """
    matches = []  # Initialize matches list
    
    try:
        from googleapiclient.discovery import build
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)
        
        logger.info("🔍 Checking YouTube for matching content...")
        lookback_start = datetime.now(timezone.utc) - timedelta(days=YOUTUBE_LOOKBACK_DAYS)
        
        for channel_name, channel_info in YOUTUBE_CHANNELS.items():
            try:
                configured_id = channel_info["id"]
                handle = channel_info["handle"]
                logger.info(f"   📺 Scanning {channel_name} (handle=@{handle})...")
                channel_id = resolve_channel_id(youtube, configured_id, handle)
                if not channel_id:
                    logger.warning(f"   ⚠️ Could not resolve channel id for {channel_name}")
                    continue

                uploads_playlist_id = fetch_uploads_playlist_id(youtube, channel_id)
                if not uploads_playlist_id:
                    logger.warning(f"   ⚠️ Could not resolve uploads playlist for {channel_name} ({channel_id})")
                    continue

                items = fetch_recent_channel_items(youtube, channel_id, uploads_playlist_id)
                logger.info(f"   📹 Found {len(items)} recent uploads in {channel_name}")

                for item in items:
                    snippet = item.get('snippet', {})
                    content = item.get('contentDetails', {})
                    published_at = parse_iso_datetime(content.get('videoPublishedAt') or snippet.get('publishedAt'))
                    if published_at and published_at < lookback_start:
                        continue

                    resource_id = snippet.get('resourceId', {})
                    video_id_yt = resource_id.get('videoId') or content.get('videoId')
                    if not video_id_yt:
                        continue

                    title = snippet.get('title', 'Untitled')
                    thumbs = snippet.get('thumbnails', {})
                    thumbnail_url = (thumbs.get('high') or thumbs.get('medium') or thumbs.get('default') or {}).get('url')
                    if not thumbnail_url:
                        continue

                    logger.info(f"      🔗 Processing: {title[:50]}")
                    match_result = download_and_hash_youtube_thumbnail(
                        thumbnail_url,
                        uploaded_hash,
                        video_id_yt,
                        title,
                        channel_name,
                        published_at,
                        upload_context
                    )
                    logger.info(f"      📊 Match result: {match_result}")

                    if match_result and match_result['multi_signal_score'] >= EXTERNAL_MATCH_THRESHOLD:
                        matches.append(match_result)
                        logger.info(f"      ✅ MATCH FOUND: {title} (multi-signal={match_result['multi_signal_score']:.1f}%)")
            
            except Exception as e:
                logger.warning(f"   ⚠️ Error scanning {channel_name}: {e}")
                continue
        
        if matches:
            logger.info(f"🎉 Found {len(matches)} YouTube matches")
        else:
            logger.info("✅ No YouTube matches found")
            
    except ImportError:
        logger.warning("⚠️ Google API client not installed - skipping YouTube check")
    except Exception as e:
        logger.error(f"❌ YouTube check failed: {e}")
    
    return matches


def fetch_recent_channel_items(youtube, channel_id: str, uploads_playlist_id: str) -> List[Dict]:
    """
    Get recent channel videos with robust fallback.
    """
    items = []

    try:
        response = youtube.playlistItems().list(
            part='snippet,contentDetails',
            playlistId=uploads_playlist_id,
            maxResults=10
        ).execute()
        items = response.get('items', [])
    except Exception as e:
        logger.warning(f"   ⚠️ Upload playlist fetch failed for {channel_id}: {e}")

    if items:
        return items

    # Fallback for channels where uploads playlist is inaccessible/invalid.
    try:
        search_response = youtube.search().list(
            channelId=channel_id,
            part='id,snippet',
            order='date',
            maxResults=10,
            type='video'
        ).execute()
        for search_item in search_response.get('items', []):
            snippet = search_item.get('snippet', {})
            search_video_id = search_item.get('id', {}).get('videoId')
            if not search_video_id:
                continue
            items.append({
                "snippet": {
                    "title": snippet.get("title"),
                    "publishedAt": snippet.get("publishedAt"),
                    "thumbnails": snippet.get("thumbnails", {}),
                    "resourceId": {"videoId": search_video_id}
                },
                "contentDetails": {}
            })
    except Exception as e:
        logger.warning(f"   ⚠️ Search fallback failed for {channel_id}: {e}")

    return items


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """Parse YouTube timestamps safely."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except Exception:
        return None


def resolve_channel_id(youtube, configured_id: str, handle: str) -> Optional[str]:
    """
    Resolve a channel id, preferring handle lookup then configured fallback.
    """
    try:
        response = youtube.channels().list(part='id', forHandle=handle, maxResults=1).execute()
        items = response.get('items', [])
        if items:
            return items[0].get('id')
    except Exception as e:
        logger.warning(f"   ⚠️ Handle lookup failed for @{handle}: {e}")

    try:
        response = youtube.channels().list(part='id', id=configured_id, maxResults=1).execute()
        items = response.get('items', [])
        if items:
            return items[0].get('id')
    except Exception as e:
        logger.warning(f"   ⚠️ Channel ID lookup failed for {configured_id}: {e}")

    return None


def fetch_uploads_playlist_id(youtube, channel_id: str) -> Optional[str]:
    """Get channel uploads playlist id from channel content details."""
    try:
        response = youtube.channels().list(part='contentDetails', id=channel_id, maxResults=1).execute()
        items = response.get('items', [])
        if not items:
            return None
        related = items[0].get('contentDetails', {}).get('relatedPlaylists', {})
        return related.get('uploads')
    except Exception as e:
        logger.warning(f"   ⚠️ Upload playlist lookup failed for {channel_id}: {e}")
        return None


def download_and_hash_youtube_thumbnail(thumbnail_url: str, uploaded_hash: str,
                                        video_id: str, title: str, channel: str,
                                        published_at: Optional[datetime],
                                        upload_context: Optional[Dict]) -> Optional[Dict]:
    """Download YouTube thumbnail and compare with uploaded video hash"""
    try:
        response = requests.get(thumbnail_url, timeout=5)
        if response.status_code != 200:
            return None
        
        # Load image and generate hash
        img = Image.open(BytesIO(response.content))
        img_array = np.array(img)
        thumbnail_hash = generate_hash(img_array)
        
        if not thumbnail_hash:
            return None
        
        # Calculate multi-signal score
        distance = hamming_distance(uploaded_hash, thumbnail_hash)
        hash_similarity = max(0, 100 - (distance * 2.5))  # More tolerant for frame-vs-thumbnail comparisons
        upload_title = (upload_context or {}).get("upload_title", "")
        upload_time = (upload_context or {}).get("uploaded_at")
        title_similarity = title_similarity_score(upload_title, title)
        temporal_similarity = temporal_similarity_score(upload_time, published_at)
        embedding_similarity = optional_embedding_similarity(upload_title, title)
        score = multisignal_score(hash_similarity, title_similarity, temporal_similarity, embedding_similarity)
        
        # DEBUG: Log all comparisons (even if below threshold)
        logger.info(
            f"         📊 {title[:40]}: hash={hash_similarity:.1f}% title={title_similarity:.1f}% "
            f"time={temporal_similarity:.1f}% score={score:.1f}%"
        )
        
        if score >= EXTERNAL_MATCH_THRESHOLD:
            logger.info(f"      ✅ MATCH FOUND: {title} ({score:.1f}% multi-signal)")
            return {
                "source": "YouTube",
                "platform": "YouTube",
                "channel": channel,
                "video_id": video_id,
                "title": title,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": thumbnail_url,
                "similarity": hash_similarity,
                "hash_similarity": hash_similarity,
                "title_similarity": title_similarity,
                "temporal_similarity": temporal_similarity,
                "embedding_similarity": embedding_similarity,
                "multi_signal_score": score,
                "source_platform": "youtube",
                "source_url": f"https://www.youtube.com/watch?v={video_id}",
                "parent_asset_id": make_asset_id("youtube", video_id),
                "asset_id": make_asset_id("upload", video_id),
                "detected_at": datetime.now(timezone.utc).isoformat()
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"Error processing YouTube thumbnail: {e}")
        return None


def check_reddit_sources(uploaded_hash: str, video_id: str, upload_context: Optional[Dict] = None) -> List[Dict]:
    """
    Check Reddit subreddits for similar content
    
    Returns list of matching posts found
    """
    matches = []
    
    try:
        logger.info("🔍 Checking Reddit for matching content...")
        
        for subreddit in REDDIT_SUBREDDITS:
            try:
                logger.info(f"   🤖 Scanning r/{subreddit}...")
                
                # Fetch recent posts from subreddit
                url = f"https://www.reddit.com/r/{subreddit}/new.json?limit=15"
                headers = {'User-Agent': REDDIT_USER_AGENT}
                
                response = requests.get(url, headers=headers, timeout=10)
                if response.status_code != 200:
                    logger.warning(f"   ⚠️ Failed to fetch r/{subreddit}")
                    continue
                
                data = response.json()
                posts = data.get('data', {}).get('children', [])
                logger.info(f"   📊 Found {len(posts)} posts in r/{subreddit}")
                
                for post in posts:
                    post_data = post.get('data', {})
                    post_id = post_data.get('id', 'unknown')
                    title = post_data.get('title', 'Untitled')[:60]
                    author = post_data.get('author', 'unknown')
                    
                    # Check if post has media
                    media = post_data.get('media') or post_data.get('secure_media')
                    if not media:
                        continue
                    
                    # Try to get video or image
                    thumbnail_url = post_data.get('thumbnail')
                    if thumbnail_url and thumbnail_url.startswith('http'):
                        logger.info(f"      🔗 Processing Reddit: {title[:50]}")
                        match_result = download_and_hash_reddit_media(
                            thumbnail_url,
                            uploaded_hash,
                            post_id,
                            title,
                            author,
                            subreddit,
                            datetime.fromtimestamp(post_data.get("created_utc", 0), tz=timezone.utc) if post_data.get("created_utc") else None,
                            upload_context
                        )
                        logger.info(f"      📊 Match result: {match_result}")
                        
                        if match_result and match_result['multi_signal_score'] >= EXTERNAL_MATCH_THRESHOLD:
                            matches.append(match_result)
                            logger.info(f"      ✅ MATCH FOUND: {title} by u/{author} ({match_result['multi_signal_score']:.1f}% multi-signal)")
            
            except Exception as e:
                logger.warning(f"   ⚠️ Error scanning r/{subreddit}: {e}")
                continue
        
        if matches:
            logger.info(f"🎉 Found {len(matches)} Reddit matches")
        else:
            logger.info("✅ No Reddit matches found")
            
    except Exception as e:
        logger.error(f"❌ Reddit check failed: {e}")
    
    return matches


def download_and_hash_reddit_media(media_url: str, uploaded_hash: str,
                                   post_id: str, title: str, author: str,
                                   subreddit: str, published_at: Optional[datetime],
                                   upload_context: Optional[Dict]) -> Optional[Dict]:
    """Download Reddit media and compare with uploaded video hash"""
    try:
        response = requests.get(media_url, timeout=5)
        if response.status_code != 200:
            return None
        
        # Load image and generate hash
        img = Image.open(BytesIO(response.content))
        img_array = np.array(img)
        media_hash = generate_hash(img_array)
        
        if not media_hash:
            return None
        
        # Calculate multi-signal score
        distance = hamming_distance(uploaded_hash, media_hash)
        hash_similarity = max(0, 100 - (distance * 2.5))
        upload_title = (upload_context or {}).get("upload_title", "")
        upload_time = (upload_context or {}).get("uploaded_at")
        title_similarity = title_similarity_score(upload_title, title)
        temporal_similarity = temporal_similarity_score(upload_time, published_at)
        embedding_similarity = optional_embedding_similarity(upload_title, title)
        score = multisignal_score(hash_similarity, title_similarity, temporal_similarity, embedding_similarity)
        
        # DEBUG: Log all comparisons (even if below threshold)
        logger.info(
            f"         📊 r/{subreddit} - {title[:40]}: hash={hash_similarity:.1f}% "
            f"title={title_similarity:.1f}% time={temporal_similarity:.1f}% score={score:.1f}%"
        )
        
        if score >= EXTERNAL_MATCH_THRESHOLD:
            logger.info(f"      ✅ MATCH FOUND: {title} by u/{author} ({score:.1f}% multi-signal)")
            return {
                "source": "Reddit",
                "platform": "Reddit",
                "subreddit": subreddit,
                "post_id": post_id,
                "title": title,
                "author": author,
                "url": f"https://reddit.com/r/{subreddit}/comments/{post_id}",
                "media_url": media_url,
                "similarity": hash_similarity,
                "hash_similarity": hash_similarity,
                "title_similarity": title_similarity,
                "temporal_similarity": temporal_similarity,
                "embedding_similarity": embedding_similarity,
                "multi_signal_score": score,
                "source_platform": "reddit",
                "source_url": f"https://reddit.com/r/{subreddit}/comments/{post_id}",
                "parent_asset_id": make_asset_id("reddit", post_id),
                "detected_at": datetime.now(timezone.utc).isoformat()
            }
        
        return None
        
    except Exception as e:
        logger.warning(f"Error processing Reddit media: {e}")
        return None


def check_all_external_sources(video_frames: List, video_id: str, upload_context: Optional[Dict] = None) -> Dict:
    """
    Check all external sources for matches
    
    Args:
        video_frames: List of (frame_id, frame_array) tuples
        video_id: ID of uploaded video
    
    Returns:
        {
            "youtube_matches": [...],
            "reddit_matches": [...],
            "total_matches": int,
            "external_piracy_detected": bool
        }
    """
    
    print(f"\n{'='*60}")
    print(f"🌐 CHECKING EXTERNAL SOURCES FOR PIRACY")
    print(f"{'='*60}")
    
    youtube_matches = []
    reddit_matches = []
    x_matches = []
    instagram_matches = []
    tiktok_matches = []
    upload_context = upload_context or {
        "upload_title": video_id,
        "uploaded_at": datetime.now(timezone.utc)
    }
    
    logger.info(f"📊 Total frames received: {len(video_frames)}")
    
    # Analyze multiple early frames to reduce misses when first frame is intro/logo.
    frame_limit = min(max(EXTERNAL_FRAME_LIMIT, 1), len(video_frames))
    logger.info(f"🎞️  External check frame limit: {frame_limit}")
    for idx, frame_data in enumerate(video_frames[:frame_limit]):
        logger.info(f"🔍 Processing frame {idx}: {type(frame_data)}")
        
        # Handle both tuple and direct frame array formats
        if isinstance(frame_data, tuple) and len(frame_data) == 2:
            frame_id, frame = frame_data
        else:
            frame_id = idx
            frame = frame_data
        
        frame_hash = generate_hash(frame)
        if not frame_hash:
            logger.warning(f"⚠️ Could not generate hash for frame {frame_id}")
            continue
        
        logger.info(f"📽️  Analyzing frame {frame_id}... (hash generated)")
        
        # Check YouTube
        logger.info(f"   🔄 Starting YouTube check for frame {frame_id}")
        yt_matches = check_youtube_sources(frame_hash, video_id, upload_context)
        logger.info(f"   ✅ YouTube check complete: {len(yt_matches)} matches")
        if yt_matches:
            youtube_matches.extend(yt_matches)
        
        # Check Reddit
        logger.info(f"   🔄 Starting Reddit check for frame {frame_id}")
        reddit_match = check_reddit_sources(frame_hash, video_id, upload_context)
        logger.info(f"   ✅ Reddit check complete: {len(reddit_match)} matches")
        if reddit_match:
            reddit_matches.extend(reddit_match)

        x_matches.extend(check_seed_social_sources("X", parse_seed_posts(X_SEED_POSTS, "X"), upload_context))
        instagram_matches.extend(check_seed_social_sources("Instagram", parse_seed_posts(INSTAGRAM_SEED_POSTS, "Instagram"), upload_context))
        tiktok_matches.extend(check_seed_social_sources("TikTok", parse_seed_posts(TIKTOK_SEED_POSTS, "TikTok"), upload_context))
    
    # Deduplicate by URL
    youtube_matches = deduplicate_matches(youtube_matches)
    reddit_matches = deduplicate_matches(reddit_matches)
    x_matches = deduplicate_matches(x_matches)
    instagram_matches = deduplicate_matches(instagram_matches)
    tiktok_matches = deduplicate_matches(tiktok_matches)
    
    total_matches = len(youtube_matches) + len(reddit_matches) + len(x_matches) + len(instagram_matches) + len(tiktok_matches)
    external_piracy = total_matches > 0
    
    print(f"\n{'='*60}")
    print(f"📊 EXTERNAL SOURCE CHECK SUMMARY")
    print(f"{'='*60}")
    print(f"   YouTube Matches: {len(youtube_matches)}")
    print(f"   Reddit Matches: {len(reddit_matches)}")
    print(f"   X Matches: {len(x_matches)}")
    print(f"   Instagram Matches: {len(instagram_matches)}")
    print(f"   TikTok Matches: {len(tiktok_matches)}")
    print(f"   Total External Matches: {total_matches}")
    print(f"   External Piracy Detected: {'🚨 YES' if external_piracy else '✅ NO'}")
    print(f"{'='*60}\n")
    
    return {
        "youtube_matches": youtube_matches,
        "reddit_matches": reddit_matches,
        "x_matches": x_matches,
        "instagram_matches": instagram_matches,
        "tiktok_matches": tiktok_matches,
        "total_external_matches": total_matches,
        "external_piracy_detected": external_piracy,
        "check_timestamp": datetime.now(timezone.utc).isoformat()
    }


def check_seed_social_sources(platform: str, seed_posts: List[Dict], upload_context: Dict) -> List[Dict]:
    """
    MVP metadata-only adapters for X/Instagram/TikTok.
    Uses title + temporal + optional embedding proxies for scoring.
    """
    matches: List[Dict] = []
    upload_title = upload_context.get("upload_title", "")
    upload_time = upload_context.get("uploaded_at")

    for item in seed_posts:
        title = item.get("title", "")
        published_at = parse_iso_datetime(item.get("published_at"))
        title_similarity = title_similarity_score(upload_title, title)
        temporal_similarity = temporal_similarity_score(upload_time, published_at)
        embedding_similarity = optional_embedding_similarity(upload_title, title)
        score = multisignal_score(0.0, title_similarity, temporal_similarity, embedding_similarity)
        if score < SOCIAL_MATCH_THRESHOLD:
            continue
        external_id = item.get("external_id", "unknown")
        matches.append({
            "source": platform,
            "platform": platform,
            "title": title,
            "author": item.get("author", ""),
            "url": item.get("url", ""),
            "similarity": score,
            "hash_similarity": 0.0,
            "title_similarity": title_similarity,
            "temporal_similarity": temporal_similarity,
            "embedding_similarity": embedding_similarity,
            "multi_signal_score": score,
            "source_platform": platform.lower(),
            "source_url": item.get("url", ""),
            "parent_asset_id": make_asset_id(platform, external_id),
            "detected_at": datetime.now(timezone.utc).isoformat(),
        })
    return matches


def deduplicate_matches(matches: List[Dict]) -> List[Dict]:
    """Remove duplicate matches by URL"""
    seen = set()
    unique = []
    for match in matches:
        url = match.get('url', '')
        if url not in seen:
            seen.add(url)
            unique.append(match)
    return unique


if __name__ == "__main__":
    # Test the external source checker
    print("🧪 Testing External Source Checker")
    
    # This would be called with real frame data in production
    logger.info("External source checker module loaded successfully")
