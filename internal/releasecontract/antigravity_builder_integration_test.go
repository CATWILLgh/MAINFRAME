package releasecontract_test

import (
	"os/exec"
	"path/filepath"
	"testing"

	"github.com/CATWILLgh/MAINFRAME/internal/domain"
	"github.com/CATWILLgh/MAINFRAME/internal/releasecontract"
)

func TestPythonReleaseBuilderAndGoLoaderAgreeOnAntigravityMCP(t *testing.T) {
	repository, err := filepath.Abs("../..")
	if err != nil {
		t.Fatal(err)
	}
	output := filepath.Join(t.TempDir(), "release")
	command := exec.Command(
		"python3",
		filepath.Join(repository, "tools/build_release.py"),
		"--root", repository,
		"--output", output,
		"--release-id", "antigravity-cross-runtime",
	)
	command.Dir = repository
	if combined, err := command.CombinedOutput(); err != nil {
		t.Fatalf("build Python release: %v\n%s", err, combined)
	}

	release, err := releasecontract.Load(output)
	if err != nil {
		t.Fatalf("load Python release in Go: %v", err)
	}
	for _, projection := range release.MCPProjections {
		if projection.ID != "antigravity-2.mcp.context7" {
			continue
		}
		if projection.ComponentID != domain.ComponentAntigravity2 ||
			projection.Codec != releasecontract.MCPProjectionAntigravityGlobalHTTP ||
			projection.Target != (domain.Location{
				Root: domain.RootAntigravityConfig, Path: "mcp_config.json",
			}) || projection.MapPointer != "/mcpServers" ||
			projection.RegistryTarget != (domain.Location{
				Root: domain.RootAntigravityData, Path: "mainframe/mcp-ownership.json",
			}) || projection.DesiredEntry !=
			`{"serverUrl":"https://mcp.context7.com/mcp"}` {
			t.Fatalf("cross-runtime projection = %#v", projection)
		}
		return
	}
	t.Fatal("Python release omitted Antigravity MCP projection")
}
