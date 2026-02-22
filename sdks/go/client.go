package condensate

import (
	"bytes"
	"encoding/json"
	"fmt"
	"net/http"
	"time"
)

type Client struct {
	BaseURL    string
	APIKey     string
	HTTPClient *http.Client
}

func NewClient(baseURL, apiKey string) *Client {
	return &Client{
		BaseURL: baseURL,
		APIKey:  apiKey,
		HTTPClient: &http.Client{
			Timeout: time.Minute,
		},
	}
}

// EpisodicItem corresponds to src/db/schemas.py EpisodicItemCreate
type EpisodicItem struct {
	ProjectID  string                 `json:"project_id"`
	Source     string                 `json:"source"` // chatgpt_export | api | tool | note
	Text       string                 `json:"text"`
	OccurredAt string                 `json:"occurred_at,omitempty"` // ISO-8601
	Metadata   map[string]interface{} `json:"metadata,omitempty"`
}

type Assertion struct {
	ID          string   `json:"id"`
	ProjectID   string   `json:"project_id"`
	SubjectText string   `json:"subject_text"`
	Predicate   string   `json:"predicate"`
	ObjectText  string   `json:"object_text"`
	Confidence  float64  `json:"confidence"`
	Status      string   `json:"status"`
	Formatted   string   `json:"formatted_statement,omitempty"` // For convenience
}

func (c *Client) AddItem(item EpisodicItem) error {
	data, err := json.Marshal(item)
	if err != nil {
		return err
	}

	// V2 Endpoint: /api/admin/memories (Maps to EpisodicItems)
	req, err := http.NewRequest("POST", c.BaseURL+"/api/admin/memories", bytes.NewBuffer(data))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/json")
	if c.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.APIKey)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return fmt.Errorf("failed to ingest item: status %d", resp.StatusCode)
	}

	return nil
}

func (c *Client) QueryAssertions(query string) ([]Assertion, error) {
	// V2 Endpoint for retrieving "Learnings" (now Assertions) has changed.
	// Current admin.py has GET /learnings which returns all.
	// For search/query, likely need a new endpoint or filter.
	// Supporting generic GET /learnings for now.
	
	req, err := http.NewRequest("GET", c.BaseURL+"/api/admin/learnings", nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	if c.APIKey != "" {
		req.Header.Set("Authorization", "Bearer "+c.APIKey)
	}

	resp, err := c.HTTPClient.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		return nil, fmt.Errorf("failed to query assertions: status %d", resp.StatusCode)
	}

	// The admin.py GET /learnings returns a list of dicts that need mapping
	// Response format in admin.py: {id, statement, confidence...}
	// We might need an adapter struct if the JSON keys differ significantly
	var rawAssertions []map[string]interface{}
	if err := json.NewDecoder(resp.Body).Decode(&rawAssertions); err != nil {
		return nil, err
	}
	
	var assertions []Assertion
	for _, raw := range rawAssertions {
		a := Assertion{
			ID: raw["id"].(string),
			// Mapping 'statement' to Formatted for now, as individual fields strictly might not be in the 'view'
			Formatted: raw["statement"].(string), 
			Confidence: raw["confidence"].(float64),
			Status: raw["status"].(string),
		}
		assertions = append(assertions, a)
	}
	return assertions, nil
}

