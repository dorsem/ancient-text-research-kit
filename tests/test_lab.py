from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('lab',ROOT/'tools/lab.py')
lab=importlib.util.module_from_spec(spec); spec.loader.exec_module(lab)


class RegistryChecks(unittest.TestCase):
    def setUp(self):
        self.data=json.loads((ROOT/'study/registry.json').read_text())

    def test_current_example(self):
        self.assertEqual(lab.registry_errors(self.data),[])

    def test_duplicate_ids_are_rejected(self):
        self.data['sources'].append(copy.deepcopy(self.data['sources'][0]))
        self.assertTrue(any('duplicate' in x for x in lab.registry_errors(self.data)))

    def test_dangling_evidence_is_rejected(self):
        self.data['claims'][0]['evidence'][0]['evidence_id']='NOT_PRESENT'
        self.assertTrue(any('unknown evidence_id' in x for x in lab.registry_errors(self.data)))

    def test_missing_source_is_rejected(self):
        self.data['evidence'][0]['source_id']='NOT_PRESENT'
        self.assertTrue(any('unknown source_id' in x for x in lab.registry_errors(self.data)))

    def test_unknown_requires_reason(self):
        self.data['evidence'][0]['locator']={'status':'unknown'}
        self.assertTrue(any('missing locator' in x for x in lab.registry_errors(self.data)))

    def test_checked_cannot_hide_unknown_locator(self):
        self.data['evidence'][0]['locator']={'status':'unknown','reason':'Image unavailable'}
        c=self.data['claims'][0]; c['review_status']='checked'
        c['review']={'reviewer':'test','role':'ai','method':'source comparison','date':'2026-10-05'}
        self.assertTrue(any('unknown locator' in x for x in lab.registry_errors(self.data)))

    def test_checked_requires_attributed_review(self):
        self.data['claims'][0]['review_status']='checked'
        self.assertTrue(any('attributed review' in x for x in lab.registry_errors(self.data)))

    def test_confidence_is_not_review_status(self):
        c=self.data['claims'][0]; c['confidence']='checked'
        self.assertTrue(any('invalid confidence' in x for x in lab.registry_errors(self.data)))

    def test_malformed_reference_reports_error(self):
        self.data['evidence'][0]['source_id']={'bad':'shape'}
        self.data['claims'][0]['kind']=[]
        self.assertGreaterEqual(len(lab.registry_errors(self.data)),2)


class LinkAndRenderChecks(unittest.TestCase):
    def test_script_urls_and_traversal_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp); (p/'README.md').write_text('[bad](javascript:alert) [escape](../outside.md)')
            errors=lab.link_errors(p)
            self.assertTrue(any('unsafe link' in x for x in errors))
            self.assertTrue(any('escapes package' in x for x in errors))

    def test_editorial_superscript_survives_and_script_is_escaped(self):
        out=lab.inline('<code><sup>tumu</sup>u₅ mu-kéše</code><script>alert(1)</script>')
        self.assertIn('<sup>tumu</sup>',out)
        self.assertNotIn('<script>',out)
        self.assertIn('&lt;script&gt;',out)

    def test_explicit_pipe_inside_transliteration_is_one_cell(self):
        out=lab.render('| Line | Reading |\n|---|---|\n| 1 | <code>&#124;BU.KU6.DU&#124;</code> |','index.html','study.html')
        self.assertEqual(out.count('<td>'),2)
        self.assertIn('|BU.KU6.DU|',out)

    def test_o1920_contains_all_42_addressed_lines(self):
        import re
        text=(ROOT/'study/corpus/Early_incantations/O1920_full_text.md').read_text()
        rows=re.findall(r'^\| (?:obv|rev) [^|]+ \|',text,re.M)
        self.assertEqual(len(rows),42)

    def test_uruk_full_edition_and_audit_stay_consistent(self):
        import re, subprocess, sys
        folder=ROOT/'study/corpus/Uruk_P000928'
        atf=(folder/'transliteration.atf').read_text()
        lines=re.findall(r'^\d+\. (.+)$',atf,re.M)
        prose=(folder/'full_analysis.md').read_text()
        table=re.findall(r'^\| (?:obv|rev)\. [^|]+ \| `([^`]+)` \|',prose,re.M)
        self.assertEqual(len(lines),21)
        self.assertEqual(table,lines)
        subprocess.run([sys.executable,str(ROOT/'study/analysis/check_uruk.py'),'--check'],
                       check=True,capture_output=True,text=True)

    def test_fara_keeps_witnesses_and_superscript(self):
        text=(ROOT/'study/corpus/Fara_FSB15/full_text.md').read_text()
        self.assertIn('SF54',text)
        self.assertIn('TSŠ170',text)
        self.assertIn('<sup>tumu</sup>',text)
        self.assertIn('g[en₇]',text)


