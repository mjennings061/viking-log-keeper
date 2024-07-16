# Log Keeper
661 VGS - All-in-one log keeper for the Viking fleet. Records launches from 2965D log sheets, uploads to MongoDB Atlas, and provides a web interface for viewing statistics.

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/cd4929e4-7a13-4d48-b4b6-1cd52f865b8d)

## Contents

1. [Installation](#installation)
2. [Usage](#usage)
3. [Contribution](#contribution)
4. [Support](#support)
5. [License](#license)

## Installation
1. Ensure [Python 3.11](https://www.python.org/downloads/windows/) is installed and `python.exe` is [added to the path](https://realpython.com/add-python-to-path/):

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/f2d58a92-752c-426e-878f-832cfcf7e175)

2. Sync your squadron sharepoint using OneDrive:

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/e9c856aa-48c3-429d-9685-d3b586538ea2)

3. Create a directory on your sharepoint in documents called `Log Sheets`. The naming is important!

4. Save the `2965D_YYMMDD_ZEXXX.xlsx` template (See `docs/`) into the `#Statistics/Log Sheets` directory. 

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/ea8e51e0-ee2b-481a-88ce-63a544e0da1b)

5. Get started with creating some log sheets to test it out. Note, you will need to update the hidden `INPUT_DATA` sheet to add your aircraft and pilots:

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/0b826db1-fbf1-43e0-b07a-389521f9f697)

6. Sign up to [MongoDB Atlas](https://cloud.mongodb.com). Contact the project owner for access to the database.

7. Using powershell, git bash, or command prompt, run the following command:

```bash
python -m pip install viking-log-keeper
```

## Usage

### Normal Usage

1. Following installation, run the log keeper function:

```bash
update-logs
```

2. Enter the credentials of your database. These will be sent to you by the project owner.

### Debugging

1. To update your database configuration, run the following command:

```bash
update-config
```
![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/575ae822-f805-4ccf-832d-0ba989076977)

2. To update your log sheet location, run the following command:

```bash
update-log-sheet-location
```

## Python Dashboard

The log keeper comes with a python dashboard for viewing statistics. To run the dashboard, run the following command:

```bash
viking-dashboard
```

![image](https://github.com/mjennings061/viking-log-keeper/assets/24479573/5939a9e6-9dc9-41a2-ab27-60f929ff1214)


## Contribution

- Issue Tracker: https://github.com/mjennings061/viking-log-keeper/issues
- Source Code: https://github.com/mjennings061/viking-log-keeper/tree/main

### Testing

To run the tests, run the following commands:

```bash
playwright install
python -m pytest
```

## Support

For questions and assistance, consider raising an issue on the [issue tracker](https://github.com/mjennings061/viking-log-keeper/issues). All other queries can be directed to [mjennings061@gmail.com]()

## License

The project is licensed under the MIT License.
