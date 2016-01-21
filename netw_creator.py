__author__ = 'Agostino Sturaro'

import os
import sys
import json
import math
import random
import logging
import numpy as np
import networkx as nx
import matplotlib.pyplot as plt
import shared_functions as sf
from collections import OrderedDict
from collections import defaultdict
from pkg_resources import parse_version

try:
    import Queue as Q  # ver. < 3.0
except ImportError:
    import queue as Q

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import ConfigParser  # ver. < 3.0

if sys.version_info[0] < 3:
    integer_types = (int, long,)
    string_types = (basestring)
else:
    integer_types = (int,)
    string_types = (str,)

logger = logging.getLogger(__name__)


def arrange_nodes(G, pos_by_node):
    for node, (x, y) in pos_by_node.items():
        G.node[node]['x'] = float(x)
        G.node[node]['y'] = float(y)


# this is a deterministic version of nx.random_layout
def uar_layout(G, span, center, seed=None):
    my_random = random.Random(seed)
    pos_by_node = dict()
    half_span = span / 2.0
    for node in G.nodes():
        pos_x = my_random.uniform(-half_span, half_span) + center[0]
        pos_y = my_random.uniform(-half_span, half_span) + center[1]
        pos_by_node[node] = np.array([pos_x, pos_y])
    return pos_by_node


def create_1to1_dep(G1, G2):
    if G1.number_of_nodes() != G2.number_of_nodes():
        raise ValueError('Networks have a different number of nodes, cannot create a symmetric 1-to-1 dependency')

    Inter_G = nx.Graph()
    Inter_G.add_nodes_from(G1.nodes(data=True))
    Inter_G.add_nodes_from(G2.nodes(data=True))

    sorted_G1_nodes = sorted(G1.nodes(), key=sf.natural_sort_key)
    sorted_G2_nodes = sorted(G2.nodes(), key=sf.natural_sort_key)

    # for node1, node2 in zip(G1.nodes(), G2.nodes()):
    for node1, node2 in zip(sorted_G1_nodes, sorted_G2_nodes):
        Inter_G.add_edge(node1, node2)

    return Inter_G


def create_n_to_n_dep(G1, G2, n, max_tries=10, seed=None):
    if not isinstance(n, integer_types):
        raise TypeError("n is not an integer")
    elif n <= 0:
        raise ValueError("n is not larger than 0")
    elif G1.number_of_nodes() != G2.number_of_nodes():
        raise ValueError("Networks have a different number of nodes, cannot create a {}-to-{} dependency".format(n, n))
    elif G1.number_of_nodes() % n != 0:
        raise ValueError("The number of nodes in network A is not divisible by {}, "
                         "cannot create a symmetric {}-to-{} dependency".format(n, n, n))
    elif G2.number_of_nodes() % n != 0:
        raise ValueError("The number of nodes in network B is not divisible by {}, "
                         "cannot create a symmetric {}-to-{} dependency".format(n, n, n))

    my_random = random.Random(seed)

    Inter_G = nx.Graph()
    Inter_G.add_nodes_from(G1.nodes(data=True))
    Inter_G.add_nodes_from(G2.nodes(data=True))

    tries = 0
    done = False
    while tries < max_tries and done is False:
        failed = False
        unsaturated_b = G2.nodes()

        for node_a in G1.nodes():
            if failed is True:
                break

            available_b = list(unsaturated_b)

            while Inter_G.degree(node_a) < n:
                if len(available_b) == 0:
                    failed = True
                    break

                node_b = my_random.choice(available_b)
                Inter_G.add_edge(node_a, node_b)
                available_b.remove(node_b)  # we don't want to link 2 times the same 2 nodes

                if Inter_G.degree(node_b) == n:
                    unsaturated_b.remove(node_b)

        if failed is False:
            done = True
        else:
            tries += 1
            Inter_G.remove_edges_from(Inter_G.edges())  # remove all edges before starting over

    if tries == max_tries:
        raise RuntimeError("Could not create a {}-to-{} dependency in {} attempts".format(n, n, max_tries))

    return Inter_G


# TODO: remove the "dependeds_from" stupidity
def create_m_to_n_dep(G1, G2, m, n, arc_dir='dependeds_from', max_tries=10, seed=None):
    if not isinstance(n, integer_types):
        raise TypeError('n is not an integer')
    elif n <= 0:
        raise ValueError('n is not larger than 0')
    elif not isinstance(m, integer_types):
        raise TypeError('m is not an integer')
    elif m <= 0:
        raise ValueError('m is not larger than 0')
    elif G1.number_of_nodes() % n != 0:
        raise ValueError("The number of nodes in network A is not divisible by {}, "
                         "cannot create a symmetric {}-to-{} dependency".format(n, m, n))
    elif G2.number_of_nodes() % m != 0:
        raise ValueError("The number of nodes in network B is not divisible by {}, "
                         "cannot create a symmetric {}-to-{} dependency".format(m, m, n))

    my_random = random.Random(seed)

    Inter_G = nx.DiGraph()
    Inter_G.add_nodes_from(G1.nodes(data=True))
    Inter_G.add_nodes_from(G2.nodes(data=True))

    tries = 0
    done = False
    while tries < max_tries and done is False:
        failed = False

        # every node of the communication network...
        for node_b in G2.nodes():
            if failed is True:
                break

            # ...supports n nodes of the power grid
            available_a = G1.nodes()
            while Inter_G.out_degree(node_b) < n:
                if len(available_a) == 0:
                    failed = True
                    break

                node_a = my_random.choice(available_a)
                Inter_G.add_edge(node_b, node_a)  # node_b supports node_a
                available_a.remove(node_a)  # we don't want to link 2 times the same 2 nodes

        # every node of the power grid...
        for node_a in G1.nodes():
            if failed is True:
                break
            available_b = G2.nodes()

            # ...supports m nodes of the communication network
            while Inter_G.out_degree(node_a) < m:
                if len(available_b) == 0:
                    failed = True
                    break

                node_b = my_random.choice(available_b)
                Inter_G.add_edge(node_a, node_b)  # node_a powers node_b
                available_b.remove(node_b)  # we don't want to link 2 times the same 2 nodes

        if failed is False:
            done = True
        else:
            tries += 1
            Inter_G.remove_edges_from(Inter_G.edges())  # remove all edges before starting over

    if tries == max_tries:
        raise RuntimeError("Could not create a {}-to-{} dependency in {} attempts".format(m, n, max_tries))

    # if we want (a, b) to mean a depends from b, reverse the arcs
    if arc_dir == 'dependeds_from':
        nx.reverse(Inter_G, copy=False)

    return Inter_G


