# utils/logger.py
# Ghi log toàn bộ app

import logging
import os
from datetime import datetime
from utils.config import LOG_LEVEL, LOG_FILE

def setup_logger(name: str) -> logging.Logger:
    """
    Tạo logger cho từng module.
    Dùng: logger = setup_logger(__name__)
    """
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Tránh thêm handler trùng
    if logger.handlers:
        return logger

    # Format log
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Ghi ra console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Ghi ra file
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# ============================================================
# Dùng nhanh
# ============================================================
def log_info(module: str, message: str):
    logger = setup_logger(module)
    logger.info(message)


def log_warning(module: str, message: str):
    logger = setup_logger(module)
    logger.warning(message)


def log_error(module: str, message: str):
    logger = setup_logger(module)
    logger.error(message)
