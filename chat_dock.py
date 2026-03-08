"""Chat dock widget — the main UI panel for GIS Chat."""
import threading

from qgis.PyQt.QtWidgets import (
    QDockWidget, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QLineEdit, QPushButton, QLabel, QMessageBox,
    QSizePolicy
)
from qgis.PyQt.QtCore import Qt, pyqtSignal, QObject
from qgis.PyQt.QtGui import QColor, QTextCursor

from .settings import Settings, PROVIDER_INFO
from .llm_service import LlmService
from .map_context import get_map_context
from .code_executor import run_pyqgis


class _WorkerSignals(QObject):
    """Signals to relay LLM results back to the GUI thread."""
    response_ready = pyqtSignal(object)  # LlmResponse
    error = pyqtSignal(str)


class ChatDockWidget(QDockWidget):
    def __init__(self, parent=None):
        super().__init__("GIS Chat", parent)
        self.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        self._llm = LlmService()
        self._signals = _WorkerSignals()
        self._signals.response_ready.connect(self._on_response)
        self._signals.error.connect(self._on_error)
        self._pending_map_context = ""
        self._is_processing = False
        self._tool_depth = 0

        self._build_ui()
        self._append_system(
            f"Welcome! Using {PROVIDER_INFO[Settings.provider()]['display']}.\n"
            "Ask me to perform GIS tasks. For example:\n"
            '  "Buffer all roads by 500m"\n'
            '  "How many features are in the flood zone?"\n'
            '  "Export selected features to GeoPackage"'
        )

    def _build_ui(self):
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(4, 4, 4, 4)

        # Status bar
        status_layout = QHBoxLayout()
        self._status_dot = QLabel("\u25cf")
        self._status_dot.setStyleSheet("color: #9E9E9E; font-size: 14px;")
        self._status_label = QLabel("Ready")
        self._status_label.setStyleSheet("color: #888; font-size: 11px;")
        status_layout.addWidget(self._status_dot)
        status_layout.addWidget(self._status_label, 1)

        clear_btn = QPushButton("Clear")
        clear_btn.setMaximumWidth(50)
        clear_btn.clicked.connect(self._clear_chat)
        status_layout.addWidget(clear_btn)
        layout.addLayout(status_layout)

        # Chat display
        self._chat_display = QTextEdit()
        self._chat_display.setReadOnly(True)
        self._chat_display.setStyleSheet(
            "QTextEdit { background: #FAFAFA; border: 1px solid #DDD; border-radius: 4px; "
            "font-family: 'Segoe UI', sans-serif; font-size: 13px; padding: 6px; }"
        )
        layout.addWidget(self._chat_display, 1)

        # Input area
        input_layout = QHBoxLayout()
        self._input_edit = QLineEdit()
        self._input_edit.setPlaceholderText("Type a message...")
        self._input_edit.setStyleSheet(
            "QLineEdit { border: 1px solid #1565C0; border-radius: 4px; padding: 6px; font-size: 13px; }"
        )
        self._input_edit.returnPressed.connect(self._send_message)
        input_layout.addWidget(self._input_edit, 1)

        self._send_btn = QPushButton("Send")
        self._send_btn.setStyleSheet(
            "QPushButton { background: #1565C0; color: white; border: none; border-radius: 4px; "
            "padding: 6px 16px; font-weight: bold; font-size: 13px; }"
            "QPushButton:hover { background: #1976D2; }"
            "QPushButton:disabled { background: #BDBDBD; }"
        )
        self._send_btn.clicked.connect(self._send_message)
        input_layout.addWidget(self._send_btn)
        layout.addLayout(input_layout)

        self.setWidget(container)

    # ---- Chat display helpers ----

    def _append_msg(self, role: str, text: str, color: str = "#333"):
        label = {"user": "You", "assistant": "GIS Chat", "system": "System"}.get(role, role)
        label_color = {"user": "#1565C0", "assistant": "#2E7D32", "system": "#888"}.get(role, "#333")
        html = (
            f'<p style="margin:6px 0 2px 0;">'
            f'<b style="color:{label_color};">{label}</b></p>'
            f'<p style="margin:0 0 4px 8px; color:{color}; white-space:pre-wrap;">{_escape(text)}</p>'
        )
        self._chat_display.append(html)
        self._scroll_bottom()

    def _append_code(self, code: str):
        html = (
            '<pre style="background:#F5F5F5; border:1px solid #DDD; border-radius:4px; '
            f'padding:6px; margin:2px 8px 4px 8px; font-size:12px; white-space:pre-wrap;">{_escape(code)}</pre>'
        )
        self._chat_display.append(html)
        self._scroll_bottom()

    def _append_result(self, result_str: str, success: bool):
        color = "#2E7D32" if success else "#C62828"
        prefix = "Result" if success else "Error"
        html = (
            f'<p style="margin:2px 0 2px 8px; color:{color}; font-size:12px;">'
            f'<b>{prefix}:</b> {_escape(result_str)}</p>'
        )
        if not success and self._tool_depth < self._MAX_TOOL_ROUND_TRIPS:
            html += (
                '<p style="margin:2px 0 2px 8px; color:#F57C00; font-size:12px; font-style:italic;">'
                'Analyzing error and working on a fix...</p>'
            )
        self._chat_display.append(html)
        self._scroll_bottom()

    def _append_system(self, text: str):
        self._append_msg("system", text, "#666")

    def _scroll_bottom(self):
        cursor = self._chat_display.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._chat_display.setTextCursor(cursor)

    # ---- Actions ----

    def _clear_chat(self):
        self._chat_display.clear()
        self._llm.clear_history()
        self._append_system(f"Chat cleared. Using {PROVIDER_INFO[Settings.provider()]['display']}.")

    def _set_processing(self, active: bool):
        self._is_processing = active
        self._send_btn.setEnabled(not active)
        self._input_edit.setEnabled(not active)
        if active:
            self._status_dot.setStyleSheet("color: #FFA000; font-size: 14px;")
            self._status_label.setText("Thinking...")
        else:
            self._status_dot.setStyleSheet("color: #4CAF50; font-size: 14px;")
            self._status_label.setText(f"Connected to {PROVIDER_INFO[Settings.provider()]['display']}")

    def _send_message(self):
        text = self._input_edit.text().strip()
        if not text or self._is_processing:
            return

        self._append_msg("user", text)
        self._input_edit.clear()
        self._set_processing(True)

        # Check API key
        provider = Settings.provider()
        if PROVIDER_INFO[provider]["needs_key"] and not Settings.api_key():
            self._append_system(
                f"API key not set for {PROVIDER_INFO[provider]['display']}.\n"
                "Go to Plugins > GIS Chat > Settings to configure."
            )
            self._set_processing(False)
            return

        map_context = get_map_context()
        self._pending_map_context = map_context
        self._tool_depth = 0

        # Run LLM call in a background thread to keep UI responsive
        thread = threading.Thread(
            target=self._llm_worker,
            args=(lambda: self._llm.send(text, map_context),),
            daemon=True,
        )
        thread.start()

    def _llm_worker(self, fn):
        try:
            response = fn()
            self._signals.response_ready.emit(response)
        except Exception as e:
            self._signals.error.emit(str(e))

    _MAX_TOOL_ROUND_TRIPS = 10

    def _on_response(self, response):
        # Show text if present and no tool calls
        if not response.has_tool_call:
            if response.text:
                self._append_msg("assistant", response.text)
            self._set_processing(False)
            return

        if self._tool_depth >= self._MAX_TOOL_ROUND_TRIPS:
            self._append_system("Stopped: too many consecutive tool calls.")
            self._set_processing(False)
            return

        # Execute ALL tool calls and collect results
        tool_results = []
        for i, tc in enumerate(response.tool_calls):
            if tc["name"] != "run_pyqgis":
                tool_results.append((tc["id"], f"Unknown tool: {tc['name']}"))
                continue

            code = tc["arguments"].get("code", "")
            explanation = tc["arguments"].get("explanation", "")

            # Show text before first tool call
            if i == 0 and response.text:
                self._append_msg("assistant", response.text)

            display_text = explanation or "Executing code..."
            self._append_msg("assistant", display_text)

            if Settings.show_generated_code() and code:
                self._append_code(code)

            # Confirm if needed
            if Settings.confirm_before_execute():
                reply = QMessageBox.question(
                    self, "GIS Chat - Confirm Execution",
                    f"Execute this GIS operation?\n\n{explanation}",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.Yes
                )
                if reply != QMessageBox.Yes:
                    tool_results.append((tc["id"], "Cancelled by user."))
                    self._append_result("Cancelled by user.", False)
                    continue

            # Execute code
            result = run_pyqgis(code)
            self._append_result(str(result), result.success)
            tool_results.append((tc["id"], str(result)))

        # Send ALL tool results back — follow-up comes via signal back to _on_response
        self._tool_depth += 1
        map_context = self._pending_map_context
        thread = threading.Thread(
            target=self._llm_worker,
            args=(lambda: self._llm.send_tool_results(tool_results, map_context),),
            daemon=True,
        )
        thread.start()

    def _on_error(self, error_msg: str):
        self._append_system(f"Error: {error_msg}")

        # Rollback instead of clearing full history on tool sync errors
        if "tool_result" in error_msg or "tool_use" in error_msg:
            self._llm.rollback_history(1)
            self._append_system("History sync error — last message rolled back. Please try again.")

        self._set_processing(False)
        self._status_dot.setStyleSheet("color: #F44336; font-size: 14px;")
        self._status_label.setText("Error — check settings")


def _escape(text: str) -> str:
    """Escape HTML special characters."""
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;"))
