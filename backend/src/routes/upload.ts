import express from "express";
import multer from "multer";
import { Storage } from "@google-cloud/storage";
import * as admin from "firebase-admin";
import { spawn } from "child_process";
import path from "path";
import fs from "fs";
import {
  createRateLimiter,
  requireApiGuard,
  sanitizeFilename,
  sanitizeIdentifier,
} from "../middleware/security";

const router = express.Router();
const ALLOWED_VIDEO_MIME_TYPES = new Set([
  "video/mp4",
  "video/webm",
  "video/quicktime",
  "video/x-msvideo",
  "video/x-matroska",
]);

// ✅ memory storage
const upload = multer({ 
  storage: multer.memoryStorage(),
  limits: { fileSize: 100 * 1024 * 1024 }, // 100MB limit
  fileFilter: (_req, file, cb) => {
    if (!ALLOWED_VIDEO_MIME_TYPES.has(file.mimetype)) {
      cb(new Error("Unsupported file type"));
      return;
    }
    cb(null, true);
  }
});

// GCP storage (optional - for cloud storage)
const storage = new Storage();
const bucketName = "netrax-video-storage";
const db = admin.firestore();
const uploadRateLimit = createRateLimiter({
  windowMs: 60 * 1000,
  maxRequests: 12,
  keyPrefix: "upload-route",
});
const heavyActionRateLimit = createRateLimiter({
  windowMs: 60 * 1000,
  maxRequests: 4,
  keyPrefix: "upload-heavy",
});

// 🎬 Upload official video (for judges to add reference content)
router.post("/upload-official", uploadRateLimit, heavyActionRateLimit, requireApiGuard, upload.single("video"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file uploaded" });
    }

    const originalName = sanitizeFilename(req.file.originalname);
    console.log(`📤 Judge Upload: Official video - ${originalName}`);
    
    const videoId = `official_${sanitizeIdentifier(String(Date.now()))}`;
    const fileName = `${videoId}_${originalName}`;
    
    // Save to temp directory for Python processing
    const tempDir = path.join(__dirname, "../../../temp");
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }
    
    const tempPath = path.join(tempDir, fileName);
    fs.writeFileSync(tempPath, req.file.buffer);
    
    console.log(`✅ Saved to: ${tempPath}`);

    // Save metadata to Firestore
    await db.collection("official_videos").add({
      video_id: videoId,
      filename: originalName,
      local_path: tempPath,
      size: req.file.size,
      uploaded_at: admin.firestore.FieldValue.serverTimestamp(),
      status: "processing"
    });

    // Trigger Python ingestion (synchronous for demo)
    const pythonPath = path.join(__dirname, "../../../python");
    // Execute Python script without shell interpolation
    const child = spawn("python", ["ingest_from_path.py"], {
      cwd: pythonPath,
      env: { ...process.env, VIDEO_PATH: tempPath, VIDEO_ID: videoId }
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });
    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });
    child.on("close", (code) => {
      if (code !== 0) {
        console.error(`❌ Python error (exit=${code})`);
        if (stderr) console.error(`stderr: ${stderr}`);
      } else if (stdout) {
        console.log(`✅ Python output: ${stdout}`);
      }
    });

    res.json({
      success: true,
      message: "Official video uploaded! Processing frames and generating reference hashes...",
      video_id: videoId,
      filename: originalName,
      next_step: "Upload a test video to detect matches"
    });

  } catch (err: any) {
    console.error("❌ Upload error:", err);
    res.status(500).json({ error: "Upload failed", details: err.message });
  }
});

// 📤 Unified Upload - Automatically detects piracy
router.post("/upload-test", uploadRateLimit, heavyActionRateLimit, requireApiGuard, upload.single("video"), async (req, res) => {
  try {
    if (!req.file) {
      return res.status(400).json({ error: "No file uploaded" });
    }
    const originalName = sanitizeFilename(req.file.originalname);

    console.log(`\n${"=".repeat(60)}`);
    console.log(`📤 VIDEO UPLOAD RECEIVED`);
    console.log(`${"=".repeat(60)}`);
    console.log(`📁 Filename: ${originalName}`);
    console.log(`💾 Size: ${(req.file.size / 1024 / 1024).toFixed(2)} MB`);
    
    const videoId = `upload_${sanitizeIdentifier(String(Date.now()))}`;
    const fileName = `${videoId}_${originalName}`;
    
    // Save to temp directory
    const tempDir = path.join(__dirname, "../../../temp");
    if (!fs.existsSync(tempDir)) {
      fs.mkdirSync(tempDir, { recursive: true });
    }
    
    const tempPath = path.join(tempDir, fileName);
    fs.writeFileSync(tempPath, req.file.buffer);
    
    console.log(`✅ Saved to: ${tempPath}`);
    console.log(`🚀 Starting piracy detection pipeline...`);
    console.log(`${"=".repeat(60)}\n`);

    // Trigger unified Python processor safely
    const pythonPath = path.join(__dirname, "../../../python");
    const child = spawn("python", ["upload_processor.py"], {
      cwd: pythonPath,
      env: { ...process.env, VIDEO_PATH: tempPath }
    });
    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (data) => {
      stdout += data.toString();
    });
    child.stderr.on("data", (data) => {
      stderr += data.toString();
    });
    child.on("close", (code) => {
      console.log(`\n${"=".repeat(60)}`);
      console.log(`🐍 PYTHON PROCESSING RESULT`);
      console.log(`${"=".repeat(60)}`);
      
      if (stdout) {
        console.log(stdout);
      }
      
      if (code !== 0) {
        console.error(`❌ Python Error: process exited with ${code}`);
        if (stderr) console.error(`stderr: ${stderr}`);
      } else if (stderr) {
        console.log(`⚠️  Python warnings:\n${stderr}`);
      }
      
      console.log(`${"=".repeat(60)}\n`);
      
      // Clean up after 60 seconds (longer to allow analysis)
      setTimeout(() => {
        if (fs.existsSync(tempPath)) {
          fs.unlinkSync(tempPath);
          console.log(`🗑️  Cleaned up: ${fileName}`);
        }
      }, 60000);
    });

    res.json({
      success: true,
      message: "Video uploaded! Analyzing for piracy detection...",
      video_id: videoId,
      filename: originalName,
      status: "Processing",
      note: "Results will appear on dashboard in 5-10 seconds"
    });

  } catch (err: any) {
    console.error("❌ Upload error:", err);
    res.status(500).json({ error: "Upload failed", details: err.message });
  }
});

export default router;
