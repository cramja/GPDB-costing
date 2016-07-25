#! /usr/#!/usr/bin/env python

import subprocess
import os
import sys

from xforms_parse import parse, print_tree, tree_equals

DBG = False
xforms = open('xforms.txt', 'r').read().split()


def get_gucs():
    # SQL string enabling or disabling GUCS
    gucs = {
        "optimizer"                 :          "on",       
        "client_min_messages"       :          "'log'",    
        "optimizer_print_optimization_stats":  "on",
        "optimizer_print_xform"     :          "off",     
        "optimizer_print_plan"      :          "on"
    }
    gstring = ""
    for k,v in gucs.iteritems():
        gstring += "SET " +  k + "=" + v + ";\n"
    return gstring

def get_disable(xforms):
    if not xforms:
        return ""
    query = ""
    for xform in xforms:
        query += "SELECT disable_xform('{}');\n".format(xform)
    return query

def get_psql_port():
    pport = os.environ.get('PGPORT')
    if not pport:
        print "Error: PGPORT not set. Try to source gpdemo-env.sh"
        exit(-1)
    return pport

def get_query_cmd(query, disable=None):
    full_query = get_gucs() + get_disable(disable) + "\n\\timing\n" + query
    return "/usr/local/gpdb/bin/psql -p {} <<< \"{}\"".format(\
        get_psql_port(),\
        full_query)

def execute_query(query, disable=None):
    proc = subprocess.Popen([get_query_cmd(query,disable=disable)], shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.wait() != 0:
        print "command: {}\nfailed!".format(get_query_cmd(query,disable=disable))
        sys.exit(-1)

    return proc.stdout.read(), proc.stderr.read()

def parse_results(stdout, stderr):
    # takes the entire log of a single query execution and returns
    # (map of xforms to number of alts they produced, 
    # the final query plan tree)
    if not stderr:
        return None
    return parse(stdout, stderr)

plans = []
def add_plan(tree, disable):
    if not disable:
        disable = []

    for plan in plans:
        if tree_equals(plan[0], tree):
            plan[1].append(disable)
            return
    plans.append([tree, [disable]])

already_tested = []

def execute_for_results(query, disable=None):
    global xforms
    if not disable:
        disable = []
    if set(disable) in already_tested:
        return

    stdout, stderr = execute_query(query, disable)
    alt_map, plan_tree, time = parse_results(stdout, stderr)
    print time
    if not alt_map or not plan_tree:
        return

    add_plan(plan_tree, disable)
    already_tested.append(set(disable))

    if DBG:
        print "query:\n{}".format(query)
        if disable:
            print "disabled:"
            for xform in disable:
                print xform

        # print results if returned.
        print "final plan:"
        print_tree(plan_tree)
        print "xforms:"
        for xform, count in alt_map.iteritems():
            if xform in xforms:
                print "*{}, {}".format(xform, count)
            else:
                print " {}, {}".format(xform, count)

    if not disable:
        disable = []

    for xform, count in alt_map.iteritems():
        if xform in xforms and count > 0:
            execute_for_results(query, disable + [xform])

def main():   
    q = sys.stdin.read()

    execute_for_results(q)

    for plan in plans:
        print_tree(plan[0])
        for disable in plan[1]:
            print disable


if __name__ == '__main__':
    main()
