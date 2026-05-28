# Copyright (c) 2026 Marc Schütze @ ZKM | Center for Art and Media Karlsruhe
# SPDX-License-Identifier: MIT
"""API error handling utilities.

Provides decorators and context managers for consistent error handling
across API endpoints. Eliminates the repetitive try-except-HTTPException
pattern that appears in most endpoints.
"""

import functools
import logging
from contextlib import asynccontextmanager
from typing import Callable, TypeVar

from fastapi import HTTPException

T = TypeVar("T")


@asynccontextmanager
async def handle_api_errors(operation: str, logger: logging.Logger):
    """Context manager for consistent API error handling.

    Re-raises HTTPException unchanged, wraps other exceptions in HTTP 500.

    Usage:
        async with handle_api_errors("getting exhibition", logger):
            # business logic here
            ...

    Args:
        operation: Description of the operation for error logging
        logger: Logger instance to use for error messages
    """
    try:
        yield
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error {operation}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def api_error_handler(operation: str):
    """Decorator for consistent API error handling.

    Re-raises HTTPException unchanged, wraps other exceptions in HTTP 500.

    Usage:
        @router.get("/{id}")
        @api_error_handler("getting exhibition")
        async def get_exhibition(id: str):
            # business logic here
            ...

    Args:
        operation: Description of the operation for error logging
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            # Get logger from module where function is defined
            logger = logging.getLogger(func.__module__)
            try:
                return await func(*args, **kwargs)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error {operation}: {e}")
                raise HTTPException(status_code=500, detail=str(e))
        return wrapper
    return decorator
