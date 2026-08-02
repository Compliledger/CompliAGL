import pytest

from compliagl import CompliAGL, CompliAGLConfig
from tests.mock_server import MockCompliAGLServer


@pytest.fixture
def mock_server():
    with MockCompliAGLServer() as server:
        yield server


@pytest.fixture
def sdk(mock_server):
    return CompliAGL(CompliAGLConfig(base_url=mock_server.base_url, organization_id="org_test", api_key="key", auto_idempotency=False, retry_base_ms=0))
