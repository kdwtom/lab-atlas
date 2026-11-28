# Search performance — 2026-11-23

The final production build was measured in headless Microsoft Edge
`158.0.4370.33` on this Windows desktop, served by Vite preview on localhost.
The run finished at `2026-11-23T10:49:08Z` (November 23 locally).
See [raw observations](performance-results.json) and
[correctness checks](browser-checks.json). This is not a phone measurement.

## Results

| Measurement | Observed value |
|---|---:|
| Dataset | 852 labs / 17,712 papers |
| Indexed records, including translated fallback records | 226,535 |
| Cold index construction | 2,809.3 ms |
| Navigation to available search input | 4,042 ms |
| Largest per-query p95 across 50 cases | 13.3 ms |
| Median of the 50 per-query p95 values | 2.6 ms |
| Heap sampled after Atlas loaded, before indexing | 59.91 MiB |
| Heap sampled after indexing | 138.42 MiB |
| Heap sampled after the query benchmark | 148.12 MiB |
| Six JSON responses: encoded bodies | 3,661,362 bytes |
| Six JSON responses: decoded bodies | 32,850,973 bytes |

Each query receives five warmups and 30 timed executions. The reported p95 is
the 29th sorted sample. The largest p95 belongs to benchmark case 01. Timing
includes parsing, filtering, matching, evidence and ranking; the cached index
is acquired before each timed query. These desktop observations meet the
plan's sub-100 ms post-index query target on this machine only.

Resource Timing reports gzip-compressed localhost responses; decoded sizes
agree with the files on disk. This does not measure GitHub Pages or a mobile
network. Heap samples include application data, React and engine allocations;
garbage collection is not controlled, so their difference is not a precise
retained-index size. Cold indexing remains a main-thread startup cost. A prior
run measured 2,036.5 ms, illustrating variability rather than a startup guarantee.

## Input updates and measured changes

The script also measures a Playwright `fill`, waiting for the corresponding URL
query update and reading the browser clock again. These values include automation
and React update overhead. They are a coarse interaction proxy, not a measurement
of first painted results, single-key latency or real IME responsiveness.

| Query | Final observed input/update time |
|---|---:|
| `machine learning` | 229.5 ms |
| `기계 학습` | 79.3 ms |
| `RNA` | 141.2 ms |
| `zxqvnomatch913` | 62.8 ms |

Three changes address observed costs without changing retrieval:

- Exact identity candidates use a name index instead of scanning every record
  for every query. The index remains cached per Atlas instance; query and filter
  changes do not rebuild it.
- The explorer initially renders 50 rows and adds 50 per button press. A prior
  unpaged run measured 511.6 ms for the same `machine learning` update proxy;
  the first paged run measured 271.4 ms. This is a directional observation from separate
  runs, not a controlled speedup claim. Sorting applies to the complete result
  set before slicing. Browser assertions expand every page and verify all IDs
  exactly once in engine order. Shortlist results similarly load in groups of 12.
- Matching now reuses the union of records already found through the index,
  instead of scanning every record again for each candidate lab. The saved
  [run before this change](performance-before-record-reuse.json) had four queries
  above 100 ms p95, with a maximum of 112.9 ms. The final run's maximum is 13.3 ms.
  All 50 corpus cases were also compared against the retained full-record-scan
  implementation, with identical IDs, scores, evidence and cautions. Exact names,
  scattered coverage and additional-paper contributions are preserved. This is
  an observed desktop improvement, not a guarantee for other devices.

No debounce or worker was introduced. All result IDs and explanations remain
available. The full papers dataset is still eagerly loaded; compact export and
lazy detail loading remain separately scoped work.

## Reproduce and remaining validation

From `web`, build and serve in one terminal:

```powershell
npm.cmd run build
npm.cmd run preview -- --host 127.0.0.1 --port 4173
```

Then run in another terminal, without concurrent builds or tests:

```powershell
npm.cmd run perf:search
```

`BASE_URL` and `BROWSER_CHANNEL` can override the default preview address and
installed Edge channel. Diagnostics are opt-in via `searchDebug=1` and only
installed on localhost. The raw report is replaced on each measurement run.

The user requested automated checks only for phone/IME validation. The synthetic
composition test and mobile viewport assertions pass, but actual Korean IME,
phone performance, CPU/network throttling and paint-level typing latency remain
unverified. T12's physical-device gate therefore remains open.
