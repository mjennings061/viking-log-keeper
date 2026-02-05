import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from attendance import xls_to_dataframe

s = xls_to_dataframe("../../rsc/Roster 2025.xlsx")


def plot_attendance_by_day(s):
    # 1. Clean data (Ensure datetime and numeric)
    s.index = pd.to_datetime(s.index)
    s = pd.to_numeric(s)

    # 2. Convert dates to ordinal numbers (Days since a starting point)
    # This allows the math to work on the X-axis
    x_days = (s.index - s.index.min()).days.values
    y_counts = s.values

    # 3. Calculate Linear Regression (1st degree polynomial)
    # m = slope, b = intercept
    m, b = np.polyfit(x_days, y_counts, 1)

    # 4. Create the regression line
    regression_line = m * x_days + b

    # 5. Plotting
    plt.figure(figsize=(10, 6))
    plt.scatter(s.index, s.values, label='Actual Attendance', alpha=0.5)
    plt.plot(s.index, regression_line, color='red', linewidth=2, label=f'Trend (Slope: {m:.2f})')

    plt.title('661 Attendance Trend 2025')
    plt.legend()
    plt.xticks(rotation=45)
    plt.show()




plot_attendance_by_day(s)