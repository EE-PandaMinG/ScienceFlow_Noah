# Resource Management ownership (V3-5)

This note freezes the source-of-truth boundaries introduced in Phase V3-5. It
is an implementation map, not a policy specification.

| Component | Owns | Must not own |
| --- | --- | --- |
| `ResourceObservationProjector` | normalization and typed resource facts | admission, release, kill, workspace writes |
| `ResourceRegistry` | job/process/resource identity | scientific-value evaluation |
| `QueueScheduler` | pending membership, recovery, heartbeat cadence | admission value or lease effects |
| `LeaseManager` | recovered/local lease identity and release mechanism | LLM calls or execution-value policy |
| `ResourceReviewMachine` | typed review transitions and replay | process signaling |
| `AdmissionProposalProjector` | read-only admission proposal projection | applying admission or lease actions |
| `ResourceEffectExecutor` | validated, allowlisted, idempotent effects | creating policy decisions |
| `LHRResourceObserver` | compatibility composition and legacy callbacks | direct resource effects or authoritative job storage |

The compatibility fields `_jobs`, `_queue_started`, `_last_heartbeat`, and
`_leased_gpu_ids` are views of component-owned collections. They remain only so
the legacy method surface can migrate incrementally. New code must use the
component interfaces.

The allowed execution chain is:

```text
probe -> projector -> facts -> mechanism/policy proposal
      -> Runtime validation -> effect executor -> domain event/projection
```

Resource effects require a `ResourceEffectCommand` with `validated=True` and a
non-empty idempotency key. Replaying the same key returns the prior result and
does not invoke the backend again. The legacy observer is guarded by an AST
fixture that rejects direct calls to release, queue timeout, shared grant, or
shared revoke methods.
