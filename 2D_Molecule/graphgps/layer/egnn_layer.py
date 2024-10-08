import math

import torch
from torch.nn import Parameter
from torch_geometric.nn.conv import MessagePassing
from torch_geometric.nn.inits import glorot, zeros
from torch_geometric.utils import add_remaining_self_loops
from torch_scatter import scatter_add


class EGNNConv(MessagePassing):
    def __init__(
        self, in_channels, out_channels, c_max=1.0, improved=False, bias=True, **kwargs
    ):
        super(EGNNConv, self).__init__(aggr="add", **kwargs)

        self.in_channels = in_channels
        self.out_channels = out_channels
        self.improved = improved
        self.weight = Parameter(torch.eye(in_channels) * math.sqrt(c_max))
        if bias:
            self.bias = Parameter(torch.Tensor(out_channels))
        else:
            self.register_parameter("bias", None)
        self.reset_parameters()

    def reset_parameters(self):
        zeros(self.bias)
        self.cached_result = None
        self.cached_num_edges = None

    @staticmethod
    def norm(edge_index, num_nodes, edge_weight=None, improved=False, dtype=None):
        if edge_weight is None:
            edge_weight = torch.ones(
                (edge_index.size(1),), dtype=dtype, device=edge_index.device
            )
        fill_value = 1.0 if not improved else 2.0
        edge_index, edge_weight = add_remaining_self_loops(
            edge_index, edge_weight, fill_value, num_nodes
        )
        row, col = edge_index
        deg = scatter_add(edge_weight, row, dim=0, dim_size=num_nodes)
        deg_inv_sqrt = deg.pow(-0.5)
        deg_inv_sqrt[deg_inv_sqrt == float("inf")] = 0

        return edge_index, deg_inv_sqrt[row] * edge_weight * deg_inv_sqrt[col]

    def forward(
        self, x, edge_index, x_0=None, beta=0.0, residual_weight=0.0, edge_weight=None
    ):
        """"""
        x_input = x

        self.cached_num_edges = edge_index.size(1)
        edge_index, norm = self.norm(
            edge_index, x.size(0), edge_weight, self.improved, x.dtype
        )
        self.cached_result = edge_index, norm

        edge_index, norm = self.cached_result
        x = self.propagate(edge_index, x=x, norm=norm)
        x = (1 - residual_weight - beta) * x + residual_weight * x_input + beta * x_0
        x = torch.matmul(x, self.weight)
        return x

    def message(self, x_j, norm):
        return norm.view(-1, 1) * x_j

    def update(self, aggr_out):
        if self.bias is not None:
            aggr_out = aggr_out + self.bias
        return aggr_out

    def __repr__(self):
        return "{}({}, {})".format(
            self.__class__.__name__, self.in_channels, self.out_channels
        )
