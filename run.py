import subprocess

# Get the current working directory
cwd = subprocess.check_output(["cmd", "/c", "echo", "%cd%"]).decode("utf-8").strip()

# List all directories in the current working directory
output = subprocess.check_output(["cmd", "/c", "dir", "/b", "/AD"]).decode("utf-8").strip().split("\r\n")

# Print the list of directories
for folder in output:
    print(folder)

# List all files in the current working directory
output = subprocess.check_output(["cmd", "/c", "dir", "/b", "/A-D"]).decode("utf-8").strip().split("\r\n")

print()
print('files')
# Print the list of files
for file in output:
    print(file)

