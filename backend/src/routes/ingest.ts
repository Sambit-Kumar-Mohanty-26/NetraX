import express, { Router, Request, Response } from "express";
import { spawn } from "child_process";
import * as admin from "firebase-admin";
import fs from "fs";
import path from "path";
import {
  createRateLimiter,
  requireApiGuard,
  sanitizeFilename,
  sanitizeIdentifier,
} from "../middleware/security";

const router = Router();
const db = admin.firestore();
const ingestRateLimit = createRateLimiter({
  windowMs: 60 * 1000,
  maxRequests: 3,
  keyPrefix: "ingest-route",
});

function runIngestFromPath(localVideoPath: string, videoId: string): Promise<{ frameCount: number; hashCount: number; stdout: string }> {
  return new Promise((resolve, reject) => {
    const pythonPath = path.join(__dirname, "../../../python");
    const child = spawn("python", ["ingest_from_path.py"], {
      cwd: pythonPath,
      env: { ...process.env, VIDEO_PATH: localVideoPath, VIDEO_ID: videoId },
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });
    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });
    child.on("error", (error) => reject(error));
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr || `Ingest process failed with exit code ${code}`));
        return;
      }

      const frameMatches = stdout.match(/Extracted\s+(\d+)\s+frames/i);
      const hashMatches = stdout.match(/(\d+)\s+reference hashes created/i);
      const frameCount = frameMatches ? Number(frameMatches[1]) : 0;
      const hashCount = hashMatches ? Number(hashMatches[1]) : frameCount;
      resolve({ frameCount, hashCount, stdout });
    });
  });
}

/**
 * POST /api/ingest-official
 * Trigger Python ingestion script to extract frames and generate hashes
 * from an uploaded video file
 */
router.post("/ingest-official", ingestRateLimit, requireApiGuard, async (req: Request, res: Response) => {
  try {
    const { videoUrl, videoId, filename, fileSize } = req.body as {
      videoUrl?: string;
      videoId?: string;
      filename?: string;
      fileSize?: number;
    };

    if (!videoUrl || !videoId) {
      return res.status(400).json({
        error: "videoUrl and videoId are required"
      });
    }
    const safeVideoId = sanitizeIdentifier(videoId);
    if (!safeVideoId) {
      return res.status(400).json({ error: "Invalid videoId" });
    }
    const safeFilename = sanitizeFilename(filename || `${safeVideoId}.mp4`);

    console.log(`\n📹 Starting ingestion for: ${safeVideoId}`);
    console.log(`   File: ${safeFilename} (${fileSize || 0} bytes)`);

    // Download video from GCS to temporary location
    const tempDir = "/tmp/netrax-videos";
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }

    const localVideoPath = path.join(tempDir, `${safeVideoId}.mp4`);

    console.log(`   🔗 Downloading from GCS...`);
    
    // Expected format: gs://bucket/object
    const match = videoUrl.match(/^gs:\/\/([^/]+)\/(.+)$/);
    if (!match) {
      return res.status(400).json({ error: "videoUrl must be a gs:// URL" });
    }
    const [, bucketName, objectPath] = match;
    const storage = admin.storage();
    const bucket = storage.bucket(bucketName);
    await bucket.file(objectPath).download({ destination: localVideoPath });
    
    // Execute Python ingestion script
    console.log(`   ⚙️  Running frame extraction & hashing...`);
    const { frameCount, hashCount, stdout } = await runIngestFromPath(localVideoPath, safeVideoId);
    console.log(`   ✅ Ingestion complete: ${frameCount} frames, ${hashCount} hashes`);

    // Store ingestion metadata in Firestore
    const ingestDocId = `ingest_${safeVideoId}_${Date.now()}`;
    await db.collection("ingestions").doc(ingestDocId).set({
      videoId: safeVideoId,
      filename: safeFilename,
      fileSize,
      frameCount,
      hashCount,
      status: "completed",
      startedAt: admin.firestore.FieldValue.serverTimestamp(),
      completedAt: admin.firestore.FieldValue.serverTimestamp(),
      scriptOutput: stdout.substring(0, 500) // Save first 500 chars
    });

    console.log(`   💾 Metadata saved to Firestore (${ingestDocId})`);

    // Clean up temporary file
    if (fs.existsSync(localVideoPath)) {
      fs.unlinkSync(localVideoPath);
    }

    // Return success response
    return res.json({
      success: true,
      videoId: safeVideoId,
      frameCount,
      hashCount,
      processingTime: Math.round(Date.now() / 1000) % 60, // Mock processing time
      ingestionId: ingestDocId
    });

  } catch (error) {
    console.error(`❌ Ingestion failed:`, error);

    const errorMessage = error instanceof Error ? error.message : "Unknown error";

    // Store error in Firestore
    try {
      await db.collection("ingestions").add({
        videoId: sanitizeIdentifier(String(req.body?.videoId || "unknown")),
        status: "failed",
        error: errorMessage,
        failedAt: admin.firestore.FieldValue.serverTimestamp()
      });
    } catch (dbError) {
      console.error("Failed to log error to Firestore:", dbError);
    }

    return res.status(500).json({
      error: "Ingestion failed",
      details: errorMessage
    });
  }
});

/**
 * GET /api/ingest-status/:videoId
 * Check ingestion status for a video
 */
router.get("/ingest-status/:videoId", async (req: Request, res: Response) => {
  try {
    const rawVideoId = Array.isArray(req.params.videoId) ? req.params.videoId[0] : req.params.videoId;
    const videoId = sanitizeIdentifier(rawVideoId || "");
    if (!videoId) {
      return res.status(400).json({ error: "Invalid videoId" });
    }

    const snapshot = await db.collection("ingestions")
      .where("videoId", "==", videoId)
      .orderBy("startedAt", "desc")
      .limit(1)
      .get();

    if (snapshot.empty) {
      return res.status(404).json({
        status: "not_found",
        videoId
      });
    }

    const ingestion = snapshot.docs[0].data();
    return res.json({
      status: ingestion.status,
      videoId,
      frameCount: ingestion.frameCount,
      hashCount: ingestion.hashCount,
      completedAt: ingestion.completedAt
    });

  } catch (error) {
    console.error("Status check failed:", error);
    return res.status(500).json({
      error: "Status check failed"
    });
  }
});

export default router;
