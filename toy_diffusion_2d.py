import matplotlib.pyplot as plt
from scipy.ndimage.filters import uniform_filter1d
from scipy import spatial
import sys
from datetime import datetime
import os, time
import numpy as np
from netCDF4 import Dataset
import ast 
import getargs
import subprocess

#
# this is a new version of the diffusion code in 2D
# I decided to rewite from scratch as the plotting and structure were
# rather clunky in the previous code
#

#
# Dq/Dt= C - S - D
# C=Convection
# S=Subsidence
# D=Diffusion
#
# S=constant tau relaxation here
# C=fast relaxation to saturated+detrained IWP
# D=Diffusion at constant K
#
# Convection is an average rate
# 1. distribute this over the day according to diurnal cycle
# 2. Choose where to locate according to
#    a) CRH profile of Bretherton
#    b) A Coldpool inhibition function

# surface nfig out frequency (slows it down a lot!)

def defaults():
    # NOTE: anything in pars can be controlled from command line
    # and is saved in both nc files 
    pars={}

    # key run default values:
    pars["diffK"]=37500. # m2/s
    # crh_ad from Rushley et al 18, https://doi.org/10.1002/2017GL076296
    # See also Bretherton ref therein, 16.12=trmm v5, 14.72 = trmm v7
    pars["crh_ad"]=14.72
    pars["tau_sub"]=20. # days!
    pars["cin_radius"]=-99. # switched off by default
    pars["diurn_opt"]=0

    # COLDPOOL: diffusion K=eps.u.L
    pars["diffCIN"]=0.25*10*50.e3 # DEFAULT 0.15*10*20.e3

    # velocity scales
    pars["w_cnv"]=10.

    # convective detrained value
    # this is 1+L-IWP/PW, IWP max ~ 3kg/m**2 for 60kg/m**2 PW
    # IWP refs from CloudSat
    pars["crh_det"]=1.05

    pars["tau_cin"]=3*3600. # 3 hour lifetime for coldpools (seconds) 
    pars["cnv_lifetime"]=1800. # e-folding convection detrains for 30mins
    pars["tau_cnv"]=60. # timescale of convection moistening seconds

    # fake diurnal cycle pars
    pars["diurn_a"]=0.6
    pars["diurn_p"]=2.0

    # initial conditions
    pars["crh_init_mn"]=0.8 # initial CRH mean
    pars["crh_init_sd"]=0.0 # initial CRH standard deviation

    # domain size and integration pars:
    pars["nday"]=5 # short for testing
    pars["domain_xy"]=500.e3
    pars["dxy"]=2000.
    pars["dt"]=60.     # timestep of model

    # diagnostics:
    pars["nfig_hr"]=24 # freq of maps slices
    return(pars)


def diffusion(fld,a0,a1,ndiff):
    """ diffusion of field using Dufort Frankel explicit scheme"""
    """ argments are fld: 3 slice field"""
    """ a0 and a1 are the DF coefficients"""
    for i in range(ndiff):
        fld[2,:,:]=a0*fld[0,:,:]+a1*(
        np.roll(fld[1,:,:],-1,axis=0) +
        np.roll(fld[1,:,:], 1,axis=0) +
        np.roll(fld[1,:,:],-1,axis=1) +
        np.roll(fld[1,:,:], 1,axis=1))
        fld=np.roll(fld,-1,axis=0) # 2 to 1, 1 to 0 and 0 overwritten
    return(fld)


