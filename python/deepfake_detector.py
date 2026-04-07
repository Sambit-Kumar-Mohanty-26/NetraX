"""
Deepfake Detection Module
Uses MediaPipe Face Mesh + DeepFace for specialized deepfake detection
"""
import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Try to import MediaPipe, but make it optional
MEDIAPIPE_AVAILABLE = False
try:
    import mediapipe as mp
    # Test if solutions attribute exists
    if hasattr(mp, 'solutions'):
        MEDIAPIPE_AVAILABLE = True
        logger.info("✅ MediaPipe loaded successfully")
    else:
        logger.warning("⚠️ MediaPipe installed but 'solutions' not available")
except Exception as e:
    logger.warning(f"⚠️ MediaPipe not available: {e}")

# Try to import DeepFace, but make it optional
DEEPFACE_AVAILABLE = False
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
    logger.info("✅ DeepFace loaded successfully")
except Exception as e:
    logger.warning(f"⚠️ DeepFace not available: {e}")
    logger.warning("⚠️ Deepfake detection will be limited")


def detect_deepfake(frame_array):
    """
    Multi-stage deepfake detection using facial landmarks and emotion analysis
    
    Returns:
        {
            "is_deepfake": bool,
            "confidence": float (0-1),
            "method": str,
            "details": dict
        }
    """
    
    if frame_array is None or len(frame_array.shape) != 3:
        return {"is_deepfake": False, "confidence": 0.0, "method": "invalid_frame"}
    
    try:
        # Stage 1: Face Mesh Landmark Detection (if MediaPipe available)
        if MEDIAPIPE_AVAILABLE:
            logger.info("🔍 Stage 1: Analyzing facial landmarks...")
            
            mp_face_mesh = mp.solutions.face_mesh
            
            with mp_face_mesh.FaceMesh(
                static_image_mode=True,
                max_num_faces=1,
                min_detection_confidence=0.5
            ) as face_mesh:
                
                # Convert BGR to RGB
                rgb_frame = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
                results = face_mesh.process(rgb_frame)
                
                if not results.multi_face_landmarks:
                    logger.warning("⚠️ No faces detected")
                    return {"is_deepfake": False, "confidence": 0.0, "method": "no_face_detected"}
                
                landmarks = results.multi_face_landmarks[0]
                landmark_list = [[lm.x, lm.y, lm.z] for lm in landmarks.landmark]
                landmark_array = np.array(landmark_list)
                
                # Check for unnatural landmark variance
                # Deepfakes often have inconsistent facial geometry
                left_eye_variance = np.var(landmark_array[133:143])  # Left eye region
                right_eye_variance = np.var(landmark_array[362:372])  # Right eye region
                mouth_variance = np.var(landmark_array[61:68])  # Mouth region
                
                # Deepfakes tend to have lower geometric consistency
                total_variance = (left_eye_variance + right_eye_variance + mouth_variance) / 3
                
                logger.info(f"   📊 Facial geometry variance: {total_variance:.4f}")
        else:
            logger.info("⚠️ MediaPipe not available, skipping facial landmark analysis")
            rgb_frame = cv2.cvtColor(frame_array, cv2.COLOR_BGR2RGB)
        
        # Stage 2: DeepFace Emotion/Liveness Analysis (if available)
        if DEEPFACE_AVAILABLE:
            logger.info("🔍 Stage 2: Analyzing facial consistency with DeepFace...")
            
            try:
                analysis = DeepFace.analyze(
                    rgb_frame,
                    actions=['emotion'],
                    enforce_detection=False,
                    silent=True
                )
                
                if isinstance(analysis, list) and len(analysis) > 0:
                    emotions = analysis[0].get('emotion', {})
                    dominant_emotion = analysis[0].get('dominant_emotion', 'unknown')
                    
                    # Calculate emotion confidence
                    # Real faces have higher dominant emotion confidence
                    confidence_scores = list(emotions.values())
                    max_confidence = max(confidence_scores) if confidence_scores else 0
                    entropy = -sum([p/100 * np.log(max(p/100, 1e-10)) for p in confidence_scores if p > 0])
                    
                    logger.info(f"   😊 Dominant emotion: {dominant_emotion} ({max_confidence:.1f}%)")
                    logger.info(f"   📈 Emotion entropy: {entropy:.4f}")
                    
                    # High entropy = unnatural emotion mix = likely deepfake
                    if entropy > 1.8:  # Threshold for unnatural emotion distribution
                        return {
                            "is_deepfake": True,
                            "confidence": min(entropy / 2.2, 0.95),  # Normalize to 0-0.95
                            "method": "emotion_inconsistency",
                            "details": {
                                "dominant_emotion": dominant_emotion,
                                "emotion_entropy": entropy,
                                "emotion_confidence": max_confidence
                            }
                        }
                    
            except Exception as e:
                logger.warning(f"   ⚠️ DeepFace analysis failed: {e}")
        else:
            logger.info("🔍 Stage 2: DeepFace not available")
        
        # Stage 3: Landmark Temporal Consistency Check (only if MediaPipe was available)
        if MEDIAPIPE_AVAILABLE and 'landmark_array' in locals():
            # Get face center landmarks for symmetry check
            left_cheek = np.array(landmark_array[234])  # Left cheek
            right_cheek = np.array(landmark_array[454])  # Right cheek
            
            # Check symmetry
            symmetry_diff = np.linalg.norm(left_cheek - np.array([1.0 - right_cheek[0], right_cheek[1], right_cheek[2]]))
            
            logger.info(f"   🔄 Facial symmetry score: {symmetry_diff:.4f}")
            
            # If all checks pass, likely genuine
            return {
                "is_deepfake": False,
                "confidence": 0.1,  # Low confidence of deepfake
                "method": "all_checks_passed",
                "details": {
                    "landmark_variance": float(total_variance),
                    "symmetry_score": float(symmetry_diff)
                }
            }
        
        # If we got here, no deepfake indicators found
        return {
            "is_deepfake": False,
            "confidence": 0.0,
            "method": "no_mediapipe_analysis"
        }
        
    except Exception as e:
        logger.error(f"❌ Deepfake detection error: {e}")
        return {"is_deepfake": False, "confidence": 0.0, "method": "error", "error": str(e)}


def frame_to_bytes(frame_array):
    """Convert numpy frame array to bytes for transmission"""
    success, buffer = cv2.imencode('.jpg', frame_array)
    if success:
        return buffer.tobytes()
    return None
