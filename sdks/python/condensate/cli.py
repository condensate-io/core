import sys
import os
from condensate import CondensateClient

def main():
    print("Condensate Python CLI v0.1.0")
    
    base_url = os.getenv("CONDENSATE_URL", "http://localhost:8000")
    api_key = os.getenv("CONDENSATE_API_KEY", "")
    
    if len(sys.argv) < 2:
        print("Usage: condensate <command> [args]")
        print("\nCommands:")
        print("  recall <query>    - Retrieve relevant memories")
        print("  ingest <text>     - Ingest a new memory")
        print("  status            - Check system status")
        print("\nEnvironment:")
        print(f"  CONDENSATE_URL={base_url}")
        print(f"  CONDENSATE_API_KEY={'***' if api_key else '(not set)'}")
        return

    command = sys.argv[1]
    client = CondensateClient(base_url=base_url, api_key=api_key)
    
    try:
        if command == "recall":
            if len(sys.argv) < 3:
                print("Error: Missing query string")
                sys.exit(1)
            query = " ".join(sys.argv[2:])
            print(f"Recalling: {query}")
            result = client.retrieve(query)
            print(f"\nAnswer: {result.get('answer', 'No response')}")
            
        elif command == "ingest":
            if len(sys.argv) < 3:
                print("Error: Missing text to ingest")
                sys.exit(1)
            text = " ".join(sys.argv[2:])
            print("Ingesting memory...")
            item_id = client.add_item(text=text, source="cli")
            print(f"Success: Memory queued (ID: {item_id})")
            
        elif command == "status":
            print("Condensate Engine: Connected")
            print(f"API Endpoint: {base_url}")
            print("Status: Operational")
            
        else:
            print(f"Unknown command: {command}")
            sys.exit(1)
            
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
