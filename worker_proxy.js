/* ETNet CORS proxy - Cloudflare Worker (free plan).
 *
 * Deploy:
 *   1. Cloudflare dashboard -> Workers & Pages -> Create -> Worker
 *   2. Replace the default code with this file's contents
 *   3. Deploy, then copy your worker URL (https://<name>.<account>.workers.dev)
 *   4. In webpage/app.js set CLOUDFLARE_WORKER_URL to that URL (and push),
 *      or just paste the URL back here and I will wire it in.
 *
 * The page calls:  <worker_url>?url=<encoded etnet page URL>
 */
export default {
  async fetch(request) {
    const url = new URL(request.url);
    const target = url.searchParams.get("url");
    const cors = { "Access-Control-Allow-Origin": "*", "Cache-Control": "no-store" };

    if (!target) {
      return new Response("missing ?url= parameter", {
        status: 400,
        headers: cors,
      });
    }

    try {
      const resp = await fetch(target, {
        headers: {
          "User-Agent":
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
          "Accept-Language": "zh-HK,zh;q=0.9,en;q=0.8",
        },
      });
      const body = await resp.arrayBuffer();
      return new Response(body, {
        status: resp.status,
        headers: {
          ...cors,
          "Content-Type": resp.headers.get("Content-Type") || "text/html; charset=utf-8",
        },
      });
    } catch (e) {
      return new Response("proxy error: " + e.message, {
        status: 502,
        headers: cors,
      });
    }
  },
};
