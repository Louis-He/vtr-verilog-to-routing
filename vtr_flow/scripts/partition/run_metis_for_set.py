import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

path = "/home/siwei/Developer/vtr-verilog-to-routing/vtr_flow/tasks/regression_tests/vtr_reg_nightly_test3/vtr_reg_qor_chain/run001/"
copied_path = "/home/siwei/Developer/vtr-verilog-to-routing/vtr_flow/tasks/regression_tests/vtr_reg_nightly_test3/vtr_reg_qor_chain/run022/"
# path = "/home/siwei/Developer/vtr-verilog-to-routing/vtr_flow/tasks/regression_tests/vtr_reg_nightly_test2/titan_quick_qor/run005/"
# copied_path = "/home/siwei/Developer/vtr-verilog-to-routing/vtr_flow/tasks/regression_tests/vtr_reg_nightly_test2/titan_quick_qor/run006/"
VTR_ROOT = "/home/siwei/Developer/vtr-verilog-to-routing"

# Global lock for synchronizing access to the working directory
def run_command(command, working_directory):
    try:
        # Change the working directory if specified
        # if working_directory:
        #     os.chdir(working_directory)

        # Run the command, capture the output, and get the return code
        command = command.split()
        # print(command)
        result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, cwd=working_directory)
        with open(os.path.join(working_directory, "vpr.out"), 'w') as file:
            file.write(result.stdout)
        with open(os.path.join(working_directory, "vpr.crit_path.out"), 'w') as file:
            file.write(result.stdout)
        
        return result.returncode
    except Exception as e:
        # Handle exceptions, if any
        print(f"Error running command '{command}': {str(e)}")
        return 1  # Return a non-zero code to indicate an error

dir_list = []

# clean and copy the files to the copied_path
os.system("rm -rf %s" % (copied_path))
os.system("cp -r %s %s" % (path, copied_path))

# get VPR command-line command from vpr_stdout.log in copied_path
for dirpath, dirnames, filenames in os.walk(copied_path):
    vpr_command = ""
    for filename in filenames:
        if filename.endswith(".block_file.metis.txt"):
            # indicate that we found a design folder
            
            # Locate the vpr_stdout.log file
            vpr_stdout_file_path = os.path.join(dirpath, "vpr.out")
            with open(vpr_stdout_file_path, "r") as f:
                is_next_line = False
                for line in f:
                    if is_next_line:
                        vpr_command = line.replace('\n', '')
                        is_next_line = False
                        break
                    if line.startswith("VPR was run with the following command-line:"):
                        is_next_line = True
            
            dir_list.append(
                [dirpath, # design folder
                 os.path.join(dirpath, filename), # deign block file path
                 os.path.join(dirpath, filename).replace(".block_file.metis.txt", ".logical_hypergraph.metis.txt"), # design logical hypergraph file path
                 vpr_command, # vpr command
                 os.path.join(dirpath, "test_attraction_data.txt") # partitioned result
                 ])

vpr_command_rerun_list = []
for directory, block_file, logical_hypergraph_file, vpr_command, partioned_result_file in dir_list:
    os.chdir(directory)
    # Run recursive metis
    
    os.system("python3 %s/vtr_flow/scripts/partition/run_metis.py %s %s" % (VTR_ROOT, block_file, logical_hypergraph_file))
    print("Done running recursive metis for " + directory)
    print()
    
    # Construct VPR command with the partitioned result as input
    # vpr_command += "  --allow_unrelated_clustering on --external_attraction_file %s" % (partioned_result_file)
    vpr_command += "  --external_attraction_file %s" % (partioned_result_file)
    # vpr_command += " --allow_unrelated_clustering on"
    print({"cmd": vpr_command, "dir": directory})
    vpr_command_rerun_list.append({"cmd": vpr_command, "dir": directory})
    
print("Done running recursive metis for all designs")

# Set the maximum number of threads in the thread pool
# max_workers = 7
max_workers = 16

# Using ThreadPoolExecutor to run commands in parallel
return_codes = []
with ThreadPoolExecutor(max_workers=max_workers) as executor:
    # Submit each command to the executor and collect the Future objects
    futures = {executor.submit(run_command, cmd["cmd"], working_directory=cmd["dir"]): cmd["cmd"] for cmd in vpr_command_rerun_list}

    # As commands complete, print their return codes
    for future in as_completed(futures):
        command = futures[future]
        try:
            return_code = future.result()
            print(f"Command '{command}' finished with return code: {return_code}")
        except Exception as e:
            print(f"Error running command '{command}': {str(e)}")
        finally:
            return_codes.append((command, return_code))
            
for command, return_code in return_codes:
    if return_code != 0:
        print(f"Command '{command}' failed with return code: {return_code}")
        exit(1)
    # else:
    #     print(f"Command '{command}' finished with return code: {return_code}")

print("Done running VPR with partitioned result")
