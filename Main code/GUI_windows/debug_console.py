from qtconsole.inprocess import QtInProcessKernelManager
from qtconsole.rich_jupyter_widget import RichJupyterWidget


class DebugConsole(RichJupyterWidget):
    def __init__(self, **namespace):
        super().__init__()

        self.kernel_manager = QtInProcessKernelManager()
        self.kernel_manager.start_kernel()
        self.kernel_manager.kernel.shell.push(namespace)  # inject your objects

        self.kernel_client = self.kernel_manager.client()
        self.kernel_client.start_channels()

        self.banner = (
            "Debug console. Available objects: "
            + ", ".join(namespace.keys())
            + "\n"
        )

    def shutdown(self):
        self.kernel_client.stop_channels()
        self.kernel_manager.shutdown_kernel()