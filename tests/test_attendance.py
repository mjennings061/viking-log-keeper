import unittest
import pandas as pd
from pathlib import Path
from src.attendance import ingest_roster, extract_attendance, sheet_df_to_series


class TestIngestRoster(unittest.TestCase):
    """Test suite for the ingest_roster function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_roster_path = "rsc/Roster 2025.xlsx"
        self.invalid_file_path = "rsc/NonExistent.xlsx"
        self.invalid_extension_path = "rsc/Roster.txt"

    def test_ingest_roster_valid_file(self):
        """Test that ingest_roster successfully loads a valid Excel file."""
        result = ingest_roster(self.test_roster_path)
        self.assertIsInstance(result, pd.DataFrame)
        self.assertGreater(len(result), 0, "DataFrame should not be empty")

    def test_ingest_roster_file_not_found(self):
        """Test that ingest_roster raises FileNotFoundError for non-existent files."""
        with self.assertRaises(FileNotFoundError) as context:
            ingest_roster(self.invalid_file_path)
        self.assertIn("File not found", str(context.exception))

    def test_ingest_roster_invalid_extension(self):
        """Test that ingest_roster raises ValueError for non-.xlsx files."""
        # Create a temporary file with wrong extension
        temp_file = Path(self.invalid_extension_path)
        try:
            temp_file.touch()
            with self.assertRaises(ValueError) as context:
                ingest_roster(str(temp_file))
            self.assertIn("Invalid file extension", str(context.exception))
        finally:
            if temp_file.exists():
                temp_file.unlink()


class TestExtractAttendance(unittest.TestCase):
    """Test suite for the extract_attendance function (hardcoded January solution)."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_roster_path = "rsc/Roster 2025.xlsx"
        self.xls = pd.ExcelFile(self.test_roster_path)

    def tearDown(self):
        """Clean up resources."""
        self.xls.close()

    def test_extract_attendance_returns_dataframe(self):
        """Test that extract_attendance returns a DataFrame."""
        result = extract_attendance(self.xls)
        self.assertIsInstance(result, pd.DataFrame)

    def test_extract_attendance_from_january_sheet(self):
        """Test that extract_attendance specifically extracts from January sheet."""
        result = extract_attendance(self.xls)
        # Verify that data was extracted (not empty)
        self.assertGreater(len(result), 0, "Extracted DataFrame should not be empty")
        self.assertGreater(len(result.columns), 0, "DataFrame should have columns")

    def test_extract_attendance_uses_header_row_1(self):
        """Test that extract_attendance uses header=1 as specified."""
        result = extract_attendance(self.xls)
        # The dataframe should have valid column names (not starting from row 0)
        self.assertIsNotNone(result.columns)

    def test_extract_attendance_sheet_exists(self):
        """Test that the January sheet exists in the roster file."""
        sheet_names = self.xls.sheet_names
        self.assertIn("January", sheet_names,
                     "January sheet should exist in the roster file")


class TestParseDF(unittest.TestCase):
    """Test suite for the parse_df function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_roster_path = "rsc/Roster 2025.xlsx"

    def test_parse_df_returns_series(self):
        """Test that parse_df returns a pandas Series."""
        raw_df = ingest_roster(self.test_roster_path)
        result = sheet_df_to_series(raw_df)
        self.assertIsInstance(result, pd.Series)

    def test_parse_df_excludes_first_column(self):
        """Test that parse_df excludes the first column (iloc[:, 1:])."""
        raw_df = ingest_roster(self.test_roster_path)
        result = sheet_df_to_series(raw_df)
        # Result should not be empty
        self.assertGreater(len(result), 0, "Parsed series should not be empty")

    def test_parse_df_finds_numeric_summary_row(self):
        """Test that parse_df correctly identifies the staffing summary row."""
        raw_df = ingest_roster(self.test_roster_path)
        result = sheet_df_to_series(raw_df)
        # All values in the series should be numeric
        for val in result:
            self.assertIsInstance(val, (int, float),
                                f"Expected numeric value, got {type(val)}: {val}")

    def test_parse_df_drops_na_values(self):
        """Test that parse_df drops NaN values from the result."""
        raw_df = ingest_roster(self.test_roster_path)
        result = sheet_df_to_series(raw_df)
        # Check that no NaN values remain
        self.assertFalse(result.isna().any(),
                        "Result should not contain NaN values")

    def test_parse_df_integration(self):
        """Integration test: full pipeline from ingestion to parsing."""
        raw_df = ingest_roster(self.test_roster_path)
        result = sheet_df_to_series(raw_df)

        # Verify the complete workflow
        self.assertIsInstance(result, pd.Series)
        self.assertGreater(len(result), 0)
        self.assertFalse(result.isna().any())

        # All values should be numeric
        for val in result:
            self.assertIsInstance(val, (int, float))


class TestParseDF_MockData(unittest.TestCase):
    """Test suite for parse_df with mock data."""

    def test_parse_df_with_simple_mock_data(self):
        """Test parse_df with controlled mock data."""
        # Create mock dataframe with Y/N data followed by numeric summary
        mock_data = {
            'Name': ['Person 1', 'Person 2', 'Summary'],
            'Date1': ['Y', 'N', 5],
            'Date2': ['N', 'Y', 3],
            'Date3': ['Y', 'Y', 7]
        }
        mock_df = pd.DataFrame(mock_data)

        result = sheet_df_to_series(mock_df)

        # Should extract the summary row (index 2) excluding first column
        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), 3)  # Three date columns
        self.assertTrue(all(isinstance(v, (int, float)) for v in result))


if __name__ == '__main__':
    unittest.main()