# PUT default values here in argument list dictionary :-) 
def main(pars):
    """main routine for diff 2d model"""

    execute=sys.argv[0]
    try:
        version=subprocess.check_output(["git", "describe"]).strip()
    except: 
        version="unknown"

    # split some options from dictionary
    dxy=pars["dxy"]
    dt=pars["dt"]
    domain_x=domain_y=pars["domain_xy"]

    tab="diffK"+str(pars["diffK"])+"_tausub"+str(pars["tau_sub"])[0:6]+"_crhad"+str(pars["crh_ad"])+"_cin_radius"+str(pars["cin_radius"])+"_diurn"+str(pars["diurn_opt"])
    sfig_day=0
    dx=dy=dxy
    dxkm=dx/1000.
    
    # diurnal cycle: 0="none", 1="weak", 2="strong"

    # timestep
    dtdiff=dt
    ndiff=int(dt/dtdiff)

    # initial column RH


    # CRH: diffusion K=eps.u.L
    # diffK=0.15*5*50e3    # DEFAULT :  0.4*5*50.e3
    

    # timescale of subsidence and convection
    #tau_sub=20 # days

    # thresh for cin inhibition 



    # diurn_o=0.35

    
    ltest=False
    
    #-------------------
    # derived stuff
    #-------------------
    #
    # sub facs
    #

    w_sub=15000./(86400.*pars["tau_sub"]) # subsidence velocity is depth of trop/tau_sub.
    dt_tau_sub=1.0+dt/(86400.*pars["tau_sub"])
    dt_tau_cnv=dt/pars["tau_cnv"]
    dt_tau_cin_fac=1.0+dt/pars["tau_cin"]
    dt_tau_cin=dt/pars["tau_cin"]

    # will assume diffusion same in both directions:
    alfa=pars["diffK"]*dtdiff/(dxy*dxy)
    alf0=(1.0-4.0*alfa)/(1.0+4.0*alfa) # level zero factor 
    alf1=2.*alfa/(1.0+4.0*alfa) # level 1 factor
    # print(" first alf",pars["diffK"],alfa,alf0,alf1)
    alfacin=pars["diffCIN"]*dtdiff/(dxy*dxy)
    alfcin0=(1.0-4.0*alfacin)/(1.0+4.0*alfacin) # level zero factor 
    alfcin1=2.*alfacin/(1.0+4.0*alfacin) # level 1 factor

    #print(" cin alf",alfcin0,alfcin1)

    cnv_death=min(dt/pars["cnv_lifetime"],1.0)
    nx=int(domain_x/dxy)+1 ; ny=int(domain_y/dxy)+1
    x1d=np.linspace(0,domain_x,nx)
    y1d=np.linspace(0,domain_y,nx)
    x,y=np.meshgrid(x1d/1000,y1d/1000) # grid in km
    allidx=np.argwhere(np.zeros([nx,ny])<1) # all true

    print ("toy_diffusion_2d model of atmosphere")
    print ("opening output maps/stats:",tab)

    # open the netcdf files:
    nc1 = Dataset("td_maps_"+tab+".nc", "w", format="NETCDF4")
    nc2 = Dataset("td_stats_"+tab+".nc", "w", format="NETCDF4")

    # dims:                  
    time1=nc1.createDimension("time", None)
    x1=nc1.createDimension("x", ny)
    y1=nc1.createDimension("y", nx)
    nccnt = 0 # counter for ncindex

    # vars
    var_time1 = nc1.createVariable("time","f8",("time",))
    var_x = nc1.createVariable("X","f4",("x",))
    var_y = nc1.createVariable("Y","f4",("y",))

    # two dimensions unlimited
    var_CRH=nc1.createVariable("CRH","f4",("time","y","x",))
    var_CRH.units = "fraction"
    var_CRH.long_name = "Column total water relative humidity"
    var_D2C=nc1.createVariable("D2C","f4",("time","y","x",))
    var_D2C.units = "km"
    var_D2C.long_name = "Distance to nearest updraft"

    if pars["cin_radius"]>0:
        var_CIN=nc1.createVariable("CIN","f4",("time","y","x",))
        var_CIN.units = "fraction"

    # timeseries file
    dim_time2 = nc2.createDimension("time", None)
    var_time2 = nc2.createVariable("time","f8",("time",))
    crh_mean = nc2.createVariable("CRH_mean","f8",("time",))
    crh_std = nc2.createVariable("CRH_std","f8",("time",))
    crh_in_new = nc2.createVariable("CRH_new_conv","f8",("time",))
    crh_driest = nc2.createVariable("CRH_driest","f8",("time",))
    nc2_ncnv = nc2.createVariable("nconv","i8",("time",))
    d2c_95=nc2.createVariable("D2C95","f8",("time",))
    d2c_max=nc2.createVariable("D2C_max","f8",("time",))
    d2c_mean=nc2.createVariable("D2C_mean","f8",("time",))
    d2c_median=nc2.createVariable("D2C_median","f8",("time",))

    d2c_95.long_name="distance to convection 95th percentile"
    d2c_95.units="km"
    d2c_max.long_name="distance to convection - maximum"
    d2c_max.units="km"
    d2c_mean.long_name="distance to convection - mean"
    d2c_mean.units="km"
    d2c_median.long_name="distance to convection - median"
    d2c_median.units="km"
    
    crh_mean.long_name = "CRH domain mean"
    crh_std.long_name = "CRH domain standard deviation"
    crh_in_new.long_name = "CRH value in new convective locations"
    nc2_ncnv.long_name="Total number of convective events"
    nc2_ncnv.units="total number"

    #
    # Global attributes here for both files:
    #
    nc1.description="2D diffusion model, 2d slice snapshots"
    nc2.description="2D diffusion model, Timeseries statistics"
    nc1.history=nc2.history="Created "+datetime.today().strftime('%Y-%m-%d')
    nc1.source=nc2.source="Adrian Tompkins (tompkins@ictp.it)"
    nc1.center=nc2.center="International Centre for Theoretical Physics (ICTP)"
    nc1.exe=nc2.exe=execute
    nc1.version=nc2.version=version



    #
    # All users defined values in par also saved as global attributes
    print ("------------")
    print ("- RUN PARS -")
    print ("------------")
    for key,val in pars.items():
        print (key,"=",val)
        setattr(nc1,key,pars[key])
        setattr(nc2,key,pars[key])
    print ("-----------")

    # parameter settings:
