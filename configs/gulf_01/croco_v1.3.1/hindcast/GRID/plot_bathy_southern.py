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

figsize=(11,6) # (hz,vt)
extents = [51.173,55.742,24.018,26.374]
cmap = cmo.deep_r
ticks = [-90,-70,-50,-40,-30,-25,-20,-15,-12,-10,-8,-6,-4,-2,0]
cbar_loc = [0.9, 0.15, 0.01, 0.7]
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

jpg_out = 'plot_bathy_southern.jpg'
plt.savefig(jpg_out,dpi=500,bbox_inches = 'tight')

