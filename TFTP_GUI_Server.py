import sys
import os
import threading
import socket
import logging
from PyQt5 import QtWidgets, QtGui, QtCore
from tftp.TFTPServer import TftpServer, TftpPacketDAT, TftpPacketERR
from tftp.TftpClient import TftpClient
import psutil

# Logging Configuration
logger = logging.getLogger('tftp_server')
logger.setLevel(logging.INFO)
file_handler = logging.FileHandler('tftp_server_activity.log')
formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)


def get_ip_addresses():
    """Get the list of available IP addresses on the local machine across all interfaces."""
    ip_addresses = []

    for interface, addresses in psutil.net_if_addrs().items():
        for address in addresses:
            if address.family == socket.AF_INET:  # IPv4 addresses only
                ip_addresses.append(address.address)

    # Remove duplicates and return the list of IP addresses
    return list(set(ip_addresses))


class TFTPServer(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TFTP Server")
        self.setGeometry(100, 100, 500, 400)

        self.current_directory = os.getcwd()
        self.server = None

        # UI Elements
        self.ip_combo = QtWidgets.QComboBox(self)
        self.ip_combo.addItems(get_ip_addresses())  # Populate with available IPs

        self.start_button = QtWidgets.QPushButton("Start Server", self)
        self.start_button.clicked.connect(self.start_server)

        self.stop_button = QtWidgets.QPushButton("Stop Server", self)
        self.stop_button.clicked.connect(self.stop_server)
        self.stop_button.setEnabled(False)

        self.status_label = QtWidgets.QLabel("Server Status: Stopped", self)
        # We'll change status_label colors dynamically as needed.

        self.port_input = QtWidgets.QSpinBox(self)
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(69)
        self.port_label = QtWidgets.QLabel("Port:", self)

        self.dir_label = QtWidgets.QLabel(f"Current Directory: {self.current_directory}", self)

        self.browse_button = QtWidgets.QPushButton("Change Directory", self)
        self.browse_button.clicked.connect(self.change_directory)

        self.view_dir_button = QtWidgets.QPushButton("View Directory Contents", self)
        self.view_dir_button.clicked.connect(self.view_directory)

        self.log_output = QtWidgets.QTextEdit(self)
        self.log_output.setReadOnly(True)

        # Layout
        layout = QtWidgets.QVBoxLayout()

        layout.addWidget(QtWidgets.QLabel("Select Server IP:"))
        layout.addWidget(self.ip_combo)

        port_layout = QtWidgets.QHBoxLayout()
        port_layout.addWidget(self.port_label)
        port_layout.addWidget(self.port_input)
        layout.addLayout(port_layout)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.start_button)
        button_layout.addWidget(self.stop_button)
        layout.addLayout(button_layout)

        layout.addWidget(self.status_label)
        layout.addWidget(self.dir_label)
        layout.addWidget(self.browse_button)
        layout.addWidget(self.view_dir_button)
        layout.addWidget(QtWidgets.QLabel("Server Log:"))
        layout.addWidget(self.log_output)

        self.setLayout(layout)

    def start_server(self):
        if not self.server:
            port = self.port_input.value()
            ip_address = self.ip_combo.currentText()  # Get selected IP from dropdown
            self.server = TftpServer(self.current_directory)  # Use current directory
            threading.Thread(target=self.server.listen, args=(ip_address, port), daemon=True).start()
            self.status_label.setText("Server Status: Running")
            self.status_label.setStyleSheet("font-weight: bold; color: green;")
            self.start_button.setEnabled(False)
            self.stop_button.setEnabled(True)

            # Redirect logs to the text output
            logger.addHandler(TextHandler(self.log_output))

    def stop_server(self):
        if self.server:
            self.server.stop()
            self.server = None
            self.status_label.setText("Server Status: Stopped")
            self.status_label.setStyleSheet("font-weight: bold; color: red;")
            self.start_button.setEnabled(True)
            self.stop_button.setEnabled(False)

    def change_directory(self):
        new_dir = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Directory", self.current_directory)
        if new_dir:
            self.current_directory = new_dir
            self.dir_label.setText(f"Current Directory: {self.current_directory}")
            if self.server:
                self.server.root = self.current_directory  # Update server root

    def view_directory(self):
        self.dir_window = DirectoryView(self.current_directory)
        self.dir_window.show()


class TextHandler(logging.Handler):
    """Custom logging handler to write logs to a QTextEdit."""
    def __init__(self, text_edit):
        super().__init__()
        self.text_edit = text_edit

    def emit(self, record):
        msg = self.format(record)
        self.text_edit.append(msg)