# k is the number of control centers supporting each power node
# n is the number of power nodes that each control center supports
# com_access_pts is the number of relays a power node uses to access the communication network
# TODO: add an option com_roles, remove the "dependeds_from" stupidity
def create_k_to_n_dep(G1, G2, k, n, arc_dir='dependeds_from', power_roles=False, prefer_nearest=False, com_access_pts=1,
                      max_tries=100, seed=None):
    if not isinstance(k, integer_types):
        raise TypeError('k is not an integer')
    elif k <= 0:
        raise ValueError('k is not larger than 0')
    elif not isinstance(n, integer_types):
        raise TypeError('n is not an integer')
    elif n <= 0:
        raise ValueError('n is not larger than 0')
    elif not isinstance(power_roles, bool):
        raise ValueError('power_roles is not a boolean')
    elif not isinstance(prefer_nearest, bool):
        raise ValueError('prefer_nearest is not a boolean')
    elif com_access_pts < 0:
        raise ValueError('com_access_pts is not a positive number')

    # logger.info('create_k_to_n_dep start')

    my_random = random.Random(seed)

    Inter_G = nx.DiGraph()
    Inter_G.add_nodes_from(G1.nodes())
    Inter_G.add_nodes_from(G2.nodes())

    control_nodes = list()
    relay_nodes = list()
    for node_b in G2.nodes():
        if G2.node[node_b]['role'] == 'controller':
            control_nodes.append(node_b)
        else:
            relay_nodes.append(node_b)

    if power_roles is True:
        distribution_subs = list()
        for node_a in G1.nodes():
            if G1.node[node_a]['role'] == 'distribution_substation':
                distribution_subs.append(node_a)

    if k * G1.number_of_nodes() != n * len(control_nodes):
        raise ValueError('Make sure that k * (number of power nodes) equals n * (number of controllers)')

    if prefer_nearest is True:
        distances = defaultdict(dict)
        for node_a in G1.nodes():
            for node_b in G2.nodes():
                distance = math.hypot(G1.node[node_a]['x'] - G2.node[node_b]['x'],
                                      G1.node[node_a]['y'] - G2.node[node_b]['y'])
                distances[node_a][node_b] = distance
                distances[node_b][node_a] = distance

    tries = 0
    done = False
    while tries < max_tries and done is False:
        failed = False
        unsaturated_a = G1.nodes()  # list of power nodes with less than n control centers supporting them

        # every control center of the communication network supports n nodes of the power grid
        for controller in control_nodes:
            if failed is True:
                break

            # find available_am the list of power nodes this control center can be linked to
            if prefer_nearest is True:
                # sort available nodes based on their distance from the controller
                available_a = sorted(unsaturated_a, key=lambda x: distances[controller][x])
            else:
                available_a = list(unsaturated_a)

            while Inter_G.out_degree(controller) < n:
                if len(available_a) == 0:
                    failed = True
                    break

                if prefer_nearest is True:
                    node_a = available_a[0]
                else:
                    node_a = my_random.choice(available_a)
                Inter_G.add_edge(controller, node_a)  # controller monitors node_a
                available_a.remove(node_a)  # we don't want to link 2 times the same 2 nodes

                # every node in the power grid is supported by k control nodes
                if Inter_G.in_degree(node_a) == k:
                    unsaturated_a.remove(node_a)

        if failed is False:
            done = True
        else:
            tries += 1
            Inter_G.remove_edges_from(Inter_G.edges())  # remove all edges before starting over

    if tries == max_tries:
        raise RuntimeError("Could not create a {}-to-{} dependency in {} attempts".format(k, n, max_tries))

    if prefer_nearest is True:
        # every communication node receives power from a single power node
        if power_roles is True:  # select distribution substations only
            other_nodes = distribution_subs
        else:
            other_nodes = G1.nodes()
        for node in G2.nodes():
            nearest_other = other_nodes[0]  # pick the first element to initialize the search
            min_distance = distances[node][nearest_other]
            for other_node in other_nodes:  # search for the closest node
                distance = distances[node][other_node]
                if distance < min_distance:
                    nearest_other = other_node
                    min_distance = distance
            Inter_G.add_edge(nearest_other, node)  # the nearest appropriate power node provides the service

        # every power node needs to access a relay node
        other_nodes = relay_nodes
        for node in G1.nodes():
            if com_access_pts == 1:  # if only the nearest needs to be selected (faster code)
                nearest_other = other_nodes[0]  # pick the first element to initialize the search
                min_distance = distances[node][nearest_other]
                for other_node in other_nodes:
                    distance = distances[node][other_node]
                    if distance < min_distance:
                        nearest_other = other_node
                        min_distance = distance
                Inter_G.add_edge(nearest_other, node)  # the nearest relay provides the service
            else:  # if the n nearest need to be selected
                dist_from_others = list()
                for other_node in other_nodes:
                    distance = distances[node][other_node]
                    dist_from_others.append((distance, other_node))
                dist_from_others.sort()
                for i in range(0, com_access_pts):
                    other_node = dist_from_others[i][1]
                    Inter_G.add_edge(other_node, node)  # the nearest relays provide the service
    else:
        # every communication node receives power from a single power node
        if power_roles is True:  # select distribution substations only
            other_nodes = distribution_subs
        else:
            other_nodes = G1.nodes()
        for node in G2.nodes():
            chosen_other = my_random.choice(other_nodes)
            Inter_G.add_edge(chosen_other, node)  # a power node provides the service

        # every power node needs to access a relay node
        other_nodes = relay_nodes
        for node in G1.nodes():
            chosen_other_nodes = my_random.sample(other_nodes, com_access_pts)  # function to pick n nodes at random
            for chosen_other in chosen_other_nodes:
                Inter_G.add_edge(chosen_other, node)  # a relay provides the service

    # in the k-n description, an arc (a, b) means a offers services to be
    # usually though, we want (a, b) to mean a depends from b
    if arc_dir == 'dependeds_from':
        nx.reverse(Inter_G, copy=False)

    # logger.info('create_k_to_n_dep finish')

    return Inter_G


def create_ranged_dep(G1, G2, radius):
    global logger

    if radius <= 0:
        raise ValueError('radius is not a number larger than 0')

    Inter_G = nx.Graph()

    Inter_G.add_nodes_from(G1.nodes(data=True))
    Inter_G.add_nodes_from(G2.nodes(data=True))
    free_nodes = G2.nodes()

    for node_a in G1.nodes():

        # calc distances to all free nodes in the other network
        distances = Q.PriorityQueue()
        link_cnt = 0
        for node_b in free_nodes:
            dist = math.hypot(G1.node[node_a]['x'] - G2.node[node_b]['x'],
                              G1.node[node_a]['y'] - G2.node[node_b]['y'])
            distances.put((dist, node_b))

            if dist < radius:
                Inter_G.add_edge(node_a, node_b)
                link_cnt += 1
                logger.debug('r link ' + node_a + ' ' + node_b)

        if link_cnt == 0:
            node_b = distances.get()[1]  # pick the node with the lowest distance
            Inter_G.add_edge(node_a, node_b)
            logger.debug('n link ' + node_a + ' ' + node_b)

    for node_b in G2.nodes():

        if len(Inter_G.neighbors(node_b)) == 0:
            # calc distances to all free nodes in the other network
            distances = Q.PriorityQueue()
            for node_a in G1.nodes():
                dist = math.hypot(G1.node[node_a]['x'] - G2.node[node_b]['x'],
                                  G1.node[node_a]['y'] - G2.node[node_b]['y'])
                distances.put((dist, node_a))

            node_a = distances.get()[1]  # pick the node with the lowest distance
            Inter_G.add_edge(node_b, node_a)
            logger.debug('n2 link ' + node_b + ' ' + node_a)

    return Inter_G


