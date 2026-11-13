import { NextRequest, NextResponse } from "next/server";

const backend = process.env.FLEETMIX_API_URL ?? "http://127.0.0.1:8000";
type RouteContext = { params: Promise<{ path: string[] }> };

async function handle(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const url = `${backend}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  let body: ArrayBuffer | undefined;
  if (!(["GET", "HEAD"].includes(request.method))) body = await request.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(url, { method: request.method, headers, body, cache: "no-store" });
  } catch {
    return NextResponse.json({ detail: "FleetMix API is unavailable. Start the local API and worker." }, { status: 503 });
  }
  const raw = await upstream.text();
  return new NextResponse(raw, { status: upstream.status, headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" } });
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
