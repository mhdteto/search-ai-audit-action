import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        shutil.copyfile(ROOT/'tests/fixture.json', self.workspace/'fixture.json')

    def run_action(self, **overrides):
        env = {**os.environ, 'GITHUB_WORKSPACE':str(self.workspace),
               'AUDIT_URL':'https://example.org', 'AUDIT_FIXTURE':'fixture.json',
               'AUDIT_OUTPUT_DIR':'reports/demo', 'GITHUB_OUTPUT':str(self.workspace/'outputs'),
               'GITHUB_STEP_SUMMARY':str(self.workspace/'summary')}
        env.update(overrides)
        return subprocess.run([sys.executable,str(ROOT/'run.py')],env=env,capture_output=True,text=True)

    def test_runner_exists(self):
        self.assertTrue((ROOT/'run.py').is_file(),'Action runner has not been implemented')

    def test_offline_reports_and_outputs(self):
        p=self.run_action()
        self.assertEqual(p.returncode,0,p.stderr)
        report=json.loads((self.workspace/'reports/demo/report.json').read_text())
        self.assertEqual(report['transport'],'synthetic offline fixture')
        self.assertEqual(report['page']['status'],200)
        self.assertIn('report-json=reports/demo/report.json',(self.workspace/'outputs').read_text())
        self.assertIn('synthetic offline fixture',(self.workspace/'summary').read_text())

    def test_offline_404_still_generates_reports(self):
        examples = self.workspace / 'examples'
        examples.mkdir()
        shutil.copyfile(ROOT / 'examples/http-404.json', examples / 'http-404.json')
        p = self.run_action(
            AUDIT_URL='https://example.org/missing',
            AUDIT_FIXTURE='examples/http-404.json',
            AUDIT_OUTPUT_DIR='reports/http-404',
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        output = self.workspace / 'reports/http-404'
        report = json.loads((output / 'report.json').read_text(encoding='utf-8'))
        self.assertEqual(report['page']['status'], 404)
        self.assertEqual(report['transport'], 'synthetic offline fixture')
        html = (output / 'report.html').read_text(encoding='utf-8')
        self.assertIn('<dt>Page HTTP status</dt><dd>404</dd>', html)

    def test_path_boundaries(self):
        for path in ['../escape',str(self.workspace.parent/'escape'),'reports\nforged=1','.', '']:
            with self.subTest(path=path):
                p=self.run_action(AUDIT_OUTPUT_DIR=path)
                self.assertNotEqual(p.returncode,0)
        self.assertFalse((self.workspace/'reports').exists())

    def test_symlink_directory_and_fixture_refused(self):
        (self.workspace/'linked').symlink_to(self.workspace,target_is_directory=True)
        p=self.run_action(AUDIT_OUTPUT_DIR='linked/report')
        self.assertNotEqual(p.returncode,0)
        (self.workspace/'linked-fixture.json').symlink_to(self.workspace/'fixture.json')
        p=self.run_action(AUDIT_FIXTURE='linked-fixture.json')
        self.assertNotEqual(p.returncode,0)

    def test_fixture_outside_workspace_refused(self):
        p=self.run_action(AUDIT_FIXTURE='../fixture.json')
        self.assertNotEqual(p.returncode,0)

    def test_fixture_cannot_be_overwritten(self):
        target=self.workspace/'reports'
        target.mkdir()
        shutil.copyfile(self.workspace/'fixture.json',target/'report.json')
        original=(target/'report.json').read_bytes()
        p=self.run_action(AUDIT_FIXTURE='reports/report.json',AUDIT_OUTPUT_DIR='reports')
        self.assertNotEqual(p.returncode,0)
        self.assertEqual((target/'report.json').read_bytes(),original)

    def test_shell_syntax_is_literal(self):
        path='reports/$(touch SHOULD_NOT_EXIST);literal'
        p=self.run_action(AUDIT_OUTPUT_DIR=path)
        self.assertEqual(p.returncode,0,p.stderr)
        self.assertTrue((self.workspace/path/'report.html').is_file())
        self.assertFalse((self.workspace/'SHOULD_NOT_EXIST').exists())

    def test_private_url_fails_without_network(self):
        p=self.run_action(AUDIT_URL='http://127.0.0.1/',AUDIT_FIXTURE='')
        self.assertNotEqual(p.returncode,0)
        self.assertFalse((self.workspace/'reports').exists())

if __name__=='__main__': unittest.main()
