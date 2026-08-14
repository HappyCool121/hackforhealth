const BODYLESS_METHODS = new Set(["GET", "HEAD"]);
const REQUEST_HEADERS_TO_DROP = ["connection", "content-length", "host", "keep-alive", "transfer-encoding"];
const RESPONSE_HEADERS_TO_DROP = ["connection", "content-length", "keep-alive", "transfer-encoding"];

type ProxyContext = {
  params: Promise<{ path: string[] }>;
};

async function proxyRequest(request: Request, context: ProxyContext) {
  const apiUrl = process.env.API_INTERNAL_URL;
  const gatewaySecret = process.env.BACKEND_GATEWAY_SECRET;
  if (!apiUrl || !gatewaySecret) {
    return Response.json({ detail: "Backend gateway is not configured" }, { status: 503 });
  }

  const { path } = await context.params;
  const base = apiUrl.endsWith("/") ? apiUrl : `${apiUrl}/`;
  const target = new URL(`api/${path.map(encodeURIComponent).join("/")}`, base);
  target.search = new URL(request.url).search;

  const headers = new Headers(request.headers);
  REQUEST_HEADERS_TO_DROP.forEach((name) => headers.delete(name));
  headers.set("x-clinicpass-gateway", gatewaySecret);
  headers.set("x-forwarded-host", new URL(request.url).host);

  const init: RequestInit = {
    method: request.method,
    headers,
    redirect: "manual",
    cache: "no-store",
  };
  if (!BODYLESS_METHODS.has(request.method)) {
    init.body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetch(target, init);
    const responseHeaders = new Headers(upstream.headers);
    RESPONSE_HEADERS_TO_DROP.forEach((name) => responseHeaders.delete(name));
    return new Response(upstream.body, {
      status: upstream.status,
      statusText: upstream.statusText,
      headers: responseHeaders,
    });
  } catch {
    return Response.json({ detail: "Backend service is unavailable" }, { status: 502 });
  }
}

export const dynamic = "force-dynamic";
export const GET = proxyRequest;
export const POST = proxyRequest;
export const PUT = proxyRequest;
export const PATCH = proxyRequest;
export const DELETE = proxyRequest;
export const HEAD = proxyRequest;
export const OPTIONS = proxyRequest;
