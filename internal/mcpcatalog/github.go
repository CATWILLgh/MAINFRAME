package mcpcatalog

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"path"
	"time"
)

const (
	GitHubAPIBaseURL       = "https://api.github.com"
	GitHubAPIVersion       = "2022-11-28"
	maxGitHubResponseBytes = 64 << 10
)

type RepositoryStats struct {
	Stars     int
	FetchedAt time.Time
}

type StatsSource interface {
	Stats(context.Context, Repository) (RepositoryStats, error)
}

type GitHubStatsClient struct {
	httpClient *http.Client
	baseURL    *url.URL
	now        func() time.Time
}

func NewGitHubStatsClient(
	httpClient *http.Client,
	baseURL string,
	now func() time.Time,
) (GitHubStatsClient, error) {
	parsed, err := url.ParseRequestURI(baseURL)
	if err != nil || parsed.Host == "" || !safeStatsBaseURL(parsed) {
		return GitHubStatsClient{}, fmt.Errorf("invalid GitHub API base URL")
	}
	if httpClient == nil || now == nil {
		return GitHubStatsClient{}, fmt.Errorf("GitHub stats dependencies must not be nil")
	}
	return GitHubStatsClient{httpClient: httpClient, baseURL: parsed, now: now}, nil
}

func safeStatsBaseURL(parsed *url.URL) bool {
	if parsed.Scheme == "https" {
		return true
	}
	if parsed.Scheme != "http" {
		return false
	}
	host := parsed.Hostname()
	if host == "localhost" {
		return true
	}
	address := net.ParseIP(host)
	return address != nil && address.IsLoopback()
}

func (client GitHubStatsClient) Stats(
	context context.Context,
	repository Repository,
) (RepositoryStats, error) {
	if !repositorySegmentPattern.MatchString(repository.Owner) ||
		!repositorySegmentPattern.MatchString(repository.Name) {
		return RepositoryStats{}, fmt.Errorf("repository identity is invalid")
	}
	endpoint := *client.baseURL
	endpoint.Path = path.Join(endpoint.Path, "repos", repository.Owner, repository.Name)
	request, err := http.NewRequestWithContext(context, http.MethodGet, endpoint.String(), nil)
	if err != nil {
		return RepositoryStats{}, fmt.Errorf("create GitHub request: %w", err)
	}
	request.Header.Set("Accept", "application/vnd.github+json")
	request.Header.Set("X-GitHub-Api-Version", GitHubAPIVersion)
	request.Header.Set("User-Agent", "mainframe-installer")
	response, err := client.httpClient.Do(request)
	if err != nil {
		return RepositoryStats{}, fmt.Errorf("request GitHub repository: %w", err)
	}
	defer response.Body.Close()
	if response.StatusCode != http.StatusOK {
		return RepositoryStats{}, fmt.Errorf("GitHub repository returned HTTP %d", response.StatusCode)
	}
	payload, err := io.ReadAll(io.LimitReader(response.Body, maxGitHubResponseBytes+1))
	if err != nil {
		return RepositoryStats{}, fmt.Errorf("read GitHub response: %w", err)
	}
	if len(payload) > maxGitHubResponseBytes {
		return RepositoryStats{}, fmt.Errorf("GitHub response exceeds %d bytes", maxGitHubResponseBytes)
	}
	var result struct {
		Stars *int `json:"stargazers_count"`
	}
	if err := json.Unmarshal(payload, &result); err != nil {
		return RepositoryStats{}, fmt.Errorf("decode GitHub response: %w", err)
	}
	if result.Stars == nil || *result.Stars < 0 {
		return RepositoryStats{}, fmt.Errorf("GitHub star count is missing or negative")
	}
	return RepositoryStats{Stars: *result.Stars, FetchedAt: client.now()}, nil
}