class BuiltSiteChecks(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)/'kit'
        shutil.copytree(ROOT,self.root,ignore=shutil.ignore_patterns('site','__pycache__','*.pyc','.git'))

    def tearDown(self): self.tmp.cleanup()

    def test_clean_copy_build_and_every_generated_local_link(self):
        lab.build(self.root)
        self.assertEqual(lab.validate(self.root),[])
        class Links(HTMLParser):
            def __init__(self): super().__init__(); self.links=[]; self.ids=set()
            def handle_starttag(self,tag,attrs):
                a=dict(attrs)
                if 'id' in a:self.ids.add(a['id'])
                if tag=='a' and 'href' in a:self.links.append(a['href'])
        parsed={}
        for p in (self.root/'site').rglob('*.html'):
            parser=Links(); parser.feed(p.read_text()); parsed[p.resolve()]=parser
        for p,parser in parsed.items():
            for url in parser.links:
                u=urlsplit(url)
                if u.scheme:continue
                target=(p.parent/unquote(u.path)).resolve() if u.path else p
                self.assertTrue(lab.within(self.root/'site',target),(p,url))
                self.assertTrue(target.is_file(),(p,url))
                if u.fragment and target in parsed:self.assertIn(unquote(u.fragment),parsed[target].ids)

    def test_evidence_links_keep_main_document_targets(self):
        main=self.root/'study/reports/main_research.md'
        text=main.read_text()
        marker='### C01.'
        start=text.index('\n',text.index(marker))
        links='\n\n[Same section](#c01) [Sibling](chronology.md) [Object](../corpus/Uruk_P000928/reading.md) [External](https://cdli.earth/artifacts/928)\n'
        main.write_text(text[:start]+links+text[start:])
        html=lab.evidence_view(self.root)
        for target in ['study/reports/main_research.html#c01',
                       'study/reports/chronology.html',
                       'study/corpus/Uruk_P000928/reading.html',
                       'https://cdli.earth/artifacts/928']:
            self.assertIn('href="'+target+'"',html)
        self.assertNotIn('href="../corpus/',html)

    def test_rebuild_preserves_manual_html_edits(self):
        lab.build(self.root)
        p=self.root/'site/index.html'; p.write_text(p.read_text()+'<!-- human edit -->')
        with self.assertRaisesRegex(ValueError,'edited or missing'):lab.build(self.root)
        self.assertIn('human edit',p.read_text())

    def test_changed_source_is_stale_until_rebuilt(self):
        lab.build(self.root)
        p=self.root/'study/reports/main_research.md'; p.write_text(p.read_text()+'\nРедакционное уточнение.\n')
        self.assertTrue(any('source files changed' in x for x in lab.validate(self.root)))
        lab.build(self.root)
        self.assertEqual(lab.validate(self.root),[])

    def test_deterministic_rebuild(self):
        lab.build(self.root); first=(self.root/'site/build.json').read_bytes()
        lab.build(self.root); self.assertEqual(first,(self.root/'site/build.json').read_bytes())

    def test_generated_directory_symlink_cannot_redirect_writes(self):
        site=self.root/'site'; site.mkdir()
        outside=Path(self.tmp.name)/'outside'; outside.mkdir()
        (site/'study').symlink_to(outside,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'symlinks'):lab.build(self.root)
        self.assertEqual(list(outside.iterdir()),[])


if __name__=='__main__': unittest.main()