def relabel_nodes(G, prefix):
    if not isinstance(prefix, str):
        raise TypeError('prefix is not a string')

    mapping = {}

    for node in G.nodes():
        mapping[node] = prefix + str(node)

    nx.relabel_nodes(G, mapping, copy=False)


def relabel_nodes_by_role(G, role_prefixes):
    mapping = {}
    role_counters = {}
    for role in role_prefixes:
        role_counters[role] = 0

    for node in G.nodes():
        role = G.node[node]['role']
        mapping[node] = role_prefixes[role] + str(role_counters[role])
        role_counters[role] += 1

    nx.relabel_nodes(G, mapping, copy=False)


def relabel_nodes_by_subnet_role(G, role_prefixes):
    mapping = {}
    role_counters = {}
    for role in role_prefixes:
        role_counters[role] = 0

    nodes_by_subnet = {}
    for node in G.nodes():
        subnet = G.node[node]['subnet']
        if subnet not in nodes_by_subnet:
            nodes_by_subnet[subnet] = []
        nodes_by_subnet[subnet].append(node)

    # sort by subnet number
    nodes_by_subnet = OrderedDict(sorted(nodes_by_subnet.items(), key=lambda t: t[0]))

    for subnet, nodes in nodes_by_subnet.items():
        nodes.sort()  # sort the list of nodes before
        for node in nodes:
            role = G.node[node]['role']
            mapping[node] = role_prefixes[role] + str(role_counters[role])
            role_counters[role] += 1

    logger.debug('mapping = {}'.format(mapping))
    nx.relabel_nodes(G, mapping, copy=False)


def draw_node_groups(G, node_groups):
    colors = ['b', 'g', 'r', 'c', 'm', 'y', 'k', 'w']
    for idx, cluster in enumerate(node_groups):
        nx.draw_circular(G, nodelist=cluster, node_color=colors[idx % len(colors)], with_labels=True)

    nx.draw_circular(G, alpha=0)
    plt.show()
    plt.close()


# G is the network graph
# generator_cnt is the number of generators in the network
# distr_subst_cnt is the number of distribution substations in the network
# only_unassigned is a boolean telling if nodes that already have a role should not be reassigned one
def assign_power_roles(G, generator_cnt, transm_subst_cnt, distr_subst_cnt, only_unassigned, seed=None):
    global logger
    if generator_cnt < 0:
        raise ValueError('generators must be a positive number')
    elif distr_subst_cnt < 0:
        raise ValueError('distribution_subs must be a positive number')
    elif transm_subst_cnt < 0:
        raise ValueError('transm_subst_cnt must be a positive number')
    elif generator_cnt + transm_subst_cnt + distr_subst_cnt > G.number_of_nodes():
        raise ValueError('The number of roles to assign is larger than the number of nodes in the graph')

    my_random = random.Random(seed)

    # find out which nodes have not been assigned a role
    if only_unassigned is True:
        assignable_nodes = list()
        for node in G.nodes():
            if 'role' not in G.node[node] or G.node[node]['role'] is None:
                assignable_nodes.append(node)
        if len(assignable_nodes) < generator_cnt + transm_subst_cnt + distr_subst_cnt:
            raise ValueError('The number of roles to assign is larger than the number of nodes without a role')
    else:
        assignable_nodes = list(G.nodes())

    assignable_nodes.sort()  # sort to make the algorithm deterministic
    my_random.shuffle(assignable_nodes)  # shuffle nodes
    for i in range(0, generator_cnt):
        node = assignable_nodes.pop(0)  # pop front
        G.node[node]['role'] = 'generator'
    for i in range(0, distr_subst_cnt):
        node = assignable_nodes.pop()
        G.node[node]['role'] = 'distribution_substation'
    for i in range(0, transm_subst_cnt):
        node = assignable_nodes.pop()
        G.node[node]['role'] = 'transmission_substation'


# this assumes subnets have the same number of nodes, +-1 should work too
def assign_power_roles_to_subnets(G, generator_cnt, distr_subst_cnt, seed=None):
    global logger
    if generator_cnt <= 0:
        raise ValueError('generator_cnt must be larger than 0')
    elif distr_subst_cnt <= 0:
        raise ValueError('distr_subst_cnt must be larger than 0')

    my_random = random.Random(seed)

    nodes_by_subnet = OrderedDict()  # nodes of each sub-network, dict of lists
    logger.debug('G.nodes(data=True) = {}'.format(G.nodes(data=True)))  # debug
    for node in G.nodes():
        subnet = G.node[node]['subnet']
        if subnet not in nodes_by_subnet:
            nodes_by_subnet[subnet] = list()
        nodes_by_subnet[subnet].append(node)

    subnet_cnt = len(nodes_by_subnet)
    # the configuration must allow for a transmission substation in each subnet
    if generator_cnt + distr_subst_cnt + subnet_cnt > G.number_of_nodes():
        raise ValueError('generator_cnt {} + distr_subst_cnt {} + number of subnets {} must be'
                         '< total nodes {}'.format(generator_cnt, distr_subst_cnt, subnet_cnt, G.number_of_nodes()))

    # sort subnets, shuffle them then shuffle subnet nodes
    subnets = sorted(nodes_by_subnet.items())
    my_random.shuffle(subnets)
    nodes_by_subnet = OrderedDict(subnets)
    for subnet in nodes_by_subnet:
        subnet_nodes = nodes_by_subnet[subnet]
        my_random.shuffle(subnet_nodes)

    # assign roles, we want to pick the same distribution substations and the same generators even if the number
    # changes, so we pick them starting from the opposite ends of the list, and what's left in the middles is the
    # transmission substations
    for i in range(0, generator_cnt):
        node = nodes_by_subnet[i % subnet_cnt].pop(0)  # cycle between subnets, picking the first nodes (pop front)
        G.node[node]['role'] = 'generator'

    for i in range(0, distr_subst_cnt):
        node = nodes_by_subnet[i % subnet_cnt].pop()
        G.node[node]['role'] = 'distribution_substation'

    for subnet in nodes_by_subnet:
        for node in nodes_by_subnet[subnet]:
            G.node[node]['role'] = 'transmission_substation'

    logger.debug('G.nodes(data=True) = {}'.format(G.nodes(data=True)))  # debug


