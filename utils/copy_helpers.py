"""Utility helpers to enable selectable text copy, clipboard management, and Excel-compatible visual order grids exports."""

from PySide6.QtCore import Qt, QObject, QEvent
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication, QLabel, QTableWidget, QMenu, QAbstractItemView, QMainWindow,
    QTextBrowser, QPlainTextEdit, QTextEdit
)


_label_filter = None


class LabelCopyEventFilter(QObject):
    """Event filter for QLabels to copy entire label text to clipboard instantly on double click or keyboard Ctrl+C."""

    def eventFilter(self, obj, event):
        if isinstance(obj, QLabel):
            if event.type() == QEvent.MouseButtonDblClick:
                copy_to_clipboard(obj.text())
                show_status_message(obj, "Copied text to clipboard")
                return True
            elif event.type() == QEvent.KeyPress:
                key_event = event
                if key_event.matches(QKeySequence.Copy):
                    copy_to_clipboard(obj.text())
                    show_status_message(obj, "Copied text to clipboard")
                    return True
        return super().eventFilter(obj, event)


def enable_label_selection(label: QLabel, links: bool = True):
    """Enable text selection on a QLabel with mouse/keyboard, keyboard focus, and copy shortcut listeners."""
    global _label_filter
    flags = Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard
    if links:
        flags |= Qt.LinksAccessibleByMouse | Qt.LinksAccessibleByKeyboard
    label.setTextInteractionFlags(flags)
    label.setFocusPolicy(Qt.ClickFocus)

    # Initialize and attach the double-click event filter
    if _label_filter is None:
        _label_filter = LabelCopyEventFilter(QApplication.instance())
    label.installEventFilter(_label_filter)


def enable_selection_recursive(widget):
    """Recursively search a widget layout tree and enable selection + copy event filters on all QLabels."""
    if isinstance(widget, QLabel):
        enable_label_selection(widget)
    for child in widget.findChildren(QLabel):
        enable_label_selection(child)


def copy_to_clipboard(text: str):
    """Write Unicode/Emoji/Tabbed multiline string values to the system clipboard."""
    if not text:
        return
    clipboard = QApplication.clipboard()
    if clipboard:
        clipboard.setText(text)


def show_status_message(widget, message: str):
    """Find the top-level QMainWindow of the widget and show a temporary message on its status bar."""
    window = widget.window()
    if window and hasattr(window, "statusBar") and window.statusBar() is not None:
        window.statusBar().showMessage(message, 3000)


def get_visible_columns(table: QTableWidget) -> list[int]:
    """Return indices of columns in current visual order, skipping hidden columns."""
    header = table.horizontalHeader()
    cols = []
    for c in range(table.columnCount()):
        if not table.isColumnHidden(c):
            cols.append((header.visualIndex(c), c))
    cols.sort()
    return [c[1] for c in cols]


def get_visible_rows(table: QTableWidget) -> list[int]:
    """Return indices of rows, skipping hidden rows (filters)."""
    rows = []
    for r in range(table.rowCount()):
        if not table.isRowHidden(r):
            rows.append(r)
    return rows


def get_table_selection_text(table: QTableWidget) -> str:
    """Consolidate the current table selection ranges into tab-separated column, newline-separated row clipboard format."""
    ranges = table.selectedRanges()
    if not ranges:
        return ""

    visible_cols = get_visible_columns(table)
    visible_rows = get_visible_rows(table)
    visible_rows_set = set(visible_rows)
    visible_cols_set = set(visible_cols)

    selected_rows = set()
    selected_cols = set()

    for r in ranges:
        for row in range(r.topRow(), r.bottomRow() + 1):
            if row in visible_rows_set:
                selected_rows.add(row)
        for col in range(r.leftColumn(), r.rightColumn() + 1):
            if col in visible_cols_set:
                selected_cols.add(col)

    sorted_rows = sorted(list(selected_rows))
    sorted_cols = sorted(list(selected_cols), key=lambda c: table.horizontalHeader().visualIndex(c))

    if not sorted_rows or not sorted_cols:
        return ""

    lines = []
    for r in sorted_rows:
        row_cells = []
        row_has_selection = False
        for c in sorted_cols:
            is_selected = False
            for r_range in ranges:
                if r_range.topRow() <= r <= r_range.bottomRow() and r_range.leftColumn() <= c <= r_range.rightColumn():
                    is_selected = True
                    break
            if is_selected:
                item = table.item(r, c)
                row_cells.append(item.text() if item else "")
                row_has_selection = True
            else:
                row_cells.append("")
        if row_has_selection:
            lines.append("\t".join(row_cells))
    return "\n".join(lines)


