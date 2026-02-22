
import sys
import os

# Add src to path
sys.path.append(os.getcwd())

print("Testing imports...")

try:
    from src.db.models import Project, EpisodicItem, Entity, Assertion, Event, OntologyNode, Relation, Policy, ApiKey
    print("✅ src.db.models imported")
except Exception as e:
    print(f"❌ src.db.models failed: {e}")

try:
    from src.llm.schemas import ExtractionBundle
    print("✅ src.llm.schemas imported")
except Exception as e:
    print(f"❌ src.llm.schemas failed: {e}")

try:
    from src.agents.ingress import IngressAgent
    print("✅ src.agents.ingress imported")
except Exception as e:
    print(f"❌ src.agents.ingress failed: {e}")

try:
    from src.server.admin import router
    print("✅ src.server.admin imported")
except Exception as e:
    print(f"❌ src.server.admin failed: {e}")

try:
    from src.server.mcp import mcp_router
    print("✅ src.server.mcp imported")
except Exception as e:
    print(f"❌ src.server.mcp failed: {e}")

try:
    from src.engine.scheduler import start_scheduler
    print("✅ src.engine.scheduler imported")
except Exception as e:
    print(f"❌ src.engine.scheduler failed: {e}")

print("Import test complete.")