def clusterSmallWorld(n, avg_k, d_0, alpha, beta, q_rw, max_tries=20, deg_diff_thresh=45, seed=None):
    global logger
    if n <= 0:
        raise ValueError("Make sure that n is an integer larger than 0")
    elif not (2 <= avg_k <= 3 or 4 <= avg_k <= 5):
        raise ValueError("Please choose an avg_k value inside the intervals: [2, 3] and [4, 5]")
    elif 2 <= avg_k <= 3 and n > 30:
        raise ValueError("Make sure that n <=30 when 2 <= avg_k <= 3")
    elif 4 <= avg_k <= 5 and n > 300:
        raise ValueError("Make sure that n <=300 when 4 <= avg_k <= 5")
    elif d_0 <= 0:
        raise ValueError("Make sure that d_0 is an integer larger than 0")
    elif not 0 <= alpha <= 1:
        raise ValueError("Make sure that alpha is a number in [0, 1]")
    elif not 0 <= beta <= 1:
        raise ValueError("Make sure that beta is a number in [0, 1]")
    elif not 0 <= q_rw <= 1:
        raise ValueError("Make sure that q_rw is a number in [0, 1]")
    elif d_0 >= n / 2.0:
        raise ValueError("Make sure d_0 < n/2")

    my_random = random.Random(seed)
    my_np_random = np.random.RandomState(my_random.randint(0, 4294967296))

    G = nx.empty_graph(n)  # create a graph with n nodes, their ids will be [0, n)

    # link selection

    # each node should have a degree k taken from a geometric distribution, and this degree should be achieved by
    # linking it with nodes having a degree no more different than d_0 from its own
    # This is not so easy to achieve, deterministically, and the article does not give any specific indication on
    # how to solve this problem.
    # We try to keep the deviation from the distribution under a certain threshold.

    tries = 0
    done = False
    while not done and tries < max_tries:

        tries_b = 0
        done_b = False
        while not done_b and tries_b < max_tries:
            # build the geometric distribution of node degrees, making sure it's feasible
            k_vals = my_np_random.geometric(1.0 / avg_k, n)

            # check the restriction on neighborhood size
            if max(k_vals) > d_0 * 2:
                tries_b += 1
            else:
                done_b = True
        if done_b is False:
            raise RuntimeError('Could not find a proper geometric distribution in {} attempts. '
                               'd_0 is probably too low'.format(max_tries))

        # try to ensure that the ith has at least degree k_vals[i] (ith randomly picked value)
        for k_idx, node_id in enumerate(G.nodes()):

            k = k_vals[k_idx]  # pick the intended degree k of this node
            init_node_degree = G.degree(node_id)  # the degree this node has right now

            # if the node already has enough links, move on to the next
            if k < init_node_degree:
                continue

            # find local neighborhood
            neighborhood = []
            for d in range(-d_0, d_0 + 1):
                if d != 0:
                    other_id = (node_id + d) % n
                    neighborhood.append(other_id)

            # randomly select k edges, doesn't matter how many edges the node already has (literal interpretation)
            my_random.shuffle(neighborhood)
            for i in range(0, k):
                other_id = neighborhood.pop()
                if not G.has_edge(node_id, other_id):
                    G.add_edge(node_id, other_id)

        # if the resulting number of edges deviates from the expected number of edges more than a given percentage,
        # then this assignment is considered a failure
        avg_deg = np.average(G.degree(G.nodes()).values())
        perc_diff = 100.0 * (avg_deg - avg_k) / avg_k  # percentage of total degree differences from the distribution

        if abs(perc_diff) <= deg_diff_thresh:
            # logger.debug('expected avg deg = {}, avg deg = {}, perc_diff = {}'.format(avg_k, avg_deg, perc_diff))
            logger.info('base clusterSmallWorld created successfully in {} attempts'.format(tries + tries_b))
            done = True
        else:
            G.remove_edges_from(G.edges())  # remove all edges before starting over
            tries += 1

    if tries == max_tries:
        raise RuntimeError('Could not operate an effective link selection in {} attempts. '
                           'It can be difficult to assign edges randomly in a neighborhood and '
                           'match the outcome of a geometric degree distribution.'.format(max_tries))

    # link rewires

    tries = 0
    done = False
    while not done and tries < max_tries:
        state = 1  # the first node will be rewired
        markov_output = []
        for i in range(0, n):  # run a Markov chain with 2 states (0 and 1)
            markov_output.append(state)
            if state == 0:
                if my_random.random() < alpha:
                    state = 1
            else:  # if state is 1
                if my_random.random() < beta:
                    state = 0

        nodes = G.nodes()
        clusters_to_rewire = []  # this will be a list of lists, each nested list containing node indices
        prev_val = 0
        for i, val in enumerate(markov_output):
            if val == 1:
                if prev_val == 0:
                    clusters_to_rewire.append(list())
                clusters_to_rewire[-1].append(nodes[i])
            prev_val = val

        if len(clusters_to_rewire) > 1:

            # check if the first and the last cluster are adjacent (cover the ends of the ring), if so, unify them
            if nodes[0] in clusters_to_rewire[0] and nodes[-1] in clusters_to_rewire[-1]:
                for node in clusters_to_rewire[-1]:
                    clusters_to_rewire[0].append(node)

                clusters_to_rewire.pop()

                if len(clusters_to_rewire) > 1:
                    done = True
                else:
                    tries += 1
            else:
                done = True
        else:
            tries += 1

    if tries == max_tries:
        raise RuntimeError('Could not select 2 node clusters to be rewired in {} attempts.'.format(max_tries))

    # draw_node_groups(G, clusters_to_rewire)  # debug

    # rewire links of nodes in a cluster with nodes of another cluster with probability q_rw
    tries = 0
    done = False
    while not done and tries < max_tries:

        failed = False
        tmp_G = G.copy()

        for cluster_idx in range(0, len(clusters_to_rewire)):

            if failed is True:
                break

            # build the list of other clusters
            other_clusters = clusters_to_rewire[:cluster_idx] + clusters_to_rewire[(cluster_idx + 1):]

            # search the edges of each node of the cluster to find the ones that target another node of the same cluster
            for node in clusters_to_rewire[cluster_idx]:

                if failed is True:
                    break

                # nodes in other clusters that can be used for long range links
                usable_other_nodes = []
                for other_cluster_idx in range(0, len(other_clusters)):
                    for other_node in other_clusters[other_cluster_idx]:
                        # if not G.has_edge(node, other_node):
                        if not tmp_G.has_edge(node, other_node):
                            usable_other_nodes.append(other_node)

                my_random.shuffle(usable_other_nodes)

                # for edge in G.edges([node]):
                for edge in tmp_G.edges(node):

                    if edge[0] in clusters_to_rewire[cluster_idx] and edge[1] in clusters_to_rewire[cluster_idx]:

                        # rewire the local edge with probability q_rw, making it a long-range edge to another cluster
                        if my_random.random() < q_rw:

                            if len(usable_other_nodes) == 0:
                                # failed = True
                                break

                            outside_node = usable_other_nodes.pop()  # pick a node from another cluster
                            tmp_G.remove_edge(edge[0], edge[1])  # remove local edge
                            tmp_G.add_edge(edge[0], outside_node)  # create long-range edge

        if failed is False:
            G = tmp_G
            done = True
        else:
            tries += 1

    if tries == max_tries:
        raise RuntimeError("Could not operate an effective rewiring in {} attempts. "
                           "Not enough available targets for rewire. "
                           "If d_0 is high, nodes in different clusters are likely to be already linked. "
                           "Retry, or adjust one or more of the following: "
                           "d_0, q_rw, (alpha and beta) or (K_clst and p_1).".format(max_tries))

    return G  # there is no guarantee that the returned subnetwork is conneced


