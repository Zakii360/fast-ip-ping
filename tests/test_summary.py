import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch


SUMMARY_PATH = Path(__file__).parents[1] / '.github' / 'workflows' / 'scripts' / 'summary.py'

spec = importlib.util.spec_from_file_location('summary', SUMMARY_PATH)
summary = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = summary
spec.loader.exec_module(summary)


class FakeProperties:
    def __init__(self):
        self.values = {}

    def load(self, file_obj):
        for line in file_obj.read().decode().splitlines():
            if '=' in line:
                key, value = line.split('=', 1)
                self.values[key] = value

    def __getitem__(self, key):
        return types.SimpleNamespace(data=self.values[key])


class SummaryTests(unittest.TestCase):
    def run_summary(self, files=None):
        files = files or {}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)

            (root / 'settings.json').write_text(
                json.dumps({'versions': ['test-version']})
            )

            properties = root / 'versions' / 'test-version' / 'gradle.properties'
            properties.parent.mkdir(parents=True)
            properties.write_text('game_versions=1.21.10')

            libs = root / 'build-artifacts' / 'test-version' / 'build' / 'libs'
            libs.mkdir(parents=True)

            for name, contents in files.items():
                (libs / name).write_bytes(contents)

            summary_path = root / 'summary.md'

            env = {
                'GITHUB_STEP_SUMMARY': str(summary_path),
                'TARGET_SUBPROJECT': '',
                'WORKFLOW_ARTIFACTS': '{"artifacts":[]}',
            }

            fake_jproperties = types.SimpleNamespace(Properties=FakeProperties)

            with patch.dict(
                sys.modules,
                {'jproperties': fake_jproperties}
            ), patch.dict(
                os.environ,
                env,
                clear=False
            ), contextlib.chdir(root):
                with contextlib.redirect_stdout(io.StringIO()):
                    summary.main()

            return summary_path.read_text()

    def test_missing_jar_is_reported_without_crashing(self):
        output = self.run_summary()

        self.assertIn(
            '| test-version | 1.21.10 | *not found* | *N/A* | *N/A* |',
            output
        )

    def test_jar_metadata_is_still_reported(self):
        output = self.run_summary({
            'fast-ip-ping.jar': b'test jar'
        })

        self.assertIn('`fast-ip-ping.jar`', output)
        self.assertIn('| 8 B |', output)
        self.assertIn('SHA-256', output)


if __name__ == '__main__':
    unittest.main()
