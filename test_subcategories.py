import config
from rag_engine import get_subcategories

# Mock config path if needed, but it should be correct
print(f"Database path: {config.DATABASE_PATH}")

subcats = get_subcategories("1. О Ферсол")
print("Subcategories found:")
for s in subcats:
    print(f"- {s}")

if not subcats:
    print("No subcategories found! Check regex or file structure.")
