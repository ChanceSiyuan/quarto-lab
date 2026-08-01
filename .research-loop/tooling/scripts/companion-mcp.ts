import { execFile } from "node:child_process";
import { promisify } from "node:util";

import { createCompanionContext } from "../../../src/lib/companion/context.js";
import { startCompanionMcpHttpServer } from "../../../src/lib/companion/server.js";

const run = promisify(execFile);

function enabled(value: string | undefined): boolean {
  return value === "1" || value === "true";
}

async function repositoryRootIsReadOnlyMount(repoRoot: string): Promise<boolean> {
  try {
    const { stdout } = await run(
      "findmnt",
      ["--noheadings", "--output", "OPTIONS", "--target", repoRoot],
      { encoding: "utf8" },
    );
    const options = stdout
      .trim()
      .split(/[\s,]+/u)
      .filter(Boolean);
    return options.includes("ro") && !options.includes("rw");
  } catch {
    return false;
  }
}

function requiredEnvironment(name: string): string {
  const value = process.env[name];
  if (value === undefined || value === "") {
    throw new Error(`Required environment variable is missing: ${name}`);
  }
  return value;
}

async function main(): Promise<void> {
  const repoRoot = requiredEnvironment("QLAB_COMPANION_REPO_ROOT");
  const endpointBaseUrl = requiredEnvironment("QLAB_COMPANION_ENDPOINT_BASE_URL");
  const publicBaseUrl = requiredEnvironment("QLAB_COMPANION_PUBLIC_BASE_URL");
  const accessToken = requiredEnvironment("QLAB_COMPANION_ACCESS_TOKEN");
  const host = process.env.QLAB_COMPANION_HOST;
  const portValue = process.env.QLAB_COMPANION_PORT;
  const port = portValue === undefined ? undefined : Number(portValue);
  const unsafeAllowWritableRepositoryRootForDevelopment = enabled(
    process.env.QLAB_COMPANION_UNSAFE_ALLOW_WRITABLE_ROOT_FOR_DEVELOPMENT,
  );

  const context = await createCompanionContext({
    repoRoot,
    publicBaseUrl,
    accessToken,
  });
  const running = await startCompanionMcpHttpServer({
    context,
    repoRoot,
    endpointBaseUrl,
    publicBaseUrl,
    accessToken,
    ...(host === undefined ? {} : { host }),
    ...(port === undefined ? {} : { port }),
    trustedTunnelMode: enabled(process.env.QLAB_COMPANION_TRUSTED_TUNNEL),
    unsafeAllowNonLoopbackDevelopment: enabled(
      process.env.QLAB_COMPANION_UNSAFE_ALLOW_NON_LOOPBACK_DEVELOPMENT,
    ),
    unsafeAllowWritableRepositoryRootForDevelopment,
    isRepositoryRootReadOnly: repositoryRootIsReadOnlyMount,
    logger: {
      info(event) {
        process.stdout.write(`${JSON.stringify(event)}\n`);
      },
      error(event) {
        process.stderr.write(`${JSON.stringify(event)}\n`);
      },
    },
  });

  const stop = async () => {
    await running.close();
    process.exitCode = 0;
  };
  process.once("SIGINT", () => void stop());
  process.once("SIGTERM", () => void stop());
}

void main().catch(() => {
  process.stderr.write("QLab Companion MCP failed to start safely.\n");
  process.exitCode = 1;
});
