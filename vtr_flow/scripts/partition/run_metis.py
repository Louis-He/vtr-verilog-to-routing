from hypergraph_to_graph import METIS_Runner
import sys

class METIS_Recursive_Runner:
    def __init__(self, blocks_file, input_hypergraph) -> None:
        self.blocks_file = blocks_file
        self.input_hypergraph = input_hypergraph
        
        self.block_infos = {}
        self.block_paritioned_result = {} # blkname -> partition_id
        
        self.intermediate_txt = "metis_default_in_*.txt"
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
    
    # MUST be called after each partitioning
    def update_partitioned_result(self, partioned_blk_name_to_result_map):
        for blkname, partition_id in partioned_blk_name_to_result_map.items():
            if self.block_paritioned_result[blkname] == "-1":
                # If first time, update the parition
                self.block_paritioned_result[blkname] = str(partition_id)
            else:
                # otherwise, append the partition id to reflect the recursive partitioning
                self.block_paritioned_result[blkname] += str(partition_id)

    def run_metis_recursive(self, blocks_file, input_hypergraph, output_graph, graph_model, partition_count, run_count):
        assert(run_count >= 0)
        if (run_count == 0):
            return
        runner = METIS_Runner()
        
        runner.dump_metis_input(blocks_file, input_hypergraph, output_graph, graph_model)
        runner.run_metis(output_graph, partition_count)
        runner.read_metis_output(partition_count, "%s.part.%d" % (output_graph, partition_count))
        self.update_partitioned_result(runner.partioned_blk_name_to_result_map)
        runner.dump_partitioned_result(partition_count, blocks_file, input_hypergraph)
        
        for partition_idx in range(partition_count):
            self.run_metis_recursive("%s.%d" % (blocks_file, partition_idx),
                                     "%s.%d" % (input_hypergraph, partition_idx),
                                     "%s.%d" % (output_graph, partition_idx),
                                     graph_model, partition_count, run_count-1)
    
    def run_metis(self, partition_count, graph_model, run_count=1):
        print("run metis %d times" % run_count)
        self.run_metis_recursive(self.blocks_file, self.input_hypergraph, self.output_graph, graph_model, partition_count, run_count)
        print(self.block_paritioned_result)


def main():
    blocks_file = sys.argv[1]
    input_hypergraph = sys.argv[2]

    runner = METIS_Recursive_Runner(blocks_file, input_hypergraph)
    runner.run_metis(2, "star", 4)
    

if __name__=="__main__":
    main()