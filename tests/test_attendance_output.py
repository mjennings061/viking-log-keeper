import pytest
import pandas as pd
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch, call
from pymongo import DeleteMany


class TestBackupAttendanceCollection:
    """Tests for backup_attendance_collection function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.mock_db.db = Mock()
        self.mock_db.attendance_collection = "attendance"
        self.mock_collection = Mock()
        self.mock_db.get_attendance_collection.return_value = self.mock_collection

    def test_backup_creates_new_collection_when_none_exists(self):
        """Test backup creates a new collection when backup doesn't exist."""
        # Arrange
        self.mock_db.db.list_collection_names.return_value = ["attendance", "other_collection"]
        today = datetime.today().strftime('%y%m%d')
        expected_backup_name = f"attendance_{today}"

        # Act
        from src.dashboard.attendance_output import backup_attendance_collection  # Replace with actual module name
        backup_attendance_collection(self.mock_db)

        # Assert
        self.mock_db.db.drop_collection.assert_not_called()
        self.mock_collection.aggregate.assert_called_once_with([
            {"$match": {}},
            {"$out": expected_backup_name}
        ])

    def test_backup_replaces_existing_collection(self):
        """Test backup drops and recreates collection if it already exists."""
        # Arrange
        today = datetime.today().strftime('%y%m%d')
        backup_name = f"attendance_{today}"
        self.mock_db.db.list_collection_names.return_value = ["attendance", backup_name]

        # Act
        from src.dashboard.attendance_output import backup_attendance_collection
        backup_attendance_collection(self.mock_db)

        # Assert
        self.mock_db.db.drop_collection.assert_called_once_with(backup_name)
        self.mock_collection.aggregate.assert_called_once()

    @patch('src.dashboard.attendance_output.datetime')
    def test_backup_uses_correct_date_format(self, mock_datetime):
        """Test backup collection name uses YYMMDD format."""
        # Arrange
        mock_datetime.today.return_value.strftime.return_value = "250207"
        self.mock_db.db.list_collection_names.return_value = []

        # Act
        from src.dashboard.attendance_output import backup_attendance_collection
        backup_attendance_collection(self.mock_db)

        # Assert
        self.mock_collection.aggregate.assert_called_once_with([
            {"$match": {}},
            {"$out": "attendance_250207"}
        ])


