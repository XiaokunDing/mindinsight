# Copyright 2020-2021 Huawei Technologies Co., Ltd
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ============================================================================
"""Implement the session manager."""
import os
import threading
from urllib.parse import unquote

import _thread

from mindinsight.conf import settings
from mindinsight.debugger.common.log import LOGGER as logger
from mindinsight.debugger.common.exceptions.exceptions import DebuggerSessionNumOverBoundError, \
    DebuggerSessionNotFoundError
from mindinsight.debugger.debugger_services.debugger_server_factory import DebuggerServerContext
from mindinsight.debugger.debugger_session import DebuggerSession


class SessionManager:
    """The server manager of debugger."""

    ONLINE_TYPE = "ONLINE"
    MAX_SESSION_NUM = 2
    ONLINE_SESSION_ID = "0"
    _instance = None
    _cls_lock = threading.Lock()

    def __init__(self):
        self.train_jobs = {}
        self.sessions = {}
        self.session_id = 1
        self.online_session = None
        self._lock = threading.Lock()
        self._exiting = False
        enable_debugger = settings.ENABLE_DEBUGGER if hasattr(settings, 'ENABLE_DEBUGGER') else False
        if enable_debugger:
            self.creat_session(self.ONLINE_TYPE)

    @classmethod
    def get_instance(cls):
        """Get the singleton instance."""
        with cls._cls_lock:
            if cls._instance is None:
                cls._instance = SessionManager()
            return cls._instance

    def exit(self):
        """
        Called when the gunicorn worker process is exiting.
        """
        with self._lock:
            logger.info("Start to exit sessions.")
            self._exiting = True
            for session in self.sessions:
                session.stop()
            self.online_session.stop()
        logger.info("Exited.")

    def get_session(self, session_id):
        """
        Get session by session id or get all session info.

        Args:
            session_id (Union[None, str]: The id of session.

        Returns:
            DebuggerSession, debugger session object.
        """
        with self._lock:
            if session_id == self.ONLINE_SESSION_ID and self.online_session is not None:
                return self.online_session

            if session_id in self.sessions:
                return self.sessions.get(session_id)

            raise DebuggerSessionNotFoundError("{}".format(session_id))

    def creat_session(self, session_type, train_job=None):
        """
        Create session by the train job info.

        Args:
            session_type (str): The session_type.
            train_job (str): The train job info.

        Returns:
            str, session id.
        """
        with self._lock:
            if self._exiting:
                logger.info(
                    "System is exiting, will terminate the thread.")
                _thread.exit()

            if session_type == self.ONLINE_TYPE:
                if self.online_session is None:
                    context = DebuggerServerContext(dbg_mode='online')
                    self.online_session = DebuggerSession(context)
                    self.online_session.start()
                return self.ONLINE_SESSION_ID

            if train_job in self.train_jobs:
                return self.train_jobs.get(train_job)

            self._check_session_num()
            summary_base_dir = settings.SUMMARY_BASE_DIR
            unquote_path = unquote(train_job, errors='strict')
            whole_path = os.path.join(summary_base_dir, unquote_path)
            normalized_path = validate_and_normalize_path(whole_path)
            context = DebuggerServerContext(dbg_mode='offline', train_job=train_job, dbg_dir=normalized_path)
            session = DebuggerSession(context)
            session.start()
            session_id = str(self.session_id)
            self.sessions[session_id] = session
            self.train_jobs[train_job] = session_id
            self.session_id += 1
            return session_id

    def delete_session(self, session_id):
        """Delete session by session id."""
        with self._lock:
            if session_id == self.ONLINE_SESSION_ID:
                self.online_session.stop()
                self.online_session = None
                return

            if session_id not in self.sessions:
                raise DebuggerSessionNotFoundError("session id {}".format(session_id))

            session = self.sessions.get(session_id)
            session.stop()
            self.sessions.pop(session_id)
            self.train_jobs.pop(session.train_job)
            return

    def get_sessions(self):
        """get all sessions"""
        return {"train_jobs": self.train_jobs}

    def _check_session_num(self):
        """Check the amount of sessions."""
        if len(self.sessions) >= self.MAX_SESSION_NUM:
            raise DebuggerSessionNumOverBoundError()


def validate_and_normalize_path(path):
    """Validate and normalize_path"""
    if not path:
        raise ValueError("The path is invalid!")

    path_str = str(path)

    if not path_str.startswith("/"):
        raise ValueError("The path is invalid!")

    try:
        normalized_path = os.path.realpath(path)
    except ValueError:
        raise ValueError("The path is invalid!")

    return normalized_path