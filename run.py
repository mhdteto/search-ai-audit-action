#!/usr/bin/env python3
"""Run the bundled bounded checker; no shell evaluation of action inputs."""
import importlib.util
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent

def workspace_path(value, workspace):
    if not value or any(ord(c)<32 or ord(c)==127 for c in value):
        raise ValueError('Path must be nonempty and contain no control characters')
    relative = Path(value)
    if relative.is_absolute() or '..' in relative.parts or relative == Path('.'):
        raise ValueError('Path must be relative and stay inside the workspace')
    current=workspace
    for part in relative.parts:
        current=current/part
        if current.is_symlink():
            raise ValueError('Path symlinks are forbidden')
    current.resolve().relative_to(workspace)
    return current

def main():
    try:
        workspace=Path(os.environ['GITHUB_WORKSPACE']).resolve(strict=True)
        output=workspace_path(os.environ.get('AUDIT_OUTPUT_DIR','reports/discoverability'),workspace)
        fixture_value=os.environ.get('AUDIT_FIXTURE','')
        fixture=workspace_path(fixture_value,workspace) if fixture_value else None
        if fixture is not None and not fixture.is_file():
            raise ValueError('Fixture must be an existing regular workspace file')
        spec=importlib.util.spec_from_file_location('bundled_checker',ROOT/'vendor/check.py')
        checker=importlib.util.module_from_spec(spec)
        spec.loader.exec_module(checker)
        url=os.environ.get('AUDIT_URL','')
        # Validate before CLI argument parsing so flag-like values remain URLs.
        checker.validate_url(url)
        argv=[url,'--output-dir',str(output)]
        if fixture is not None: argv.extend(['--fixture',str(fixture)])
        code=checker.main(argv)
        if code: return code
        relative=output.relative_to(workspace).as_posix()
        mode='synthetic offline fixture' if fixture is not None else 'live public HTTP(S)'
        if os.environ.get('GITHUB_OUTPUT'):
            with open(os.environ['GITHUB_OUTPUT'],'a',encoding='utf-8') as stream:
                stream.write('report-json='+relative+'/report.json\nreport-html='+relative+'/report.html\ntransport='+mode+'\n')
        if os.environ.get('GITHUB_STEP_SUMMARY'):
            with open(os.environ['GITHUB_STEP_SUMMARY'],'a',encoding='utf-8') as stream:
                stream.write('## Search and AI discoverability observation\n\nTransport: **'+mode+'**. JSON and standalone HTML reports are available in the configured output directory.\n\nSuccessful execution does not establish indexing, ranking, AI retrieval or citations. Inspect the report and preserve its date and scope.\n')
        return 0
    except (ValueError,OSError,KeyError) as exc:
        print('Action failed: '+str(exc),file=sys.stderr)
        return 2

if __name__=='__main__': sys.exit(main())
