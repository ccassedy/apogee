from functools import wraps
import os, os.path
import tempfile
import numpy
import apogee.tools.path as appath
from apogee.tools import paramIndx
from apogee.tools.read import modelspecOnApStarWavegrid
import apogee.tools.read as apread
def paramArrayInputDecorator(startIndx):
    """Decorator to parse spectral input parameters given as arrays,
    assumes the arguments are: something,somethingelse,teff,logg,metals,am,nm,cm,vmicro=,
    startindx is the index in arguments where the teff,logg,... sequence starts"""
    def wrapper(func):
        @wraps(func)
        def scalar_wrapper(*args,**kwargs):
            if numpy.array(args[startIndx]).shape == ():
                newargs= ()
                for ii in range(startIndx):
                    newargs= newargs+(args[ii],)
                for ii in range(6):
                    newargs= newargs+(numpy.array([args[ii+startIndx]]),)
                for ii in range(len(args)-6-startIndx):
                    newargs= newargs+(args[ii+startIndx+6],)
                args= newargs
                if not kwargs.get('vm',None) is None:
                    kwargs['vm']= numpy.array([kwargs['vm']])
            result= func(*args,**kwargs)
            return result
        return scalar_wrapper
    return wrapper

@modelspecOnApStarWavegrid
@paramArrayInputDecorator(0)
def interpolate(teff,logg,metals,am,nm,cm,vm=None,
                lib='GK',pca=True,sixd=True,dr=None,
                offile=None,
                inter=3,f_format=1,f_access=None,
                verbose=False,apStarWavegrid=True):
    """
    NAME:
       interpolate
    PURPOSE:
       Interpolate the model spectral library to give a model spectrum at a desired point
    INPUT:
       Parameters (can be 1D arrays, in this case multiple spectra will be returned):
          teff - Effective temperature (K)
          logg - log10 surface gravity / cm s^-2
          metals - overall metallicity
          am - [alpha/M]
          nm - [N/M]
          cm - [C/M]
          vm= if using the 7D library, also specify the microturbulence
       Library options:
          lib= ('GK') spectral library
          pca= (True) if True, use a PCA compressed library
          sixd= (True) if True, use the 6D library (w/o vm)
          dr= data release
       FERRE options:
          inter= (3) order of the interpolation
          f_format= (1) file format (0=ascii, 1=unf)
          f_access= (None) 0: load whole library, 1: use direct access (for small numbers of interpolations), None: automatically determine a good value (currently, 1)
       Output options:
          apStarWavegrid= (True) if True, output the spectrum onto the apStar wavelength grid, otherwise just give the ASPCAP version (blue+green+red directly concatenated)
          offile= (None) if offile is set, the FERRE OFFILE is saved to this file, otherwise this file is removed
       verbose= (False) if True, run FERRE in verbose mode
    OUTPUT:
       spec[nspec,nwave]
    HISTORY:
       2015-01-23 - Written - Bovy (IAS)
    """
    import apogee.modelspec.ferre as ferre
    # Setup temporary directory to run FERRE from
    tmpDir= tempfile.mkdtemp(dir='./')
    try:
        # First write the ipf file with the parameters
        ferre.write_ipf(tmpDir,teff,logg,metals,am,nm,cm,vm=vm)
        # Now write the input.nml file
        if f_access is None:
            f_access= 1
        ferre.write_input_nml(tmpDir,'input.ipf','output.dat',ndim=7-sixd,
                              nov=0,
                              synthfile=appath.ferreModelLibraryPath\
                                  (lib=lib,pca=pca,sixd=sixd,dr=dr,
                                   header=True,unf=False),
                              inter=inter,f_format=f_format,
                              f_access=f_access)
        # Run FERRE
        ferre.run_ferre(tmpDir,verbose=verbose)
        # Read the output
        out= numpy.loadtxt(os.path.join(tmpDir,'output.dat'))
        if not offile is None:
            os.rename(os.path.join(tmpDir,'output.dat'),offile)
    finally:
        # Clean up
        if os.path.exists(os.path.join(tmpDir,'input.ipf')):
            os.remove(os.path.join(tmpDir,'input.ipf'))
        if os.path.exists(os.path.join(tmpDir,'input.nml')):
            os.remove(os.path.join(tmpDir,'input.nml'))
        if os.path.exists(os.path.join(tmpDir,'output.dat')):
            os.remove(os.path.join(tmpDir,'output.dat'))
        os.rmdir(tmpDir)
    return out