#    nc1.diffK=nc2.diffK=pars["diffK"]
#    nc1.tau_sub=nc2.tau_sub=tau_sub
#    nc1.crh_ad=nc2.crh_ad=float(crh_ad)
#    nc1.crh_det=nc2.crh_det=crh_det
    #nc1.cin_radius=nc2.cin_radius=cin_radius
    #nc1.crh_init_mn=nc2.crh_init_mn=pars["crh_init_mn"]
    #nc1.crh_init_sd=nc2.crh_init_sd=pars["crh_init_sd"]
    #nc1.cnv_lifetime=nc2.cnv_lifetime=cnv_lifetime
    #nc1.tau_cnv=nc2.tau_cnv=tau_cnv
    #nc1.tau_cin=nc2.tau_cin=tau_cin
#    nc1.diffCIN=nc2.diffCIN=diffCIN
#    nc1.w_cnv=nc2.w_cnv=w_cnv
    #nc1.diurn=nc2.diurn=diurn_opt


    var_y.units = "km"
    var_x.units = "km"
    var_time1.units=var_time2.units="seconds since 2000-01-01 00:00:00.0"
    var_time1.calendar=var_time2.calendar="gregorian"

    var_y[:]=y1d*dxkm
    var_x[:]=x1d*dxkm

    # file 2 is the timeseries file

    # number of timesteps:
    nt=int(pars["nday"]*86400/dt)
    times=np.arange(0,nt,1)
    days=times*dt/86400.

    # total number of events to distribute
    ncnv_tot=int(nt*nx*ny*w_sub/pars["w_cnv"])

    #
    # set up plots, timeseries
    #

    # 3 options of diurnal cycle!
    if pars["diurn_opt"]==0:
        pdiurn=np.ones(nt)
    if pars["diurn_opt"]==1:
        pdiurn=pars["diurn_a"]*np.sin(np.pi*2*times*dt/86400.)+1.0
    if pars["diurn_opt"]==2:
        pdiurn=(np.sin(np.pi*2*times*dt/86400.)+1.0)**pars["diurn_p"]

    pdiurn/=np.sum(pdiurn) # probs must add to 1

    #
    # number of convective events as function of time
    # 
    ncnv=np.bincount(np.random.choice(times,ncnv_tot,p=pdiurn),minlength=nt)
    ncnv_overflow=0 # storage for overflow 
    Nsmth=int(pars["cnv_lifetime"]/dt) # need to smooth to lifetime of convection
    if Nsmth>1:
        ncnv=uniform_filter1d(ncnv,size=Nsmth)

    # save to netcdf
        

    # index for convection locations, 0 or 1 
    cnv_idx=np.zeros([nx,ny],dtype=np.int)

    # CIN array for coldpools
    cin=np.zeros([3,nx,ny])

    # crh, 3 time-level DF explicit scheme:
    crh=np.random.normal(loc=pars["crh_init_mn"],scale=pars["crh_init_sd"],size=[3,nx,ny])

    # TEST top hat
    mp=int(nx/2)
    if ltest:
        crh[:,mp-5:mp+5,mp-5:mp+5]=1.0

    dummy_idx=np.arange(0,nx*ny,1)

    ifig=0

    # loop over time
    for it in range(nt):
        if (it*dt)%(24*3600)==0:
            print ("day ",int(it*dt/86400.))
        # explicit diffusion.
        # use np.roll for efficient periodic boundary conditions
        crh=diffusion(crh,alf0,alf1,ndiff)

        #
        # now apply implicit solution for subsidence
        #
        crh[1,:,:]/=dt_tau_sub

        #
        # now apply implicit solution for convection 
        #

        # First calculate residual N to generate this timestep
        ncnv_curr=np.sum(cnv_idx)
        ncnv_new=ncnv[it]+ncnv_overflow-ncnv_curr
        #print("current",ncnv_curr,"ncnv ",ncnv[it]," overflow",ncnv_overflow," new ",ncnv_new)
        ncnv_overflow=0 # overflow accounted for, so reset to zero
        if (ncnv_new<0):
            # we have too many convection events still alive, so we borrow from a future
            # timestep.
            ncnv_overflow=ncnv_new  # store overflow
            ncnv_new=0 #  can't have neg new events 

        #
        # now need to decide where to put the new events, 
        # bretherton updated CRH - with Craig adjustment
        prob_crh=np.exp(pars["crh_ad"]*crh[1,:,:])-1.0

        # fudge to stop 2 conv in one place, coldpool will sort
        prob_crh*=(1-cnv_idx)
        prob_crh/=np.mean(prob_crh)

        # INCLUDE cold pool here:
        #prob_cin=np.where(cin[1,:,:]>cin_thresh,0.0,1.0)
        #prob_cin=1.0-np.power(cin[1,:,:],0.15)
        prob_cin=1.0-cin[1,:,:]

        # product of 2:
        prob=prob_crh
        if pars["cin_radius"]>0:
            prob*=prob_cin # switch off coldpools here:
        prob/=np.sum(prob) # normalized
        prob1d=prob.flatten()

        #
        # sample the index using the prob function
        # and PLACE NEW EVENTS:
        #

        coords=np.random.choice(dummy_idx,ncnv_new,p=prob1d,replace=False)
        new_loc=np.unravel_index(coords,(nx,ny))
        cnv_idx[new_loc]=1 # new events in slice zero
        slice=crh[1,:,:]
        if ncnv_new>0:
            crh_in_new[it]=np.mean(slice[new_loc])
        crh_driest[it]=np.min(slice)


        # cnv_idx[mp,mp]=1 # TEST

        # update humidity
        # collape conv array again # Q_Detrain where conv, zero otherwise
        crh[1,:,:]=(crh[1,:,:]+cnv_idx*pars["crh_det"]*dt_tau_cnv)/(1.0+cnv_idx*dt_tau_cnv)

        #
        # calculate distance to convection 
        #
        cnv_coords=np.argwhere(cnv_idx) #need to update to include new events
        ncnv_curr=np.sum(cnv_idx)
        nc2_ncnv[it]=ncnv_curr
        if ncnv_curr>0:
            #cnvdst*=dxkm
            for xoff in [0,nx,-nx]:
                for yoff in [0,-ny,ny]:
                    if xoff==0 and yoff==0:
                        j9=cnv_coords.copy()
                    else:
                        jo=cnv_coords.copy()
                        jo[:,0]+=xoff
                        jo[:,1]+=yoff
                        j9=np.vstack((j9,jo))
            tree=spatial.cKDTree(j9)
            cnvdst,minidx=tree.query(allidx)
            cnvdst=cnvdst.reshape([nx,ny])
            cnvdst*=dxkm
        else:
            cnvdst=np.ones([nx,ny])*1.e6

        #
        # update coldpool here
        #
        if pars["cin_radius"]>0:
            maskcin=np.where(cnvdst<pars["cin_radius"],1,0)
            cin[1,:,:]=cin[1,:,:]+maskcin # all conv points sets to 1
            cin=np.clip(cin,0,1)
            # cin[1,:,:]*=dt_tau_cin_fac # implicit
            cin[1,:,:]-=dt_tau_cin # explicit 
            cin=diffusion(cin,alfcin0,alfcin1,ndiff)            
            cin=np.clip(cin,0,1)

        #
        # random death of cells.
        # 
        mask=np.where(np.random.uniform(size=(nx,ny))<=cnv_death,0,1)
        cnv_idx*=mask

        #
        cnv_loc=np.argwhere(cnv_idx==1)    

        # 
        # netcdf output for timeseries:
        #
        var_time2[it]=it*dt
        crh_mean[it]=np.mean(crh[1,:,:])
        crh_std[it]=np.std(crh[1,:,:])
        d2c_mean[it]=np.mean(cnvdst)
        d2c_median[it]=np.median(cnvdst)
        d2c_max[it]=np.max(cnvdst)
        d2c_95[it]=np.percentile(cnvdst,95)

        
        day=it*dt/86400
        if (it*dt)%(pars["nfig_hr"]*3600)==0:
            var_time1[nccnt]=it*dt
            var_CRH[nccnt,:,:]=crh[1,:,:]     
            var_D2C[nccnt,:,:]=cnvdst     
            if pars["cin_radius"]>0:
                var_CIN[nccnt,:,:]=cin[1,:,:]     

            nccnt+=1


    nc1.close()
    nc2.close()

if __name__ == "__main__":
    pars=defaults() 
    pars=getargs.getargs(pars)
    main(pars)
