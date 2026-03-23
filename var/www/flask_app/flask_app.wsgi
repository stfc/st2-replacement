import sys
import logging

sys.path.insert(0, "/usr/local/lib/python3.9/site-packages")

# Add app directory to path
sys.path.insert(0, "/var/www/flask_app")

# Set up logging for troubleshooting
logging.basicConfig(stream=sys.stderr)

from app import app as application
