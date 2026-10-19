import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from install_card import PACKAGE, BEGIN, END, build_bundle, install_card, remove_legacy_block


class NativeCardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name).resolve()
        self.root = self.base/'project with spaces'
        self.root.mkdir()
        shutil.copytree(Path(__file__).parent/'harness-card',self.root/'harness-card')
        (self.root/'skill/hv-literature').mkdir(parents=True)
        self.home = self.base/'home'
        self.profile = self.home/'profiles/desktop'
        self.profile.mkdir(parents=True)
        self.manifest = self.profile/'package.json'
        self.manifest.write_text(json.dumps({'dependencies':{'unrelated':'1.0'},'dsh':{'profile':{'bundles':['unrelated']}}}))
        self.patch_file = self.profile/'cordis.patch.yml'
        self.unrelated = '- insert:\n    - {"id":"unrelated","name":"example"}\n'
        self.original = self.unrelated+'\n'+BEGIN+'\n- insert: []\n'+END+'\n'
        self.patch_file.write_text(self.original)
        self.skills = self.base/'skills'

    def tearDown(self):
        self.temp.cleanup()

    def fake_cli(self, command, **kwargs):
        self.assertEqual(kwargs['env']['DSH_HOME'],str(self.home))
        self.assertEqual(command[-1],'link:'+str(self.root/'data/harness-plugin'))
        manifest = json.loads(self.manifest.read_text())
        manifest['dependencies'][PACKAGE] = command[-1]
        manifest['dsh']['profile']['bundles'].append(PACKAGE)
        self.manifest.write_text(json.dumps(manifest))
        linked = self.profile/'node_modules'/PACKAGE
        linked.parent.mkdir(parents=True,exist_ok=True)
        linked.symlink_to(self.root/'data/harness-plugin',target_is_directory=True)
        return subprocess.CompletedProcess(command,0,'','')

    def test_card_is_native_bundle_with_no_private_data(self):
        (self.root/'config.json').write_text('{"private":"do not package"}')
        bundle = build_bundle(self.root)
        manifest = json.loads((bundle/'package.json').read_text())
        self.assertEqual(manifest['name'],PACKAGE)
        self.assertTrue((bundle/manifest['dsh']['bundle']['patch']).exists())
        config = json.loads((bundle/'cordis.patch.yml').read_text())[0]['insert'][0]['config']
        self.assertEqual(config['command'],str(self.root/'hv-literature'))
        self.assertEqual(config['serverName'],'hv_research')
        self.assertEqual(config['env'],{})
        self.assertFalse((bundle/'config.json').exists())
        self.assertEqual(len([p for p in bundle.rglob('*') if p.is_file()]),6)

    def test_migration_and_reinstall_preserve_other_plugins(self):
        with patch('install_card.shutil.which',return_value='/usr/local/bin/dsh'),patch('install_card.subprocess.run',side_effect=self.fake_cli) as run:
            first = install_card(self.root,self.home,['desktop'],[str(self.skills)])
            self.assertTrue(first['profiles'][0]['enabled'])
            self.assertNotIn(BEGIN,self.patch_file.read_text())
            self.assertIn(self.unrelated.strip(),self.patch_file.read_text())
            second = install_card(self.root,self.home,['desktop'],[str(self.skills)])
            self.assertTrue(second['profiles'][0]['already_installed'])
            self.assertEqual(run.call_count,1)
        self.assertEqual(json.loads(self.manifest.read_text())['dependencies']['unrelated'],'1.0')

    def test_failed_install_and_timeout_restore_legacy_registration(self):
        with patch('install_card.shutil.which',return_value='/usr/local/bin/dsh'):
            for effect in [subprocess.CompletedProcess([],1,'','synthetic failure'), subprocess.TimeoutExpired('dsh',180)]:
                with patch('install_card.subprocess.run',side_effect=effect if isinstance(effect,Exception) else None,return_value=effect):
                    with self.assertRaises(RuntimeError):
                        install_card(self.root,self.home,['desktop'],[str(self.skills)])
                    self.assertEqual(self.patch_file.read_text(),self.original)

    def test_dry_run_has_no_side_effects(self):
        result = install_card(self.root,self.home,['desktop'],[str(self.skills)],dry_run=True)
        self.assertTrue(result['profiles'][0]['migrate_legacy'])
        self.assertEqual(self.patch_file.read_text(),self.original)
        self.assertFalse((self.root/'data').exists())
        self.assertFalse(self.skills.exists())

    def test_empty_patch_remains_valid_and_malformed_block_fails(self):
        self.assertEqual(remove_legacy_block(BEGIN+'\n- insert: []\n'+END),'[]\n')
        self.assertEqual(remove_legacy_block('# comment\n'+BEGIN+'\n'+END),'# comment\n[]\n')
        with self.assertRaises(ValueError):remove_legacy_block(BEGIN+'\n')


if __name__ == '__main__':
    unittest.main()
