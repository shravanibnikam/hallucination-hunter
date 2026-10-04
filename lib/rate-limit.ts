import "server-only";
import { HttpError } from "./http";
/** Bounded, per-process limits with no IPs, user agents, cookies, or timers. */
export function createLimiter(maxKeys = 10000) {
  const buckets = new Map<string, {
    count: number;
    expires: number;
  }>();
  return (key: string, limit: number, windowMs: number, now = Date.now()) => {
    for (const [id, bucket] of buckets)
      if (bucket.expires <= now)
        buckets.delete(id);
    let bucket = buckets.get(key);
    if (!bucket) {
      if (buckets.size >= maxKeys)
        throw new HttpError(429, "The study is busy. Please try again in a minute.");
      bucket = { count: 0, expires: now + windowMs };
      buckets.set(key, bucket);

    }
    if (bucket.count >= limit)
      throw new HttpError(429, "Too many requests. Please try again in a minute.");
    bucket.count++;

  };
}
export const rateLimit = createLimiter();
