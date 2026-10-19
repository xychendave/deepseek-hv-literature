import contextlib
import io
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from hv_literature import Library, abstract_text, topic_score, mcp, initialize


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.papers=self.root/'papers';self.papers.mkdir()
        self.cfg={'library_roots':[str(self.papers)],'credential_file':str(self.root/'none'),
          'daily_limit':2,'recent_days':30,'backfill_days':365,'topics':{
          'gas':{'name':'gas','queries':['gas']},'fault':{'name':'fault','queries':['fault']}}}
        self.lib=Library(self.root,self.cfg)

    def tearDown(self):
        self.lib.db.close();self.tmp.cleanup()

    def pdf(self,path,lines):
        from reportlab.pdfgen import canvas
        c=canvas.Canvas(str(path));c.setTitle('Holomorphic embedding convergence study')
        for t in lines:c.drawString(50,700,t);c.showPage()
        c.save()

    def test_ingest_duplicate_page_and_changed_file(self):
        p=self.papers/'a.pdf';self.pdf(p,['Holomorphic embedding offers robust convergence and efficient calculation.',
          'However, holomorphic embedding suffers from computational complexity for large networks.'])
        shutil.copyfile(p,self.papers/'copy.pdf')
        out=self.lib.ingest();self.assertEqual(out['counts']['new_documents'],1)
        self.assertEqual(self.lib.status()['counts']['active_files'],2)
        hits=self.lib.search('全纯嵌入','limitations')['results'];self.assertTrue(hits);self.assertEqual(hits[0]['page'],2)
        self.assertIn(hits[0]['quote'],self.lib.page(hits[0]['document_id'],2)['text'])
        self.assertEqual(self.lib.ingest()['counts']['unchanged'],2)
        (self.papers/'copy.pdf').unlink();p.write_bytes(b'not a PDF')
        self.lib.ingest();self.assertEqual(self.lib.search('全纯嵌入','limitations')['results'],[])

    def test_no_evidence_no_fabrication(self):
        self.assertEqual(self.lib.search('绝缘气体 分子','advantages')['results'],[])
        self.assertEqual(abstract_text({'world':[1],'hello':[0]}),'hello world')

    def test_initialization_preserves_existing_config_and_optional_journals(self):
        out=initialize(self.root,[str(self.papers)])
        path=Path(out['config']);before=path.read_bytes()
        with self.assertRaises(RuntimeError):initialize(self.root,['/different/path'])
        self.assertEqual(path.read_bytes(),before)
        self.assertTrue(self.lib.import_journals()['skipped'])

    def test_relevance_gates(self):
        self.assertEqual(topic_score('gas',{'title':'Hydrogen gas separation membranes','abstract':'air and wind energy'})[0],0)
        self.assertEqual(topic_score('gas',{'title':'Insulating gas blankets in oil wells','abstract':'Thermal design of CO2 storage'})[0],0)
        self.assertGreater(topic_score('gas',{'title':'Machine learning screening of insulating gas molecules for dielectric strength'})[0],0)
        self.assertEqual(topic_score('fault',{'title':'Multimodal fusion for medical diagnosis'})[0],0)
        self.assertGreater(topic_score('fault',{'title':'Acoustic and optical fusion for partial discharge classification'})[0],0)

    def work(self,id,title,date,doi):
        return {'id':'https://openalex.org/'+id,'title':title,'publication_date':date,'doi':doi,'is_retracted':False}

    def test_daily_idempotence_dedup_and_future_exclusion(self):
        from hv_literature import now
        day=now().date().isoformat()
        w=self.work('W1','Molecular screening of insulating gas for dielectric strength',day,'https://doi.org/10.1/a')
        duplicate=dict(w,id='https://openalex.org/W2')
        future=self.work('W3','Molecular screening of insulating gas','2999-01-01','https://doi.org/10.1/b')
        retract=dict(w,id='W4',doi='https://doi.org/10.1/c',is_retracted=True)
        with patch.object(self.lib,'api',return_value={'meta':{'count':4},'results':[w,duplicate,future,retract]}) as api:
            out=self.lib.daily();self.assertEqual(out['count'],1)
            calls=api.call_count
            same=self.lib.daily();self.assertTrue(same['cached']);self.assertEqual(api.call_count,calls)
        self.assertEqual(self.lib.db.execute('select count(*) from works').fetchone()[0],1)
        self.assertEqual(self.lib.db.execute('select count(*) from featured').fetchone()[0],1)

    def test_partial_failure_not_no_papers(self):
        with patch.object(self.lib,'api',side_effect=RuntimeError('OpenAlex HTTP 503')):
            out=self.lib.daily();self.assertEqual(out['status'],'partial');self.assertTrue(out['errors'])
            self.assertIn('部分成功',Path(out['report']).read_text())

    def test_mcp_handshake_and_tool_call(self):
        messages=[{'jsonrpc':'2.0','id':1,'method':'initialize','params':{'protocolVersion':'2025-06-18'}},
          {'jsonrpc':'2.0','method':'notifications/initialized'},
          {'jsonrpc':'2.0','id':2,'method':'tools/list'},
          {'jsonrpc':'2.0','id':3,'method':'tools/call','params':{'name':'search_passages','arguments':{'query':'nonexistent'}}}]
        output=io.StringIO()
        with patch('sys.stdin',io.StringIO('\n'.join(json.dumps(x) for x in messages))),contextlib.redirect_stdout(output):mcp(self.lib)
        responses=[json.loads(x) for x in output.getvalue().splitlines()]
        self.assertEqual(len(responses),3);self.assertEqual(len(responses[1]['result']['tools']),5)
        self.assertFalse(responses[2]['result']['isError'])


class InstallationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.project=self.root/'project';(self.project/'skill/hv-literature').mkdir(parents=True)
        self.home=self.root/'dsh-home';self.profile=self.home/'profiles/desktop'
        self.profile.mkdir(parents=True)
        self.config=self.profile/'cordis.patch.yml'
        self.existing='- insert:\n    - {"id":"existing-plugin","name":"example"}\n'
        self.config.write_text(self.existing)
        self.skills=self.root/'skills'

    def tearDown(self):
        self.tmp.cleanup()

    def test_install_dry_run_preserves_plugins_and_is_idempotent(self):
        from install_dsh import install, BEGIN
        with patch('install_dsh.ROOT',self.project):
            install(self.home,['desktop'],[str(self.skills)],dry_run=True)
            self.assertEqual(self.config.read_text(),self.existing)
            self.assertFalse(self.skills.exists())
            first=install(self.home,['desktop'],[str(self.skills)])
            self.assertEqual(Path(first['profiles'][0]['backup']).read_text(),self.existing)
            self.assertTrue((self.skills/'hv-literature').is_symlink())
            after=self.config.read_text()
            self.assertIn(self.existing.strip(),after)
            again=install(self.home,['desktop'],[str(self.skills)])
            self.assertFalse(again['profiles'][0]['changed'])
            self.assertEqual(self.config.read_text(),after)
            self.assertEqual(after.count(BEGIN),1)

    def test_conflicting_skill_does_not_change_profile(self):
        from install_dsh import install
        (self.skills/'hv-literature').mkdir(parents=True)
        with patch('install_dsh.ROOT',self.project),self.assertRaises(ValueError):
            install(self.home,['desktop'],[str(self.skills)])
        self.assertEqual(self.config.read_text(),self.existing)
        self.assertFalse((self.project/'data').exists())

    def test_credential_permissions_without_echo(self):
        import configure_key
        credential=self.root/'credentials/key.json'
        (self.project/'config.json').write_text(json.dumps({'credential_file':str(credential)}))
        output=io.StringIO()
        with patch('configure_key.ROOT',self.project),patch('getpass.getpass',return_value='synthetic-test-value'),contextlib.redirect_stdout(output):
            configure_key.main()
        self.assertEqual(credential.stat().st_mode & 0o777,0o600)
        self.assertEqual(json.loads(credential.read_text())['openalex_api_key'],'synthetic-test-value')
        self.assertNotIn('synthetic-test-value',output.getvalue())


if __name__=='__main__':unittest.main()
