import { execFileSync } from "node:child_process";
import process from "node:process";

export function createZipArchive(root, archive, env = process.env) {
  execFileSync("zip", ["-X", "-q", "-r", archive, "."], { cwd: root, env });
}

export function extractZipArchive(archive, destination, env = process.env) {
  try {
    execFileSync("unzip", ["-n", "-q", archive, "-d", destination], { env });
  }
  catch (error) {
    // Info-ZIP returns status 1 when -n deliberately skips an existing user
    // file. That is the expected non-overwrite path, not an extraction error.
    if (!error || typeof error !== "object" || error.status !== 1) throw error;
  }
}