def get_entire_row_text(table: QTableWidget) -> str:
    """Format all cells of selected rows as tab-separated clipboard lines."""
    ranges = table.selectedRanges()
    if not ranges:
        return ""

    visible_cols = get_visible_columns(table)
    visible_rows = get_visible_rows(table)
    visible_rows_set = set(visible_rows)

    selected_rows = set()
    for r in ranges:
        for row in range(r.topRow(), r.bottomRow() + 1):
            if row in visible_rows_set:
                selected_rows.add(row)

    sorted_rows = sorted(list(selected_rows))
    if not sorted_rows:
        return ""

    lines = []
    for r in sorted_rows:
        row_cells = []
        for c in visible_cols:
            item = table.item(r, c)
            row_cells.append(item.text() if item else "")
        lines.append("\t".join(row_cells))
    return "\n".join(lines)


def get_entire_table_text(table: QTableWidget) -> str:
    """Format the entire table including header titles as a tab-separated text block."""
    visible_cols = get_visible_columns(table)
    visible_rows = get_visible_rows(table)

    lines = []
    headers = []
    for c in visible_cols:
        header_item = table.horizontalHeaderItem(c)
        headers.append(header_item.text() if header_item else f"Column {c+1}")
    lines.append("\t".join(headers))

    for r in visible_rows:
        row_cells = []
        for c in visible_cols:
            item = table.item(r, c)
            row_cells.append(item.text() if item else "")
        lines.append("\t".join(row_cells))
    return "\n".join(lines)


def copy_table_selection(table: QTableWidget):
    """Copy the selected grid cell range to clipboard, preserving visual order, and skip hidden cells."""
    text = get_table_selection_text(table)
    if text:
        copy_to_clipboard(text)
        lines = text.split("\n")
        cell_count = sum(len(line.split("\t")) for line in lines if line)
        row_count = len(lines)
        if row_count > 1:
            show_status_message(table, f"Copied {row_count} rows ({cell_count} cells)")
        else:
            show_status_message(table, f"Copied {cell_count} cells")


def copy_single_cell(table: QTableWidget):
    """Copy the value of the active cell or first selected cell."""
    ranges = table.selectedRanges()
    if not ranges:
        return
    r = ranges[0].topRow()
    c = ranges[0].leftColumn()
    if not table.isRowHidden(r) and not table.isColumnHidden(c):
        item = table.item(r, c)
        copy_to_clipboard(item.text() if item else "")
        show_status_message(table, "Copied cell value")


def copy_table_rows(table: QTableWidget):
    """Copy entire visible rows for the currently selected row set."""
    text = get_entire_row_text(table)
    if text:
        copy_to_clipboard(text)
        row_count = len(text.split("\n"))
        show_status_message(table, f"Copied {row_count} rows")


def copy_table_columns(table: QTableWidget):
    """Copy entire columns for currently selected column set across all visible rows."""
    ranges = table.selectedRanges()
    if not ranges:
        return

    visible_cols = get_visible_columns(table)
    visible_rows = get_visible_rows(table)
    visible_cols_set = set(visible_cols)

    selected_cols = set()
    for r in ranges:
        for col in range(r.leftColumn(), r.rightColumn() + 1):
            if col in visible_cols_set:
                selected_cols.add(col)

    sorted_cols = sorted(list(selected_cols), key=lambda c: table.horizontalHeader().visualIndex(c))
    if not sorted_cols:
        return

    lines = []
    for r in visible_rows:
        row_cells = []
        for c in sorted_cols:
            item = table.item(r, c)
            row_cells.append(item.text() if item else "")
        lines.append("\t".join(row_cells))

    copy_to_clipboard("\n".join(lines))
    show_status_message(table, f"Copied {len(sorted_cols)} columns")


