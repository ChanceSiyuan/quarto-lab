/// <reference types="@cloudflare/workers-types" />

declare module "cloudflare:workers" {
  export const env: {
    DB?: D1Database;
  };
}

declare namespace Cloudflare {
  interface Env {
    DB?: D1Database;
  }
}