class DirectoryView(QtWidgets.QDialog):
    def __init__(self, directory):
        super().__init__()
        self.setWindowTitle("Directory Contents")
        self.setGeometry(200, 200, 400, 300)

        self.directory = directory

        self.file_list = QtWidgets.QListWidget(self)
        self.load_directory_contents()

        self.copy_button = QtWidgets.QPushButton("Copy Selected Name", self)
        self.copy_button.clicked.connect(self.copy_selected_name)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.file_list)
        layout.addWidget(self.copy_button)

        self.setLayout(layout)

    def load_directory_contents(self):
        self.file_list.clear()
        for item in os.listdir(self.directory):
            self.file_list.addItem(item)

    def copy_selected_name(self):
        selected_items = self.file_list.selectedItems()
        if selected_items:
            file_name = selected_items[0].text()
            QtWidgets.QApplication.clipboard().setText(file_name)
            QtWidgets.QMessageBox.information(self, "Copy Name", f"Copied: {file_name}")


class TFTPClient(QtWidgets.QWidget):
    log_signal = QtCore.pyqtSignal(str)  # Signal to update log

    def __init__(self):
        super().__init__()
        self.setWindowTitle("TFTP Client")
        self.setGeometry(500, 100, 500, 400)

        self.ip_input = QtWidgets.QLineEdit(self)
        self.ip_input.setPlaceholderText("Enter Server IP Address")

        # Separate inputs for upload and download
        self.upload_file_input = QtWidgets.QLineEdit(self)
        self.upload_file_input.setPlaceholderText("Select File to Upload")

        self.download_file_input = QtWidgets.QLineEdit(self)
        self.download_file_input.setPlaceholderText("Enter File Name to Download")

        self.browse_button = QtWidgets.QPushButton("Browse Upload...", self)
        self.browse_button.clicked.connect(self.browse_upload_file)

        self.download_button = QtWidgets.QPushButton("Download File", self)
        self.download_button.clicked.connect(self.download_file)

        self.upload_button = QtWidgets.QPushButton("Upload File", self)
        self.upload_button.clicked.connect(self.upload_file)

        self.use_folder_checkbox = QtWidgets.QCheckBox("Use selected folder for download", self)
        self.use_folder_checkbox.setChecked(False)  # Default unchecked

        self.default_directory_label = QtWidgets.QLabel(self)
        self.default_directory_label.setText(f"Default Download Directory: {self.get_default_directory()}")

        self.status_label = QtWidgets.QLabel("Status: Waiting", self)
        self.status_label.setStyleSheet("font-weight: bold;")

        self.log_output = QtWidgets.QTextEdit(self)
        self.log_output.setReadOnly(True)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(QtWidgets.QLabel("Enter Server IP Address:"))
        layout.addWidget(self.ip_input)

        # Upload file section
        layout.addWidget(QtWidgets.QLabel("File to Upload:"))
        layout.addWidget(self.upload_file_input)
        layout.addWidget(self.browse_button)

        # Download file section
        layout.addWidget(QtWidgets.QLabel("File to Download:"))
        layout.addWidget(self.download_file_input)
        layout.addWidget(self.use_folder_checkbox)  # Add the checkbox here

        # Add the default directory label
        layout.addWidget(self.default_directory_label)

        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addWidget(self.download_button)
        button_layout.addWidget(self.upload_button)
        button_layout.addWidget(self.status_label)
        layout.addLayout(button_layout)

        layout.addWidget(QtWidgets.QLabel("Client Log:"))
        layout.addWidget(self.log_output)

        self.setLayout(layout)

        self.total_size = 0
        self.downloaded_size = 0

        # Connect the log signal to the update_log method
        self.log_signal.connect(self.update_log)

    def get_default_directory(self):
        """Return the default download directory."""
        return os.path.expanduser("~")  # User's home directory

    def browse_upload_file(self):
        options = QtWidgets.QFileDialog.Options()
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Select File to Upload", "", "All Files (*);;Text Files (*.txt)", options=options)
        if file_name:
            self.upload_file_input.setText(file_name)  # Save the full path for the selected file

    def download_file(self):
        ip = self.ip_input.text()  # Get the manually entered IP address
        filename = self.download_file_input.text()

        if self.use_folder_checkbox.isChecked():
            # Open a dialog to select the folder for saving the downloaded file
            folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Select Folder to Save Downloaded File")

            if folder:  # Proceed only if a folder was selected
                self.status_label.setText("Status: Downloading...")
                self.log_output.clear()  # Clear previous logs

                # Construct the full path for the downloaded file
                full_path = os.path.join(folder, filename)

                # Start a new thread for downloading to avoid blocking the UI
                threading.Thread(target=self.perform_download, args=(ip, full_path), daemon=True).start()
            else:
                self.log_signal.emit("Download canceled: No folder selected.")
        else:
            # Default save path
            default_directory = self.get_default_directory()
            full_path = os.path.join(default_directory, filename)

            self.status_label.setText("Status: Downloading...")
            self.log_output.clear()  # Clear previous logs

            # Start a new thread for downloading to avoid blocking the UI
            threading.Thread(target=self.perform_download, args=(ip, full_path), daemon=True).start()

    def perform_download(self, ip, full_path):
        try:
            client = TftpClient(ip, 69)

            # Get total file size
            self.total_size = client.get_file_size(os.path.basename(full_path))
            if self.total_size <= 0:
                self.status_label.setText("Error: Invalid file size.")
                self.log_signal.emit("Error: Invalid file size.")
                return

            # Function to update progress
            def update_progress(packet):
                if isinstance(packet, TftpPacketERR):
                    self.log_signal.emit(f"Error: {packet.errmsg.decode()}")
                    return
                # Check for DAT packets (data packets)
                if isinstance(packet, TftpPacketDAT):
                    self.downloaded_size += len(packet.data)
                    self.log_signal.emit(f"Downloaded: {self.downloaded_size} bytes")

            # Start downloading with the update_progress callback
            client.download(os.path.basename(full_path), output=full_path, packethook=update_progress)

            self.status_label.setText("Status: Download Complete")
            self.log_signal.emit("Download complete.")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.log_signal.emit(f"Error: {str(e)}")

    def upload_file(self):
        ip = self.ip_input.text()  # Get the manually entered IP address
        filename = self.upload_file_input.text()
        self.status_label.setText("Status: Uploading...")
        self.log_output.clear()  # Clear previous logs

        # Start a new thread for uploading to avoid blocking the UI
        threading.Thread(target=self.perform_upload, args=(ip, filename), daemon=True).start()

    def perform_upload(self, ip, filename):
        try:
            client = TftpClient(ip, 69)

            # Get total file size
            self.total_size = os.path.getsize(filename)
            self.downloaded_size = 0  # Reset downloaded size

            # Function to update progress
            def update_progress(packet):
                if isinstance(packet, TftpPacketERR):
                    self.log_signal.emit(f"Error: {packet.errmsg.decode()}")
                    return

                # Check for DAT packets (data packets)
                if isinstance(packet, TftpPacketDAT):
                    self.downloaded_size += len(packet.data)
                    self.log_signal.emit(f"Uploaded: {self.downloaded_size} bytes")

            # Start uploading with the update_progress callback
            with open(filename, 'rb') as f:
                client.upload(os.path.basename(filename), input=f, packethook=update_progress)

            self.status_label.setText("Status: Upload Complete")
            self.log_signal.emit("Upload complete.")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            self.log_signal.emit(f"Error: {str(e)}")

    def update_log(self, message):
        self.log_output.append(message)
        self.log_output.moveCursor(QtGui.QTextCursor.End)


