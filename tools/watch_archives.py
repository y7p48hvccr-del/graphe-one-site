import time
import subprocess
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WATCH_PATHS = [
    "/Users/richardbillings/Library/Containers/com.graphe.scripturystudy/Data/Library/Application Support/Graphe/Modules/GrapheModules",
    "/Users/richardbillings/Books"
]

SYNC_SCRIPT = "/Users/richardbillings/graphe-one-site/tools/sync_archives.sh"


class ChangeHandler(FileSystemEventHandler):

    def on_any_event(self, event):

        if event.is_directory:
            return

        print(f"Detected change: {event.src_path}")

        subprocess.run([SYNC_SCRIPT])


observer = Observer()

for path in WATCH_PATHS:
    observer.schedule(ChangeHandler(), path, recursive=True)

observer.start()

print("Watching archives for changes...")

try:
    while True:
        time.sleep(1)

except KeyboardInterrupt:
    observer.stop()

observer.join()
