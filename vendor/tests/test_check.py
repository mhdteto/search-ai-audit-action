import importlib.util
import pathlib
import json
import os
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('checker', ROOT / 'check.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)

class CheckerTests(unittest.TestCase):
    def test_unsafe_urls(self):
        for url in ['file:///etc/passwd', 'https://u:p@example.org', 'https://127.0.0.1', 'https://[::1]', 'https://localhost', 'https://example.org:abc', 'https://example.org:8080', 'https://example.org/\nabc', '//user@example.org', 'https://example.org\\@127.0.0.1']:
            with self.subTest(url=url), self.assertRaises(ValueError): c.validate_url(url)
    def test_dns_all_answers(self):
        with self.assertRaises(ValueError): c.resolve_public('example.org',443,lambda *a, **k: [(2,1,6,'',('93.184.216.34',443)),(2,1,6,'',('10.0.0.1',443))])
    def test_pin_connection(self):
        with patch.object(c.socket,'create_connection') as connect:
            connection=c.PinnedHTTPConnection('example.org',80,'93.184.216.34',2)
            connection.connect()
            self.assertEqual(connect.call_args[0][0],('93.184.216.34',80))
            self.assertLessEqual(connect.call_args[0][1],2)
    def test_https_hostname(self):
        with patch.object(c.socket,'create_connection'), patch.object(c.ssl,'create_default_context') as context:
            connection=c.PinnedHTTPSConnection('example.org',443,'93.184.216.34',2)
            connection.connect()
            self.assertEqual(context.return_value.wrap_socket.call_args.kwargs['server_hostname'],'example.org')
    def test_unsafe_redirect(self):
        calls=[]
        def transport(url):
            calls.append(url)
            return {'status':302,'headers':{'location':'//u@127.0.0.1/x'},'body':''}
        with self.assertRaises(ValueError): c.fetch('https://example.org',transport)
        self.assertEqual(len(calls),1)
    def test_redirect_limit(self):
        with self.assertRaises(ValueError): c.fetch('https://example.org',lambda u:{'status':302,'headers':{'location':'/again'},'body':''})
    def test_parse(self):
        data=c.parse_page('<meta name="robots" content="noindex"><link rel="canonical" href="javascript:alert(1)"><script type="application/ld+json">{"@type":"Organization"}</script><a href="/about">About</a>', 'https://example.org/')
        self.assertEqual(data['meta_robots'],['noindex'])
        self.assertFalse(data['canonicals'][0]['valid_http_url'])
        self.assertEqual(data['json_ld_types'],['Organization'])
        self.assertEqual(data['internal_links'],['https://example.org/about'])
    def test_bad_json(self):
        self.assertEqual(c.parse_page('<script type="application/ld+json">oops</script>','https://example.org')['json_ld_invalid_blocks'],1)
    def test_error_nonhtml_and_robots(self):
        def transport(u):
            return {'status':403 if u.endswith('robots.txt') else 500,'headers':{'content-type':'application/json'},'body':'{"bad":true}'}
        report=c.analyze('https://example.org/',transport,'2026-01-01T00:00:00Z')
        self.assertEqual(report['page']['analysis'],'skipped: response is not successful HTML')
        self.assertEqual(report['robots']['availability'],'forbidden (403); policy unknown')
    def test_limits(self):
        for response in [{'status':200,'headers':{'content-encoding':'gzip'},'body':'a'}, {'status':200,'headers':{},'body':'x'*(c.MAX_BODY+1)}]:
            with self.assertRaises(ValueError): c.fetch('https://example.org',lambda u:response)
    def test_output_collision(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=pathlib.Path(tmp)/'report.json';p.write_text('keep')
            with self.assertRaises(ValueError): c.output_paths(pathlib.Path(tmp),p)
            self.assertEqual(p.read_text(),'keep')
    def test_fixture_no_network(self):
        with patch.object(c.socket,'getaddrinfo',side_effect=AssertionError('network forbidden')):
            t, stamp=c.fixture_transport(ROOT/'examples/fixture.json')
            report=c.analyze('https://example.org/',t,stamp)
            self.assertEqual(report['robots']['availability'],'available')
            self.assertEqual(report['mode'],'observational')
    def test_alias_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=pathlib.Path(tmp)
            source=root/'fixture.json';source.write_text('keep')
            target=root/'report.json'
            os.link(source,target)
            with self.assertRaises(ValueError): c.output_paths(root,source)
            target.unlink()
            target.symlink_to(source)
            with self.assertRaises(ValueError): c.output_paths(root,source)
            self.assertEqual(source.read_text(),'keep')
    def test_missing_robots(self):
        def transport(u):
            return {'status':404,'headers':{'content-type':'text/html'},'body':'<meta name="robots" content="noindex">'}
        report=c.analyze('https://example.org/',transport,'fixture')
        self.assertEqual(report['robots']['availability'],'missing (404); no robots file observed')
        self.assertNotIn('meta_robots',report['page'])
    def test_fixture_malformed(self):
        for response in [None, {'status':'200','headers':{},'body':''}, {'status':True,'headers':{},'body':''}, {'status':200,'headers':[],'body':''}, {'status':200,'headers':{},'body':42}]:
            with tempfile.TemporaryDirectory() as tmp:
                fixture=pathlib.Path(tmp)/'fixture.json'
                fixture.write_text(json.dumps({'collected_at':'fictional','responses':{'https://example.org/':response}}))
                with self.assertRaises(ValueError): c.fixture_transport(fixture)
    def test_invalid_input_leaves_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            target=pathlib.Path(tmp)/'report.json';target.write_text('keep')
            self.assertEqual(c.main(['https://localhost/','--output-dir',tmp]),2)
            self.assertEqual(target.read_text(),'keep')
    def test_robots_and_sitemap_redirect_validation(self):
        seen=[]
        def transport(u):
            seen.append(u)
            if u.endswith('robots.txt') or u.endswith('sitemap.xml'):
                return {'status':302,'headers':{'location':'http://169.254.169.254/latest/'},'body':''}
            return {'status':200,'headers':{'content-type':'text/html'},'body':'<link rel="canonical" href="">'}
        report=c.analyze('https://example.org/',transport,'fixture')
        self.assertEqual(len(seen),3)
        self.assertIn('error',report['robots'])
        self.assertIn('error',report['sitemap'])
        self.assertFalse(report['page']['canonicals'][0]['valid_http_url'])
    def test_live_uses_resolved_address_and_host(self):
        class FakeConnection:
            def __init__(self,*args): self.args=args; self.sock=None
            def request(self,*args,**kwargs): self.request_args=(args,kwargs)
            def getresponse(self):
                class Response:
                    status=200
                    def getheaders(self): return [('Content-Type','text/html')]
                    def read(self,limit): return b'<h1>Example</h1>'
                return Response()
            def close(self): pass
        with patch.object(c,'resolve_public',return_value='93.184.216.34') as resolve, patch.object(c,'PinnedHTTPSConnection',side_effect=FakeConnection) as connection:
            c.live_transport('https://example.org/')
            self.assertEqual(connection.call_args[0][:3],('example.org',443,'93.184.216.34'))
            resolve.assert_called_once_with('example.org',443)
    def test_readable_summary(self):
        report={'transport':'synthetic offline fixture','page':{'status':503,'url':'https://example.org/<unsafe>','headers':{'x-robots-tag':'noindex'},'analysis':'skipped: response is not successful HTML'},'robots':{'availability':'forbidden (403); policy unknown'},'sitemap':{'status':'request failed'}}
        rendered=c.render_html(report)
        for expected in ['Page HTTP status','503','synthetic offline fixture','policy unknown','noindex','&lt;unsafe&gt;','<details>','Manual review']:
            self.assertIn(expected,rendered)
        self.assertNotIn('<unsafe>',rendered)
        self.assertGreaterEqual(len(c.review_findings(report)),3)
    def test_diagnostic_headers_only(self):
        def transport(u):
            return {'status':200,'headers':{'content-type':'text/html','set-cookie':'secret-token','x-robots-tag':'noindex','x-debug-secret':'secret-token'},'body':'<h1>Example</h1>'}
        report=c.analyze('https://example.org/',transport,'fixture')
        self.assertNotIn('secret-token',json.dumps(report))
        self.assertEqual(report['page']['headers']['x-robots-tag'],'noindex')
    def test_html_escape(self):
        rendered=c.render_html({'input_url':'<script>alert(1)</script>','url':'javascript:alert(1)'})
        self.assertNotIn('<script>',rendered)
        self.assertNotIn('href="javascript:',rendered)

if __name__ == '__main__': unittest.main()
