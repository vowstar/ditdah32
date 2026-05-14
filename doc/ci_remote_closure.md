# Remote CI Closure Procedure

The CI gap closes when the hosted `verify-ci-smoke` profile has a successful
run with uploaded artifacts for the current local git HEAD.

## Preconditions

- Pushed to GitHub with `.github/workflows/verification.yml`.
- GitHub Actions enabled with `permissions: { contents: read, actions: read }`.
- `gh` CLI authenticated (`gh auth status`), or `GH_TOKEN` set, or the
  workflow is reachable through `make audit-ci-remote
  CI_REMOTE_ARGS="--repo owner/repo"`.

## Closure

```bash
git push origin HEAD                                 # push the commit
make ci-remote-dispatch CI_REMOTE_DISPATCH_ARGS="--wait"  # trigger smoke
make audit-ci-remote                                 # collect evidence
make audit-gaps                                      # require expected_head_sha matches HEAD
make audit-completion                                # final checklist
```

`make audit-ci-remote` records the run id, profile job, and artifact list under
`result/verification/ci_remote_evidence.json`. The audit fails if
`expected_head_sha` differs from the current local git HEAD or if any required
profile job is missing.

## Notes

- The fast `verify-ci-smoke` profile intentionally avoids the Nix RTL toolchain
  so push and PR CI stays usable. `full`, `signoff`, and `spike-matrix`
  profiles are supporting evidence, not required for closure.
- The hosted `manual` workflow dispatch may be used for any profile when a
  heavier remote run is needed.
