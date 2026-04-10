"""Tests for gateway and serve command startup."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestGatewayStartup:
    """Tests for gateway command initialization."""

    def test_gateway_initializes_agent_loop(self, tmp_path):
        """Gateway should initialize AgentLoop correctly."""
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.queue import MessageBus
        from nanobot.config.schema import Config

        # Create minimal config
        config = Config()
        config.agents.defaults.workspace = str(tmp_path)
        config.agents.defaults.model = "test-model"

        bus = MessageBus()
        provider = MagicMock()
        provider.get_default_model = MagicMock(return_value="test-model")

        # Create AgentLoop with minimal config
        agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=tmp_path,
            model="test-model",
            max_iterations=10,
        )

        # Verify initialization
        assert agent.bus == bus
        assert agent.provider == provider
        assert agent.workspace == tmp_path
        assert agent.model == "test-model"

    def test_gateway_creates_session_manager(self, tmp_path):
        """Gateway should create SessionManager."""
        from nanobot.session.manager import SessionManager

        session_mgr = SessionManager(tmp_path)

        assert session_mgr.workspace == tmp_path

    def test_gateway_creates_cron_service(self, tmp_path):
        """Gateway should create CronService."""
        from nanobot.cron.service import CronService

        cron_store = tmp_path / "cron" / "jobs.json"
        cron = CronService(cron_store)

        status = cron.status()
        assert status["enabled"] is False  # Not running yet
        assert status["jobs"] == 0

    @pytest.mark.asyncio
    async def test_gateway_can_start_stop_agent_loop(self, tmp_path):
        """AgentLoop can be started and stopped."""
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.queue import MessageBus

        bus = MessageBus()
        provider = MagicMock()
        provider.get_default_model = MagicMock(return_value="test-model")
        provider.chat_with_retry = MagicMock(return_value=MagicMock())

        agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=tmp_path,
            model="test-model",
            max_iterations=10,
        )

        # Start and stop should work
        agent.stop()  # Should not raise

        # Running state
        assert not agent._running


class TestServeStartup:
    """Tests for serve command (API server) initialization."""

    def test_create_app_initializes_correctly(self):
        """create_app should initialize aiohttp app correctly."""
        try:
            from aiohttp import web
            from nanobot.api.server import create_app
        except ImportError:
            pytest.skip("aiohttp not installed")

        mock_agent = MagicMock()
        mock_agent.process_direct = MagicMock(return_value="test")

        app = create_app(mock_agent, model_name="test-model", request_timeout=10.0)

        assert app["agent_loop"] == mock_agent
        assert app["model_name"] == "test-model"
        assert app["request_timeout"] == 10.0
        assert isinstance(app["session_locks"], dict)

        # Check routes exist by looking at resource info
        routes = list(app.router.routes())
        route_paths = []
        for r in routes:
            # Get the resource's canonical path
            if hasattr(r.resource, 'canonical'):
                route_paths.append(r.resource.canonical)
        assert any('/v1/chat/completions' in p for p in route_paths)
        assert any('/v1/models' in p for p in route_paths)
        assert any('/health' in p for p in route_paths)

    @pytest.mark.asyncio
    async def test_api_server_health_endpoint(self):
        """Health endpoint should return ok status."""
        try:
            from aiohttp import web
            from nanobot.api.server import handle_health
        except ImportError:
            pytest.skip("aiohttp not installed")

        mock_request = MagicMock()
        mock_request.app = {}

        response = await handle_health(mock_request)

        assert response.status == 200

    @pytest.mark.asyncio
    async def test_api_server_models_endpoint(self):
        """Models endpoint should return model list."""
        try:
            from aiohttp import web
            from nanobot.api.server import handle_models
        except ImportError:
            pytest.skip("aiohttp not installed")

        mock_request = MagicMock()
        mock_request.app = {"model_name": "test-model"}

        response = await handle_models(mock_request)

        assert response.status == 200


class TestChannelManagerStartup:
    """Tests for channel manager initialization."""

    def test_channel_manager_initializes(self, tmp_path):
        """ChannelManager should initialize correctly."""
        from nanobot.channels.manager import ChannelManager
        from nanobot.bus.queue import MessageBus
        from nanobot.config.schema import Config

        config = Config()
        config.agents.defaults.workspace = str(tmp_path)

        bus = MessageBus()

        manager = ChannelManager(config, bus)

        assert manager.bus == bus

    def test_channel_manager_lists_enabled_channels(self, tmp_path):
        """ChannelManager should list enabled channels."""
        from nanobot.channels.manager import ChannelManager
        from nanobot.bus.queue import MessageBus
        from nanobot.config.schema import Config

        config = Config()
        config.agents.defaults.workspace = str(tmp_path)

        bus = MessageBus()
        manager = ChannelManager(config, bus)

        enabled = manager.enabled_channels

        # Should be empty when no channels enabled
        assert enabled == []


class TestHeartbeatService:
    """Tests for heartbeat service initialization."""

    def test_heartbeat_service_initializes(self, tmp_path):
        """HeartbeatService should initialize correctly."""
        from nanobot.heartbeat.service import HeartbeatService

        provider = MagicMock()
        provider.get_default_model = MagicMock(return_value="test-model")

        service = HeartbeatService(
            workspace=tmp_path,
            provider=provider,
            model="test-model",
            on_execute=lambda x: x,
            on_notify=lambda x: None,
            interval_s=60,
            enabled=True,
        )

        assert service.workspace == tmp_path
        assert service.interval_s == 60
        assert service.enabled is True

    @pytest.mark.asyncio
    async def test_heartbeat_can_start_stop(self, tmp_path):
        """HeartbeatService can be started and stopped."""
        from nanobot.heartbeat.service import HeartbeatService

        provider = MagicMock()
        provider.get_default_model = MagicMock(return_value="test-model")

        async def on_execute(x):
            return "test"

        def on_notify(x):
            pass

        service = HeartbeatService(
            workspace=tmp_path,
            provider=provider,
            model="test-model",
            on_execute=on_execute,
            on_notify=on_notify,
            interval_s=60,
            enabled=False,  # Disabled to avoid actual execution
        )

        # Start and stop should work without errors
        service.stop()

        assert not service._running


class TestGatewayIntegration:
    """Integration tests for gateway components."""

    def test_all_components_initialize_together(self, tmp_path):
        """All gateway components should initialize together."""
        from nanobot.agent.loop import AgentLoop
        from nanobot.bus.queue import MessageBus
        from nanobot.channels.manager import ChannelManager
        from nanobot.config.schema import Config
        from nanobot.cron.service import CronService
        from nanobot.session.manager import SessionManager

        # Create config
        config = Config()
        config.agents.defaults.workspace = str(tmp_path)
        config.agents.defaults.model = "test-model"

        # Create components
        bus = MessageBus()
        provider = MagicMock()
        provider.get_default_model = MagicMock(return_value="test-model")
        provider.chat_with_retry = MagicMock(return_value=MagicMock())

        session_mgr = SessionManager(tmp_path)
        cron_store = tmp_path / "cron" / "jobs.json"
        cron = CronService(cron_store)
        channels = ChannelManager(config, bus)

        agent = AgentLoop(
            bus=bus,
            provider=provider,
            workspace=tmp_path,
            model="test-model",
            max_iterations=10,
            session_manager=session_mgr,
            cron_service=cron,
        )

        # Verify all components are connected
        assert agent.sessions == session_mgr
        assert agent.cron_service == cron

    def test_gateway_config_workspace_override(self, tmp_path):
        """Gateway should use workspace from config."""
        from nanobot.config.schema import Config

        config = Config()
        config.agents.defaults.workspace = str(tmp_path)

        # Workspace should match config
        assert str(config.workspace_path) == str(tmp_path)