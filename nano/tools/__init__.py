"""
NANO Banking Assistant Tools Package

This package contains all the tools available to the NANO banking assistant:

- identity: Customer identity verification and authentication
- database: Account balance, transactions, and customer record management  
- files: Document upload, storage, and management
- support: General banking knowledge base and escalation
- ocr: Optical Character Recognition for document text extraction

Each tool module provides factory functions to get tool instances with database sessions.
"""

from .identity import get_identity_tools
from .database import get_database_tools
from .files import get_file_tools
from .support import get_support_tools
from .ocr import get_ocr_tools

__all__ = [
    'get_identity_tools',
    'get_database_tools', 
    'get_file_tools',
    'get_support_tools',
    'get_ocr_tools'
]