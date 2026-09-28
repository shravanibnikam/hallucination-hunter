import { z } from "zod";
export class HttpError extends Error { constructor(public status: number, message: string) { super(message); } }
export function json(data: unknown, status = 200) { return Response.json(data, { status, headers: { "Cache-Control": "no-store" } }); }
export async function body<T>(request: Request, schema: z.ZodType<T>): Promise<T> {
 if (Number(request.headers.get("content-length")) > 8192) throw new HttpError(413, "Request is too large.");
 const reader = request.body?.getReader(); let text = "", size = 0;
 if (reader) { const decoder = new TextDecoder(); while (true) { const { done, value } = await reader.read(); if (done) break; size += value.length; if (size > 8192) { await reader.cancel(); throw new HttpError(413, "Request is too large."); } text += decoder.decode(value, { stream: true }); } text += decoder.decode(); }
 return schema.parse(JSON.parse(text || "{}"));
}
export function endpoint(fn: () => Promise<Response>): Promise<Response> { return fn().catch((error: unknown) => { if (error instanceof HttpError) return json({ error: error.message }, error.status); if (error instanceof z.ZodError) return json({ error: "Please check the submitted fields." }, 400); if (error instanceof SyntaxError) return json({ error: "Request must contain valid JSON." }, 400); return json({ error: "Something went wrong. Please try again." }, 500); }); }
