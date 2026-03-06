"""
GIS Chat — AI-powered chat assistant for QGIS.
"""


def classFactory(iface):
    from .plugin import GISChatPlugin
    return GISChatPlugin(iface)
