"""Environment-only configuration."""

import pytest
from bot.config import ConfigError, load_config


def test_token_required():
    with pytest.raises(ConfigError, match="DISCORD_TOKEN"):
        load_config({})
    with pytest.raises(ConfigError, match="DISCORD_TOKEN"):
        load_config({"DISCORD_TOKEN": "   "})


def test_minimal_config():
    config = load_config({"DISCORD_TOKEN": "token-1"})
    assert config.token == "token-1"
    assert config.guild_id is None


def test_guild_id_parsed_or_rejected():
    assert load_config({"DISCORD_TOKEN": "t", "GUILD_ID": "123"}).guild_id == 123
    with pytest.raises(ConfigError, match="GUILD_ID"):
        load_config({"DISCORD_TOKEN": "t", "GUILD_ID": "my-server"})