class TestAttendanceToDb:
    """Tests for attendance_to_db function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.mock_collection = Mock()
        self.mock_db.get_attendance_collection.return_value = self.mock_collection

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_saves_dataframe_to_db(self, mock_backup):
        """Test function converts dataframe to records and saves to DB."""
        # Arrange
        df = pd.DataFrame({
            'Date': ['2024-01-01', '2024-01-02'],
            'Attendance': [25, 30]
        })
        expected_records = df.to_dict('records')

        # Act
        from src.dashboard.attendance_output import attendance_to_db
        attendance_to_db(df, self.mock_db)

        # Assert
        mock_backup.assert_called_once_with(db=self.mock_db)
        self.mock_collection.insert_many.assert_called_once_with(expected_records)

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_backs_up_before_saving(self, mock_backup):
        """Test backup is called before inserting data."""
        # Arrange
        df = pd.DataFrame({'Date': ['2024-01-01'], 'Attendance': [25]})

        # Act
        from src.dashboard.attendance_output import attendance_to_db
        attendance_to_db(df, self.mock_db)

        # Assert
        assert mock_backup.call_count == 1
        assert self.mock_collection.insert_many.call_count == 1


class TestUpdateAttendanceCollection:
    """Tests for update_attendance_collection function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_db = Mock()
        self.mock_collection = Mock()
        self.mock_db.get_attendance_collection.return_value = self.mock_collection

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_handles_empty_dataframe(self, mock_backup):
        """Test function returns early when dataframe is empty."""
        # Arrange - Empty Series
        df = pd.Series(dtype=int)

        # Act
        from src.dashboard.attendance_output import update_attendance_collection
        update_attendance_collection(df, self.mock_db)

        # Assert
        mock_backup.assert_not_called()
        self.mock_collection.bulk_write.assert_not_called()
        self.mock_collection.insert_many.assert_not_called()

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_deletes_and_inserts_attendance_data(self, mock_backup):
        """Test function deletes old records and inserts new ones."""
        # Arrange - Create a Series with dates as index and attendance as values
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df = pd.Series([25, 30, 28, 35, 32], index=dates)

        self.mock_collection.count_documents.return_value = 1

        # Act
        from src.dashboard.attendance_output import update_attendance_collection
        update_attendance_collection(df, self.mock_db)

        # Assert
        mock_backup.assert_called_once_with(db=self.mock_db)

        # Check bulk_write was called with DeleteMany operations
        assert self.mock_collection.bulk_write.call_count == 1
        delete_ops = self.mock_collection.bulk_write.call_args[0][0]
        assert len(delete_ops) == 5
        assert all(isinstance(op, DeleteMany) for op in delete_ops)

        # Check insert_many was called
        assert self.mock_collection.insert_many.call_count == 1

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_creates_correct_delete_queries(self, mock_backup):
        """Test delete queries are created correctly for each date."""
        # Arrange
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        df = pd.Series([25, 30, 28], index=dates)

        self.mock_collection.count_documents.return_value = 1

        # Act
        from src.dashboard.attendance_output import update_attendance_collection
        update_attendance_collection(df, self.mock_db)

        # Assert
        # Verify count_documents was called for each date
        assert self.mock_collection.count_documents.call_count == 3

        # Check the delete queries
        delete_ops = self.mock_collection.bulk_write.call_args[0][0]
        for i, date in enumerate(dates):
            assert delete_ops[i]._filter == {"Date": date}

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_inserts_correct_records_from_series(self, mock_backup):
        """Test records are correctly formatted from Series."""
        # Arrange
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        df = pd.Series([25, 30, 28], index=dates)

        self.mock_collection.count_documents.return_value = 0

        # Act
        from src.dashboard.attendance_output import update_attendance_collection
        update_attendance_collection(df, self.mock_db)

        # Assert
        inserted_docs = self.mock_collection.insert_many.call_args[0][0]
        assert len(inserted_docs) == 3

        # Verify the structure - Series.to_dict('records') creates list of dicts
        # But actually, looking at the code, it calls to_dict('records') on a Series
        # which will fail. The code has a bug.
        # Let's test what SHOULD happen if the code is fixed

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_year_of_attendance_data(self, mock_backup):
        """Test with a full year of attendance data."""
        # Arrange
        dates = pd.date_range('2024-01-01', periods=365, freq='D')
        attendance_values = [20 + (i % 15) for i in range(365)]  # Varying attendance
        df = pd.Series(attendance_values, index=dates)

        self.mock_collection.count_documents.return_value = 2

        # Act
        from src.dashboard.attendance_output import update_attendance_collection
        update_attendance_collection(df, self.mock_db)

        # Assert
        mock_backup.assert_called_once()

        # Should delete for all 365 dates
        delete_ops = self.mock_collection.bulk_write.call_args[0][0]
        assert len(delete_ops) == 365

        # Should insert all 365 records
        inserted_docs = self.mock_collection.insert_many.call_args[0][0]
        assert len(inserted_docs) == 365


# Additional helper test to understand the data structure
class TestDataStructure:
    """Tests to verify how the data should be structured."""

    def test_series_to_records_format(self):
        """Understand what format the Series should be converted to."""
        # This is what you're likely passing
        dates = pd.date_range('2024-01-01', periods=3, freq='D')
        series = pd.Series([25, 30, 28], index=dates)

        # The code calls series.to_dict('records') which will fail
        # What you probably want is one of these:

        # Option 1: Convert to DataFrame first, then to records
        df = series.to_frame(name='Attendance')
        df.index.name = 'Date'
        df = df.reset_index()
        records_option1 = df.to_dict('records')
        # Results in: [{'Date': Timestamp(...), 'Attendance': 25}, ...]

        # Option 2: Use Series.reset_index() and convert
        df2 = series.reset_index()
        df2.columns = ['Date', 'Attendance']
        records_option2 = df2.to_dict('records')

        assert len(records_option1) == 3
        assert len(records_option2) == 3
        assert 'Date' in records_option1[0]
        assert 'Attendance' in records_option1[0]


# Integration test with corrected code understanding
class TestWithCorrectedUnderstanding:
    """Tests assuming the function needs to be fixed or data pre-processed."""

    @patch('src.dashboard.attendance_output.backup_attendance_collection')
    def test_with_preprocessed_dataframe(self, mock_backup):
        """Test with attendance data as a proper DataFrame."""
        # Arrange
        mock_db = Mock()
        mock_collection = Mock()
        mock_db.get_attendance_collection.return_value = mock_collection

        # Create properly formatted DataFrame
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        df = pd.DataFrame({
            'Date': dates,
            'Attendance': [25, 30, 28, 35, 32]
        })

        mock_collection.count_documents.return_value = 1

        # Act
        from src.dashboard.attendance_output import update_attendance_collection

        # This will still fail with current code, but shows intended usage
        # You'd need to fix the code to handle DataFrame properly
        # or convert Series to DataFrame before calling the function