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

## Python / Jupyter usage

Install from Git and use the notebook helpers:

```python
%pip install --force-reinstall git+https://github.com/hemanth-asirvatham/econ-tabletop.git@main

import econ_tabletop as et

deck_dir = "decks/my_run"

# Generate the full deck pipeline (generate -> render -> images -> print)
et.deck_builder(
    deck_dir,
    model_text="gpt-5.2",
    model_image="gpt-image-1.5",
    concurrency_text=6,
    resume=True,
    scenario_injection="Add UAE-specific policy context and examples.",
)

# Launch the local GUI for play/testing
session = et.run_simulation(deck_dir, npm_install=True)
# session.stop()
```

If you only want to generate without printable PDFs, you can skip the print step:

```python
et.deck_builder(deck_dir, print_pdf=False)
```

If you see `ModuleNotFoundError: No module named 'reportlab'`, install the print dependency:

```bash
pip install reportlab
```

### Notebook setup, API key, and parameters

The generator uses the OpenAI API. Set your API key in the notebook (or your shell) before running:

```python
import os
os.environ["OPENAI_API_KEY"] = "sk-..."
```

### Advanced: YAML config (optional)

For full control, you can still use the YAML config workflow. A common notebook pattern is to copy the
example config to a working directory, edit it, and then run the pipeline:

```python
import shutil
from pathlib import Path
import yaml
import econ_tabletop as et

config_src = Path(et.get_example_config("baseline"))
config_dst = Path("configs/my_run.yaml")
config_dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copy(config_src, config_dst)

config = yaml.safe_load(config_dst.read_text())
config["models"]["text"]["model"] = "gpt-5.2"
config["models"]["image"]["model"] = "gpt-image-1.5"
config["runtime"]["concurrency_text"] = 6
config["runtime"]["resume"] = True
config_dst.write_text(yaml.safe_dump(config, sort_keys=False))

deck_dir = Path("decks/my_run")
et.run_all(config_dst, deck_dir)
```

Key configurable parameters in the YAML:

- `models.text`: `model`, `reasoning_effort`, `max_output_tokens`, `store`.
- `models.image`: `model`, `size`, `background`.
- `runtime`: `concurrency_text`, `concurrency_image`, `image_batch_size`, `resume`, `cache_requests`.
- `deck_sizes`: total policies and per-stage developments.
- `mix_targets`: balance of positive/negative/conditional/supersedes/powerups/quant indicators.
- `gameplay_defaults`: parameters surfaced to the UI for play setup.
- `scenario`: tone, locale visuals, and any scenario injection context.

### Output locations and saved artifacts

- **Deck output root**: whatever `deck_dir` you pass (e.g. `decks/baseline`).
- **Rendered cards**: `deck_dir/render/` (PNGs for cards and thumbnails).
- **Generated art**: `deck_dir/images/`.
- **Printable PDF**: `deck_dir/print/cards_letter.pdf`.
- **Resolved config & metadata**: `deck_dir/meta/`.
- **Validation reports**: `deck_dir/validation/`.
- **OpenAI request/response cache**: `cache/` at the repo root when `runtime.cache_requests` is true.

Launch the GUI from a notebook cell:

```python
import econ_tabletop as et

# If you installed from a repo checkout, this will auto-detect ui/
session = et.launch_ui(deck_dir="decks/baseline", npm_install=True)

# When done:
# session.stop()
```

If you installed the package without a local repo checkout, pass the UI directory explicitly:

```python
session = et.launch_ui(
    deck_dir="decks/baseline",
    ui_dir="/path/to/econ-tabletop/ui",
    npm_install=True,
)
```

You can also start only the deck API server:

```python
server = et.start_deck_server(deck_dir="decks/baseline", port=8787)
# server.terminate()
```

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
