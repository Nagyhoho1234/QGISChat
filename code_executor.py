"""Execute Python/PyQGIS code inside the running QGIS environment."""
import io
import sys
import traceback


class ExecutionResult:
    def __init__(self, success: bool, output: str, error: str | None = None):
        self.success = success
        self.output = output
        self.error = error

    def __str__(self):
        if self.success:
            return self.output.strip() if self.output.strip() else "Completed successfully."
        return f"Error: {self.error or 'Unknown error'}\n{self.output}".strip()


def run_pyqgis(code: str) -> ExecutionResult:
    """Execute PyQGIS code, capturing stdout and handling errors."""
    capture = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = capture

    try:
        # Provide common imports in the execution namespace
        exec_globals = {
            "__builtins__": __builtins__,
        }
        # Import commonly needed modules into the namespace
        setup = (
            "from qgis.core import *\n"
            "from qgis.gui import *\n"
            "from qgis.utils import iface\n"
            "import qgis.processing as processing\n"
            "import os\n"
        )
        exec(setup, exec_globals)
        exec(code, exec_globals)

        output = capture.getvalue()
        if "ERROR:" in output:
            return ExecutionResult(False, output, output)
        return ExecutionResult(True, output)

    except Exception as e:
        output = capture.getvalue()
        tb = traceback.format_exc()
        return ExecutionResult(False, output, f"{type(e).__name__}: {e}\n{tb}")

    finally:
        sys.stdout = old_stdout
