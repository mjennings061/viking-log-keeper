# Log Keeper
661 VGS - Function to collate 2965D log sheets into a single master log file and database.

## Usage
1. Ensure python is installed and `python.exe` is added to the path.

2. Sign up to [MongoDB Atlas](https://cloud.mongodb.com) to create your database and collection. It is free for 512 MB.

3. Using powershell, git bash, or command prompt, run the following command.

```bash
python -m pip install viking-log-keeper
```

4. Run the log keeper function.

```bash
python -m log_keeper.main
```