import sys
from unittest.mock import MagicMock
sys.modules['httpx'] = MagicMock()
sys.modules['aiohttp'] = MagicMock()
sys.modules['fastapi'] = MagicMock()
sys.modules['uvicorn'] = MagicMock()
sys.path.insert(0, "/home/ubuntu/git/wharenui-hermes-agent")

class FakePhaseHandler:
    initial_phase = "private"

def get_control_tool_names():
    return ["reflect_pause"]

def get_control_phase_handler(cn):
    return FakePhaseHandler()

import hermes_cli.plugins
hermes_cli.plugins.get_control_tool_names = get_control_tool_names
hermes_cli.plugins.get_control_phase_handler = get_control_phase_handler

from agent.agent_init import init_agent
import logging
logging.basicConfig(level=logging.WARNING)

class MockAgent:
    def __init__(self):
        self.model = "test"
        self.provider = "test"
        self.base_url = None
        self.api_mode = "test"
        self.tools = [{"function": {"name": "reflect_pause"}}]
        self._client_kwargs = {}
        self._use_prompt_caching = False
        self._use_native_cache_layout = False
        self.quiet_mode = True
        self.context_compressor = None
        self.ephemeral_system_prompt = ""
        self.valid_tool_names = {"reflect_pause"}

agent = MockAgent()
init_agent(agent)
print("Phase after init:", agent._phase)
print("System Prompt:", agent.ephemeral_system_prompt)