def fit(spec,specerr,
        teff=4750.,logg=2.5,metals=0.,am=0.,nm=0.,cm=0.,vm=None,
        fixteff=False,fixlogg=False,fixmetals=False,fixam=False,fixcm=False,
        fixnm=False,fixvm=False,
        lib='GK',pca=True,sixd=True,dr=None,
        offile=None,
        inter=3,f_format=1,f_access=None,
        errbar=1,indini=[1,1,1,2,2,3],init=1,
        verbose=False):
    """
    NAME:
       ifit
    PURPOSE:
       Fit a model spectrum to a given data spectrum
    INPUT:
       Either:
          (1) location ID - single or list/array of location IDs
              APOGEE ID - single or list/array of APOGEE IDs; loads aspcapStar
          (2) spec - spectrum: can be (nwave) or (nspec,nwave)
              specerr - spectrum errors: can be (nwave) or (nspec,nwave)
       Input parameters (can be 1D arrays); only used when init=0
          teff= (4750.) Effective temperature (K)
          logg= (2.5) log10 surface gravity / cm s^-2
          metals= (0.) overall metallicity
          am= (0.) [alpha/M]
          nm= (0.) [N/M]
          cm= (0.) [C/M]
          vm= if using the 7D library, also specify the microturbulence
       Fit options:
          fixteff= (False) if True, fix teff at the input value
          fixlogg= (False) if True, fix logg at the input value
          fixmetals= (False) if True, fix metals at the input value
          fixam= (False) if True, fix am at the input value
          fixcm= (False) if True, fix cm at the input value
          fixnm= (False) if True, fix nm at the input value
          fixvm= (False) if True, fix vm at the input value (only if sixd is False)
       Library options:
          lib= ('GK') spectral library
          pca= (True) if True, use a PCA compressed library
          sixd= (True) if True, use the 6D library (w/o vm)
          dr= data release
       FERRE options:
          inter= (3) order of the interpolation
          errbar= (1) method for calculating the error bars
          indini= ([2,1,1,1,3,2]) how to initialize the search (int or array/list with ndim entries)
          init= (1) if 0, initialize the search at the parameters in the pfile
          f_format= (1) file format (0=ascii, 1=unf)
          f_access= (None) 0: load whole library, 1: use direct access (for small numbers of interpolations), None: automatically determine a good value (currently, 1)
       Output options:
          offile= (None) if offile is set, the FERRE OFFILE is saved to this file, otherwise this file is removed
       verbose= (False) if True, run FERRE in verbose mode
    OUTPUT:
       best-fit parameters (nspec,nparams); in the same order as the FPARAM APOGEE data product
    HISTORY:
       2015-01-29 - Written - Bovy (IAS)
    """
    # Parse input
    if isinstance(specerr,str): # locID+APOGEE-ID; array
        ispec= apread.aspcapStar(spec,specerr,ext=1,header=False,
                                 aspcapWavegrid=True)
        ispecerr= apread.aspcapStar(spec,specerr,ext=2,header=False,
                                    aspcapWavegrid=True)
        spec= ispec
        specerr= ispecerr
    elif (isinstance(specerr,(list,numpy.ndarray)) \
              and isinstance(specerr[0],str)): # locID+APOGEE-ID; array
        nspec= len(specerr)
        ispec= numpy.empty((nspec,7214))
        ispecerr= numpy.empty((nspec,7214))
        for ii in range(nspec):
            ispec[ii]= apread.aspcapStar(spec[ii],specerr[ii],ext=1,
                                         header=False,aspcapWavegrid=True)
            ispecerr[ii]= apread.aspcapStar(spec[ii],specerr[ii],ext=2,
                                            header=False,aspcapWavegrid=True)
        spec= ispec
        specerr= ispecerr
    # Make sure the Teff etc. have the right dimensionality
    if len(spec.shape) == 1:
        nspec= 1
    else:
        nspec= spec.shape[0]
    if nspec > 1 and isinstance(teff,float):
        teff= teff*numpy.ones(nspec)
    if nspec > 1 and isinstance(logg,float):
        logg= logg*numpy.ones(nspec)
    if nspec > 1 and isinstance(metals,float):
        metals= metals*numpy.ones(nspec)
    if nspec > 1 and isinstance(am,float):
        am= am*numpy.ones(nspec)
    if nspec > 1 and isinstance(nm,float):
        nm= nm*numpy.ones(nspec)
    if nspec > 1 and isinstance(cm,float):
        cm= cm*numpy.ones(nspec)
    if nspec > 1 and not vm is None and isinstance(vm,float):
        vm= vm*numpy.ones(nspec)
    if dr is None: dr= appath._default_dr()
    # Fix any of the parameters?
    indv= []
    if not sixd and not fixvm:
        indv.append(1)
    if not fixcm:
        indv.append(2-sixd)
    if not fixnm:
        indv.append(3-sixd)
    if not fixam:
        indv.append(4-sixd)
    if not fixmetals:
        indv.append(5-sixd)
    if not fixlogg:
        indv.append(6-sixd)
    if not fixteff:
        indv.append(7-sixd)
    # Setup temporary directory to run FERRE from
    import apogee.modelspec.ferre as ferre
    tmpDir= tempfile.mkdtemp(dir='./')
    try:
        # First write the ipf file with the parameters
        ferre.write_ipf(tmpDir,teff,logg,metals,am,nm,cm,vm=vm)
        # Write the file with the fluxes and the flux errors
        ferre.write_ffile(tmpDir,spec,specerr=specerr)
        # Now write the input.nml file
        if f_access is None:
            f_access= 1
        ferre.write_input_nml(tmpDir,'input.ipf','output.dat',ndim=7-sixd,
                              nov=7-sixd-fixcm-fixnm-fixam-fixmetals\
                                  -fixlogg-fixteff,
                              indv=indv,
                              synthfile=appath.ferreModelLibraryPath\
                                  (lib=lib,pca=pca,sixd=sixd,dr=dr,
                                   header=True,unf=False),
                              ffile='input.frd',erfile='input.err',
                              opfile='output.opf',
                              inter=inter,f_format=f_format,
                              errbar=errbar,indini=indini,init=init,
                              f_access=f_access)
        # Run FERRE
        ferre.run_ferre(tmpDir,verbose=verbose)
        # Read the output
        cols= (1,2,3,4,5,6)
        tmpOut= numpy.loadtxt(os.path.join(tmpDir,'output.opf'),usecols=cols)
        if len(spec.shape) == 1:
            out= numpy.zeros((1,7))
            tmpOut= numpy.reshape(tmpOut,(1,7-sixd))
        else:
            out= numpy.zeros((nspec,7))
        out[:,paramIndx('TEFF')]= tmpOut[:,-1]
        out[:,paramIndx('LOGG')]= tmpOut[:,-2]
        out[:,paramIndx('METALS')]= tmpOut[:,-3]
        out[:,paramIndx('ALPHA')]= tmpOut[:,-4]
        out[:,paramIndx('N')]= tmpOut[:,-5]
        out[:,paramIndx('C')]= tmpOut[:,-6]
        if sixd and dr == '12':
            out[:,paramIndx('LOG10VDOP')]=\
                numpy.log10(2.478-0.325*out[:,paramIndx('LOGG')])
        else:
            out[:,paramIndx('LOG10VDOP')]= tmpOut[:,0]
        if nspec == 1: out= out[0,:]
        if not offile is None:
            os.rename(os.path.join(tmpDir,'output.dat'),offile)
    finally:
        # Clean up
        if os.path.exists(os.path.join(tmpDir,'input.ipf')):
            os.remove(os.path.join(tmpDir,'input.ipf'))
        if os.path.exists(os.path.join(tmpDir,'input.frd')):
            os.remove(os.path.join(tmpDir,'input.frd'))
        if os.path.exists(os.path.join(tmpDir,'input.err')):
            os.remove(os.path.join(tmpDir,'input.err'))
        if os.path.exists(os.path.join(tmpDir,'input.nml')):
            os.remove(os.path.join(tmpDir,'input.nml'))
        if os.path.exists(os.path.join(tmpDir,'output.dat')):
            os.remove(os.path.join(tmpDir,'output.dat'))
        if os.path.exists(os.path.join(tmpDir,'output.opf')):
            os.remove(os.path.join(tmpDir,'output.opf'))
        os.rmdir(tmpDir)
    return out