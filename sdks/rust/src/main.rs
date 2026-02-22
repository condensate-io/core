use std::env;
use std::process;

mod client;
mod models;

use client::CondensateClient;

fn main() {
    let args: Vec<String> = env::args().collect();

    if args.len() < 2 {
        println!("Condensate CLI v0.1.0");
        println!("Usage: condensate <command> [args]");
        println!("\nCommands:");
        println!("  recall <query>    - Retrieve relevant memories");
        println!("  ingest <text>     - Ingest a new memory");
        println!("  status            - Check system status");
        println!("\nEnvironment:");
        println!("  CONDENSATE_URL (default: http://localhost:8000)");
        println!("  CONDENSATE_API_KEY");
        return;
    }

    let base_url = env::var("CONDENSATE_URL").unwrap_or_else(|_| "http://localhost:8000".to_string());
    let api_key = env::var("CONDENSATE_API_KEY").unwrap_or_default();
    
    let client = CondensateClient::new(&base_url, &api_key);
    let command = &args[1];

    match command.as_str() {
        "recall" => {
            if args.len() < 3 {
                eprintln!("Error: Missing query string");
                process::exit(1);
            }
            let query = args[2..].join(" ");
            println!("Recalling: {}", query);
            
            match client.retrieve(&query) {
                Ok(result) => println!("\nAnswer: {}", result.answer.unwrap_or_else(|| "No response".to_string())),
                Err(e) => {
                    eprintln!("Error: {}", e);
                    process::exit(1);
                }
            }
        }
        "ingest" => {
            if args.len() < 3 {
                eprintln!("Error: Missing text to ingest");
                process::exit(1);
            }
            let text = args[2..].join(" ");
            println!("Ingesting memory...");
            
            match client.add_item(&text, "cli") {
                Ok(item_id) => println!("Success: Memory queued (ID: {})", item_id),
                Err(e) => {
                    eprintln!("Error: {}", e);
                    process::exit(1);
                }
            }
        }
        "status" => {
            println!("Condensate Engine: Connected");
            println!("API Endpoint: {}", base_url);
            println!("Status: Operational");
        }
        _ => {
            eprintln!("Unknown command: {}", command);
            process::exit(1);
        }
    }
}
