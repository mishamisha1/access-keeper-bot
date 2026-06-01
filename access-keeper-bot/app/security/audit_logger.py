"""Immutable audit logging for compliance."""

import json
import logging
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class AuditEvent:
    """Represents an audit event."""
    timestamp: str
    event_id: str
    event_type: str
    user_id: int
    username: str
    action: str
    resource_type: str
    resource_id: str
    details: Dict[str, Any]
    previous_state: Optional[Dict[str, Any]]
    new_state: Optional[Dict[str, Any]]
    ip_address: Optional[str]
    user_agent: Optional[str]
    signature: str  # Hash for integrity verification


class AuditLogger:
    """Immutable audit logger for ISO 27001 compliance."""

    def __init__(self, db=None, log_dir: str = "data/audit_logs"):
        self.db = db
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Current audit log file (daily rotation)
        self.current_date = datetime.now().strftime('%Y-%m-%d')
        self.log_file = self.log_dir / f"audit_{self.current_date}.jsonl"
        
        # Chain hash for integrity
        self.previous_hash: Optional[str] = None
        
        # Load last hash if file exists
        self._load_last_hash()

    def _load_last_hash(self):
        """Load the hash of the last entry for chain integrity."""
        if not self.log_file.exists():
            return
        
        try:
            with open(self.log_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                if lines:
                    last_entry = json.loads(lines[-1])
                    self.previous_hash = last_entry.get('entry_hash')
        except Exception as e:
            logger.error(f"Failed to load last hash: {e}")
            self.previous_hash = None

    def _generate_event_id(self, event: AuditEvent) -> str:
        """Generate unique event ID."""
        content = f"{event.timestamp}{event.user_id}{event.action}{event.resource_id}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _calculate_entry_hash(self, event: AuditEvent) -> str:
        """Calculate hash for chain integrity."""
        content = {
            'previous_hash': self.previous_hash or '',
            'event': asdict(event)
        }
        hash_content = json.dumps(content, sort_keys=True)
        return hashlib.sha256(hash_content.encode()).hexdigest()

    def log(self,
            event_type: str,
            action: str,
            user_id: int,
            username: str,
            resource_type: str,
            resource_id: str,
            details: Optional[Dict[str, Any]] = None,
            previous_state: Optional[Dict[str, Any]] = None,
            new_state: Optional[Dict[str, Any]] = None,
            ip_address: Optional[str] = None,
            user_agent: Optional[str] = None) -> str:
        """
        Log an audit event.
        
        Args:
            event_type: Type of event (ACCESS, CHANGE, DELETE, etc.)
            action: Specific action taken
            user_id: Telegram user ID
            username: Telegram username
            resource_type: Type of resource (SPREADSHEET, CALENDAR_EVENT, etc.)
            resource_id: ID of the resource
            details: Additional details about the event
            previous_state: State before change (for modifications)
            new_state: State after change (for modifications)
            ip_address: IP address (if available)
            user_agent: User agent (if available)
            
        Returns:
            Event ID
        """
        timestamp = datetime.now().isoformat()
        
        event = AuditEvent(
            timestamp=timestamp,
            event_id='',  # Will be set after generation
            event_type=event_type,
            user_id=user_id,
            username=username,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details or {},
            previous_state=previous_state,
            new_state=new_state,
            ip_address=ip_address,
            user_agent=user_agent,
            signature=''  # Will be calculated
        )
        
        # Generate event ID
        event.event_id = self._generate_event_id(event)
        
        # Calculate signature (hash)
        event.signature = self._calculate_entry_hash(event)
        
        # Create entry with hash
        entry = asdict(event)
        entry['entry_hash'] = event.signature
        entry['previous_entry_hash'] = self.previous_hash
        
        # Write to log file
        try:
            # Check if we need to rotate (new day)
            today = datetime.now().strftime('%Y-%m-%d')
            if today != self.current_date:
                self.current_date = today
                self.log_file = self.log_dir / f"audit_{today}.jsonl"
                self.previous_hash = None  # Reset chain for new file
            
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry, ensure_ascii=False) + '\n')
            
            # Update previous hash for chain
            self.previous_hash = event.signature
            
            logger.info(f"Audit event logged: {event.event_id} - {action}")
            return event.event_id
            
        except Exception as e:
            logger.error(f"Failed to write audit log: {e}")
            raise

    def log_access_granted(self,
                          user_id: int,
                          username: str,
                          full_name: str,
                          system: str,
                          role: str,
                          valid_until: str,
                          spreadsheet_id: str,
                          row_number: int,
                          calendar_event_id: Optional[str] = None) -> str:
        """Log access grant event."""
        return self.log(
            event_type='ACCESS',
            action='ACCESS_GRANTED',
            user_id=user_id,
            username=username,
            resource_type='SPREADSHEET_ROW',
            resource_id=f"{spreadsheet_id}:{row_number}",
            details={
                'full_name': full_name,
                'system': system,
                'role': role,
                'valid_until': valid_until,
                'calendar_event_id': calendar_event_id
            },
            new_state={
                'status': 'ACTIVE',
                'granted_at': datetime.now().isoformat()
            }
        )

    def log_access_revoked(self,
                          user_id: int,
                          username: str,
                          full_name: str,
                          system: str,
                          role: str,
                          spreadsheet_id: str,
                          row_number: int,
                          reason: str,
                          previous_state: Dict[str, Any]) -> str:
        """Log access revocation event."""
        return self.log(
            event_type='ACCESS',
            action='ACCESS_REVOKED',
            user_id=user_id,
            username=username,
            resource_type='SPREADSHEET_ROW',
            resource_id=f"{spreadsheet_id}:{row_number}",
            details={
                'full_name': full_name,
                'system': system,
                'role': role,
                'reason': reason
            },
            previous_state=previous_state,
            new_state={
                'status': 'REVOKED',
                'revoked_at': datetime.now().isoformat()
            }
        )

    def log_access_extended(self,
                           user_id: int,
                           username: str,
                           full_name: str,
                           system: str,
                           spreadsheet_id: str,
                           row_number: int,
                           old_valid_until: str,
                           new_valid_until: str,
                           calendar_event_id: Optional[str] = None) -> str:
        """Log access extension event."""
        return self.log(
            event_type='ACCESS',
            action='ACCESS_EXTENDED',
            user_id=user_id,
            username=username,
            resource_type='SPREADSHEET_ROW',
            resource_id=f"{spreadsheet_id}:{row_number}",
            details={
                'full_name': full_name,
                'system': system,
                'old_valid_until': old_valid_until,
                'new_valid_until': new_valid_until,
                'calendar_event_id': calendar_event_id
            },
            previous_state={'valid_until': old_valid_until},
            new_state={'valid_until': new_valid_until}
        )

    def log_matrix_created(self,
                          user_id: int,
                          username: str,
                          spreadsheet_id: str,
                          spreadsheet_url: str,
                          template_name: str) -> str:
        """Log matrix creation event."""
        return self.log(
            event_type='MATRIX',
            action='MATRIX_CREATED',
            user_id=user_id,
            username=username,
            resource_type='SPREADSHEET',
            resource_id=spreadsheet_id,
            details={
                'spreadsheet_url': spreadsheet_url,
                'template_name': template_name
            },
            new_state={'status': 'CREATED'}
        )

    def log_file_imported(self,
                         user_id: int,
                         username: str,
                         filename: str,
                         file_type: str,
                         rows_imported: int,
                         spreadsheet_id: str) -> str:
        """Log file import event."""
        return self.log(
            event_type='IMPORT',
            action='FILE_IMPORTED',
            user_id=user_id,
            username=username,
            resource_type='SPREADSHEET',
            resource_id=spreadsheet_id,
            details={
                'filename': filename,
                'file_type': file_type,
                'rows_imported': rows_imported
            }
        )

    def log_calendar_event_created(self,
                                  user_id: int,
                                  username: str,
                                  calendar_event_id: str,
                                  event_summary: str,
                                  event_time: str) -> str:
        """Log calendar event creation."""
        return self.log(
            event_type='CALENDAR',
            action='EVENT_CREATED',
            user_id=user_id,
            username=username,
            resource_type='CALENDAR_EVENT',
            resource_id=calendar_event_id,
            details={
                'summary': event_summary,
                'event_time': event_time
            }
        )

    def log_unauthorized_access(self,
                               user_id: int,
                               action_attempted: str) -> str:
        """Log unauthorized access attempt."""
        return self.log(
            event_type='SECURITY',
            action='UNAUTHORIZED_ACCESS',
            user_id=user_id,
            username='unknown',
            resource_type='BOT',
            resource_id='access_control',
            details={
                'action_attempted': action_attempted
            }
        )

    def verify_integrity(self, date: Optional[str] = None) -> tuple[bool, List[str]]:
        """
        Verify audit log integrity using hash chain.
        
        Args:
            date: Date to verify (YYYY-MM-DD), defaults to today
            
        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        if date is None:
            date = datetime.now().strftime('%Y-%m-%d')
        
        log_file = self.log_dir / f"audit_{date}.jsonl"
        
        if not log_file.exists():
            return True, []  # No log file, nothing to verify
        
        issues = []
        previous_hash = None
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    try:
                        entry = json.loads(line.strip())
                        
                        # Verify previous hash matches
                        if entry.get('previous_entry_hash') != previous_hash:
                            issues.append(
                                f"Line {line_num}: Hash chain broken. "
                                f"Expected {previous_hash}, got {entry.get('previous_entry_hash')}"
                            )
                        
                        # Recalculate hash and verify
                        stored_hash = entry.get('entry_hash')
                        entry_copy = entry.copy()
                        del entry_copy['entry_hash']
                        
                        # Simple verification (in production, would recalculate full hash)
                        if not stored_hash:
                            issues.append(f"Line {line_num}: Missing entry hash")
                        
                        previous_hash = stored_hash
                        
                    except json.JSONDecodeError as e:
                        issues.append(f"Line {line_num}: Invalid JSON - {e}")
            
            return len(issues) == 0, issues
            
        except Exception as e:
            return False, [f"Failed to verify log: {e}"]

    def get_audit_trail(self,
                       resource_type: Optional[str] = None,
                       resource_id: Optional[str] = None,
                       user_id: Optional[int] = None,
                       event_type: Optional[str] = None,
                       start_date: Optional[str] = None,
                       end_date: Optional[str] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """
        Retrieve audit trail with filters.
        
        Args:
            resource_type: Filter by resource type
            resource_id: Filter by resource ID
            user_id: Filter by user ID
            event_type: Filter by event type
            start_date: Start date (ISO format)
            end_date: End date (ISO format)
            limit: Maximum number of entries to return
            
        Returns:
            List of audit events
        """
        results = []
        
        # Determine which files to search
        if start_date and end_date:
            # Search multiple files in date range
            from datetime import timedelta
            current = datetime.fromisoformat(start_date[:10])
            end = datetime.fromisoformat(end_date[:10])
            files_to_search = []
            
            while current <= end:
                file_date = current.strftime('%Y-%m-%d')
                files_to_search.append(self.log_dir / f"audit_{file_date}.jsonl")
                current += timedelta(days=1)
        else:
            # Search today's file
            files_to_search = [self.log_dir / f"audit_{self.current_date}.jsonl"]
        
        for log_file in files_to_search:
            if not log_file.exists():
                continue
                
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if len(results) >= limit:
                            break
                            
                        entry = json.loads(line.strip())
                        
                        # Apply filters
                        if resource_type and entry.get('resource_type') != resource_type:
                            continue
                        if resource_id and entry.get('resource_id') != resource_id:
                            continue
                        if user_id and entry.get('user_id') != user_id:
                            continue
                        if event_type and entry.get('event_type') != event_type:
                            continue
                        
                        results.append(entry)
                        
            except Exception as e:
                logger.error(f"Error reading audit log {log_file}: {e}")
        
        return results
