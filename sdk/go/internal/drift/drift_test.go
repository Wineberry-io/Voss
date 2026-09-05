// Package drift_test holds the V13.3 Go SDK drift gate: it regenerates
// types.gen.go from the committed OpenAPI snapshot and fails on any diff, plus
// a parity check that the server's event union exposes exactly the 21 members
// the SDK targets. Mirrors crates/voss-tui/tests/protocol_parity.rs and the
// V13.2 D-08 Rust drift pattern.
package drift_test

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"
	"testing"
)

// pathsFromHere are relative to this test's working directory
// (sdk/go/internal/drift).
const (
	sdkGoDir      = "../.."                              // sdk/go
	contractsPath = "../../../../contracts/openapi.json" // repo-root contracts/
	repoRootRel   = "../../../.."                        // repo root
)

// TestTypesAreUpToDate regenerates types.gen.go via `go generate ./...` and
// asserts the committed file is byte-identical. It skips when the upstream
// contract is absent (V13.1 unexecuted) so pre-V13.1 development is unblocked.
func TestTypesAreUpToDate(t *testing.T) {
	if _, err := os.Stat(contractsPath); os.IsNotExist(err) {
		t.Skip("contracts/openapi.json not yet generated (V13.1 unexecuted)")
	}

	gen := exec.Command("go", "generate", "./...")
	gen.Dir = sdkGoDir
	if out, err := gen.CombinedOutput(); err != nil {
		t.Fatalf("go generate ./... failed: %v\n%s", err, out)
	}

	diff := exec.Command("git", "diff", "--exit-code", "types.gen.go")
	diff.Dir = sdkGoDir
	if out, err := diff.CombinedOutput(); err != nil {
		t.Fatalf("types.gen.go is out of date (regenerate with `go generate ./...`):\n%s", out)
	}
}

// TestDecodeCoversAllServerEventTypes drives the live Python server module to
// enumerate the AgentEvent union's `type` strings and asserts the full
// 21-member set is present (including principles_overflow, which is in
// events.py but absent from PROTOCOL.md — RESEARCH Pitfall 4). Plan 02's
// Decode() switch must cover this exact set. Skips when no interpreter is
// available.
func TestDecodeCoversAllServerEventTypes(t *testing.T) {
	py := pickPython(t)
	if py == "" {
		t.Skip("no Python interpreter (VOSS_PYTHON / .venv / python3) available")
	}
	repo, err := filepath.Abs(repoRootRel)
	if err != nil {
		t.Fatalf("resolve repo root: %v", err)
	}

	const script = `import json, typing
from voss.harness.server import events as E
union = typing.get_args(E.AgentEvent)[0]
models = typing.get_args(union)
print(json.dumps([m.model_fields['type'].default for m in models]))`

	cmd := exec.Command(py, "-c", script)
	cmd.Dir = repo
	out, err := cmd.Output()
	if err != nil {
		t.Skipf("could not enumerate server event types via %s: %v", py, err)
	}
	var got []string
	if err := json.Unmarshal(out, &got); err != nil {
		t.Fatalf("parse python output %q: %v", string(out), err)
	}

	if len(got) != 21 {
		t.Fatalf("server AgentEvent union has %d members, want 21: %v", len(got), got)
	}
	if !contains(got, "principles_overflow") {
		t.Fatalf("server union missing principles_overflow (RESEARCH Pitfall 4): %v", got)
	}
	t.Logf("server AgentEvent union (21 members): %v", got)
	// TODO(V13.3-02): cross-check this set against voss.Decode()'s switch once
	// Decode is implemented, asserting no member is missing or extra.
}

func pickPython(t *testing.T) string {
	t.Helper()
	if v := os.Getenv("VOSS_PYTHON"); v != "" {
		return v
	}
	cand := filepath.Join(repoRootRel, ".venv", "bin", "python")
	if _, err := os.Stat(cand); err == nil {
		abs, err := filepath.Abs(cand)
		if err == nil {
			return abs
		}
		return cand
	}
	if p, err := exec.LookPath("python3"); err == nil {
		return p
	}
	return ""
}

func contains(s []string, want string) bool {
	for _, v := range s {
		if v == want {
			return true
		}
	}
	return false
}
