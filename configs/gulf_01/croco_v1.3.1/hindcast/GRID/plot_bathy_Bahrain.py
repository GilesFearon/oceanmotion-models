import crocotools_py.postprocess as post
import crocotools_py.plotting as crocplot
import crocotools_py.validation as val
from datetime import datetime
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.colors as mplc
import matplotlib.cm as cm
from matplotlib.animation import FuncAnimation
import cartopy
import cartopy.crs as ccrs
import cartopy.feature as cfeature
import cmocean.cm as cmo

fname='croco_grd.nc'

h = post.get_grd_var(fname, 'h')
lon_rho, lat_rho, mask_rho = post.get_lonlatmask(fname)
h = h * mask_rho * -1 # making it negative down

figsize=(10,6) # (hz,vt)
# ticks = np.linspace(0,100,num=11) # the ticks to plot
# ticks = [0,10,20,30,40,50,60,80,100,200,500,1000]
ticks = np.linspace(-15,0,num=16)
cmap = cmo.deep_r
extents = [53.8,54.35,24.15,24.5]
cbar_loc = [0.88, 0.15, 0.01, 0.7]
cbar_label = 'bathymetry (m)'

fig = plt.figure(figsize=figsize) 
ax = plt.axes(projection=ccrs.Mercator())

# set up the plot
crocplot.setup_plot(ax,fname,extents = extents)

levs = np.array(ticks)
cmap_norm = mplc.BoundaryNorm(boundaries=levs, ncolors=256)

# plot the data
var_plt = ax.pcolormesh(lon_rho,
                          lat_rho,
                          h,
                          cmap=cmap,
                          norm=cmap_norm,
                          transform=ccrs.PlateCarree())

# crocplot.plot_cbar(var_plt,label=cbar_label,ticks=ticks,loc=cbar_loc)
crocplot.plot_cbar(ax,var_plt,label=cbar_label,ticks=ticks,loc=cbar_loc)

# approx. coords of turbidity observations
lat_ts = 24.385
lon_ts = 54.065
ax.scatter(lon_ts,lat_ts,s=60,c='red',transform=ccrs.PlateCarree())
# time_plt = ax.text(lon_ts-0.1, lat_ts-0.1, 'obs',
#     ha='right', va='top', fontsize=10,
#     transform=ccrs.PlateCarree())

# # Coords for Majis
# lat_ts = 24.512053
# lon_ts = 56.637126
# ax.scatter(lon_ts,lat_ts,20,color='k',transform=ccrs.PlateCarree())
# time_plt = ax.text(lon_ts-0.1, lat_ts-0.1, 'Majis',
#     ha='right', va='top', fontsize=10,
#     transform=ccrs.PlateCarree())

jpg_out = 'plot_bathy_Bahrain.jpg'
plt.savefig(jpg_out,dpi=500,bbox_inches = 'tight')

