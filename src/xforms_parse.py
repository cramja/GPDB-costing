import re
import sys

pat_xform = re.compile(ur'.*TRACE,"Xform: (.*)')
pat_alt_num = re.compile(ur'^\d+\:')
pat_tree_line = re.compile(ur'--(\w+)')
pat_timing = re.compile(ur'Time\:\s+(\d+\.\d+)\s+ms', re.MULTILINE)
pat_xforms_stats = re.compile(ur'\[OPT\]\:\s*<Begin Xforms.*>\n([^[]*)\[OPT\]: <End Xforms', re.MULTILINE)
pat_calls = re.compile(ur'(CX\w+)\:\s+(\d+)\scalls', re.MULTILINE)

def preprocess_plan(raw):
    # remove any square bracket groups. They often contain parsing anomolies
    pat_sb = re.compile(ur'\[[^][]*\]', re.MULTILINE)
    while pat_sb.search(raw):
        raw = pat_sb.sub("", raw)
    return raw
    
def parse(std_out, std_err):
    if "LOG:  Planner produced plan :0" in std_err:
        return None, None
    return parse_for_xforms(std_err), parse_for_plan(std_err), parse_for_time(std_out)

def parse_for_time(raw):
    times = pat_timing.findall(raw)
    if not times:
        return -1
    return float(times[len(times) -1])

def find_physical_plan(raw):
    # finds the last plan tree in a query's STDERR output
    plans = []
    in_plan = False
    lines = raw.split('\n')
    lines.reverse()
    lines_last = []
    lcnt = 0
    for line in lines:
        lines_last.append(line)
        if "\"," in line:
            lcnt += 1
            if lcnt > 1:
                break

    lines_last.reverse()
    for line in lines_last:
        if "Physical plan:" in line:
            in_plan = True
            plans.append("")
        elif in_plan and "--" in line:
            plans[len(plans) - 1] += line + "\n"
        elif in_plan:
            in_plan = False
    return plans


def parse_for_plan(raw):
    preprocessed = preprocess_plan(raw)
    plans = find_physical_plan(preprocessed)
    if len(plans) < 1:
        return None
    # parse the last plan
    return parse_plan(plans.pop().rstrip())
    
def parse_for_xforms(raw):
    # returns a map of xforms to number of alternatives they produced
    m = pat_xforms_stats.findall(raw)

    if not m:
        return None
    xforms = m.pop()
    xmap = {}
    
    matches = pat_calls.findall(xforms)
    for m in matches:
        xmap[m[0]] = float(m[1])
    return xmap

def parse_tree_line(line):
    # (line number, node name)
    n = line.find("--")/3

    m = pat_tree_line.search(line)
    if m:
        return n, m.group(1)
    else:
        return n, "Misparse" 

def tree_fold(node_q, n_level):
    while len(node_q) > n_level + 1:
        orphans = node_q.pop()
        lq = len(node_q) - 1
        surrogate = node_q[lq].pop()
        surrogate['children'] = surrogate['children'] + orphans
        node_q[lq].append(surrogate)

def parse_plan(tree):
    # return a python representation of the expression tree
    node_q = []
    for line in tree.split('\n'):
        n_level, n_name = parse_tree_line(line)
        node = {'name':n_name, 'children':[]}
        if len(node_q) == n_level:
            node_q.append([node])
        else:
            tree_fold(node_q, n_level)
            node_q[n_level].append(node)

    tree_fold(node_q, 0)
    return node_q[0][0]

def print_tree(ptree):
    if ptree:
        print_tree_r(ptree, 0)

def print_tree_r(stree, level):
    print " " * level * 2 + stree['name']
    for child in stree['children']:
        print_tree_r(child, level + 1)

def tree_equals(t1, t2):
    if t1['name'] != t2['name']:
        return False
    if len(t1['children']) != len(t2['children']):
        return False
    for i in range(len(t1['children'])):
        if not tree_equals(t1['children'][i], t2['children'][i]):
            return False

    return True

def main():
    # read stdin and do counting
    #print parse(sys.stdin.read())
    tree = parse_for_plan(sys.stdin.read())
    print_tree(tree)
        

if __name__ == '__main__':
    main()
