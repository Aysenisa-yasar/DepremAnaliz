import torch
import torch.nn as nn
from torch_geometric.nn import GCNConv, global_mean_pool


class EarthquakeGNN(nn.Module):
    def __init__(self, in_channels: int, hidden_channels: int = 32):
        super().__init__()
        self.conv1 = GCNConv(in_channels, hidden_channels)
        self.conv2 = GCNConv(hidden_channels, hidden_channels)
        self.relu = nn.ReLU()
        self.dropout = nn.Dropout(0.2)
        self.fc = nn.Linear(hidden_channels, 1)

    def forward(self, x, edge_index, batch, edge_weight=None):
        x = self.conv1(x, edge_index, edge_weight=edge_weight)
        x = self.relu(x)
        x = self.dropout(x)

        x = self.conv2(x, edge_index, edge_weight=edge_weight)
        x = self.relu(x)

        x = global_mean_pool(x, batch)
        x = self.fc(x)
        return torch.sigmoid(x)
