"""Main plugin class — creates toolbar, menu entries, and the dock widget."""
import os

from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtCore import Qt
from qgis.utils import iface


class GISChatPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.dock_widget = None
        self.actions = []
        self.menu_name = "&GIS Chat"
        self.toolbar = None

    def initGui(self):
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        icon = QIcon(icon_path)

        # Toolbar
        self.toolbar = self.iface.addToolBar("GIS Chat")
        self.toolbar.setObjectName("GISChatToolbar")

        # Open Chat action
        self.action_chat = QAction(icon, "GIS Chat", self.iface.mainWindow())
        self.action_chat.setToolTip("Open the AI chat assistant panel")
        self.action_chat.triggered.connect(self.toggle_chat)
        self.toolbar.addAction(self.action_chat)
        self.iface.addPluginToMenu(self.menu_name, self.action_chat)
        self.actions.append(self.action_chat)

        # Settings action
        self.action_settings = QAction("Settings", self.iface.mainWindow())
        self.action_settings.setToolTip("Configure GIS Chat provider and API key")
        self.action_settings.triggered.connect(self.open_settings)
        self.toolbar.addAction(self.action_settings)
        self.iface.addPluginToMenu(self.menu_name, self.action_settings)
        self.actions.append(self.action_settings)

    def unload(self):
        for action in self.actions:
            self.iface.removePluginMenu(self.menu_name, action)
        if self.toolbar:
            del self.toolbar
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)
            self.dock_widget = None

    def toggle_chat(self):
        if self.dock_widget is None:
            from .chat_dock import ChatDockWidget
            self.dock_widget = ChatDockWidget(self.iface.mainWindow())
            self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        else:
            self.dock_widget.setVisible(not self.dock_widget.isVisible())

    def open_settings(self):
        from .settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.iface.mainWindow())
        if dlg.exec_() and self.dock_widget:
            # Refresh status display after settings change
            from .settings import Settings, PROVIDER_INFO
            provider = Settings.provider()
            self.dock_widget._status_label.setText(
                f"Provider changed to {PROVIDER_INFO[provider]['display']}"
            )
