"""
Database Manager for Pocketbase integration
Handles all database operations for the Schedule Quality Analyzer
"""

import json
import os
from typing import Dict, List, Optional, Any
from datetime import datetime
import streamlit as st


class DatabaseManager:
    """
    Manages database operations with Pocketbase
    For MVP, uses session state as a lightweight database simulation
    Can be upgraded to actual Pocketbase later
    """

    def __init__(self):
        """Initialize the database manager"""
        self._init_session_state()

    def _init_session_state(self):
        """Initialize session state for data storage"""
        if 'users' not in st.session_state:
            st.session_state.users = self._get_default_users()
        if 'projects' not in st.session_state:
            st.session_state.projects = []
        if 'schedules' not in st.session_state:
            st.session_state.schedules = []
        if 'analysis_results' not in st.session_state:
            st.session_state.analysis_results = []
        if 'audit_log' not in st.session_state:
            st.session_state.audit_log = []

    def _get_default_users(self) -> List[Dict]:
        """Get default users for testing"""
        return [
            {
                'id': 'user_001',
                'email': 'admin@example.com',
                'username': 'admin',
                'password': 'admin123',  # In production, this should be hashed
                'role': 'admin',
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            },
            {
                'id': 'user_002',
                'email': 'viewer@example.com',
                'username': 'viewer',
                'password': 'viewer123',
                'role': 'viewer',
                'created': datetime.now().isoformat(),
                'updated': datetime.now().isoformat()
            }
        ]

    # User Management
    def authenticate_user(self, username: str, password: str) -> Optional[Dict]:
        """Authenticate a user"""
        for user in st.session_state.users:
            if user['username'] == username and user['password'] == password:
                return user
        return None

    def get_user_by_id(self, user_id: str) -> Optional[Dict]:
        """Get user by ID"""
        for user in st.session_state.users:
            if user['id'] == user_id:
                return user
        return None

    def create_user(self, email: str, username: str, password: str, role: str = 'viewer') -> Dict:
        """Create a new user"""
        user = {
            'id': f'user_{len(st.session_state.users) + 1:03d}',
            'email': email,
            'username': username,
            'password': password,  # Should be hashed in production
            'role': role,
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat()
        }
        st.session_state.users.append(user)
        return user

    # Project Management
    def create_project(self, project_name: str, project_code: str, description: str, created_by: str) -> Dict:
        """Create a new project"""
        project = {
            'id': f'proj_{len(st.session_state.projects) + 1:03d}',
            'project_name': project_name,
            'project_code': project_code,
            'description': description,
            'created_by': created_by,
            'created': datetime.now().isoformat(),
            'updated': datetime.now().isoformat()
        }
        st.session_state.projects.append(project)
        self._log_action(created_by, 'create_project', project['id'], {'project_name': project_name})
        return project

    def get_all_projects(self) -> List[Dict]:
        """Get all projects"""
        return st.session_state.projects

    def get_project_by_id(self, project_id: str) -> Optional[Dict]:
        """Get project by ID"""
        for project in st.session_state.projects:
            if project['id'] == project_id:
                return project
        return None

    def get_project_by_code(self, project_code: str) -> Optional[Dict]:
        """Get project by code"""
        for project in st.session_state.projects:
            if project['project_code'] == project_code:
                return project
        return None

    # Schedule Management
    def create_schedule(self, project_id: str, schedule_data: Dict, file_name: str,
                       uploaded_by: str) -> Dict:
        """Create a new schedule"""
        # Get version number for this project
        project_schedules = [s for s in st.session_state.schedules if s['project_id'] == project_id]
        version_number = len(project_schedules) + 1

        schedule = {
            'id': f'sched_{len(st.session_state.schedules) + 1:03d}',
            'project_id': project_id,
            'version_number': version_number,
            'schedule_data': schedule_data,
            'file_name': file_name,
            'upload_date': datetime.now().isoformat(),
            'uploaded_by': uploaded_by,
            'analysis_status': 'pending'
        }
        st.session_state.schedules.append(schedule)
        self._log_action(uploaded_by, 'upload_schedule', schedule['id'],
                        {'file_name': file_name, 'project_id': project_id})
        return schedule

    def get_schedule_by_id(self, schedule_id: str) -> Optional[Dict]:
        """Get schedule by ID"""
        for schedule in st.session_state.schedules:
            if schedule['id'] == schedule_id:
                return schedule
        return None

    def get_schedules_by_project(self, project_id: str) -> List[Dict]:
        """Get all schedules for a project"""
        return [s for s in st.session_state.schedules if s['project_id'] == project_id]

    def update_schedule_status(self, schedule_id: str, status: str):
        """Update schedule analysis status"""
        for schedule in st.session_state.schedules:
            if schedule['id'] == schedule_id:
                schedule['analysis_status'] = status
                break

    def delete_schedule(self, schedule_id: str, user_id: str):
        """Delete a schedule"""
        st.session_state.schedules = [s for s in st.session_state.schedules
                                     if s['id'] != schedule_id]
        # Also delete associated analysis results
        st.session_state.analysis_results = [r for r in st.session_state.analysis_results
                                            if r['schedule_id'] != schedule_id]
        self._log_action(user_id, 'delete_schedule', schedule_id, {})

    # Analysis Results Management
    def save_analysis_result(self, schedule_id: str, metrics: Dict, issues: List[Dict],
                            recommendations: List[Dict], health_score: float) -> Dict:
        """Save analysis results"""
        # Check if analysis already exists for this schedule
        existing = None
        for i, result in enumerate(st.session_state.analysis_results):
            if result['schedule_id'] == schedule_id:
                existing = i
                break

        analysis = {
            'id': f'analysis_{len(st.session_state.analysis_results) + 1:03d}',
            'schedule_id': schedule_id,
            'metrics': metrics,
            'issues': issues,
            'recommendations': recommendations,
            'health_score': health_score,
            'analysis_date': datetime.now().isoformat()
        }

        if existing is not None:
            st.session_state.analysis_results[existing] = analysis
        else:
            st.session_state.analysis_results.append(analysis)

        # Update schedule status
        self.update_schedule_status(schedule_id, 'complete')

        return analysis

    def get_analysis_by_schedule(self, schedule_id: str) -> Optional[Dict]:
        """Get analysis results for a schedule"""
        for result in st.session_state.analysis_results:
            if result['schedule_id'] == schedule_id:
                return result
        return None

    def get_all_analyses(self) -> List[Dict]:
        """Get all analysis results"""
        return st.session_state.analysis_results

    # Audit Log
    def _log_action(self, user_id: str, action_type: str, resource_id: str, details: Dict):
        """Log user action"""
        log_entry = {
            'id': f'log_{len(st.session_state.audit_log) + 1:05d}',
            'user_id': user_id,
            'action_type': action_type,
            'resource_id': resource_id,
            'details': details,
            'timestamp': datetime.now().isoformat()
        }
        st.session_state.audit_log.append(log_entry)

    def get_audit_log(self, user_id: Optional[str] = None,
                     action_type: Optional[str] = None) -> List[Dict]:
        """Get audit log with optional filters"""
        logs = st.session_state.audit_log

        if user_id:
            logs = [log for log in logs if log['user_id'] == user_id]

        if action_type:
            logs = [log for log in logs if log['action_type'] == action_type]

        return logs
