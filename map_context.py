"""Build a text description of the current QGIS map state for LLM context."""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer, QgsMapLayer, Qgis
)
from qgis.utils import iface


def get_map_context() -> str:
    lines = []
    project = QgsProject.instance()
    canvas = iface.mapCanvas()

    lines.append(f"Project: {project.fileName() or '(unsaved)'}")
    lines.append(f"CRS: {canvas.mapSettings().destinationCrs().authid()}")

    extent = canvas.extent()
    lines.append(f"Current Extent: ({extent.xMinimum():.2f}, {extent.yMinimum():.2f}) - "
                 f"({extent.xMaximum():.2f}, {extent.yMaximum():.2f})")

    lines.append("")
    lines.append("Layers:")

    for layer in project.mapLayers().values():
        tree_layer = project.layerTreeRoot().findLayer(layer.id())
        vis = "visible" if tree_layer and tree_layer.isVisible() else "hidden"

        if isinstance(layer, QgsVectorLayer):
            geom_type = QgsVectorLayer.geometryType(layer)
            geom_name = {0: "Point", 1: "Line", 2: "Polygon", 3: "Unknown", 4: "Null"}.get(geom_type, "?")
            lines.append(f'  - "{layer.name()}" [Vector/{geom_name}, {vis}]')

            count = layer.featureCount()
            lines.append(f"    Features: {count}")

            # List fields (skip geometry)
            fields = layer.fields()
            field_strs = []
            for f in fields:
                field_strs.append(f"{f.name()} ({f.typeName()})")
                if len(field_strs) >= 15:
                    break
            lines.append(f"    Fields: {', '.join(field_strs)}")

            # Selected
            sel_count = layer.selectedFeatureCount()
            if sel_count > 0:
                lines.append(f"    Selected: {sel_count} features")

        elif isinstance(layer, QgsRasterLayer):
            lines.append(f'  - "{layer.name()}" [Raster, {vis}]')
            lines.append(f"    Size: {layer.width()}x{layer.height()}, Bands: {layer.bandCount()}")
        else:
            lines.append(f'  - "{layer.name()}" [{layer.type().name}, {vis}]')

    return "\n".join(lines)