class MainApp(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("TFTP Client/Server by petrunetworking")
        self.setGeometry(100, 100, 800, 500)

        # Create tabs
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.addTab(TFTPServer(), "TFTP Server")
        self.tab_widget.addTab(TFTPClient(), "TFTP Client")

        # Theme selection
        self.light_theme_radio = QtWidgets.QRadioButton("Light Theme")
        self.dark_theme_radio = QtWidgets.QRadioButton("Dark Theme")
        self.light_theme_radio.setChecked(True)  # Default to Light theme

        self.light_theme_radio.toggled.connect(self.on_theme_changed)
        self.dark_theme_radio.toggled.connect(self.on_theme_changed)

        theme_layout = QtWidgets.QHBoxLayout()
        theme_layout.addWidget(self.light_theme_radio)
        theme_layout.addWidget(self.dark_theme_radio)
        theme_layout.addStretch()

        main_layout = QtWidgets.QVBoxLayout()
        main_layout.addLayout(theme_layout)
        main_layout.addWidget(self.tab_widget)

        self.setLayout(main_layout)

        # Apply the default (light) theme initially
        self.apply_theme("light")

    def on_theme_changed(self):
        if self.light_theme_radio.isChecked():
            self.apply_theme("light")
        else:
            self.apply_theme("dark")

    def apply_theme(self, theme):
        if theme == "light":
            # Light theme stylesheet
            qss = """
            QWidget {
                background-color: #eaeaea;
                color: #000000;
                font-family: Arial;
            }
            QPushButton {
                background-color: #f0f0f0;
                color: #000000;
            }
            QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget {
                background-color: #ffffff;
                color: #000000;
            }
            QLabel {
                color: #000000;
            }
            QTabWidget::pane {
                border: 1px solid #cccccc;
            }
            """
        else:
            # Dark theme stylesheet
            qss = """
            QWidget {
                background-color: #2e2e2e;
                color: #ffffff;
                font-family: Arial;
            }
            QPushButton {
                background-color: #4f4f4f;
                color: #ffffff;
            }
            QLineEdit, QSpinBox, QComboBox, QTextEdit, QListWidget {
                background-color: #3c3c3c;
                color: #ffffff;
            }
            QLabel {
                color: #ffffff;
            }
            QTabWidget::pane {
                border: 1px solid #555555;
            }
            """

        # Apply the stylesheet to the entire application
        QtWidgets.QApplication.instance().setStyleSheet(qss)


if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    main_app = MainApp()
    main_app.show()
    sys.exit(app.exec_())
