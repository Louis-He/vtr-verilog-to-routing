import sys
import os

class METIS_Runner:
    def __init__(self) -> None:
        # Data read from the block file
        self.btypes = None
        self.block_to_type = None
        self.block_names = None
        
        # Data read from the hypergraph file
        self.edges_conn = None # list of (net_id, sink_blokcs, net_name)
        self.edges = None
        self.num_vertices = -1
        
        # Data generated from both files
        self.edge_weight = None
        self.vertex_data = None
        
        # Data collected from the output from MeTis
        self.partition_result = None
        self.old_net_id_to_new_id_map = None # idx starts from 0
        self.old_block_id_to_new_id_map = None # idx starts from 0
        self.new_id_front = None # idx starts from 0
        
        self.partioned_blk_name_to_result_map = None # result that exposed to the outside world
    
    @staticmethod
    def edge_weight_1overf(vertices):
        return 1.0/len(vertices)
    
    def populate_block_info_from_block_file(self, block_file_path):
        print("Reading block file %s" % block_file_path)
        assert(self.btypes is None and self.block_to_type is None and self.block_names is None)
        self.btypes = []
        self.block_to_type = []
        self.block_names = []
        with open(block_file_path, 'r') as f:
            for line in f:
                binfo_list = line.strip().split()
                self.block_names.append(binfo_list[0])
                btype = binfo_list[1]
                if btype not in self.btypes:
                    self.btypes.append(btype)
                idx = self.btypes.index(btype)
                self.block_to_type.append(idx)
   
    def add_star_edges(self, hedge_parts, edges, weights):
        # add an edge from source to each dest
        for part in hedge_parts[1:]:
            # idx starts from zero, but block_idx from vpr starts from 1
            edge = (hedge_parts[0]-1, part-1)
            edges.append(edge)
            
            weight = self.edge_weight_1overf(hedge_parts)
            if edge in weights:
                weights[edge] += weight
            else:
                weights[edge] = weight
        
    def add_clique_edges(self, hedge_parts, edges, weights):
        # for each pair of vertices in this hedge, add an edge
        parts = sorted(hedge_parts)
        for i in range(len(parts)-1):
            for j in range(i+1,len(parts)):
                # idx starts from zero, but block_idx from vpr starts from 1
                edge = (parts[i]-1,parts[j]-1)
                edges.append(edge)
                
                weight = self.edge_weight_1overf(hedge_parts)
                if edge in weights:
                    weights[edge] += weight
                else:
                    weights[edge] = weight

    def populate_edge_info_from_hypergraph(self, hypergraph_file_path, graph_model):
        print("Reading hypergraph file %s" % hypergraph_file_path)
        assert(self.edges is None and self.edge_weight is None and self.edges_conn is None)
        self.edges = []
        self.edge_weight = {}
        self.edges_conn = []
        
        if graph_model == "star":
            graph_model_fn = self.add_star_edges
        elif graph_model == "clique":
            graph_model_fn = self.add_clique_edges
        
        with open(hypergraph_file_path, 'r') as f:
            first_line = True
            num_hedges_read = 0
            for line in f:
                comment_idx = line.find("//")
                net_name = None
                if comment_idx > -1:
                    net_name = line[comment_idx+2:]
                    line = line[0:comment_idx]
                line = line.strip()
                if len(line) == 0:
                    continue
                
                source_block = line.split()[0]
                sink_blocks = line.split()[1:]
                if not first_line:
                    self.edges_conn.append((source_block, sink_blocks, net_name))
                
                parts = list(map(lambda x: int(x), line.strip().split()))
                if first_line:
                    self.num_vertices = parts[1]
                    num_hedges = parts[0]
                    first_line = False
                    continue
                # the hyperedge is a list of vertex indices
                num_hedges_read += 1
                graph_model_fn(hedge_parts=parts, edges=self.edges, weights=self.edge_weight)

            print (num_hedges)
            print (num_hedges_read)
            # assert(num_hedges == num_hedges_read)
            
        # TODO: Continue here
        # edges map is done. now dump it!
        smallest_edge_weight = None
        # make edge weights integer
        for edge, weight in self.edge_weight.items():
            if smallest_edge_weight:
                smallest_edge_weight = min(smallest_edge_weight, weight)
            else:
                smallest_edge_weight = weight

        for edge in self.edge_weight:
            self.edge_weight[edge] = self.edge_weight[edge] / smallest_edge_weight
            
        # transform edge data into vertex data
        assert(self.vertex_data is None)
        self.vertex_data = {}
        for edge, weight in self.edge_weight.items():
            # print(edge)
            vertex_a = edge[0]
            vertex_b = edge[1]
            if vertex_a in self.vertex_data:
                self.vertex_data[vertex_a].append((vertex_b, weight))
            else:
                self.vertex_data[vertex_a] = [(vertex_b, weight)]
            if vertex_b in self.vertex_data:
                self.vertex_data[vertex_b].append((vertex_a, weight))
            else:
                self.vertex_data[vertex_b] = [(vertex_a, weight)]

    def dump_to_metis_input(self, output_graph="metis_default_in.txt"):
        with open(output_graph,"w") as f:
            f.write("%d %d 011 %d\n" % (self.num_vertices, len(self.edge_weight), len(self.btypes)))
            for vertex_index in range(self.num_vertices):
                # the vertex weight - what type is it?
                for i in range(len(self.btypes)):
                    if i == self.block_to_type[vertex_index]:
                        f.write("1 ")
                    else:
                        f.write("0 ")
                # After parition, it is possible that we no longer have connections within the partition
                if vertex_index in self.vertex_data:
                    for edge in self.vertex_data[vertex_index]:
                        # need the +1 to go back to 1-indexed
                        f.write("%d %d " % (edge[0]+1, edge[1]+1))
                f.write("\n")

    def dump_metis_input(self, blocks_file, input_hypergraph, output_graph, graph_model):
        self.populate_block_info_from_block_file(blocks_file)
        self.populate_edge_info_from_hypergraph(input_hypergraph, graph_model)
        self.dump_to_metis_input(output_graph)
        
    @classmethod
    def run_metis(cls, metis_input_file, partition_count):
        stream = os.popen('gpmetis %s %d' % (metis_input_file, partition_count))
        output = stream.read()
        
        print('metis output: ', output)
        
    # read the metis output file, each line represents the partition of a vertex
    def read_metis_output(self, _partition_num, metis_output_file):
        assert(self.partition_result is None)
        assert(self.partioned_blk_name_to_result_map is None)
        self.partition_result = []
        self.partioned_blk_name_to_result_map = {}
        self.old_block_id_to_new_id_map = [{} for i in range(_partition_num)]
        self.new_id_front = [0 for i in range(_partition_num)]
        
        with open(metis_output_file, 'r') as f:
            block_cnt = 0
            for line in f:
                line = line.strip()
                if len(line) == 0:
                    continue
                partition_idx = int(line)
                
                self.old_block_id_to_new_id_map[partition_idx][block_cnt] = self.new_id_front[partition_idx]
                self.new_id_front[partition_idx] += 1
                
                self.partition_result.append(partition_idx)
                block_cnt += 1
                
        for name, result in zip(self.block_names, self.partition_result):
            self.partioned_blk_name_to_result_map[name] = result
            

    def dump_partitioned_result(self, _partition_num, out_block_file, out_logical_hypergraph_file):
        assert(self.partition_result is not None)
        partition_num = max(self.partition_result) + 1
        # print(_partition_num, partition_num)
        # assert(_partition_num == partition_num)
        
        for paritition_id in range(partition_num):
            net_size = 0
            block_size = 0
            
            with open('%s.%d' % (out_block_file, paritition_id), 'w') as block_out_f:
                for idx, block in enumerate(self.block_to_type):
                    partition_result = self.partition_result[idx]
                    if partition_result == paritition_id:
                        block_size += 1
                        block_out_f.write('%s %s\n' % (self.block_names[idx], self.btypes[block]))
            
            with open('%s.%d' % (out_logical_hypergraph_file, paritition_id), 'w') as logical_hypergraph_out_f:
                block_file_content = ""
                for idx, (src_block, sink_blocks, net_name) in enumerate(self.edges_conn):
                    src_block = int(src_block) - 1
                    if (self.partition_result[src_block] != paritition_id):
                        continue
                    
                    sink_blocks = list(map(lambda x: int(x)-1, sink_blocks))
                    
                    sink_partition_result = list(map(lambda x: self.partition_result[x], sink_blocks))
                    sink_blocks_within_partition = []
                    for sink_block, dst_partition in zip(sink_blocks, sink_partition_result):
                        if dst_partition == paritition_id:
                            assert(sink_block in self.old_block_id_to_new_id_map[paritition_id])
                            assert(self.old_block_id_to_new_id_map[paritition_id][sink_block] < block_size)
                            sink_blocks_within_partition.append(self.old_block_id_to_new_id_map[paritition_id][sink_block])
                    
                    sink_blocks_within_partition = list(map(lambda x: str(x+1), sink_blocks_within_partition))
                    if sink_blocks_within_partition:
                        net_size += 1
                        assert(src_block in self.old_block_id_to_new_id_map[paritition_id])
                        block_file_content += '%d %s //%s' % (self.old_block_id_to_new_id_map[paritition_id][src_block]+1, ' '.join(sink_blocks_within_partition), net_name)

                logical_hypergraph_out_f.write("%d %d\n" % (net_size, block_size))
                logical_hypergraph_out_f.write(block_file_content)
                
def main():
    blocks_file = sys.argv[1]
    input_hypergraph = sys.argv[2]
    
    if len(sys.argv) < 4:
        output_graph = "metis_default_in.txt"
    else:
        output_graph = sys.argv[3]

    PARTITION_COUNT = 2
    runner = METIS_Runner()
    runner.dump_metis_input(blocks_file, input_hypergraph, output_graph, "star")
    runner.run_metis(output_graph, PARTITION_COUNT)
    # runner.read_metis_output("%s.part.%d" % (output_graph, PARTITION_COUNT))
    

if __name__=="__main__":
    main()