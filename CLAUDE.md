# Claude Instructions for Viking Log Keeper

This is a Python project for building a log keeper system for glider launches. The system records launches from 2965D log sheets, uploads data to MongoDB Atlas, and provides a Streamlit web interface for viewing statistics.

## Your Role

- You are assisting with the development of the Viking Log Keeper system for 661 VGS (Volunteer Gliding Squadron)
- The system is used by glider pilots and instructors to track launches and provide BI insights for operational improvements
- The system processes Excel log sheets and provides dashboard analytics

## Project Structure

- `src/dashboard/` - Streamlit web dashboard application
  - `main.py` - Main dashboard entry point
  - `auth.py` - Authentication and MongoDB credentials management
  - `plots.py` - Data visualisation and plotting functions
  - `weather.py` - Weather data integration
  - `utils.py` - Dashboard utility functions
- `src/log_keeper/` - Core log processing functionality
  - `main.py` - Main log processing entry point
  - `ingest.py` - Excel log sheet ingestion
  - `output.py` - Data output and formatting
  - `weather.py` - Weather data collection
  - `get_config.py` - Configuration management
  - `scripts/` - Batch scripts for Windows automation
- `tests/` - Unit and integration tests
- `docs/` - Documentation and Excel templates

## Development Commands

- **Install**: `pip install .` or `python setup.py install`
- **Tests**: `python -m pytest` (requires `playwright install` first)
- **Dashboard**: `viking-dashboard` (after installation)
- **Update Logs**: `update-logs` (after installation)
- **Update Config**: `update-config` (after installation)

## Key Technologies

- Python 3.11+
- Streamlit for dashboard UI
- MongoDB Atlas for database storage
- Pandas for data processing
- OpenPyXL for Excel file handling
- Playwright for end-to-end testing
- Pytest for testing framework
- Altair and matplotlib for data visualisation

## Authentication

- MongoDB Atlas connection using `.streamlit/secrets.toml`
- Format: `MONGO_URI=<YOUR_MONGO_URI>`

## Code Standards

- "The best code is no code at all" - strive for simplicity
- Follow PEP 8 naming conventions
- Use type hints and docstrings for all functions
- Functional testing prioritised over unit testing
- Support both Windows and Linux environments
- Suggest improvements, optimisations, and best practices for Python code following SOLID principles
- Do not blindly follow user requests; instead, provide thoughtful suggestions
- Ensure the code is maintainable, readable, and efficient

## Workflow

1. User requests a feature or improvement
2. Challenge the user to clarify requirements if needed
3. Provide an implementation plan
4. Implement the code following "Code Standards"
5. Update scratchpad.md with any relevant context for the next task at the end of the conversation

## Console Scripts

The project provides several console commands after installation:

- `viking-dashboard` - Launch the Streamlit dashboard
- `update-logs` - Process log sheets and update database
- `update-config` - Update MongoDB credentials
- `update-log-sheet-location` - Configure log sheet directory location
