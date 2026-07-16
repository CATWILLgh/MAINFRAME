package mcpcatalog

import (
	"context"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

func TestGitHubStatsReadsCurrentStarsWithTimestamp(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		if request.URL.Path != "/repos/upstash/context7" {
			t.Fatalf("path = %q", request.URL.Path)
		}
		writer.Header().Set("Content-Type", "application/json")
		_, _ = writer.Write([]byte(`{"stargazers_count": 4242}`))
	}))
	defer server.Close()
	wantTime := time.Date(2026, 7, 17, 12, 0, 0, 0, time.UTC)
	client, err := NewGitHubStatsClient(server.Client(), server.URL, func() time.Time { return wantTime })
	if err != nil {
		t.Fatalf("create client: %v", err)
	}
	stats, err := client.Stats(context.Background(), Repository{Owner: "upstash", Name: "context7"})
	if err != nil {
		t.Fatalf("load stats: %v", err)
	}
	if stats.Stars != 4242 || !stats.FetchedAt.Equal(wantTime) {
		t.Fatalf("stats = %#v", stats)
	}
}

func TestGitHubStatsRejectsFailuresWithoutReturningMetadata(t *testing.T) {
	tests := map[string]http.HandlerFunc{
		"rate limit": func(writer http.ResponseWriter, _ *http.Request) {
			writer.WriteHeader(http.StatusForbidden)
		},
		"malformed": func(writer http.ResponseWriter, _ *http.Request) {
			_, _ = writer.Write([]byte(`{"stargazers_count":"many"}`))
		},
		"missing count": func(writer http.ResponseWriter, _ *http.Request) {
			_, _ = writer.Write([]byte(`{"name":"context7"}`))
		},
		"oversized": func(writer http.ResponseWriter, _ *http.Request) {
			_, _ = writer.Write([]byte(`{"stargazers_count":1,"padding":"` + strings.Repeat("x", 70<<10) + `"}`))
		},
	}
	for name, handler := range tests {
		t.Run(name, func(t *testing.T) {
			server := httptest.NewServer(handler)
			defer server.Close()
			client, err := NewGitHubStatsClient(server.Client(), server.URL, time.Now)
			if err != nil {
				t.Fatalf("create client: %v", err)
			}
			if stats, err := client.Stats(
				context.Background(), Repository{Owner: "upstash", Name: "context7"},
			); err == nil || stats != (RepositoryStats{}) {
				t.Fatalf("stats = %#v, error = %v", stats, err)
			}
		})
	}
}

func TestGitHubStatsHonorsRequestCancellation(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(writer http.ResponseWriter, request *http.Request) {
		<-request.Context().Done()
	}))
	defer server.Close()
	client, err := NewGitHubStatsClient(server.Client(), server.URL, time.Now)
	if err != nil {
		t.Fatalf("create client: %v", err)
	}
	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Millisecond)
	defer cancel()
	if _, err := client.Stats(ctx, Repository{Owner: "upstash", Name: "context7"}); err == nil {
		t.Fatal("request cancellation was ignored")
	}
}

func TestGitHubStatsRejectsNonLocalPlainHTTPBaseURL(t *testing.T) {
	if _, err := NewGitHubStatsClient(
		&http.Client{}, "http://example.com", time.Now,
	); err == nil {
		t.Fatal("non-local plaintext GitHub base URL was accepted")
	}
}
