import os

from run_metis import METIS_Recursive_Runner

path = "/home/siwei/Developer/vtr-verilog-to-routing/vtr_flow/tasks/regression_tests/vtr_reg_nightly_test3/vtr_reg_qor_chain/run001/"
VTR_ROOT = "/home/siwei/Developer/vtr-verilog-to-routing"

dir_list = []
for dirpath, dirnames, filenames in os.walk(path):
    for filename in filenames:
        if filename.endswith(".block_file.metis.txt"):
            dir_list.append([dirpath, os.path.join(dirpath, filename), os.path.join(dirpath, filename).replace(".block_file.metis.txt", ".logical_hypergraph.metis.txt")])

for directory, block_file, logical_hypergraph_file in dir_list:
    os.chdir(directory)
    # do something in the directory
    os.system("python3 %s/vtr_flow/scripts/partition/run_metis.py %s %s" % (VTR_ROOT, block_file, logical_hypergraph_file))
    print("Done running recursive metis for " + directory)
    print()
