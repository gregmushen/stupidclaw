import sys
from pathlib import Path

# Add scripts/ to sys.path so `from shared import ...` works in tests
sys.path.insert(0, str(Path(__file__).parent / "scripts"))
