# Log Keeper
661 VGS - Function to collate 2965D log sheets into a single master log file.

## Usage
1. Ensure python is installed and `python.exe` is added to the path.

2. Ensure git is installed e.g. "Git for Windows"

3. Using the Git Bash terminal, download this repository.

```bash
git clone PROJECT_URL
```
4. Navigate into the project folder.

```bash
cd viking-log-keeper
```

5. Create a virtual environment.

```bash
python -m venv .venv
```

6. Install the required packages.

```bash
.venv\Scripts\activate
pip install -r requirements.txt
```

7. Run the log keeper function.

```bash
python log_keeper/main.py
```