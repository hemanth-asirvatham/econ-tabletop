import { readFileSync, readdirSync } from "node:fs";
import path from "node:path";

export type DeckManifest = {
  deck_id: string;
  scenario?: Record<string, unknown>;
  gameplay_defaults?: Record<string, unknown>;
  stages?: Record<string, unknown>;
};

export function loadManifest(deckDir: string): DeckManifest {
  const manifestPath = path.join(deckDir, "manifest.json");
  return JSON.parse(readFileSync(manifestPath, "utf-8"));
}

export function loadPolicies(deckDir: string): unknown[] {
  const policyPath = path.join(deckDir, "cards", "policies.jsonl");
  return readJsonl(policyPath);
}

export function loadDevelopments(deckDir: string, stage: number): unknown[] {
  const devPath = path.join(deckDir, "cards", `developments.stage${stage}.jsonl`);
  return readJsonl(devPath);
}

export function listDevelopmentStages(deckDir: string): number[] {
  const cardsDir = path.join(deckDir, "cards");
  return readdirSync(cardsDir)
    .filter((file) => file.startsWith("developments.stage"))
    .map((file) => Number(file.replace("developments.stage", "").replace(".jsonl", "")))
    .filter((value) => !Number.isNaN(value));
}

function readJsonl(filePath: string): unknown[] {
  const content = readFileSync(filePath, "utf-8");
  return content
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line));
}
