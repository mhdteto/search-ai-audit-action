# Offline HTTP 404 example

From the repository root, run the wrapper with the fictional response fixture:

```sh
GITHUB_WORKSPACE="$PWD" \
  AUDIT_URL=https://example.org/missing \
  AUDIT_FIXTURE=examples/http-404.json \
  AUDIT_OUTPUT_DIR=reports/http-404 \
  python3 run.py
```

The wrapper exits with code 0 after writing the reports. In
`reports/http-404/report.json`, `page.status` is 404 and `transport` is
`synthetic offline fixture`. Open `reports/http-404/report.html` to see the
same HTTP status in the report. Exit code 0 confirms report generation. The
fictional page still returned 404. The fixture makes no target network requests.
