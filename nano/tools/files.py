import os
import shutil
import uuid
from typing import Dict, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import Document, AuditLog
from app.config import settings
import mimetypes


class FileManagementTools:
    def __init__(self, db: Session):
        self.db = db
        self.base_path = settings.customer_files_path
        self.max_file_size = settings.max_file_size_mb * 1024 * 1024  # Convert to bytes

    def create_customer_folder(self, session_id: str, customer_id: str) -> Dict[str, any]:
        """
        Create organized folder structure for customer documents.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
        
        Returns:
            Dict with folder creation status
        """
        try:
            customer_folder = os.path.join(self.base_path, customer_id)
            
            # Create main customer folder
            os.makedirs(customer_folder, exist_ok=True)
            
            # Create subfolders for different document types
            subfolders = [
                'statements',
                'applications',
                'correspondence',
                'identification',
                'temporary'
            ]
            
            for subfolder in subfolders:
                subfolder_path = os.path.join(customer_folder, subfolder)
                os.makedirs(subfolder_path, exist_ok=True)
            
            self._log_audit(session_id, customer_id, "create_customer_folder", 
                          f"Created folder structure at {customer_folder}", "success")
            
            return {
                "success": True,
                "message": f"Customer folder structure created successfully",
                "folder_path": customer_folder,
                "subfolders": subfolders
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "create_customer_folder", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Failed to create customer folder: {str(e)}"
            }

    def upload_document(
        self, 
        session_id: str,
        customer_id: str, 
        file_content: bytes, 
        filename: str,
        document_type: str = "general"
    ) -> Dict[str, any]:
        """
        Handle secure document upload for customers.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            file_content: File content as bytes
            filename: Original filename
            document_type: Type of document (statements, applications, etc.)
        
        Returns:
            Dict with upload status and document ID
        """
        try:
            # Validate file size
            if len(file_content) > self.max_file_size:
                return {
                    "success": False,
                    "message": f"File too large. Maximum size is {settings.max_file_size_mb}MB"
                }

            # Validate file type
            file_type = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            allowed_types = [
                'application/pdf',
                'image/jpeg',
                'image/png',
                'image/gif',
                'text/plain',
                'application/msword',
                'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
            ]
            
            if file_type not in allowed_types:
                return {
                    "success": False,
                    "message": "File type not allowed. Please upload PDF, image, or document files."
                }

            # Generate unique document ID and filename
            document_id = str(uuid.uuid4())
            safe_filename = self._sanitize_filename(filename)
            unique_filename = f"{document_id}_{safe_filename}"

            # Determine subfolder based on document type
            valid_types = ['statements', 'applications', 'correspondence', 'identification', 'temporary']
            subfolder = document_type if document_type in valid_types else 'general'

            # Create customer folder if it doesn't exist
            customer_folder = os.path.join(self.base_path, customer_id, subfolder)
            os.makedirs(customer_folder, exist_ok=True)

            # Save file
            file_path = os.path.join(customer_folder, unique_filename)
            with open(file_path, 'wb') as f:
                f.write(file_content)

            # Save document record to database
            document = Document(
                document_id=document_id,
                customer_id=customer_id,
                filename=safe_filename,
                file_path=file_path,
                file_type=file_type,
                file_size=len(file_content),
                status="active"
            )
            
            self.db.add(document)
            self.db.commit()

            self._log_audit(session_id, customer_id, "upload_document", 
                          f"Uploaded {filename} ({file_type}, {len(file_content)} bytes)", "success")

            return {
                "success": True,
                "message": "Document uploaded successfully",
                "document_id": document_id,
                "filename": safe_filename,
                "file_size": len(file_content),
                "file_type": file_type
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "upload_document", 
                          f"Error uploading {filename}: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Upload failed: {str(e)}"
            }

    def retrieve_document(
        self, 
        session_id: str,
        customer_id: str, 
        document_id: str
    ) -> Dict[str, any]:
        """
        Retrieve customer document securely.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            document_id: Document ID to retrieve
        
        Returns:
            Dict with document information or error
        """
        try:
            # Find document in database
            document = self.db.query(Document).filter(
                Document.document_id == document_id,
                Document.customer_id == customer_id,
                Document.status == "active"
            ).first()

            if not document:
                return {
                    "success": False,
                    "message": "Document not found or access denied"
                }

            # Check if file exists on disk
            if not os.path.exists(document.file_path):
                return {
                    "success": False,
                    "message": "Document file not found on disk"
                }

            # Get file info (don't return content for security)
            file_stats = os.stat(document.file_path)
            
            self._log_audit(session_id, customer_id, "retrieve_document", 
                          f"Retrieved document info for {document.filename}", "success")

            return {
                "success": True,
                "document_id": document.document_id,
                "filename": document.filename,
                "file_type": document.file_type,
                "file_size": document.file_size,
                "uploaded_at": document.uploaded_at.isoformat(),
                "file_path": document.file_path  # For internal use only
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "retrieve_document", 
                          f"Error retrieving document {document_id}: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Retrieval failed: {str(e)}"
            }

    def list_customer_documents(
        self, 
        session_id: str,
        customer_id: str
    ) -> Dict[str, any]:
        """
        List all documents for a customer.
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
        
        Returns:
            Dict with list of customer documents
        """
        try:
            documents = self.db.query(Document).filter(
                Document.customer_id == customer_id,
                Document.status == "active"
            ).order_by(Document.uploaded_at.desc()).all()

            document_list = []
            for doc in documents:
                document_list.append({
                    "document_id": doc.document_id,
                    "filename": doc.filename,
                    "file_type": doc.file_type,
                    "file_size": doc.file_size,
                    "uploaded_at": doc.uploaded_at.isoformat(),
                    "status": doc.status
                })

            self._log_audit(session_id, customer_id, "list_customer_documents", 
                          f"Listed {len(document_list)} documents", "success")

            return {
                "success": True,
                "documents": document_list,
                "total_count": len(document_list)
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "list_customer_documents", 
                          f"Error: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Failed to list documents: {str(e)}"
            }

    def archive_document(
        self, 
        session_id: str,
        customer_id: str, 
        document_id: str
    ) -> Dict[str, any]:
        """
        Archive a customer document (mark as archived, don't delete).
        
        Args:
            session_id: Current session ID
            customer_id: Customer ID
            document_id: Document ID to archive
        
        Returns:
            Dict with archive status
        """
        try:
            document = self.db.query(Document).filter(
                Document.document_id == document_id,
                Document.customer_id == customer_id
            ).first()

            if not document:
                return {
                    "success": False,
                    "message": "Document not found"
                }

            # Update status to archived
            document.status = "archived"
            self.db.commit()

            self._log_audit(session_id, customer_id, "archive_document", 
                          f"Archived document {document.filename}", "success")

            return {
                "success": True,
                "message": f"Document '{document.filename}' archived successfully",
                "document_id": document_id
            }

        except Exception as e:
            self._log_audit(session_id, customer_id, "archive_document", 
                          f"Error archiving document {document_id}: {str(e)}", "failed")
            return {
                "success": False,
                "message": f"Archive failed: {str(e)}"
            }

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage."""
        # Remove any path characters and dangerous characters
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-"
        sanitized = "".join(c for c in filename if c in safe_chars)
        
        # Ensure filename is not empty and has reasonable length
        if not sanitized:
            sanitized = "document"
        
        return sanitized[:100]  # Limit filename length

    def _log_audit(self, session_id: str, customer_id: str, 
                   action: str, details: str, status: str):
        """Log audit trail for file operations."""
        try:
            audit_log = AuditLog(
                session_id=session_id,
                customer_id=customer_id,
                action=action,
                details=details,
                status=status,
                timestamp=datetime.utcnow()
            )
            self.db.add(audit_log)
            self.db.commit()
        except Exception as e:
            print(f"Audit logging error: {e}")


def get_file_tools(db: Session) -> FileManagementTools:
    """Factory function to get file management tools."""
    return FileManagementTools(db)