# n is the total number of nodes
# avg_k is the average node degree
# d_0 is the number of nodes on each side of a node that can it be linked with it (max distance for local links)
# alpha is the probability to keep NOT rewiring (stay in state 0 of Markov chain)
# beta is the probability to candidate one more node for rewiring (stay in state 1 of Markov chain)
# q_rw is the probability of rewiring a link of a node candidate for rewiring (for all links of all candidates)
# max_tries is the maximum number of attempts at performing each step that could produce an invalid network
# deg_diff_thresh is the maximum acceptable difference from the expected average degree in a subnetwork
# seed is the seed used to initialize the random number generator
def RT_nested_Smallworld(n, avg_k, d_0, alpha, beta, q_rw, subnet_cnt=None, max_tries=40, deg_diff_thresh=45,
                         seed=None):
    global logger
    my_random = random.Random(seed)

    subnet_sizes = []  # the number of nodes for each sub-network

    # d_0 determines the maximum number of sub-networks that can to be created,
    # by determining the minimum number of nodes they need to contain.
    min_subnet_size = d_0 * 2 + 1
    max_subnet_cnt = int(math.floor(1.0 * n / min_subnet_size))

    # avg_k determines the minimum number of sub-networks that need to be created,
    # by determining the maximum number of nodes they can contain.
    if 2 <= avg_k <= 3:
        max_subnet_size = 30
    elif 4 <= avg_k <= 5:
        max_subnet_size = 300
    else:
        raise ValueError("Please choose an avg_k value inside the intervals: [2, 3] and [4, 5]")
    min_subnet_cnt = int(math.ceil(1.0 * n / max_subnet_size))

    logger.debug("min_subnet_cnt = {}, max_subnet_cnt = {}".format(min_subnet_cnt, max_subnet_cnt))

    if math.ceil(avg_k) > min_subnet_size:
        raise ValueError("Sub-networks may not have enough nodes to allow for the creation of lattice links")

    # if d_0 is more (or equal) than half the nodes in a network, then some left-side neighbors would also be right-side
    # neighbors, and this creates problems
    if d_0 > max_subnet_size / 2.0:
        raise ValueError("d_0 is too high for the chosen avg_k")  # this may be indirectly re-checked in the check below

    if min_subnet_cnt > max_subnet_cnt:
        raise ValueError("The combination of parameters n, d_0 and avg_k does not allow to create "
                         "enough connected sub-networks.")

    if subnet_cnt is not None:
        if not min_subnet_cnt <= subnet_cnt <= max_subnet_cnt:
            raise ValueError('subnet_cnt is either too high or too low')
    else:
        # calculate the number of nodes for each sub-network (randomized)
        # TODO: check if max_subnet_cnt should be included (adding +1)
        subnet_cnt = my_random.randint(min_subnet_cnt, max_subnet_cnt)  # the number of sub-networks to create

    logger.info('creating {} subnets'.format(subnet_cnt))
    base_subnet_size = int(math.floor(1.0 * n / subnet_cnt))  # the base-size of all sub-networks
    remaining_nodes = n % base_subnet_size  # the remaining nodes to redistribute

    # redistribute the remaining nodes
    if remaining_nodes > 0:
        while remaining_nodes > 0:
            subnet_sizes.append(base_subnet_size + 1)
            remaining_nodes -= 1

    while len(subnet_sizes) < subnet_cnt:
        subnet_sizes.append(base_subnet_size)

    logger.debug('subnet_sizes = {}'.format(subnet_sizes))

    subnets = []
    for subnet_size in subnet_sizes:

        # make sure the generated sub-networks are connected
        tries = 0
        done = False
        while not done and tries < max_tries:
            # nice trick to provide the function with a random seed
            subnet = clusterSmallWorld(subnet_size, avg_k, d_0, alpha, beta, q_rw, max_tries, deg_diff_thresh,
                                       seed=my_random.randint(0, sys.maxsize))
            if nx.is_connected(subnet):
                subnets.append(subnet)
                done = True
            else:
                tries += 1

        if tries == max_tries:
            raise RuntimeError("Could not generate a connected sub-network of size "
                               "in {} attempts.".format(subnet_size, max_tries))

    # relabel sub-networks so their node ids are distinct and copy them to a single graph
    G = nx.empty_graph()
    node_idx = 0
    for i, subnet in enumerate(subnets):
        mapping = {}
        for node in subnet:
            subnet.node[node]['subnet'] = i
            mapping[node] = node_idx
            node_idx += 1

        if i > 0:
            nx.relabel_nodes(subnet, mapping, copy=False)

        logger.debug('Nodes in subnet {} = {}'.format(i, subnet.nodes()))  # debug
        G.add_nodes_from(subnet.nodes(data=True))
        G.add_edges_from(subnet.edges(data=True))

    # debug
    # nx.draw_circular(G, with_labels=True)
    # plt.show()
    # plt.close()  # free memory

    # build lattice connections

    links_between_subnets = int(round(avg_k))  # rounded k is "a number around k"
    for i in range(0, len(subnets)):

        # create k links between random nodes of this subnet and the previous one
        for j in range(0, links_between_subnets):

            # make sure the same couple of random nodes is not linked twice
            tries = 0
            done = False
            while not done and tries < max_tries:
                node = my_random.choice(subnets[i - 1].nodes())
                other_node = my_random.choice(subnets[i].nodes())

                if not G.has_edge(node, other_node):
                    G.add_edge(node, other_node)
                    done = True
                else:
                    tries += 1

            if tries == max_tries:
                raise RuntimeError("Could not create {} unique links between 2 sub-networks "
                                   "in {} attempts.".format(j + 1, max_tries))

    # # debug
    # nx.draw_circular(G, with_labels=True)
    # plt.show()
    # plt.close()  # free memory

    logger.info('RT_nested_Smallworld network successfully created')

    return G


