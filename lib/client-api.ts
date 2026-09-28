export async function api<T>(path: string, data?: unknown, method = "POST"): Promise<T> {
 const response = await fetch(path, data === undefined ? { cache: "no-store" } : { method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(data) });
 const result = await response.json(); if (!response.ok) throw new Error(result.error ?? "Please try again."); return result as T;
}
