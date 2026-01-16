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
    concurrency_image=6,
    concurrency_text=6,
    resume=True,
    additional_instructions="Add UAE-specific policy context and examples.",
)

# Launch the local GUI for play/testing
session = et.run_simulation(deck_dir, npm_install=True)
# session.stop()
```

### Running the UI from a notebook install

`run_simulation()`/`launch_ui()` needs the **UI source folder** (`ui/`) to start the deck server and Vite app. The
PyPI/Git install now bundles the UI assets, so you can run it without a local repo checkout:

```python
%pip install --force-reinstall git+https://github.com/hemanth-asirvatham/econ-tabletop.git@main

import econ_tabletop as et

deck_dir = "/path/to/decks/my_run"

session = et.run_simulation(deck_dir, npm_install=True)
# session.stop()
```

Notes:
- You can run this from **any working directory**; the helper will fall back to the packaged `ui/` assets.
- You need **Node.js + npm** installed for the UI (`npm install` will run if `npm_install=True`).
- If you only want the API server (no Vite UI), use `et.start_deck_server(...)`.

If you only want to generate without printable PDFs, you can skip the print step:

```python
et.deck_builder(deck_dir, print_pdf=False)
```

Image generation runs concurrently based on `concurrency_image`. In notebook
environments with an active event loop, image generation automatically runs in a worker thread to
preserve async parallelism while still exposing a synchronous API. Increase `concurrency_image` to
drive more parallel image requests.

Deck caching behavior (important when re-running):
- `deck_builder(..., resume=True)` **skips text generation** if deck card JSON files already exist.
- The image pipeline respects `resume=True` and **skips image outputs that already exist**, but it will still
  score/critique any existing candidate images to pick the best final card image.
- To skip all image work entirely, call `deck_builder(..., images=False)` or run only the steps you need.

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

If your organization or project require scoped credentials, also set:

```python
os.environ["OPENAI_ORG"] = "org_..."
os.environ["OPENAI_PROJECT"] = "proj_..."
```

If you are using a different OpenAI-compatible base URL, set it explicitly:

```python
os.environ["OPENAI_BASE_URL"] = "https://api.openai.com/v1"
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

- `models.text`: `model`, `reasoning_effort`, `max_output_tokens`, `temperature`, `top_p`, `store`.
- `models.image`: `api`, `model`, `size`, `quality`, `background`, `reference_policy_image`, `reference_development_image`.
- `runtime`: `concurrency_text`, `concurrency_image`, `image_candidate_count`, `image_reference_candidate_multiplier`, `image_timeout_s`, `critique_timeout_s`, `resume`, `prompt_path`.
- `deck_sizes`: total policies and per-stage developments.
- `mix_targets`: balance of positive/negative/conditional/supersedes/powerups/quant indicators.
- `gameplay_defaults`: parameters surfaced to the UI for play setup.
- `scenario`: tone, locale visuals, and any additional instructions.

### Output locations and saved artifacts

- **Deck output root**: whatever `deck_dir` you pass (e.g. `decks/baseline`).
- **Rendered cards**: `deck_dir/render/` (PNGs for cards and thumbnails).
- **Generated art**: `deck_dir/images/`.
- **Printable PDF**: `deck_dir/print/cards_letter.pdf`.
- **Resolved config & metadata**: `deck_dir/meta/`.
- **Validation reports**: `deck_dir/validation/`.

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
  - `additional_instructions`: extra context injected into prompts.
  - `tone`: stylistic target (e.g., "realistic, policy-relevant, grounded").
  - `locale_visuals`: list of regional motifs (affects art prompts).
- `stages`: progression stages, with `time_horizon` and `capability_profile`.
- `deck_sizes`: total policies + developments per stage.
- `mix_targets`: balances for positive/negative, conditional, supersedes, powerups, quantitative indicators.
- `gameplay_defaults`: defaults surfaced to the UI (override in the UI setup).
- `models.text` and `models.image`: model slugs and generation parameters.
- `runtime`: concurrency and batching for text/image generation.

Default sizing is **5 stages**, **~30 developments per stage**, and **~56 policies**. Tune these
directly in your config:

```yaml
stages:
  count: 5
  definitions:
    - id: 0
      name: "Stage 0"
      time_horizon: "today / near-term"
      capability_profile: "Frontier AI capabilities similar to present-day large models"
    # ...
deck_sizes:
  policies_total: 56
  developments_per_stage: [30, 30, 30, 30, 30]
```

## OpenAI API usage (structured outputs + images)

The generator uses the OpenAI Responses API for structured JSON outputs and the Images API for card art.

### Structured text calls

All text generation is routed through `POST /v1/responses` with JSON schema validation:

```json
{
  "model": "gpt-5.2",
  "input": "<rendered prompt text>",
  "response_format": {
    "type": "json_schema",
    "json_schema": {
      "name": "policy_cards",
      "schema": { "type": "object", "properties": { "cards": { "type": "array" } } },
      "strict": true
    }
  },
  "max_output_tokens": 2000,
  "temperature": 0.7,
  "top_p": 0.9,
  "reasoning": { "effort": "high" },
  "store": false
}
```

Key notes:
- `response_format` with `json_schema` forces valid JSON output matching the schema.
- `reasoning.effort` is only applied for models that support it.
- All prompts are rendered from Jinja templates under `generator/src/deckgen/prompts/`.

### Image generation calls

Art is generated via `POST /v1/images/generations`:

```json
{
  "model": "gpt-image-1.5",
  "prompt": "<image prompt>",
  "size": "1536x1024",
  "quality": "high",
  "background": null
}
```

If a reference image is supplied (or auto-generated from the first card), the pipeline uses the edits endpoint to preserve layout:

```
POST /v1/images/edits (multipart/form-data)
```

Form fields include `model`, `prompt`, `size`, `background`, plus one or more `image` files. The reference is used to keep a consistent horizontal card layout while still applying card-specific text and art.

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
    development/power_<dev_id>.png (power cards only, optional alias)
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

## Additional Instructions & Style References

- Provide `scenario.additional_instructions` and `scenario.locale_visuals` to condition **both** text and art prompts.
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
