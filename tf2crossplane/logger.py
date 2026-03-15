"""
Shared logger for the tf2crossplane package.

Import LOGGER anywhere in the package:

    from tf2crossplane.logger import LOGGER
    LOGGER.info("Cloning %s ...", url)

The log level defaults to INFO. It can be overridden at runtime by setting
the TF2CROSSPLANE_LOG_LEVEL environment variable before invoking the CLI:

    TF2CROSSPLANE_LOG_LEVEL=DEBUG tf2crossplane --module-url ...
"""

import logging
import os

_level = os.getenv("TF2CROSSPLANE_LOG_LEVEL", "INFO").upper()

logging.basicConfig(
    level=_level,
    format="%(asctime)s %(levelname)-8s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

LOGGER = logging.getLogger("tf2crossplane")
