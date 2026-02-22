use crate::models::{EpisodicItem, RetrieveRequest, RetrieveResponse};
use reqwest::blocking::Client;
use std::time::Duration;
use thiserror::Error;

#[derive(Error, Debug)]
pub enum CondensateError {
    #[error("API Request Failed: {0}")]
    RequestError(#[from] reqwest::Error),
    #[error("Serialization Error: {0}")]
    SerializationError(#[from] serde_json::Error),
}

pub struct CondensateClient {
    base_url: String,
    client: Client,
}

impl CondensateClient {
    pub fn new(base_url: &str, api_key: &str) -> Self {
        let mut headers = reqwest::header::HeaderMap::new();
        if !api_key.is_empty() {
            let mut auth_value = reqwest::header::HeaderValue::from_str(&format!("Bearer {}", api_key))
                .expect("Invalid header value");
            auth_value.set_sensitive(true);
            headers.insert(reqwest::header::AUTHORIZATION, auth_value);
        }

        let client = Client::builder()
            .default_headers(headers)
            .timeout(Duration::from_secs(30))
            .build()
            .unwrap_or_else(|_| Client::new());

        Self {
            base_url: base_url.trim_end_matches('/').to_string(),
            client,
        }
    }

    /// Add an item using simple text and source
    pub fn add_item(&self, text: &str, source: &str) -> Result<String, CondensateError> {
        let item = EpisodicItem {
            text: text.to_string(),
            source: source.to_string(),
            metadata: None,
        };
        self.add_item_full(&item)
    }

    /// Add an item using full EpisodicItem struct
    pub fn add_item_full(&self, item: &EpisodicItem) -> Result<String, CondensateError> {
        let url = format!("{}/api/v1/episodic", self.base_url);
        let resp = self.client.post(&url)
            .json(item)
            .send()?;
        
        resp.error_for_status_ref()?;
        
        let json: serde_json::Value = resp.json()?;
        Ok(json["id"].as_str().unwrap_or("").to_string())
    }

    /// Retrieve using simple query string
    pub fn retrieve(&self, query: &str) -> Result<RetrieveResponse, CondensateError> {
        let req = RetrieveRequest {
            query: query.to_string(),
            skip_llm: Some(false),
        };
        self.retrieve_full(&req)
    }

    /// Retrieve using full RetrieveRequest struct
    pub fn retrieve_full(&self, req: &RetrieveRequest) -> Result<RetrieveResponse, CondensateError> {
        let url = format!("{}/api/v1/memory/retrieve", self.base_url);
        let resp = self.client.post(&url)
            .json(req)
            .send()?;
        
        resp.error_for_status_ref()?;
        
        let result: RetrieveResponse = resp.json()?;
        Ok(result)
    }
}
