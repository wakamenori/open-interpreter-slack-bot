import logging
import sys

from pythonjsonlogger import jsonlogger

formatter = jsonlogger.JsonFormatter()

stream = logging.StreamHandler(stream=sys.stdout)
stream.setFormatter(formatter)

logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(stream)
