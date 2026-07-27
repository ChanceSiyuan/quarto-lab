/**
 * Cloudflare Worker entry point for the vinext-starter template.
 *
 * Beyond the template's image endpoint it does one extra thing: it resolves the
 * directory URLs of the published knowledge site. Quarto renders every page as
 * `<directory>/index.html` and links its stylesheets, scripts, and sibling
 * pages *relatively*, so `/knowledge/categories/theory/` has to serve
 * `knowledge/categories/theory/index.html` at exactly that URL — served one
 * segment higher, every relative link on the page would point outside the site.
 * The app router does not map directory URLs onto index documents (it strips
 * the trailing slash and then 404s), so this Worker does it for the one prefix
 * that needs it.
 *
 * The fallback is deliberately narrow. It only answers under `/knowledge`, only
 * for GET and HEAD, and only by asking for a file that the build already
 * published: it never renders anything, never reads the filesystem, and never
 * consults the knowledge tree. A path it cannot satisfy falls through to the
 * app router unchanged, so nothing outside the published site becomes reachable
 * by asking for it under this prefix.
 */
import { handleImageOptimization, DEFAULT_DEVICE_SIZES, DEFAULT_IMAGE_SIZES } from "vinext/server/image-optimization";
import handler from "vinext/server/app-router-entry";

interface Env {
  ASSETS: Fetcher;
  DB: D1Database;
  IMAGES: {
    input(stream: ReadableStream): {
      transform(options: Record<string, unknown>): {
        output(options: { format: string; quality: number }): Promise<{ response(): Response }>;
      };
    };
  };
}

interface ExecutionContext {
  waitUntil(promise: Promise<unknown>): void;
  passThroughOnException(): void;
}

// Image security config. SVG sources with .svg extension auto-skip the
// optimization endpoint on the client side (served directly, no proxy).
// To route SVGs through the optimizer (with security headers), set
// dangerouslyAllowSVG: true in next.config.js and uncomment below:
// const imageConfig: ImageConfig = { dangerouslyAllowSVG: true };

/** The URL prefix the published knowledge site occupies. */
const KNOWLEDGE_PREFIX = "/knowledge";

/** The document a directory URL resolves to. */
const DIRECTORY_INDEX = "index.html";

/** True for the knowledge prefix itself and everything below it. */
function isKnowledgePath(pathname: string): boolean {
  return pathname === KNOWLEDGE_PREFIX || pathname.startsWith(`${KNOWLEDGE_PREFIX}/`);
}

/** True when the last segment names a file, so no index lookup applies. */
function namesFile(pathname: string): boolean {
  return pathname.slice(pathname.lastIndexOf("/") + 1).includes(".");
}

/**
 * True when the asset binding served the file rather than declining it.
 *
 * A redirect is not a hit: the binding's own canonicalization must not be
 * passed back here, or a request could bounce between the two spellings of a
 * directory URL. A 304 is a hit, because a conditional request that the binding
 * validated is a file that exists.
 */
function isHit(response: Response): boolean {
  return response.status === 200 || response.status === 206 || response.status === 304;
}

/**
 * The published asset at `pathname`, or `null` if the build published none.
 *
 * Two runtimes serve this Worker's static files and only one of them binds
 * them: on Cloudflare the platform passes an `ASSETS` fetcher, while the local
 * production server calls this entry point with no environment at all and
 * serves `public/` through the app router itself. Asking whichever of the two
 * is present keeps one lookup rule — "a file this build published, by path" —
 * instead of two, and the app router only ever answers for files the build put
 * in `public/`, so neither path can reach anything else.
 */
async function publishedAsset(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  pathname: string,
): Promise<Response | null> {
  const target = new URL(request.url);
  target.pathname = pathname;
  const assetRequest = new Request(target, {
    method: request.method,
    headers: request.headers,
  });
  const assets = (env as Env | undefined)?.ASSETS;
  const response = assets
    ? await assets.fetch(assetRequest)
    : await handler.fetch(assetRequest, env, ctx);
  return isHit(response) ? response : null;
}

/**
 * The knowledge site's answer for one request, or `null` to fall through.
 *
 * The order is: the exact published path, then — for a directory URL — the
 * index document inside it. A directory URL without its trailing slash is
 * redirected to the form with one instead of being served, because that is the
 * base the pages' relative links are written against.
 */
async function knowledgeResponse(
  request: Request,
  env: Env,
  ctx: ExecutionContext,
  url: URL,
): Promise<Response | null> {
  if (request.method !== "GET" && request.method !== "HEAD") {
    return new Response("Method Not Allowed", {
      status: 405,
      headers: { allow: "GET, HEAD" },
    });
  }

  const direct = await publishedAsset(request, env, ctx, url.pathname);
  if (direct !== null) {
    return direct;
  }
  if (namesFile(url.pathname)) {
    return null;
  }

  const directory = url.pathname.endsWith("/") ? url.pathname.slice(0, -1) : url.pathname;
  const index = await publishedAsset(request, env, ctx, `${directory}/${DIRECTORY_INDEX}`);
  if (index === null) {
    return null;
  }
  if (url.pathname.endsWith("/")) {
    return index;
  }
  const canonical = new URL(url);
  canonical.pathname = `${directory}/`;
  return Response.redirect(canonical.href, 308);
}

const worker = {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url);

    if (url.pathname === "/_vinext/image") {
      const allowedWidths = [...DEFAULT_DEVICE_SIZES, ...DEFAULT_IMAGE_SIZES];
      return handleImageOptimization(request, {
        fetchAsset: (path) => env.ASSETS.fetch(new Request(new URL(path, request.url))),
        transformImage: async (body, { width, format, quality }) => {
          const result = await env.IMAGES.input(body).transform(width > 0 ? { width } : {}).output({ format, quality });
          return result.response();
        },
      }, allowedWidths);
    }

    if (isKnowledgePath(url.pathname)) {
      const knowledge = await knowledgeResponse(request, env, ctx, url);
      if (knowledge !== null) {
        return knowledge;
      }
    }

    return handler.fetch(request, env, ctx);
  },
};

export default worker;
