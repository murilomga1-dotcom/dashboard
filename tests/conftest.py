import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))


@pytest.fixture(autouse=True)
def pasta_dados_temporaria(tmp_path, monkeypatch):
    """Cada teste usa uma pasta de dados vazia (sem config externa nem execuções antigas)."""
    from leilao_sig import config

    monkeypatch.setattr(config, "pasta_dados", lambda: tmp_path / "dados")
    for f in (config.leiloeiros, config.calendario, config.triagem):
        f.cache_clear()
    yield
