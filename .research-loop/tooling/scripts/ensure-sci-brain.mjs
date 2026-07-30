#!/usr/bin/env node

import { ensureSciBrain, SCI_BRAIN_REF } from "../../../src/lib/skills/sci-brain.mjs";

try {
  const result = await ensureSciBrain();
  if (result.status === "available") {
    console.log(`sci-brain is ready: ${result.skillFile}`);
  } else {
    console.log(`Installed sci-brain ${SCI_BRAIN_REF}.`);
    console.log(`brainstorm-ideas is ready: ${result.skillFile}`);
    if (result.preservedSkills.length > 0) {
      console.log(`Preserved existing skills: ${result.preservedSkills.join(", ")}`);
    }
  }
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
}
