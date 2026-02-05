import unittest
import pandas as pd
from pathlib import Path
from dashboard.attendance import xls_to_dataframe, extract_attendance, sheet_df_to_series, clean_data


class TestIngestRoster(unittest.TestCase):
    """Test suite for the ingest_roster function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_roster_path = "rsc/Roster 2025.xlsx"
        self.invalid_file_path = "rsc/NonExistent.xlsx"
        self.invalid_extension_path = "rsc/Roster.txt"

    def test_ingest_roster_valid_file(self):
        """Test that ingest_roster successfully loads a valid Excel file."""
        result = xls_to_dataframe(self.test_roster_path)
        self.assertIsInstance(result, pd.Series)
        self.assertGreater(len(result), 0, "Series should not be empty")

    def test_ingest_roster_file_not_found(self):
        """Test that ingest_roster raises FileNotFoundError for non-existent files."""
        with self.assertRaises(FileNotFoundError) as context:
            xls_to_dataframe(self.invalid_file_path)
        self.assertIn("File not found", str(context.exception))

    def test_ingest_roster_invalid_extension(self):
        """Test that ingest_roster raises ValueError for non-.xlsx files."""
        temp_file = Path(self.invalid_extension_path)
        try:
            temp_file.touch()
            with self.assertRaises(ValueError) as context:
                xls_to_dataframe(str(temp_file))
            self.assertIn("Invalid file extension", str(context.exception))
        finally:
            if temp_file.exists():
                temp_file.unlink()

    def test_ingest_roster_has_datetime_index(self):
        """Test that the result has datetime index."""
        result = xls_to_dataframe(self.test_roster_path)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result.index))


class TestExtractAttendance(unittest.TestCase):
    """Test suite for the extract_attendance function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_roster_path = "rsc/Roster 2025.xlsx"
        self.xls = pd.ExcelFile(self.test_roster_path)

    def tearDown(self):
        """Clean up resources."""
        self.xls.close()

    def test_extract_attendance_returns_list_of_series(self):
        """Test that extract_attendance returns a list of Series."""
        result = extract_attendance(self.xls)
        self.assertIsInstance(result, list)
        self.assertTrue(all(isinstance(s, pd.Series) for s in result))

    def test_extract_attendance_processes_multiple_months(self):
        """Test that extract_attendance processes all available months."""
        result = extract_attendance(self.xls)
        self.assertGreater(len(result), 0, "Should extract at least one month")

    def test_extract_attendance_series_have_datetime_index(self):
        """Test that each series has datetime index after conversion."""
        result = extract_attendance(self.xls)
        for series in result:
            self.assertTrue(pd.api.types.is_datetime64_any_dtype(series.index))

    def test_extract_attendance_sheet_exists(self):
        """Test that month sheets exist in the roster file."""
        sheet_names = self.xls.sheet_names
        self.assertIn("January", sheet_names, "January sheet should exist")


class TestSheetDFToSeries(unittest.TestCase):
    """Test suite for the sheet_df_to_series function."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_roster_path = "rsc/Roster 2025.xlsx"

    def test_sheet_df_to_series_returns_series(self):
        """Test that sheet_df_to_series returns a pandas Series."""
        with pd.ExcelFile(self.test_roster_path) as xls:
            raw_df = pd.read_excel(xls, sheet_name="January", header=1)
            result = sheet_df_to_series(raw_df)
            self.assertIsInstance(result, pd.Series)

    def test_sheet_df_to_series_finds_numeric_summary_row(self):
        """Test that sheet_df_to_series correctly identifies the staffing summary row."""
        with pd.ExcelFile(self.test_roster_path) as xls:
            raw_df = pd.read_excel(xls, sheet_name="January", header=1)
            result = sheet_df_to_series(raw_df)
            # All values should be numeric
            for val in result:
                self.assertIsInstance(val, (int, float),
                                      f"Expected numeric value, got {type(val)}: {val}")

    def test_sheet_df_to_series_drops_na_values(self):
        """Test that sheet_df_to_series drops NaN values from the result."""
        with pd.ExcelFile(self.test_roster_path) as xls:
            raw_df = pd.read_excel(xls, sheet_name="January", header=1)
            result = sheet_df_to_series(raw_df)
            self.assertFalse(result.isna().any(), "Result should not contain NaN values")

    def test_sheet_df_to_series_with_mock_data(self):
        """Test sheet_df_to_series with controlled mock data."""
        mock_data = {
            'Name': ['Person 1', 'Person 2', 'Summary'],
            'Date1': ['Y', 'N', 5],
            'Date2': ['N', 'Y', 3],
            'Date3': ['Y', 'Y', 7]
        }
        mock_df = pd.DataFrame(mock_data)
        result = sheet_df_to_series(mock_df)

        self.assertIsInstance(result, pd.Series)
        self.assertEqual(len(result), 3)
        self.assertTrue(all(isinstance(v, (int, float)) for v in result))


class TestConvertDayToDate(unittest.TestCase):
    """Test suite for the convert_day_to_date function."""

    def test_convert_day_to_date_creates_datetime_index(self):
        """Test that convert_day_to_date creates proper datetime index."""
        mock_series = pd.Series([5, 6, 7], index=[4, 5, 6])
        result = clean_data(mock_series, month=1, year=2025)

        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result.index))
        self.assertEqual(len(result), 3)

    def test_convert_day_to_date_handles_month_boundary(self):
        """Test that convert_day_to_date handles days from previous month."""
        # Day 28 should be treated as previous month
        mock_series = pd.Series([10], index=[28])
        result = clean_data(mock_series, month=2, year=2025)

        # Should be January 28, not February 28
        self.assertEqual(result.index[0].month, 1)
        self.assertEqual(result.index[0].day, 28)

    def test_convert_day_to_date_filters_non_numeric(self):
        """Test that convert_day_to_date filters out non-numeric indices."""
        mock_series = pd.Series([5, 6, 7], index=[4, 'Unnamed: 5', 6])
        result = clean_data(mock_series, month=3, year=2025)

        # Should only have 2 entries (4 and 6)
        self.assertEqual(len(result), 2)
        self.assertTrue(all(pd.api.types.is_datetime64_any_dtype(result.index)))

    def test_convert_day_to_date_preserves_values(self):
        """Test that convert_day_to_date preserves original values."""
        values = [10, 15, 20]
        mock_series = pd.Series(values, index=[1, 2, 3])
        result = clean_data(mock_series, month=4, year=2025)

        self.assertTrue(all(result.values == values))


class TestIntegration(unittest.TestCase):
    """Integration tests for the complete attendance pipeline."""

    def setUp(self):
        """Set up test fixtures."""
        self.test_roster_path = "rsc/Roster 2025.xlsx"

    def test_full_pipeline(self):
        """Test the complete pipeline from file to final series."""
        result = xls_to_dataframe(self.test_roster_path)

        # Verify final output
        self.assertIsInstance(result, pd.Series)
        self.assertGreater(len(result), 0)
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(result.index))
        self.assertFalse(result.isna().any())

        # All values should be numeric
        for val in result:
            self.assertIsInstance(val, (int, float))

    def test_index_is_sorted(self):
        """Test that the final series has sorted datetime index."""
        result = xls_to_dataframe(self.test_roster_path)
        self.assertTrue(result.index.is_monotonic_increasing,
                        "Index should be sorted chronologically")


if __name__ == '__main__':
    unittest.main()
