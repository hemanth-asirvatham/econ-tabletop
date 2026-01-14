import express from "express";
import cors from "cors";
import path from "node:path";

import { loadDevelopments, loadManifest, loadPolicies, listDevelopmentStages } from "./deckLoader.js";

const app = express();
app.use(cors());

const deckArgIndex = process.argv.findIndex((arg) => arg === "--deck");
const deckDir = deckArgIndex >= 0 ? process.argv[deckArgIndex + 1] : process.env.DECK_DIR;

if (!deckDir) {
  console.error("Missing --deck argument or DECK_DIR env var.");
  process.exit(1);
}

const absoluteDeckDir = path.resolve(deckDir);

app.get("/api/manifest", (_req, res) => {
  res.json(loadManifest(absoluteDeckDir));
});

app.get("/api/policies", (_req, res) => {
  res.json(loadPolicies(absoluteDeckDir));
});

app.get("/api/developments", (req, res) => {
  const stage = Number(req.query.stage || 0);
  res.json(loadDevelopments(absoluteDeckDir, stage));
});

app.get("/api/stages", (_req, res) => {
  res.json({ stages: listDevelopmentStages(absoluteDeckDir) });
});

app.use("/images", express.static(path.join(absoluteDeckDir, "images")));
app.use("/render", express.static(path.join(absoluteDeckDir, "render")));

const port = Number(process.env.PORT || 8787);
app.listen(port, () => {
  console.log(`Deck server running at http://localhost:${port}`);
});
