"""Embedded PDF preview window for viewing generated wage slips in-app."""

import os
import platform
import subprocess
from pathlib import Path

from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QMessageBox
from PySide6.QtCore import Qt

try:
    from PySide6.QtPdf import QPdfDocument
    from PySide6.QtPdfWidgets import QPdfView
    PDF_VIEWER_AVAILABLE = True
except ImportError:
    PDF_VIEWER_AVAILABLE = False


def open_file_in_default_viewer(file_path: str):
    """Open a file using the operating system's default handler."""
    try:
        if platform.system() == "Windows":
            os.startfile(file_path)
        elif platform.system() == "Darwin":  # macOS
            subprocess.Popen(["open", file_path])
        else:  # Linux
            subprocess.Popen(["xdg-open", file_path])
    except Exception as e:
        QMessageBox.warning(None, "Could Not Open File", f"Failed to open {file_path}:\n{str(e)}")


class PdfPreviewDialog(QDialog):
    """Dialogue containing scrollable PDF render view and print controls."""

    def __init__(self, pdf_path: str, parent=None):
        super().__init__(parent)
        self.pdf_path = pdf_path
        self.setWindowTitle("Wage Slip PDF Viewer")
        self.resize(750, 800)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 15, 15, 15)
        layout.setSpacing(15)

        # Toolbar Row
        toolbar = QHBoxLayout()
        
        self.open_sys_btn = QPushButton("Open in OS Viewer")
        self.open_sys_btn.clicked.connect(self.open_in_system)
        toolbar.addWidget(self.open_sys_btn)

        self.copy_path_btn = QPushButton("Copy PDF Path")
        self.copy_path_btn.clicked.connect(self.copy_path)
        toolbar.addWidget(self.copy_path_btn)

        self.copy_name_btn = QPushButton("Copy File Name")
        self.copy_name_btn.clicked.connect(self.copy_file_name)
        toolbar.addWidget(self.copy_name_btn)

        self.copy_loc_btn = QPushButton("Copy File Location")
        self.copy_loc_btn.clicked.connect(self.copy_file_location)
        toolbar.addWidget(self.copy_loc_btn)

        self.open_folder_btn = QPushButton("Open Containing Folder")
        self.open_folder_btn.clicked.connect(self.open_parent_folder)
        toolbar.addWidget(self.open_folder_btn)

        toolbar.addStretch()

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.accept)
        toolbar.addWidget(self.close_btn)
        
        layout.addLayout(toolbar)

        from utils.copy_helpers import enable_label_selection, copy_to_clipboard

        # Embedded PDF view or fallback
        if PDF_VIEWER_AVAILABLE and os.path.exists(self.pdf_path):
            self.document = QPdfDocument(self)
            self.document.load(self.pdf_path)

            self.view = QPdfView(self)
            self.view.setDocument(self.document)
            self.view.setPageMode(QPdfView.PageMode.SinglePage)
            
            # Enable text selection inside view if supported
            try:
                self.view.setSelectionMode(QPdfView.SelectionMode.Text)
            except Exception:
                pass
                
            layout.addWidget(self.view)
        else:
            # Fallback when plugins missing or path incorrect
            fallback_layout = QVBoxLayout()
            fallback_layout.setAlignment(Qt.AlignCenter)
            
            lbl = QLabel("Embedded PDF viewer is not active on this platform.")
            lbl.setStyleSheet("font-weight: bold; color: #a1a1aa;")
            lbl.setAlignment(Qt.AlignCenter)
            
            path_lbl = QLabel(f"File Path: {self.pdf_path}")
            path_lbl.setWordWrap(True)
            path_lbl.setStyleSheet("color: #71717a; font-family: monospace;")
            path_lbl.setAlignment(Qt.AlignCenter)
            enable_label_selection(path_lbl)
            
            fallback_layout.addWidget(lbl)
            fallback_layout.addWidget(path_lbl)
            layout.addLayout(fallback_layout)
            
            # Automatically try to launch system default viewer
            if os.path.exists(self.pdf_path):
                open_file_in_default_viewer(self.pdf_path)

        # Metadata Row (Selectable)
        self.meta_lbl = QLabel()
        self.meta_lbl.setObjectName("pdfMetaLabel")
        self.meta_lbl.setWordWrap(True)
        
        meta_text = f"File Path: {self.pdf_path}"
        if PDF_VIEWER_AVAILABLE and os.path.exists(self.pdf_path):
            meta_text += f" | Pages: {self.document.pageCount()}"
            try:
                title = self.document.metaData(QPdfDocument.MetaDataField.Title)
                if title:
                    meta_text += f" | Title: {title}"
            except Exception:
                pass
                
        self.meta_lbl.setText(meta_text)
        enable_label_selection(self.meta_lbl)
        layout.addWidget(self.meta_lbl)

    def copy_path(self):
        """Copy PDF file path to clipboard."""
        from utils.copy_helpers import copy_to_clipboard
        copy_to_clipboard(self.pdf_path)

    def copy_file_name(self):
        """Copy PDF file name to clipboard."""
        from utils.copy_helpers import copy_to_clipboard
        copy_to_clipboard(Path(self.pdf_path).name)

    def copy_file_location(self):
        """Copy containing folder path to clipboard."""
        from utils.copy_helpers import copy_to_clipboard
        copy_to_clipboard(str(Path(self.pdf_path).parent))

    def open_in_system(self):
        """Trigger opening in the OS default viewer."""
        if os.path.exists(self.pdf_path):
            open_file_in_default_viewer(self.pdf_path)
        else:
            QMessageBox.critical(self, "Error", "PDF file does not exist on disk.")

    def open_parent_folder(self):
        """Open the enclosing folder in the OS file explorer."""
        parent_dir = str(Path(self.pdf_path).parent)
        if os.path.exists(parent_dir):
            open_file_in_default_viewer(parent_dir)
        else:
            QMessageBox.critical(self, "Error", "Parent folder does not exist.")
