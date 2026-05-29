import os
import shutil
import time
from queue import Queue

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class InstallationMonitor(FileSystemEventHandler):
    def __init__(self, source_path, destination_path, excluded_paths):
        self.source_path = source_path
        self.destination_path = destination_path
        self.excluded_paths = excluded_paths + [destination_path]
        os.makedirs(self.destination_path, exist_ok=True)
        self.queue = Queue()

    def on_created(self, event):
        if event.src_path.startswith(tuple(self.excluded_paths)):
            return
        self.queue.put((event.src_path, event.is_directory))

    def process_pending(self):
        """observer 종료 후 큐에 남은 이벤트를 처리한다."""
        while not self.queue.empty():
            src_path, is_directory = self.queue.get()
            time.sleep(2)
            if not os.path.exists(src_path):
                continue
            if is_directory:
                self.move_directory(src_path)
            else:
                self.move_file(src_path)

    def move_file(self, src_path):
        file_name = os.path.basename(src_path)
        dest_path = os.path.join(self.destination_path, file_name)

        if os.path.exists(dest_path):
            print(f"File already exists. Skipping: {dest_path}")
            return

        try:
            shutil.copy(src_path, dest_path)
            os.remove(src_path)
        except Exception as e:
            print(f"Error occurred while moving file: {str(e)}")

    def move_directory(self, src_path):
        dir_name = os.path.basename(src_path)
        dest_path = os.path.join(self.destination_path, dir_name)

        if os.path.exists(dest_path):
            print(f"Directory already exists. Skipping: {dest_path}")
            return

        try:
            shutil.copytree(src_path, dest_path)
            shutil.rmtree(src_path)
            print(f"Directory move completed: {src_path} -> {dest_path}")
        except Exception as e:
            print(f"Error occurred while moving directory: {str(e)}")


def start_monitoring(source_path, destination_path, excluded_paths):
    event_handler = InstallationMonitor(source_path, destination_path, excluded_paths)
    observer = Observer()
    observer.schedule(event_handler, source_path, recursive=True)
    observer.start()
    return observer, event_handler


def stop_monitoring(observer, event_handler):
    observer.stop()
    observer.join()
    event_handler.process_pending()
