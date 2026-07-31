import { execFileSync } from "node:child_process";
import process from "node:process";

export function createZipArchive(root, archive, env = process.env) {
  execFileSync("zip", ["-X", "-q", "-r", archive, "."], { cwd: root, env });
}

export function extractZipArchive(archive, destination, env = process.env) {
  execFileSync("unzip", ["-n", "-q", archive, "-d", destination], { env });
}
