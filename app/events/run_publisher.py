"""Entrypoint: python -m app.events.run_publisher"""
import logging

from app.events.producer import build_producer
from app.events.publisher import run_forever

if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO)
    run_forever(build_producer())
