"""Build a text description of the current QGIS map state for LLM context."""
from qgis.core import (
    QgsProject, QgsVectorLayer, QgsRasterLayer, QgsMapLayer, Qgis
)
from qgis.utils import iface


# Map QGIS data type enum values to human-readable names
_QGIS_DTYPE_NAMES = {
    0: "Unknown", 1: "Byte", 2: "UInt16", 3: "Int16", 4: "UInt32",
    5: "Int32", 6: "Float32", 7: "Float64", 8: "CInt16", 9: "CInt32",
    10: "CFloat32", 11: "CFloat64",
}


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
            band_count = layer.bandCount()

            # Cell size from raster units per pixel
            try:
                cell_x = layer.rasterUnitsPerPixelX()
                cell_y = layer.rasterUnitsPerPixelY()
                lines.append(f"    Size: {layer.width()}x{layer.height()}, "
                             f"Cell size: {cell_x:.2f}x{cell_y:.2f}, Bands: {band_count}")
            except Exception:
                lines.append(f"    Size: {layer.width()}x{layer.height()}, Bands: {band_count}")

            # Band details (name + data type), up to 20 bands
            dp = layer.dataProvider()
            if dp:
                for b in range(1, min(band_count + 1, 21)):
                    try:
                        band_name = dp.generateBandName(b)
                        dtype_val = dp.dataType(b)
                        dtype_name = _QGIS_DTYPE_NAMES.get(dtype_val, str(dtype_val))
                        lines.append(f"      [{b}] {band_name} ({dtype_name})")
                    except Exception:
                        pass

        else:
            lines.append(f'  - "{layer.name()}" [{layer.type().name}, {vis}]')

    return "\n".join(lines)
