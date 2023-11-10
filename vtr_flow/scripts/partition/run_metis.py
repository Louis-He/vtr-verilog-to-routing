from hypergraph_to_graph import METIS_Runner
import sys
import os
import math
import xml.etree.ElementTree as ET
import json

SCORE_MIN_THRESHOLD = -1
class METIS_Recursive_Runner:
    def __init__(self, blocks_file, input_hypergraph) -> None:
        self.blocks_file = blocks_file
        self.input_hypergraph = input_hypergraph
        
        self.block_infos = {}
        self.block_paritioned_result = {} # blkname -> partition_id
        
        # self.intermediate_txt = "metis_default_in_*.txt"
        self.output_graph = "metis_default_in.txt"
        
        self.construct_from_block_file()
        # self.construct_from_hypergraph_file()
    
    def construct_from_block_file(self):
        self.block_infos = {}
        assert(self.blocks_file is not None)
        with (open(self.blocks_file)) as f:
            for line in f:
                block_type_list = line.strip().split()
                self.block_infos[block_type_list[0]] = block_type_list[1]
                self.block_paritioned_result[block_type_list[0]] = "-1"
                
        print("Found a total of %d blocks" % (len(self.block_infos)))
    
    def calculate_attraction_score_only_partition(self, src_partition, dst_partition):
        common_prefix_len = 0
        for i in range(len(src_partition)):
            if len(dst_partition) <= i:
                break
            
            if (src_partition[i] == dst_partition[i]):
                common_prefix_len += 1
            else:
                break
            
        uncommon_surffix_len = min(len(src_partition), len(dst_partition)) - common_prefix_len
        if uncommon_surffix_len > 3:
            return SCORE_MIN_THRESHOLD
            
        score = 2 * math.exp(-1/3*uncommon_surffix_len) + SCORE_MIN_THRESHOLD
        return score
    
    def calculate_attraction_score(self, src_name, dst_name, src_partition, dst_partition):
        return self.calculate_attraction_score_only_partition(src_partition, dst_partition)
    
    def write_external_attraction_data_file_xml(self, out_format, filename):
        if out_format == 'xml':
            root = ET.Element("attraction_data")
            
            print(self.block_paritioned_result)
            
            for src_blkname, src_blk_partition_id in self.block_paritioned_result.items():
                attraction = ET.SubElement(root, 'attraction')
                src_blk_tag = ET.SubElement(attraction, 'src', name=src_blkname)
                dst_list_tag = ET.SubElement(attraction, 'dst_list')
                for dst_blkname, dst_blk_partition_id in self.block_paritioned_result.items():
                    if (src_blkname != dst_blkname):
                        attraction_score = self.calculate_attraction_score(src_blkname, dst_blkname, 
                                                                        src_blk_partition_id, dst_blk_partition_id)
                        
                        if attraction_score > SCORE_MIN_THRESHOLD:
                            dst_blk_tag = ET.SubElement(attraction, 'dst', name=dst_blkname, score=str(attraction_score))
                        
            tree = ET.ElementTree(root)
            tree.write(filename)        
        elif out_format == 'json':
            block_id = {}
            root = {}
            attraction_score_dict = {}
            attraction_score_rev_dict = {}
            
            i = 0
            score_id = 0
            for blkname, _ in self.block_paritioned_result.items():
                block_id[blkname] = i
                i += 1
                
            for src_blkname, src_blk_partition_id in self.block_paritioned_result.items():
                dst_list = {}
                for dst_blkname, dst_blk_partition_id in self.block_paritioned_result.items():
                    if (src_blkname != dst_blkname):
                        attraction_score = self.calculate_attraction_score(src_blkname, dst_blkname, 
                                                                        src_blk_partition_id, dst_blk_partition_id)
                        attraction_score = math.floor(attraction_score * 100) / 100
                        
                        if attraction_score > SCORE_MIN_THRESHOLD:
                            if attraction_score not in attraction_score_dict:
                                attraction_score_dict[attraction_score] = score_id
                                score_id += 1
                            
                            dst_list[block_id[dst_blkname]] = attraction_score_dict[attraction_score]
                                
                root[block_id[src_blkname]] = dst_list
            
            for score, score_id in attraction_score_dict.items():
                attraction_score_rev_dict[score_id] = score
            
            with open(filename, 'w') as f:
                json.dump(
                    {
                        "block_id": block_id,
                        "attraction_score_id": attraction_score_rev_dict,
                        "attraction_data": root
                    }, f)
        elif out_format == 'custom':
            block_id = {}
            root = {}
            attraction_score_dict = {}
            attraction_score_rev_dict = {}
            
            i = 0
            score_id = 0
            for blkname, _ in self.block_paritioned_result.items():
                block_id[blkname] = i
                i += 1
                
            for src_blkname, src_blk_partition_id in self.block_paritioned_result.items():
                dst_list = {}
                for dst_blkname, dst_blk_partition_id in self.block_paritioned_result.items():
                    if (src_blkname != dst_blkname):
                        attraction_score = self.calculate_attraction_score(src_blkname, dst_blkname, 
                                                                        src_blk_partition_id, dst_blk_partition_id)
                        attraction_score = math.floor(attraction_score * 100) / 100
                        
                        if attraction_score > SCORE_MIN_THRESHOLD:
                            reverse_attraction_score_id = None
                            if block_id[dst_blkname] in root:
                                if block_id[src_blkname] in root[block_id[dst_blkname]]:
                                    reverse_attraction_score_id = root[block_id[dst_blkname]][block_id[src_blkname]]
                            
                            if attraction_score not in attraction_score_dict:
                                attraction_score_dict[attraction_score] = score_id
                                score_id += 1
                            
                            # If A->B has the same attraction score as B->A, only keep one
                            if attraction_score_dict[attraction_score] != reverse_attraction_score_id:
                                dst_list[block_id[dst_blkname]] = attraction_score_dict[attraction_score]
                                
                root[block_id[src_blkname]] = dst_list
            
            for score, score_id in attraction_score_dict.items():
                attraction_score_rev_dict[score_id] = score
            
            with open(filename, 'w') as f:
                for block_name, block_id in block_id.items():
                    f.write("%x %s\n" % (block_id, block_name))
                
                f.write("=\n")
                    
                for attraction_score_id, attraction_score in attraction_score_rev_dict.items():
                    f.write("%d %.2f\n" % (attraction_score_id, attraction_score))
                
                f.write("=\n")
                    
                for src, dst_list in root.items():
                    if len(dst_list) == 0:
                        continue
                    f.write("%x " % (src))
                    for dst, score in dst_list.items():
                        f.write("%x %d " % (dst, score))
                    f.write("\n")
                        
                f.write("=\n")
        elif out_format == 'custom_group':
            unique_group = {}
            group_num = 0
            with open(filename, 'w') as f:
                for _, partition_group in self.block_paritioned_result.items():
                    if partition_group not in unique_group:
                        unique_group[partition_group] = group_num
                        group_num += 1
                
                # Dump out attraction score between groups
                for src_group_id in unique_group:
                    src_new_group_id = unique_group[src_group_id]
                    f.write("%s " % str(src_new_group_id))
                    for dst_group_id in unique_group:
                        dst_new_group_id = unique_group[dst_group_id]
                        attraction_score = self.calculate_attraction_score_only_partition(src_group_id, dst_group_id)
                        attraction_score = math.floor(attraction_score * 100) / 100
                        if attraction_score > SCORE_MIN_THRESHOLD:
                            f.write("%s %.2f " % (str(dst_new_group_id), attraction_score))
                    f.write("\n")
                
                f.write("=\n")
                
                # Dump out block name and its group id
                for blkname, partition_group in self.block_paritioned_result.items():
                    f.write("%s %s\n" % (blkname, unique_group[partition_group]))
        else:
            print("Unsupported output format %s" % out_format)
        
    
    # MUST be called after each partitioning
    def update_partitioned_result(self, partioned_blk_name_to_result_map):
        for blkname, partition_id in partioned_blk_name_to_result_map.items():
            if self.block_paritioned_result[blkname] == "-1":
                # If first time, update the parition
                self.block_paritioned_result[blkname] = str(partition_id)
            else:
                # otherwise, append the partition id to reflect the recursive partitioning
                self.block_paritioned_result[blkname] += str(partition_id)

    def clean_up(self):
        os.system("rm -f *.block_file.metis.txt.*")
        os.system("rm -f *.logical_hypergraph.metis.txt.*")
        os.system("rm -f metis_default_in.txt*")

    # Run this API in the same directory as the input files
    def run_metis_recursive(self, blocks_file, input_hypergraph, output_graph, graph_model, partition_count, run_count):
        assert(run_count >= 0)
        if (run_count == 0):
            return
        runner = METIS_Runner()
        
        if not os.path.exists(blocks_file):
            # print("blocks file %s does not exist" % blocks_file)
            return

        is_exist_edge = runner.dump_metis_input(blocks_file, input_hypergraph, output_graph, graph_model)
        if not is_exist_edge:
            return
        
        runner.run_metis(output_graph, partition_count)
        runner.read_metis_output(partition_count, "%s.part.%d" % (output_graph, partition_count))
        self.update_partitioned_result(runner.partioned_blk_name_to_result_map)
        runner.dump_partitioned_result(partition_count, blocks_file, input_hypergraph)
        
        for partition_idx in range(partition_count):
            self.run_metis_recursive("%s.%d" % (blocks_file, partition_idx),
                                     "%s.%d" % (input_hypergraph, partition_idx),
                                     "%s.%d" % (output_graph, partition_idx),
                                     graph_model, partition_count, run_count-1)
    
    def run_metis(self, partition_count, graph_model, run_count=None, cleanup=True):
        if run_count is None:
            run_count = int(math.log2(len(self.block_infos)) / 2)
        print("Start run metis %d times" % run_count)
        self.run_metis_recursive(self.blocks_file, self.input_hypergraph, self.output_graph, graph_model, partition_count, run_count)
        # self.write_external_attraction_data_file_xml('json', 'test_attraction_data2.json')
        self.write_external_attraction_data_file_xml('custom_group', 'test_attraction_data.txt')
        print("Successfully run metis %d times" % run_count)
        if cleanup:
            self.clean_up()

def main():
    blocks_file = sys.argv[1]
    input_hypergraph = sys.argv[2]

    runner = METIS_Recursive_Runner(blocks_file, input_hypergraph)
    runner.run_metis(2, "star", cleanup=True)
    

if __name__=="__main__":
    main()