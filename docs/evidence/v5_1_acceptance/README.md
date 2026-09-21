# V5.1 formal w2-1h acceptance evidence

This directory records the immutable three-case run started at
`2026-08-30T06:15:52Z` on the remote NVIDIA L20X host. All three cases ran in
parallel against the shared Qwen3.6-27B vLLM service. The result is mixed and
must not be reported as a full V5.1 pass.

## Frozen inputs

- ScienceFlow: `8f6e0576bb56020a04352054c81f91d4cd4bbe64`
- InquiryCraft: `502b8a48ea42aa00d6e8855f823036edba96daee`
- `sci-modeling-bench`: `0.10.0`
- Circle CPU affinity: `0-15`
- Nomad CPU affinity: `16-31`
- TFBind8 CPU affinity: `32-47`

The manifests and live process affinity were both checked. The three compute
domains were disjoint; only non-computing `tee` log writers retained the host
default affinity.

## Verdict

| Case | Runtime result | Acceptance result | Evidence |
|---|---|---|---|
| Circle Packing | exit 0; 4 captured stages; bounded merge timeout with deterministic fallback | **PASS**: `success`, 3/3 valid finals, best `radii_sum=2.628490185392066` | 26 finite non-negative circles per final, evaluator accepted, SHA verified |
| Nomad2018 Deep | exit 0; W00 captured 2 stages, W01 stopped with no candidate; bounded merge timeout with fallback | **FAIL**: `insufficient_finals`, 2/3, `requirement_met=false` | both CSVs have 240 legal rows and distinct SHA, but both metrics are risk-flagged `same_validation_meta_fit`; final reevaluation has no primary metric |
| TFBind8 | exit 0; one authoritative stage per worker; best-stage finalization | **PASS**: selected W01 S01, `best_k_mean=0.9738011717796325` | regret `0.025112354755401634`, global NDCG `0.9132261742623502`, 32 unique legal 8-mers, query ledger 1/10 for each distinct worker batch |

The scientific score thresholds are regression warnings. Artifact legality,
authoritative evaluation/finalization, and the required final count are hard
gates. Nomad therefore fails even though its launcher exited successfully.

## Model/service behavior versus framework behavior

Model or shared vLLM behavior observed in this run:

- Circle W00 and Nomad W01 produced no stage candidate; the latter ended as
  `text_only_stop_no_candidate` after exploratory tool use.
- First provider attempts failed intermittently under six-worker plus merge
  concurrency, then recovered on retry.
- Nomad produced only two distinct artifacts and used validation-set-fitted
  ensemble weights, so its recorded score is not a comparable holdout result.
- The shared vLLM generated one unusually long 12,618-token Nomad response.

Framework behavior established by the run:

- CPU affinity remained disjoint at the launcher, parallel coordinator, worker,
  and child-job levels.
- Artifact -> evaluator -> gate -> stage -> finalization wiring executed for all
  three task profiles.
- Circle and Nomad both entered a real reserved merge session. Both returned
  `agent_status=timed_out_fallback` with an empty `agent_error`, rather than the
  previous generic framework failure.
- `session.failed=0`; the previous
  `aclose(): asynchronous generator is already running` race did not recur.
- The framework correctly preserved Nomad's `insufficient_finals` result instead
  of conflating process exit 0 with acceptance success.
- One framework gap remains: ScienceFlow projected a deadline-derived
  `request_timeout`, but the OpenAI/httpx timeout is a transport inactivity
  timeout, not a total streaming wall-clock cap. A continuously streaming Nomad
  call therefore lasted `705.2801709361374` seconds. This needs an outer runtime
  wall-clock guard before another formal acceptance run.

## Files

- `evidence_summary.json`: per-worker stages, provider usage/cache, runtime
  failures, state, and final manifests.
- `artifact_audit.json`: machine checks for CPU manifests, artifact shape/SHA,
  TF query accounting, process residue, and forbidden runtime errors.
- `results/`: exact Circle/Nomad global-merge manifests and TF best-stage
  manifest.
- `artifacts/`: selected immutable final artifacts.
- `logs/nomad_w00_provider_calls.jsonl`: source record for the 705-second call
  and Nomad merge session.
- `runtime_manifests/`: the exact formal manifests.
- `vllm_metrics_before.prom`, `vllm_metrics.after.prom`, and
  `vllm_metrics_delta.json`: shared-service boundary snapshots. The delta is not
  treated as task-exclusive usage; task-exclusive usage comes from provider
  audit logs.

`SHA256SUMS` covers every evidence file except itself.

## Release verification

The frozen ScienceFlow checkout built both distributions successfully. A clean
temporary virtual environment installed the wheel with `--no-deps`; importing
from `/tmp` resolved `scienceflow` from site-packages and reported version
`0.2.0`.

- wheel SHA-256: `89e9b02ee88528cf4b630941f101022df180f68e6a4b822aa59d39ea1c6fc59e`
- sdist SHA-256: `ff62633d04dc74a28851ac5eb1709690d77e9d244bdef4d69d829bcbfa1b4b36`
