import { Request, Response, NextFunction, RequestHandler } from "express";

const rateStore = new Map<string, { count: number; resetAt: number }>();

export function sanitizeIdentifier(input: string, maxLen = 80): string {
  const cleaned = input.trim().replace(/[^a-zA-Z0-9_-]/g, "");
  return cleaned.slice(0, maxLen);
}

export function sanitizeFilename(input: string, maxLen = 120): string {
  const base = input.split(/[\\/]/).pop() || "upload.bin";
  const cleaned = base.replace(/[^a-zA-Z0-9._-]/g, "_");
  return cleaned.slice(0, maxLen);
}

export function createRateLimiter(options: {
  windowMs: number;
  maxRequests: number;
  keyPrefix: string;
}): RequestHandler {
  const { windowMs, maxRequests, keyPrefix } = options;
  return (req: Request, res: Response, next: NextFunction) => {
    const ip = req.ip || req.socket.remoteAddress || "unknown";
    const key = `${keyPrefix}:${ip}`;
    const now = Date.now();
    const existing = rateStore.get(key);

    if (!existing || now > existing.resetAt) {
      rateStore.set(key, { count: 1, resetAt: now + windowMs });
      return next();
    }

    if (existing.count >= maxRequests) {
      return res.status(429).json({
        error: "Too many requests",
        retryAfterMs: Math.max(existing.resetAt - now, 0),
      });
    }

    existing.count += 1;
    rateStore.set(key, existing);
    return next();
  };
}

export function requireApiGuard(req: Request, res: Response, next: NextFunction) {
  const configuredKey = process.env.ADMIN_API_KEY;
  if (!configuredKey) {
    return next();
  }

  const headerKey = req.header("x-admin-api-key");
  const authHeader = req.header("authorization");
  const bearerKey =
    authHeader && authHeader.startsWith("Bearer ") ? authHeader.slice(7).trim() : "";

  if (headerKey === configuredKey || bearerKey === configuredKey) {
    return next();
  }

  return res.status(401).json({ error: "Unauthorized request" });
}

export function validateAllowedOrigin(origin: string | undefined, allowedOrigins: string[]): boolean {
  if (!origin) {
    return true;
  }

  try {
    const parsed = new URL(origin);
    if (parsed.hostname.endsWith(".vercel.app")) {
      return true;
    }
  } catch {
    return false;
  }

  return allowedOrigins.includes(origin);
}
