"""Unit tests for clipboard copy helpers and QTableWidget conversion methods."""

import unittest
from PySide6.QtWidgets import QApplication, QTableWidget, QTableWidgetItem, QTableWidgetSelectionRange
from utils.copy_helpers import get_table_selection_text, get_entire_row_text, get_entire_table_text


class TestCopyHelpers(unittest.TestCase):
    """Verifies that the Excel-compatible grid copy functions correctly parse and format spreadsheet outputs."""

    @classmethod
    def setUpClass(cls):
        # Initialize QApplication singleton if not already active to support widget instances
        cls.app = QApplication.instance()
        if cls.app is None:
            cls.app = QApplication([])

    def setUp(self):
        # Construct a mock 3x3 table widget for parsing test operations
        self.table = QTableWidget(3, 3)
        self.table.setHorizontalHeaderLabels(["Col A", "Col B", "Col C"])
        
        # Populate table
        for r in range(3):
            for c in range(3):
                item = QTableWidgetItem(f"Val_{r}_{c}")
                self.table.setItem(r, c, item)

    def test_copy_single_cell_selection(self):
        # Select single cell
        self.table.clearSelection()
        self.table.setRangeSelected(QTableWidgetSelectionRange(1, 1, 1, 1), True)
        
        text = get_table_selection_text(self.table)
        self.assertEqual(text, "Val_1_1")

    def test_copy_rectangular_selection(self):
        # Select 2x2 area
        self.table.clearSelection()
        self.table.setRangeSelected(QTableWidgetSelectionRange(0, 0, 1, 1), True)
        
        text = get_table_selection_text(self.table)
        expected = "Val_0_0\tVal_0_1\nVal_1_0\tVal_1_1"
        self.assertEqual(text, expected)

    def test_copy_entire_row_selection(self):
        # Select row 1
        self.table.clearSelection()
        self.table.setRangeSelected(QTableWidgetSelectionRange(1, 0, 1, 2), True)
        
        text = get_entire_row_text(self.table)
        expected = "Val_1_0\tVal_1_1\tVal_1_2"
        self.assertEqual(text, expected)

    def test_copy_entire_table_with_headers(self):
        text = get_entire_table_text(self.table)
        expected_lines = [
            "Col A\tCol B\tCol C",
            "Val_0_0\tVal_0_1\tVal_0_2",
            "Val_1_0\tVal_1_1\tVal_1_2",
            "Val_2_0\tVal_2_1\tVal_2_2"
        ]
        expected = "\n".join(expected_lines)
        self.assertEqual(text, expected)


if __name__ == "__main__":
    unittest.main()
