import pandas as pd

# Load the CSV file (make sure it's in the same directory or provide full path)
df = pd.read_csv("MD_agric_exam-4313.csv")

# Calculate total plot size for plots where pH < 5.5
total_plot_size = df[df['pH'] < 5.5]['Plot_size'].sum()

# Round to one decimal place and print
print(round(total_plot_size, 1))
