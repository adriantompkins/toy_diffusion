#!/bin/python                                                                                       

import os
from glob import glob
import subprocess as subproc
from multiprocessing import Pool,cpu_count
import getopt, sys
import toy_diffusion_2d
import ast

def main(argv):
    """ entry point"""

    lparallel=True

    f=open("diffusion_results.txt","w")
    f.close()

    # base defaults in toy_diffusion model now.
    pars=toy_diffusion_2d.defaults()

    # need to refer to these dictionaries in the following, and looop. 
    
    odir="./"

    arglist=["help","diffK=","crh_ad=","diurn_opt=","tau_sub=","odir=","nfig_hr=","cin_radius=","dt=","nday="]
    try:
        opts, args = getopt.getopt(argv,"h",arglist)
    except getopt.GetoptError:
        print ("arg error")
        print (argv)
   
        sys.exit(2)

    # REPLACE with argparse but handling equiv lists.
    for opt, arg in opts:
        if opt in ("-h","--help"):
            print ("check out this list: ",arglist)
            sys.exit()
        elif opt in ("--diffK"):
            list_diffK = ast.literal_eval(arg)
        elif opt in ("--crh_ad"):
            list_crh_ad = ast.literal_eval(arg)
        elif opt in ("--tau_sub"):
            list_tau_sub = ast.literal_eval(arg)
        elif opt in ("--cin_radius"):
            list_cin_radius = ast.literal_eval(arg)
        elif opt in ("--diurn_opt"):
            list_diurn_opt = ast.literal_eval(arg)
        elif opt in ("--nfig_hr"):
            pars["nfig_hr"] = int(arg)
        elif opt in ("--nday"):
            pars["nday"] = int(arg)
        elif opt in ("--dt"):
            pars["dt"] = float(arg)
        elif opt in ("--odir"):
            pars["odir"] = arg

    # make a list of dictionaries with ALL combinations of the 3 arguments
#    arglist=[{"diffK":d,"tau_sub":t,"crh_ad":c,"nfig_hr":pars["nfig_hr"],"cin_radius":cr,"diurn_opt":dc,"domain_xy":pars["domain_xy"],"nday":pars["nday"],"dxy":pars["dxy"],"dt":pars["dt"]} for d in pars["diffK"] for t in pars["tau_sub"] for c in pars["crh_ad"] for cr in pars["cin_radius"] for dc in pars["diurn_opt"] ]    

    arglist=[{**pars,"diffK":d,"tau_sub":t,"crh_ad":c,"cin_radius":cr,"diurn_opt":dc} for d in list_diffK for t in list_tau_sub for c in list_crh_ad for cr in list_cin_radius for dc in list_diurn_opt]

    print("check ",arglist)

    # now farm out the jobs over the triple loop
    # only use the number of processors needed, or max-1
    if (lparallel): # parallel mode
        ncore=min(len(arglist),int(cpu_count()))
        #os.sched_setaffinity(0, set(range(cpu_count())))
        os.system('taskset -cp 0-%d %s' % (ncore, os.getpid()))
        with Pool(processes=ncore) as p:
            p.map(toy_diffusion_2d.main,arglist)
        print ("done parallel")
    else: # serial model
        for args in arglist:
             toy_diffusion_2d.main(args)
        print ("done serial")

if __name__ == "__main__":
    main(sys.argv[1:])
