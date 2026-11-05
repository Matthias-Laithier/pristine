from collections import deque
from collections.abc import Iterator
from dataclasses import dataclass

from pristine.imports.registry import ImportEdge

type DependencyGraph = dict[str, list[str]]


@dataclass(frozen=True)
class ImportCycle:
    path: list[str]
    component_size: int


def dependency_graph(edges: list[ImportEdge]) -> DependencyGraph:
    targets: dict[str, set[str]] = {}
    for edge in edges:
        targets.setdefault(edge.source, set()).add(edge.target)
    return {source: sorted(successors - {source}) for source, successors in targets.items()}


class StronglyConnectedComponents:
    def __init__(self, graph: DependencyGraph) -> None:
        self.graph = graph
        self.discovery_order: dict[str, int] = {}
        self.lowest_reachable: dict[str, int] = {}
        self.open_nodes: list[str] = []
        self.open_node_set: set[str] = set()
        self.pending: list[tuple[str, Iterator[str]]] = []
        self.components: list[list[str]] = []

    def enter(self, node: str) -> None:
        self.discovery_order[node] = self.lowest_reachable[node] = len(self.discovery_order)
        self.open_nodes.append(node)
        self.open_node_set.add(node)
        self.pending.append((node, iter(self.graph.get(node, []))))

    def leave(self, node: str) -> None:
        self.pending.pop()
        if self.pending:
            parent = self.pending[-1][0]
            self.lowest_reachable[parent] = min(self.lowest_reachable[parent], self.lowest_reachable[node])
        if self.lowest_reachable[node] != self.discovery_order[node]:
            return
        component = []
        while not component or component[-1] != node:
            component.append(self.open_nodes.pop())
            self.open_node_set.discard(component[-1])
        self.components.append(component)

    def follow(self, node: str, successor: str) -> None:
        if successor not in self.discovery_order:
            self.enter(successor)
        elif successor in self.open_node_set:
            self.lowest_reachable[node] = min(self.lowest_reachable[node], self.discovery_order[successor])

    def explore(self, start: str) -> None:
        self.enter(start)
        while self.pending:
            node, successors = self.pending[-1]
            successor = next(successors, None)
            if successor is None:
                self.leave(node)
            else:
                self.follow(node, successor)

    def find(self) -> list[list[str]]:
        for node in sorted(self.graph):
            if node not in self.discovery_order:
                self.explore(node)
        return self.components


def trace_back(parents: dict[str, str], node: str, start: str) -> list[str]:
    path = [node]
    while path[-1] != start:
        path.append(parents[path[-1]])
    return path[::-1]


def shortest_cycle(graph: DependencyGraph, members: set[str], start: str) -> list[str]:
    parents: dict[str, str] = {}
    queue = deque([start])
    while queue:
        node = queue.popleft()
        if start in graph[node]:
            return [*trace_back(parents, node, start), start]
        fresh = [successor for successor in graph[node] if successor in members and successor not in parents]
        parents.update((successor, node) for successor in fresh)
        queue.extend(fresh)
    return []


def cyclic_components(graph: DependencyGraph) -> list[set[str]]:
    return [set(component) for component in StronglyConnectedComponents(graph).find() if len(component) > 1]


def import_cycles(graph: DependencyGraph, checked: set[str]) -> list[ImportCycle]:
    starts = [(component, min(component & checked)) for component in cyclic_components(graph) if component & checked]
    return [ImportCycle(shortest_cycle(graph, component, start), len(component)) for component, start in starts]