def copy_entire_table(table: QTableWidget, with_headers: bool = False):
    """Copy all visible rows and columns, optionally including column headers."""
    if with_headers:
        text = get_entire_table_text(table)
    else:
        visible_cols = get_visible_columns(table)
        visible_rows = get_visible_rows(table)
        lines = []
        for r in visible_rows:
            row_cells = []
            for c in visible_cols:
                item = table.item(r, c)
                row_cells.append(item.text() if item else "")
            lines.append("\t".join(row_cells))
        text = "\n".join(lines)

    if text:
        copy_to_clipboard(text)
        rows_count = len(get_visible_rows(table))
        msg = f"Copied table with headers ({rows_count} rows)" if with_headers else f"Copied table without headers ({rows_count} rows)"
        show_status_message(table, msg)


def setup_table_copy(table: QTableWidget):
    """Enable right-click rich context menus, keyboard shortcuts (Ctrl+C, Ctrl+A), and cell double-click selection behaviors on a QTableWidget."""
    # Excel-like selection behaviors
    table.setEditTriggers(QAbstractItemView.NoEditTriggers)
    table.setSelectionMode(QAbstractItemView.ExtendedSelection)
    table.setSelectionBehavior(QAbstractItemView.SelectItems)
    
    # Configure custom context menu
    table.setContextMenuPolicy(Qt.CustomContextMenu)

    def show_context_menu(pos):
        ranges = table.selectedRanges()
        has_selection = len(ranges) > 0

        menu = QMenu(table)
        
        # 1. Standard copy option (maps to cell selection)
        copy_action = QAction("Copy", menu)
        copy_action.setShortcut(QKeySequence.Copy)
        copy_action.setEnabled(has_selection)
        copy_action.triggered.connect(lambda: copy_table_selection(table))
        menu.addAction(copy_action)

        # 2. Segmented copy options
        copy_sel = QAction("Copy Selected Cells", menu)
        copy_sel.setEnabled(has_selection)
        copy_sel.triggered.connect(lambda: copy_table_selection(table))
        menu.addAction(copy_sel)

        copy_cell = QAction("Copy Cell", menu)
        copy_cell.setEnabled(has_selection)
        copy_cell.triggered.connect(lambda: copy_single_cell(table))
        menu.addAction(copy_cell)

        copy_row = QAction("Copy Row", menu)
        copy_row.setEnabled(has_selection)
        copy_row.triggered.connect(lambda: copy_table_rows(table))
        menu.addAction(copy_row)

        copy_col = QAction("Copy Column", menu)
        copy_col.setEnabled(has_selection)
        copy_col.triggered.connect(lambda: copy_table_columns(table))
        menu.addAction(copy_col)

        menu.addSeparator()

        # 3. Whole table copy options
        copy_all = QAction("Copy Entire Table", menu)
        copy_all.triggered.connect(lambda: copy_entire_table(table, with_headers=False))
        menu.addAction(copy_all)

        copy_headers = QAction("Copy Table With Headers", menu)
        copy_headers.triggered.connect(lambda: copy_entire_table(table, with_headers=True))
        menu.addAction(copy_headers)

        menu.exec(table.viewport().mapToGlobal(pos))

    table.customContextMenuRequested.connect(show_context_menu)

    # Keyboard Shortcuts (Automatically map natively to Cmd+C / Cmd+A on macOS and Ctrl+C / Ctrl+A on Windows/Linux)
    copy_shortcut = QShortcut(QKeySequence.Copy, table)
    copy_shortcut.activated.connect(lambda: copy_table_selection(table))

    select_all_shortcut = QShortcut(QKeySequence.SelectAll, table)
    select_all_shortcut.activated.connect(table.selectAll)

    # Double click selects just that cell visual index
    table.doubleClicked.connect(lambda index: table.setCurrentIndex(index))


def setup_readonly_text_copy(widget):
    """Configure a text edit or browser to act as a read-only container with copy context menus and shortcuts."""
    if isinstance(widget, (QTextBrowser, QTextEdit, QPlainTextEdit)):
        widget.setReadOnly(True)
        widget.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.TextSelectableByKeyboard)
        widget.setContextMenuPolicy(Qt.CustomContextMenu)

        def show_text_context_menu(pos):
            menu = widget.createStandardContextMenu(pos)
            menu.exec(widget.viewport().mapToGlobal(pos))

        widget.customContextMenuRequested.connect(show_text_context_menu)
