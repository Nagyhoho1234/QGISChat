"""Settings dialog for GIS Chat plugin."""
from qgis.PyQt.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLabel, QLineEdit, QComboBox, QCheckBox, QDialogButtonBox, QSpinBox
)
from qgis.PyQt.QtCore import Qt

from .settings import Settings, LlmProvider, PROVIDER_INFO


class SettingsDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("GIS Chat - Settings")
        self.setMinimumWidth(450)
        self._build_ui()
        self._load_settings()
        self._on_provider_changed()

    def _build_ui(self):
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Provider
        self.provider_combo = QComboBox()
        for p in LlmProvider:
            self.provider_combo.addItem(PROVIDER_INFO[p]["display"], p.value)
        self.provider_combo.currentIndexChanged.connect(self._on_provider_changed)
        form.addRow("AI Provider:", self.provider_combo)

        # API Key
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.Password)
        self.api_key_edit.setPlaceholderText("Enter API key (optional - can set later)")
        form.addRow("API Key:", self.api_key_edit)

        self.api_key_help = QLabel()
        self.api_key_help.setStyleSheet("color: #888; font-size: 11px;")
        self.api_key_help.setWordWrap(True)
        form.addRow("", self.api_key_help)

        # Model
        self.model_combo = QComboBox()
        self.model_combo.setEditable(True)
        form.addRow("Model:", self.model_combo)

        # Endpoint
        self.endpoint_edit = QLineEdit()
        self.endpoint_edit.setPlaceholderText("Leave empty for default")
        self.endpoint_label = QLabel("Endpoint URL:")
        form.addRow(self.endpoint_label, self.endpoint_edit)

        # Max tokens
        self.max_tokens_spin = QSpinBox()
        self.max_tokens_spin.setRange(256, 32768)
        self.max_tokens_spin.setSingleStep(256)
        form.addRow("Max Tokens:", self.max_tokens_spin)

        # Options
        self.confirm_check = QCheckBox("Ask for confirmation before executing code")
        form.addRow("", self.confirm_check)

        self.show_code_check = QCheckBox("Show generated code in chat")
        form.addRow("", self.show_code_check)

        layout.addLayout(form)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._save_and_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_provider_changed(self):
        idx = self.provider_combo.currentIndex()
        provider_val = self.provider_combo.itemData(idx)
        provider = LlmProvider(provider_val)
        info = PROVIDER_INFO[provider]

        self.api_key_help.setText(info["key_help"])

        # Show/hide API key
        self.api_key_edit.setVisible(info["needs_key"])
        self.api_key_help.setVisible(info["needs_key"])

        # Show endpoint for Ollama / Compatible
        show_endpoint = provider in (LlmProvider.Ollama, LlmProvider.OpenAICompatible)
        self.endpoint_edit.setVisible(show_endpoint)
        self.endpoint_label.setVisible(show_endpoint)
        if show_endpoint and not self.endpoint_edit.text():
            self.endpoint_edit.setText(info["endpoint"])

        # Update models
        self.model_combo.clear()
        for m in info["models"]:
            self.model_combo.addItem(m)

    def _load_settings(self):
        # Provider
        provider = Settings.provider()
        for i in range(self.provider_combo.count()):
            if self.provider_combo.itemData(i) == provider.value:
                self.provider_combo.setCurrentIndex(i)
                break

        self.api_key_edit.setText(Settings.api_key())

        # Model — set after provider triggers model list update
        model = Settings.model()
        idx = self.model_combo.findText(model)
        if idx >= 0:
            self.model_combo.setCurrentIndex(idx)
        else:
            self.model_combo.setEditText(model)

        self.endpoint_edit.setText(Settings.endpoint())
        self.max_tokens_spin.setValue(Settings.max_tokens())
        self.confirm_check.setChecked(Settings.confirm_before_execute())
        self.show_code_check.setChecked(Settings.show_generated_code())

    def _save_and_accept(self):
        provider_val = self.provider_combo.currentData()
        Settings.set_provider(LlmProvider(provider_val))
        Settings.set_api_key(self.api_key_edit.text().strip())
        Settings.set_model(self.model_combo.currentText().strip())
        Settings.set_endpoint(self.endpoint_edit.text().strip())
        Settings.set_max_tokens(self.max_tokens_spin.value())
        Settings.set_confirm_before_execute(self.confirm_check.isChecked())
        Settings.set_show_generated_code(self.show_code_check.isChecked())
        self.accept()
