import { NextRequest, NextResponse } from "next/server";

const backend = process.env.FLEETMIX_API_URL ?? "http://127.0.0.1:8000";
type RouteContext = { params: Promise<{ path: string[] }> };

async function handle(request: NextRequest, context: RouteContext) {
  const { path } = await context.params;
  const url = `${backend}/api/${path.map(encodeURIComponent).join("/")}${request.nextUrl.search}`;
  if (path.join("/") === "auth/logout" && request.method === "POST") {
    const response = NextResponse.json({ ok: true });
    response.cookies.set("fleetmix_session", "", { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 0 });
    return response;
  }
  const token = request.cookies.get("fleetmix_session")?.value;
  const headers = new Headers();
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("content-type", contentType);
  if (token) headers.set("authorization", `Bearer ${token}`);
  let body: ArrayBuffer | undefined;
  if (!(["GET", "HEAD"].includes(request.method))) body = await request.arrayBuffer();
  let upstream: Response;
  try {
    upstream = await fetch(url, { method: request.method, headers, body, cache: "no-store" });
  } catch {
    return NextResponse.json({ detail: "FleetMix API is unavailable. Start the local API and worker." }, { status: 503 });
  }
  const raw = await upstream.text();
  if (path.join("/") === "auth/login" && upstream.ok) {
    const data = JSON.parse(raw) as { access_token: string; user: unknown };
    const response = NextResponse.json({ user: data.user }, { status: upstream.status });
    response.cookies.set("fleetmix_session", data.access_token, { httpOnly: true, sameSite: "lax", secure: process.env.NODE_ENV === "production", path: "/", maxAge: 60 * 60 * 10 });
    return response;
  }
  return new NextResponse(raw, { status: upstream.status, headers: { "content-type": upstream.headers.get("content-type") ?? "application/json" } });
}

export { handle as GET, handle as POST, handle as PUT, handle as PATCH, handle as DELETE };
