# Econ Tabletop: AI/AGI Economy Card Simulation

This repository provides a standalone pipeline for generating a staged tabletop card simulation about AI/AGI in the economy and a local web GUI to play it.

## Quickstart

### 1) Generator

```bash
export OPENAI_API_KEY="sk-..."

# Baseline deck
python -m deckgen.cli generate --config generator/examples/configs/baseline.yaml --out decks/baseline
python -m deckgen.cli render --deck decks/baseline
python -m deckgen.cli images --deck decks/baseline
python -m deckgen.cli print --deck decks/baseline

# Or run everything in order
python -m deckgen.cli all --config generator/examples/configs/baseline.yaml --out decks/baseline

# UAE scenario deck
python -m deckgen.cli all --config generator/examples/configs/uae.yaml --out decks/uae
```

### 2) UI

```bash
cd ui
npm install

# Run the deck server (serves /api + images)
node --loader ts-node/esm server/index.ts --deck ../decks/baseline

# In another terminal, run the web app
npm run dev
```

Open the Vite URL shown in the terminal. The UI connects to the local server (default `http://localhost:8787`).

## Configuration

All generator behavior is controlled by a YAML config.

Key knobs:

- `scenario`: optional scenario conditioning.
  - `name`: label used in manifests.
  - `injection`: extra context injected into prompts.
  - `tone`: stylistic target (e.g., "realistic, policy-relevant, grounded").
  - `locale_visuals`: list of regional motifs (affects art prompts).
- `stages`: progression stages, with `time_horizon` and `capability_profile`.
- `deck_sizes`: total policies + developments per stage.
- `mix_targets`: balances for positive/negative, conditional, supersedes, powerups, quantitative indicators.
- `gameplay_defaults`: defaults surfaced to the UI (override in the UI setup).
- `models.text` and `models.image`: model slugs and generation parameters.
- `runtime`: concurrency and batching for text/image generation.

Example configs:
- `generator/examples/configs/baseline.yaml`
- `generator/examples/configs/uae.yaml`

## Deck Folder Format

A generated deck folder is consumed by the UI and contains:

```
decks/<deck_id>/
  manifest.json
  cards/
    policies.jsonl
    developments.stage0.jsonl
    developments.stage1.jsonl
  images/
    policy/<policy_id>.png
    development/<dev_id>.png
  render/
    thumbs/
  print/
    cards_letter.pdf
  validation/
    report.json
  meta/
    config_resolved.yaml
    taxonomy.json
    tags.json
    stage_summaries.json
```

## Scenario Injection & Style References

- Provide `scenario.injection` and `scenario.locale_visuals` to condition **both** text and art prompts.
- Style references:
  - Place reference images under `generator/assets/style_refs/policy/` and `generator/assets/style_refs/development/`.
  - If no refs are present, the generator creates one policy reference and one development reference under `generator/assets/generated_refs/` and uses them as style anchors.

## Re-running Only Images or Printing

```bash
# Re-render card PNGs (text is unchanged)
python -m deckgen.cli render --deck decks/baseline

# Re-generate art (uses saved art prompts)
python -m deckgen.cli images --deck decks/baseline

# Re-generate print PDFs
python -m deckgen.cli print --deck decks/baseline
```

## Development Notes

- The generator uses the OpenAI Responses API for structured outputs, with JSON schema validation.
- If a model doesn’t support JSON schema, it falls back to JSON mode and then validates.
- All raw OpenAI request/response payloads are saved under `cache/` for reproducibility.
