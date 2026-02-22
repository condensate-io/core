import asyncio
import json
import uuid
from typing import List
from pydantic import BaseModel

# Mocking the required parts since we just want to test the parsing logic
class EpisodicItem:
    def __init__(self, id, text, metadata_=None):
        self.id = id
        self.text = text
        self.metadata_ = metadata_

class ExtractionBundle(BaseModel):
    entities: List = []
    assertions: List = []
    events: List = []
    policies: List = []

async def test_json_parsing_robustness():
    print("Testing JSON parsing robustness in MemoryExtractor logic...")
    
    # Mock content that caused issues or might cause issues
    problematic_contents = [
        "",                     # Empty string
        "   ",                  # Whitespace only
        "```json\n{\"entities\": []}\n```", # Markdown block
        "{\"entities\": []} junk", # Trailng junk
        "\n\n{\"entities\": []}",   # Leading whitespace
    ]
    
    for content in problematic_contents:
        print(f"Testing content: {repr(content)}")
        
        # This mirrors the logic I added to extractor.py
        if not content or not content.strip():
            print("  Result: Correctly handled empty/whitespace content.")
            continue
            
        try:
            cleaned_content = content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content.removeprefix("```json").removesuffix("```").strip()
            elif cleaned_content.startswith("```"):
                 cleaned_content = cleaned_content.removeprefix("```").removesuffix("```").strip()
            
            # Simple heuristic for trailing junk if first char is {
            if cleaned_content.startswith("{"):
                # Basic attempt to find the last }
                last_brace = cleaned_content.rfind("}")
                if last_brace != -1:
                    cleaned_content = cleaned_content[:last_brace+1]

            data = json.loads(cleaned_content)
            print(f"  Result: Successfully parsed: {data}")
        except Exception as e:
            print(f"  Result: FAILED to parse: {e}")

if __name__ == "__main__":
    asyncio.run(test_json_parsing_robustness())
