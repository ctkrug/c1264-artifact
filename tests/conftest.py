"""Put ``src/`` on the import path so the tests run from a bare checkout.

No installation step is required to reproduce this artifact; ``pip install -e .``
would work but is deliberately not necessary, since a referee should be able to
clone and run.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
