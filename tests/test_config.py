"""Tests for config.py constants and setup_logging."""
import pytest
from config import (
    DANGER_KEYWORDS, DISAGREE_KEYWORDS_RADIO, AGREE_KEYWORDS,
    PASS_WINDOW, INSTALLATION_KEYWORDS, PROCESSABLE_EXTENSIONS,
    EXTRACTABLE_TYPES, SILENT_COMMANDS, INSTALLER_TYPE_LIST,
    DIE_INSTALLER_MAP, DIE_SFX_MAP,
)


class TestKeywordLists:
    def test_danger_keywords_not_empty(self):
        assert len(DANGER_KEYWORDS) > 0

    def test_disagree_and_agree_no_overlap(self):
        overlap = set(DISAGREE_KEYWORDS_RADIO) & set(AGREE_KEYWORDS)
        assert overlap == set(), f"Overlap: {overlap}"

    def test_agree_contains_core_words(self):
        assert "agree" in AGREE_KEYWORDS
        assert "accept" in AGREE_KEYWORDS
        assert "동의" in AGREE_KEYWORDS

    def test_disagree_contains_core_words(self):
        assert "do not agree" in DISAGREE_KEYWORDS_RADIO
        assert "disagree" in DISAGREE_KEYWORDS_RADIO
        assert "거부" in DISAGREE_KEYWORDS_RADIO

    def test_danger_no_install_words(self):
        safe_words = {"next", "install", "finish", "ok"}
        for word in DANGER_KEYWORDS:
            assert word.lower() not in safe_words, f"Danger list has safe word: {word}"

    def test_pass_window_lowercase(self):
        for item in PASS_WINDOW:
            assert item == item.lower(), f"PASS_WINDOW item should be lowercase: {item}"

    def test_installation_keywords_includes_setup(self):
        assert "setup" in INSTALLATION_KEYWORDS
        assert "install" in INSTALLATION_KEYWORDS


class TestExtensions:
    def test_processable_extensions_is_frozenset(self):
        assert isinstance(PROCESSABLE_EXTENSIONS, frozenset)

    def test_processable_contains_exe_msi(self):
        assert ".exe" in PROCESSABLE_EXTENSIONS
        assert ".msi" in PROCESSABLE_EXTENSIONS

    def test_extractable_types_subset_of_installer_list(self):
        known = set(INSTALLER_TYPE_LIST) | {"zip"}
        for t in EXTRACTABLE_TYPES:
            assert t in known, f"EXTRACTABLE_TYPE '{t}' not in INSTALLER_TYPE_LIST or 'zip'"


class TestSilentCommands:
    def test_all_installer_types_covered(self):
        for t in INSTALLER_TYPE_LIST:
            if t not in {"WIX Toolset installer", "BitRock installer", "QT installer",
                         "Sony Windows installer", "Windows Installer",
                         "CreateInstall-Overlay", "Ghost installer", "Acronis installer[ZIP]"}:
                assert t in SILENT_COMMANDS, f"No silent command for: {t}"

    def test_inno_verysilent_flag(self):
        assert "/VERYSILENT" in SILENT_COMMANDS["Inno Setup"]

    def test_nsis_silent_flag(self):
        assert "/S" in SILENT_COMMANDS["NSIS"]

    def test_msi_qn_flag(self):
        assert "/qn" in SILENT_COMMANDS["Microsoft Installer(MSI)"]


class TestMappings:
    def test_die_installer_map_keys_lowercase(self):
        for k in DIE_INSTALLER_MAP:
            assert k == k.lower(), f"Key not lowercase: {k}"

    def test_die_installer_map_values_in_list(self):
        for v in DIE_INSTALLER_MAP.values():
            assert v in INSTALLER_TYPE_LIST, f"Value '{v}' not in INSTALLER_TYPE_LIST"

    def test_die_sfx_map_7zip(self):
        assert "7-zip" in DIE_SFX_MAP
        assert DIE_SFX_MAP["7-zip"] == "7z installer"
