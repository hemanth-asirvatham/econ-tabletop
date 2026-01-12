from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import importlib.util

yaml_spec = importlib.util.find_spec("yaml")
if yaml_spec is None:
    YAML_AVAILABLE = False
else:
    import yaml

    YAML_AVAILABLE = True



class TestPipelineSmoke(unittest.TestCase):
    def test_run_pipeline_with_minimal_config(self) -> None:
        if not YAML_AVAILABLE:
            self.skipTest("PyYAML is not installed in the test environment.")
        if importlib.util.find_spec("rich") is None:
            self.skipTest("rich is not installed in the test environment.")
        if importlib.util.find_spec("PIL") is None:
            self.skipTest("Pillow is not installed in the test environment.")
        example_config = Path("generator/examples/configs/baseline.yaml")
        config_data = yaml.safe_load(example_config.read_text(encoding="utf-8"))
        config_data["deck_sizes"]["policies_total"] = 2
        config_data["deck_sizes"]["developments_per_stage"] = [1, 1, 1]

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            config_path = tmp_path / "config.yaml"
            deck_dir = tmp_path / "deck"
            config_path.write_text(yaml.safe_dump(config_data, sort_keys=False), encoding="utf-8")

            from econ_tabletop.notebook import run_pipeline

            run_pipeline(config_path, deck_dir, render=True, images=True, print_pdf=False)

            self.assertTrue((deck_dir / "manifest.json").exists())
            self.assertTrue((deck_dir / "cards" / "policies.jsonl").exists())
            self.assertTrue((deck_dir / "render" / "thumbs").exists())

    def test_openai_client_dummy_response(self) -> None:
        if importlib.util.find_spec("httpx") is None:
            self.skipTest("httpx is not installed in the test environment.")
        from deckgen.utils.openai_client import OpenAIClient

        client = OpenAIClient(api_key="")
        response = client.responses({"model": "gpt-4.1-mini", "input": "hello"})
        self.assertIn("output", response)


if __name__ == "__main__":
    unittest.main()
