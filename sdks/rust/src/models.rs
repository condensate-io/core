use serde::{Deserialize, Serialize};
use std::collections::HashMap;

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct EpisodicItem {
    pub source: String,
    pub text: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub metadata: Option<HashMap<String, serde_json::Value>>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct RetrieveRequest {
    pub query: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub skip_llm: Option<bool>,
}

#[derive(Serialize, Deserialize, Debug, Clone)]
pub struct RetrieveResponse {
    pub answer: Option<String>,
    pub context: Vec<serde_json::Value>,
}
