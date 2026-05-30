import json
import logging
import os
import shutil
import threading
import time
from queue import Empty, Queue
from datetime import datetime

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logger = logging.getLogger(__name__)


class InstallationMonitor(FileSystemEventHandler):
    def __init__(self, source_path, destination_path, excluded_paths, manifest_path=None, collection_name="default"):
        self.source_path = source_path
        self.destination_path = destination_path
        self.manifest_path = manifest_path
        self.collection_root = os.path.join(destination_path, collection_name)
        self.excluded_paths = [os.path.normcase(os.path.abspath(path)) for path in excluded_paths + [destination_path]]
        os.makedirs(self.destination_path, exist_ok=True)
        os.makedirs(self.collection_root, exist_ok=True)
        if self.manifest_path:
            os.makedirs(os.path.dirname(self.manifest_path), exist_ok=True)
        self.queue = Queue()
        self._stop_event = threading.Event()
        self._worker = threading.Thread(target=self._drain_queue, daemon=True)
        self._worker.start()

    def _drain_queue(self):
        while True:
            try:
                src_path, is_directory = self.queue.get(timeout=1)
            except Empty:
                if self._stop_event.is_set():
                    break
                continue
            time.sleep(2)
            if not os.path.exists(src_path):
                self.queue.task_done()
                continue
            if is_directory:
                self.copy_directory(src_path)
            else:
                self.copy_file(src_path)
            self.queue.task_done()

    def on_created(self, event):
        src_path = os.path.normcase(os.path.abspath(event.src_path))
        if src_path.startswith(tuple(self.excluded_paths)):
            return
        self.queue.put((event.src_path, event.is_directory))

    def process_pending(self):
        """stop_event를 설정하고 큐가 완전히 드레인될 때까지 대기한다."""
        self._stop_event.set()
        self.queue.join()
        self._worker.join(timeout=60)

    def _destination_for(self, src_path):
        drive, rel_path = os.path.splitdrive(os.path.abspath(src_path))
        rel_path = rel_path.lstrip("\\/")
        if drive:
            rel_path = os.path.join(drive.rstrip(":").replace("\\", "_"), rel_path)
        return os.path.join(self.collection_root, rel_path)

    def _write_manifest(self, src_path, dest_path, item_type, status, error=""):
        if not self.manifest_path:
            return

        record = {
            "timestamp": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "source": src_path,
            "destination": dest_path,
            "type": item_type,
            "status": status,
            "error": error,
        }
        try:
            with open(self.manifest_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error("Error writing manifest: %s", e)

    def copy_file(self, src_path):
        dest_path = self._destination_for(src_path)

        try:
            if os.path.exists(dest_path):
                self._write_manifest(src_path, dest_path, "file", "skipped", "destination exists")
                logger.debug("File already exists, skipping: %s", dest_path)
                return
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            shutil.copy2(src_path, dest_path)
            self._write_manifest(src_path, dest_path, "file", "copied")
        except Exception as e:
            self._write_manifest(src_path, dest_path, "file", "failed", str(e))
            logger.warning("Error copying file %s: %s", src_path, e)

    def copy_directory(self, src_path):
        dest_path = self._destination_for(src_path)

        try:
            if os.path.exists(dest_path):
                self._write_manifest(src_path, dest_path, "directory", "skipped", "destination exists")
                logger.debug("Directory already exists, skipping: %s", dest_path)
                return
            shutil.copytree(src_path, dest_path)
            self._write_manifest(src_path, dest_path, "directory", "copied")
            logger.info("Directory copied: %s -> %s", src_path, dest_path)
        except Exception as e:
            self._write_manifest(src_path, dest_path, "directory", "failed", str(e))
            logger.warning("Error copying directory %s: %s", src_path, e)


def start_monitoring(source_path, destination_path, excluded_paths, manifest_path=None, collection_name="default"):
    event_handler = InstallationMonitor(
        source_path, destination_path, excluded_paths, manifest_path, collection_name
    )
    observer = Observer()
    observer.schedule(event_handler, source_path, recursive=True)
    observer.start()
    return observer, event_handler


def stop_monitoring(observer, event_handler):
    observer.stop()
    observer.join()
    event_handler.process_pending()
