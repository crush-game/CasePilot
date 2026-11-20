"""独立进程的 P08 协议替身；不能调用真实模型。"""
from pathlib import Path
import sys
from uuid import UUID

import httpx
from pydantic import SecretStr
from sqlalchemy.orm import Session

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "integration"))
from test_p08 import advance, response
from app.config import get_settings
from app.providers.configuration import ProviderConfig
from app.providers.remote import ProviderSession
from app.repositories.database import get_engine
from app.services.workflow_common import latest_snapshot

run_id, budget_id = (UUID(value) for value in sys.argv[1:])
with Session(get_engine()) as db:
    config = ProviderConfig.model_validate(latest_snapshot(db, run_id)["agent_config"]["providers"])
provider = ProviderSession(get_engine(), budget_id, config, SecretStr("CONTRACT_TEST_KEY"), transport=httpx.MockTransport(response))
assert advance(run_id, provider)
