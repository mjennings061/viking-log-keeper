# Log Keeper
661 VGS - Function to collate 2965D log sheets into a single master log file and database.

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/cd4929e4-7a13-4d48-b4b6-1cd52f865b8d)

## Installation/Usage
1. Ensure [Python 3.11](https://www.python.org/downloads/windows/) is installed and `python.exe` is [added to the path](https://realpython.com/add-python-to-path/):

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/f2d58a92-752c-426e-878f-832cfcf7e175)

2. Sync your squadron sharepoint using OneDrive:

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/e9c856aa-48c3-429d-9685-d3b586538ea2)

3. Create a directory on your sharepoint in documents called `Log Sheets`. The naming is important!

3. Save the `2965D_YYMMDD_ZEXXX.xlsx` template (See `docs/`) into the `Log Sheets` directory. Get started with creating some log sheets to test it out.

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/ea8e51e0-ee2b-481a-88ce-63a544e0da1b)

4. Sign up to [MongoDB Atlas](https://cloud.mongodb.com) to create your organisation, project, database, and collection. It is free for 512 MB. An example below:
- Organisation: RAFAC VGS
- Project: 661 VGS
- Database: 661vgs
- Collection: log_sheets

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/a2991958-93c2-45c7-9406-8dbe913c32c2)

5. Using powershell, git bash, or command prompt, run the following command:

```bash
python -m pip install viking-log-keeper
```

6. Run the log keeper function:

```bash
python -m log_keeper.main
```

7. Enter the credentials of your database. The URL can be found in the "Database > Overview > Connect" menu:

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/7b91cde7-aa26-4bc3-8f85-5c37893aceee)

