import os

from autoreach.env import load_dotenv


def test_loads_keys_from_a_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text('# a comment\nGEMINI_API_KEY=abc123\nGEMINI_MODEL="gemini-2.0-flash"\n\n')

    load_dotenv(env_file)

    assert os.environ["GEMINI_API_KEY"] == "abc123"
    assert os.environ["GEMINI_MODEL"] == "gemini-2.0-flash"


def test_never_overrides_a_real_environment_variable(tmp_path, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "real-value")
    env_file = tmp_path / ".env"
    env_file.write_text("GEMINI_API_KEY=from-dotenv\n")

    load_dotenv(env_file)

    assert os.environ["GEMINI_API_KEY"] == "real-value"


def test_missing_file_is_a_silent_noop(tmp_path):
    load_dotenv(tmp_path / "does-not-exist.env")  # no exception
