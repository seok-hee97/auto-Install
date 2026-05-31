"""Tests for vm_controller.py — explicit backend/session behavior."""
from unittest.mock import patch

from vm_controller import VMSession, restore_snapshot, start_vm, stop_vm


class TestVmControllerBackend:
    def test_restore_uses_explicit_virtualbox_backend(self):
        with patch("vm_controller._vbox_restore", return_value=True) as mock_vbox, \
             patch("vm_controller._hyperv_restore") as mock_hyperv:
            assert restore_snapshot("vm", "snap", backend="virtualbox") is True

        mock_vbox.assert_called_once_with("vm", "snap")
        mock_hyperv.assert_not_called()

    def test_start_uses_explicit_hyperv_backend(self):
        with patch("vm_controller._hyperv_start", return_value=True) as mock_hyperv, \
             patch("vm_controller._vbox_start") as mock_vbox:
            assert start_vm("vm", wait_sec=1, backend="hyperv") is True

        mock_hyperv.assert_called_once_with("vm", 1)
        mock_vbox.assert_not_called()

    def test_stop_uses_explicit_virtualbox_backend(self):
        with patch("vm_controller._vbox_stop", return_value=True) as mock_vbox, \
             patch("vm_controller._hyperv_stop") as mock_hyperv:
            assert stop_vm("vm", backend="virtualbox") is True

        mock_vbox.assert_called_once_with("vm")
        mock_hyperv.assert_not_called()


class TestVmSession:
    def test_disabled_session_is_noop(self):
        with patch("vm_controller.restore_snapshot") as mock_restore, \
             patch("vm_controller.start_vm") as mock_start, \
             patch("vm_controller.stop_vm") as mock_stop:
            session = VMSession(enabled=False, vm_name="vm", snapshot_name="snap")
            assert session.__enter__() is True
            session.__exit__(None, None, None)

        mock_restore.assert_not_called()
        mock_start.assert_not_called()
        mock_stop.assert_not_called()

    def test_enabled_session_uses_explicit_backend(self):
        with patch("vm_controller.restore_snapshot", return_value=True) as mock_restore, \
             patch("vm_controller.start_vm", return_value=True) as mock_start, \
             patch("vm_controller.stop_vm") as mock_stop:
            session = VMSession(
                enabled=True,
                vm_name="vm",
                snapshot_name="snap",
                backend="virtualbox",
                boot_wait=7,
            )
            assert session.__enter__() is True
            session.__exit__(None, None, None)

        mock_restore.assert_called_once_with("vm", "snap", "virtualbox")
        mock_start.assert_called_once_with("vm", 7, "virtualbox")
        mock_stop.assert_called_once_with("vm", "virtualbox")
