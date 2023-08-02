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
pip install .
```

7. Sign up to [MongoDB Atlas](https://cloud.mongodb.com). It is free for 512 MB.

8. Create a `.config` directory and save your DB credentials into it. Be sure to replace each one of the fields below e.g. change `mymongo.pdd134.mongodb.net` to your DB connection URL.

```bash
mkdir .config
$json='{"DB_URL": "mymongo.pdd134.mongodb.net", "DB_USERNAME": "mymongo", "DB_PASSWORD": "pass123", "DB_COLLECTION_NAME": "666vgs", "DB_NAME": "myDB"}'
echo "$json" > .config/database-config.json
```

9. Run the log keeper function.

```bash
python -m log_keeper.main
```