package condensate

import (
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestAddItem_Success(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost || r.URL.Path != "/api/admin/memories" {
			http.NotFound(w, r)
			return
		}
		body, _ := io.ReadAll(r.Body)
		if !strings.Contains(string(body), `"project_id":"p1"`) {
			t.Errorf("request body %s", body)
		}
		w.WriteHeader(http.StatusOK)
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL, "")
	err := c.AddItem(EpisodicItem{ProjectID: "p1", Source: "note", Text: "hello"})
	if err != nil {
		t.Fatal(err)
	}
}

func TestAddItem_Failure(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "bad request", http.StatusBadRequest)
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL, "")
	err := c.AddItem(EpisodicItem{ProjectID: "p1", Source: "note", Text: "hello"})
	if err == nil {
		t.Fatal("expected error for non-2xx response")
	}
	if !strings.Contains(err.Error(), "400") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestQueryAssertions_JSONMapping(t *testing.T) {
	payload := []map[string]interface{}{
		{
			"id":            "a1",
			"project_id":    "proj-1",
			"subject_text":  "alice",
			"predicate":     "knows",
			"object_text":   "bob",
			"confidence":    0.91,
			"status":        "active",
			"statement":     "alice knows bob",
		},
		{
			"id":                     "a2",
			"formatted_statement":   "full sentence",
			"confidence":             0.5,
			"status":                 "pending",
		},
	}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet || r.URL.Path != "/api/admin/learnings" {
			http.NotFound(w, r)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if err := json.NewEncoder(w).Encode(payload); err != nil {
			t.Errorf("encode: %v", err)
		}
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL, "")
	got, err := c.QueryAssertions("ignored-for-now")
	if err != nil {
		t.Fatal(err)
	}
	if len(got) != 2 {
		t.Fatalf("got %d assertions", len(got))
	}
	first := got[0]
	if first.ID != "a1" || first.ProjectID != "proj-1" || first.SubjectText != "alice" ||
		first.Predicate != "knows" || first.ObjectText != "bob" ||
		first.Confidence != 0.91 || first.Status != "active" || first.Formatted != "alice knows bob" {
		t.Fatalf("first assertion: %+v", first)
	}
	second := got[1]
	if second.ID != "a2" || second.Formatted != "full sentence" ||
		second.Confidence != 0.5 || second.Status != "pending" {
		t.Fatalf("second assertion: %+v", second)
	}
}

func TestQueryAssertions_FailureStatus(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Error(w, "internal", http.StatusInternalServerError)
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL, "")
	_, err := c.QueryAssertions("")
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "500") {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestAuthorizationHeaderWhenAPIKeySet(t *testing.T) {
	paths := []string{}
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		paths = append(paths, r.URL.Path)
		if got := r.Header.Get("Authorization"); got != "Bearer secret-key" {
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		if r.URL.Path == "/api/admin/memories" {
			w.WriteHeader(http.StatusCreated)
			return
		}
		w.Header().Set("Content-Type", "application/json")
		if _, err := w.Write([]byte(`[]`)); err != nil {
			t.Errorf("write: %v", err)
		}
	}))
	t.Cleanup(srv.Close)

	c := NewClient(srv.URL, "secret-key")
	if err := c.AddItem(EpisodicItem{ProjectID: "p", Source: "note", Text: "x"}); err != nil {
		t.Fatal(err)
	}
	if _, err := c.QueryAssertions(""); err != nil {
		t.Fatal(err)
	}
	if len(paths) != 2 || paths[0] != "/api/admin/memories" || paths[1] != "/api/admin/learnings" {
		t.Fatalf("paths: %v", paths)
	}
}