def run(conf_fpath):
    global logger
    logger.info('conf_fpath = ' + conf_fpath)

    conf_fpath = os.path.normpath(conf_fpath)
    if os.path.isabs(conf_fpath) is False:
        conf_fpath = os.path.abspath(conf_fpath)
    if not os.path.isfile(conf_fpath):
        raise ValueError('Invalid value for parameter "conf_fpath", no such file.\nPath: ' + conf_fpath)
    config = ConfigParser()
    config.read(conf_fpath)

    seed = config.getint('misc', 'seed')
    my_random = random.Random(seed)

    netw_a_name = config.get('build_a', 'name')
    netw_b_name = config.get('build_b', 'name')
    if netw_a_name == netw_b_name:
        raise ValueError('Network A and network B have been given the same name')

    netw_inter_name = config.get('build_inter', 'name')
    output_dir = os.path.normpath(config.get('paths', 'netw_dir'))
    if os.path.isabs(output_dir) is False:
        output_dir = os.path.abspath(output_dir)

    # create directory if it does not exist
    # clean it if it does exist
    sf.makedirs_clean(output_dir, False)

    # create the power network

    netw_a_model = config.get('build_a', 'model')
    netw_a_model = netw_a_model.lower()
    roles_a = config.get('build_a', 'roles')
    netw_a_seed = seed

    if netw_a_model != 'user_defined_graph':
        node_cnt = config.getint('build_a', 'nodes')

    if netw_a_model in ['rr', 'random_regular', 'random-regular']:
        degree = config.getint('build_a', 'degree')
        A = nx.random_regular_graph(degree, node_cnt, seed=netw_a_seed)
        while not nx.is_connected(A):
            netw_a_seed += 1
            A = nx.random_regular_graph(degree, node_cnt, seed=netw_a_seed)
    elif netw_a_model in ['ba', 'barabasi_albert', 'barabasi-albert']:
        m = config.getint('build_a', 'm')
        A = nx.barabasi_albert_graph(node_cnt, m, seed=netw_a_seed)
    elif netw_a_model in ['rt-nested-smallworld', 'rt_nested_smallworld']:
        avg_k = config.getfloat('build_a', 'avg_k')
        d_0 = config.getint('build_a', 'd_0')
        q_rw = config.getfloat('build_a', 'q_rw')
        if config.has_option('build_a', 'alpha'):
            alpha = config.getfloat('build_a', 'alpha')
            beta = config.getfloat('build_a', 'beta')
        elif config.has_option('build_a', 'K_clst'):
            K_clst = config.getfloat('build_a', 'K_clst')
            if K_clst <= 0:
                raise ValueError("Make sure that K_clst is a positive number larger than 0")
            p_1 = config.getfloat('build_a', 'p_1')
            if not 0 <= p_1 <= 1:
                raise ValueError("Make sure that p_1 is a number in [0, 1]")
            beta = 1 / (K_clst * 1.0)
            alpha = (beta * p_1) / ((1 - p_1) * 1.0)
            logger.debug('alpha = {}, beta = {}'.format(alpha, beta))
        else:
            raise ValueError("Please specify either alpha and beta or K_clst and p_1 for network A")
        if config.has_option('build_a', 'subnets'):
            subnet_cnt = config.getint('build_a', 'subnets')
        else:
            subnet_cnt = None
        A = RT_nested_Smallworld(node_cnt, avg_k, d_0, alpha, beta, q_rw, subnet_cnt, seed=netw_a_seed)
    elif netw_a_model == 'user_defined_graph':
        user_graph_fpath_a = config.get('build_a', 'user_graph_fpath')
        if os.path.isabs(user_graph_fpath_a) is False:
            user_graph_fpath_a = os.path.abspath(user_graph_fpath_a)
        if os.path.splitext(user_graph_fpath_a)[1].lower() == '.graphml':
            A = nx.read_graphml(user_graph_fpath_a, node_type=str)
        else:
            raise ValueError('Unsupported file format for "user_graph_fpath" of network A, unsupported format')
    else:
        raise ValueError('Invalid value for parameter "model" of network A: ' + netw_a_model)

    A.graph['name'] = netw_a_name  # assign the correct name to the graph
    role_prefixes_a = {'generator': 'G', 'transmission_substation': 'T', 'distribution_substation': 'D'}

    check_preassigned = False
    if config.has_option('build_a', 'preassigned_roles_fpath'):
        preassigned_roles_fpath = config.get('build_a', 'preassigned_roles_fpath')
        with open(preassigned_roles_fpath) as preassigned_roles_file:
            preassigned_roles = json.load(preassigned_roles_file)

        # preassigned_roles is a dictionary in the form {node: role}
        for node in preassigned_roles:
            A.node[node]['role'] = preassigned_roles[node]
        check_preassigned = True

    # assign roles and relabel nodes
    if roles_a == 'same':
        for node in A.nodes():
            A.node[node]['role'] = 'power'
        relabel_nodes(A, netw_a_name)
    elif roles_a == 'random_gen_transm_distr':
        generator_cnt = config.getint('build_a', 'generators')
        transm_subst_cnt = config.getint('build_a', 'transmission_substations')
        distr_subst_cnt = config.getint('build_a', 'distribution_substations')
        assign_power_roles(A, generator_cnt, transm_subst_cnt, distr_subst_cnt, check_preassigned, seed)
        relabel_nodes_by_role(A, role_prefixes_a)
    elif roles_a == 'subnet_gen_transm_distr':
        if check_preassigned is True:
            raise ValueError('preassigned_roles_fpath has not been implemented for subnets yet')  # TODO: implement this
        generator_cnt = config.getint('build_a', 'generators')
        distr_subst_cnt = config.getint('build_a', 'distribution_substations')
        assign_power_roles_to_subnets(A, generator_cnt, distr_subst_cnt, seed)
        relabel_nodes_by_subnet_role(A, role_prefixes_a)
    else:
        raise ValueError('Invalid value for parameter "roles" of network A: ' + roles_a)

    if config.has_option('build_a', 'layout'):
        if netw_a_model == 'user_defined_graph':
            logger.warning('Specifying a graph layout will override node positions specified in user defined graph A')
        layout = config.get('build_a', 'layout')
        layout = layout.lower()

        if config.has_option('build_a', 'span'):
            span = config.getfloat('build_a', 'span')
        else:
            span = 1.0

        if config.has_option('build_a', 'center_x'):
            center_x = config.getfloat('build_a', 'center_x')
            center_y = config.getfloat('build_a', 'center_y')
            center = [center_x, center_y]
        else:
            center = [span / 2.0, span / 2.0]

        # networkx 1.10 has some bugs in its layouts, there is extra code to check against that
        if parse_version(nx.__version__) > parse_version('1.10'):
            raise ValueError('Check issue #1750 and see if layouts work correctly in this NetworkX version')

        if layout in ['random', 'uar']:
            pos_by_node = uar_layout(A, span, center)
        elif layout == 'circular':
            if parse_version(nx.__version__) == parse_version('1.10'):
                pos_by_node = nx.circular_layout(A, dim=2, scale=span / 2.0, center=center)
            else:
                pos_by_node = nx.circular_layout(A, dim=2, scale=span)
        elif layout in ['spring', 'fruchterman_reingold']:
            logger.warning('This layout will produce a non-deterministic placement of A nodes')
            if parse_version(nx.__version__) == parse_version('1.10'):
                pos_by_node = nx.spring_layout(A, dim=2, scale=span / 2.0, center=center)
            else:
                pos_by_node = nx.spring_layout(A, dim=2, scale=span)
        else:
            raise ValueError('Invalid value for parameter "layout" of network A: ' + layout)

        # before NetworkX 1.10, layouts were centered on 0.5, 0.5 and then scaled
        if parse_version(nx.__version__) < parse_version('1.10'):
            if layout not in ['random', 'uar']:
                for node in pos_by_node:
                    pos_by_node[node][0] += center[0] - center[0] * span
                    pos_by_node[node][1] += center[1] - center[1] * span

        arrange_nodes(A, pos_by_node)

    # create the communication network

    netw_b_model = config.get('build_b', 'model')
    netw_b_model = netw_b_model.lower()
    roles_b = config.get('build_b', 'roles')
    netw_b_seed = seed

    if netw_b_model != 'user_defined_graph':
        if roles_b == 'relay_attached_controllers':
            node_cnt = config.getint('build_b', 'relays')
        else:
            relay_cnt = config.getint('build_b', 'relays')
            controller_cnt = config.getint('build_b', 'controllers')
            node_cnt = relay_cnt + controller_cnt

    if netw_b_model in ['rr', 'random_regular', 'random-regular']:
        degree = config.getint('build_b', 'degree')
        B = nx.random_regular_graph(degree, node_cnt, seed=netw_b_seed)
        while not nx.is_connected(B):
            netw_b_seed += 1
            B = nx.random_regular_graph(degree, node_cnt, seed=netw_b_seed)
    elif netw_b_model in ['ba', 'barabasi_albert', 'barabasi-albert']:
        m = config.getint('build_b', 'm')
        B = nx.barabasi_albert_graph(node_cnt, m, seed=netw_b_seed)
    elif netw_b_model == 'user_defined_graph':
        user_graph_fpath_b = config.get('build_b', 'user_graph_fpath')
        if os.path.isabs(user_graph_fpath_b) is False:
            user_graph_fpath_b = os.path.abspath(user_graph_fpath_b)
        if os.path.splitext(user_graph_fpath_b)[1].lower() == '.graphml':
            B = nx.read_graphml(user_graph_fpath_b, node_type=str)
        else:
            raise ValueError('Invalid value for parameter "user_graph_fpath" of network B, unsupported format')
    else:
        raise ValueError('Invalid value for parameter "model" of network B: ' + netw_b_model)

    B.graph['name'] = netw_b_name  # assign the correct name to the graph
    role_prefixes_b = {'relay': 'R', 'controller': 'C'}

    # assign roles and relabel nodes
    if roles_b == 'same':
        for node in B.nodes():
            B.node[node]['role'] = 'communication'
        relabel_nodes(B, netw_b_name)
    elif roles_b == 'random_relay_controller':
        relay_cnt = config.getint('build_b', 'relays')
        controller_cnt = config.getint('build_b', 'controllers')
        nodes = B.nodes()
        my_random.shuffle(nodes)
        for i in range(0, relay_cnt):
            candidate = nodes.pop()
            B.node[candidate]['role'] = 'relay'
        for i in range(0, controller_cnt):
            candidate = nodes.pop()
            B.node[candidate]['role'] = 'controller'
        relabel_nodes_by_role(B, role_prefixes_b)
    elif roles_b == 'relay_attached_controllers':
        controller_cnt = config.getint('build_b', 'controllers')  # number of control nodes

        # NOTE: this assumes all nodes were created new, and there are no nodes with a preassigned role
        nodes = B.nodes()  # these are all relay nodes
        for node in nodes:
            B.node[node]['role'] = 'relay'

        # done in case IDs are not continuous
        if isinstance(nodes[0], string_types):
            largest_id = max(B.nodes(), key=sf.natural_sort_key())  # works for strings
        else:
            largest_id = max(B.nodes())  # works for numbers

        for i in range(0, controller_cnt):  # add control nodes attaching them to existing relays
            if isinstance(largest_id, string_types):
                free_id = largest_id.join('_', i)
            else:
                free_id = largest_id + 1 + i
            B.add_node(free_id, {'role': 'controller'})

        relabel_nodes_by_role(B, role_prefixes_b)

        # create list of nodes by role
        relays = list()
        controllers = list()  # this will be used to position new controllers
        for node in B.nodes():
            if B.node[node]['role'] == 'relay':
                relays.append(node)
            elif B.node[node]['role'] == 'controller':
                controllers.append(node)
    else:
        raise ValueError('Invalid value for parameter "roles" of network B: ' + roles_b)

    # assign positions to nodes

    undefined_pos = True
    if config.has_option('build_b', 'layout'):
        if netw_b_model == 'user_defined_graph':
            logger.warning('Specifying a graph layout will override node positions specified in user defined graph B')
        undefined_pos = False
        layout = config.get('build_b', 'layout')
        layout = layout.lower()

        if config.has_option('build_b', 'span'):
            span = config.getfloat('build_b', 'span')
        else:
            span = 5.0

        if config.has_option('build_b', 'center_x'):
            center_x = config.getfloat('build_b', 'center_x')
            center_y = config.getfloat('build_b', 'center_y')
            center = [center_x, center_y]
            half_span = span / 2.0
            x_min = center_x - half_span
            x_max = center_x + half_span
            y_min = center_y - half_span
            y_max = center_y + half_span
        else:
            center = [span / 2.0, span / 2.0]
            x_min = 0
            x_max = span
            y_min = 0
            y_max = span

        # networkx 1.10 has some bugs in its layouts, there is extra code to check against that
        if parse_version(nx.__version__) > parse_version('1.10'):
            raise ValueError('Check issue #1750 and see if layouts work correctly in this NetworkX version')

        if layout in ['random', 'uar']:
            pos_by_node = uar_layout(B, span, center)
        elif layout == 'circular':
            if parse_version(nx.__version__) == parse_version('1.10'):
                pos_by_node = nx.circular_layout(B, dim=2, scale=span / 2.0, center=center)
            else:
                pos_by_node = nx.circular_layout(B, dim=2, scale=span)
        elif layout in ['spring', 'fruchterman_reingold']:
            logger.warning('This layout will produce a non-deterministic placement of B nodes')
            if parse_version(nx.__version__) == parse_version('1.10'):
                pos_by_node = nx.spring_layout(B, dim=2, scale=span / 2.0, center=center)
            else:
                pos_by_node = nx.spring_layout(B, dim=2, scale=span)
        else:
            raise ValueError('Invalid value for parameter "layout" of network B: ' + layout)

        # before NetworkX 1.10, layouts were centered on 0.5, 0.5 and then scaled
        if parse_version(nx.__version__) < parse_version('1.10'):
            if layout not in ['random', 'uar']:
                for node in pos_by_node:
                    pos_by_node[node][0] += center[0] - center[0] * span
                    pos_by_node[node][1] += center[1] - center[1] * span

        arrange_nodes(B, pos_by_node)

    elif netw_b_model == 'user_defined_graph':
        undefined_pos = False
        first_it = True
        for node in B.nodes():
            node_inst = B.node[node]
            x = node_inst['x']
            y = node_inst['y']
            if first_it is True:
                x_min = x
                x_max = x
                y_min = y
                y_max = y
                first_it = False
            else:
                if x > x_max:
                    x_max = x
                elif x < x_min:
                    x_min = x
                if y > y_max:
                    y_max = y
                elif y < y_min:
                    y_min = y
        span = max(x_max - x_min, y_max - y_min)

    if roles_b == 'relay_attached_controllers':
        # this is still half an hack
        if config.has_option('build_b', 'special_controller_placement'):
            special_controller_placement = config.getboolean('build_b', 'special_controller_placement')
        else:
            special_controller_placement = False

        if special_controller_placement is True:
            if len(controllers) == 1:
                node = controllers[0]
                B.node[node]['x'] = x_min + (x_max - x_min) / 2
                B.node[node]['y'] = y_min + (y_max - y_min) / 2
            else:  # TODO: implement this
                raise ValueError('special controller placement not implemented for more than 1 controller')
        elif undefined_pos is False:
            for node in controllers:
                B.node[node]['x'] = my_random.uniform(x_min, x_max)
                B.node[node]['y'] = my_random.uniform(y_min, y_max)

        if config.has_option('build_b', 'controller_attachment'):
            controller_attachment = config.get('build_b', 'controller_attachment')
        else:
            controller_attachment = 'random'

        if controller_attachment == 'random':
            for controller in controllers:
                B.add_edge(controller, my_random.choice(relays))
        elif controller_attachment == 'prefer_nearest':  # TODO: implement this
            raise ValueError('controller option not implemented yet')
        else:
            raise ValueError('Invalid value for parameter "controller_attachment" of network B: {}.'.format(
                controller_attachment))

    # create the interdependency network

    dep_model = config.get('build_inter', 'dependency_model')
    dep_model = dep_model.lower()

    if config.has_option('build_inter', 'prefer_nearest'):
        prefer_nearest = config.getboolean('build_inter', 'prefer_nearest')
    else:
        prefer_nearest = False
    if prefer_nearest is True and dep_model not in ['k-to-n', 'k_to_n', 'kton', 'k-n']:
        raise ValueError('The option prefer_nearest is currently only available for the k-n model')

    if dep_model in ['1-to-1', '1_to_1', '1to1']:
        I = create_n_to_n_dep(A, B, 1, seed=seed)
    elif dep_model in ['n-to-n', 'n_to_n', 'nton']:
        n = config.getint('build_inter', 'n')
        I = create_n_to_n_dep(A, B, n, seed=seed)
    elif dep_model in ['m-to-n', 'm_to_n', 'mton']:
        m = config.getint('build_inter', 'm')
        n = config.getint('build_inter', 'n')
        I = create_m_to_n_dep(A, B, m, n, seed=seed)
        for node in A.nodes():
            A.node[node]['role'] = 'power'
    elif dep_model in ['k-to-n', 'k_to_n', 'kton', 'k-n']:
        if not (roles_b == 'random_relay_controller' or roles_b == 'relay_attached_controllers'):
            raise ValueError('Invalid value for parameter "roles" of network B: {}. '
                             'When the k-n model is used, acceptable values are "random_relay_controller" '
                             'and "relay_attached_controllers"'.format(roles_b))
        k = config.getint('build_inter', 'k')
        n = config.getint('build_inter', 'n')
        if config.has_option('build_inter', 'com_access_points'):
            com_access_points = config.getint('build_inter', 'com_access_points')
        else:
            com_access_points = 1
        if roles_a != 'same':
            I = create_k_to_n_dep(A, B, k, n, prefer_nearest=prefer_nearest, power_roles=True,
                                  com_access_pts=com_access_points, seed=seed)
        else:
            I = create_k_to_n_dep(A, B, k, n, prefer_nearest=prefer_nearest, power_roles=False,
                                  com_access_pts=com_access_points, seed=seed)
    elif dep_model == 'ranged':
        radius = config.getfloat('build_inter', 'radius')
        I = create_ranged_dep(A, B, radius)
    else:
        raise ValueError('Invalid value for parameter "dependency_model" of inter network: ' + dep_model)

    I.graph['name'] = netw_inter_name  # assign the correct name to the graph

    # remember which network each node in the inter-graph is part of
    for node in I.nodes():
        if A.has_node(node):
            I.node[node]['network'] = A.graph['name']
        else:
            I.node[node]['network'] = B.graph['name']

    if config.has_option('build_inter', 'produce_max_matching'):
        produce_max_matching = config.getboolean('build_inter', 'produce_max_matching')
    else:
        produce_max_matching = False

    if produce_max_matching is True:
        max_matching_name = config.get('build_inter', 'max_matching_name')
        mm_I = nx.Graph()
        mm_I.graph['name'] = max_matching_name
        matching_edge_dict = nx.max_weight_matching(I.to_undirected())
        matching_adjlist = list(matching_edge_dict.items())
        mm_I.add_edges_from(matching_adjlist)

        for node in mm_I.nodes():
            if A.has_node(node):
                mm_I.node[node]['network'] = A.graph['name']
            else:
                mm_I.node[node]['network'] = B.graph['name']

    # draw networks

    if undefined_pos is True:
        logger.warning('No layout or positions specified for nodes. Graph will not be draw')
    else:
        #plt.axis('off')
        plt.tick_params(labeltop=True, labelright=True)
        # shifts used to position the drawings of the network graphs respective to the plot
        x_shift_a = 0.0
        y_shift_a = 0.0
        x_shift_b = 0.0
        y_shift_b = 0.0

        stretch = 1.0  # multiplier used to stretch the plot over a wider area (useful for dense graphs)
        font_size = 15.0  # value for the parameter of networkx.networkx_draw_labels
        node_col_by_role = {'power': 'r', 'generator': 'r', 'transmission_substation': 'plum',
                            'distribution_substation': 'magenta',
                            'communication': 'dodgerblue', 'controller': 'c', 'relay': 'dodgerblue'}
        # value for the parameters of networkx.networkx_draw_nodes
        draw_nodes_kwargs = {'node_size': 70, 'alpha': 0.7, 'linewidths': 0.0}
        # value for the parameters of networkx.networkx_draw_edges
        draw_edges_kwargs = {'width': 1.0, 'arrows': True, 'alpha': 0.7}
        sf.paint_netw_graphs(A, B, I, node_col_by_role, 'r', 'b', x_shift_a, y_shift_a, x_shift_b, y_shift_b, stretch,
                             font_size, draw_nodes_kwargs, draw_edges_kwargs)

        logger.info('output_dir = ' + output_dir)
        plt.savefig(os.path.join(output_dir, '_full.pdf'), bbox_inches="tight")
        # plt.show()
        plt.close()  # free memory

    # export networks

    nx.write_graphml(A, os.path.join(output_dir, netw_a_name + '.graphml'))
    nx.write_graphml(B, os.path.join(output_dir, netw_b_name + '.graphml'))
    nx.write_graphml(I, os.path.join(output_dir, netw_inter_name + '.graphml'))

    if produce_max_matching is True:
        nx.write_graphml(mm_I, os.path.join(output_dir, max_matching_name + '.graphml'))
