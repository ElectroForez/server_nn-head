from os import environ
DB_PATH = 'db_head.db'
API_PASSWORD = environ['PASS_HEAD']
SERVERS_FILENAME = 'servers.txt'
# waiting time
MAX_UPLOAD_TIME = 100  # secs
MAX_DOWNLOAD_TIME = 100  # secs
MAX_PROCESSING_TIME = 100000  # secs
MAX_NOT_AVAILABLE = 60  # secs
MAX_PARALLEL_UPLOAD = 3
MAX_PARALLEL_DOWNLOAD = 3
