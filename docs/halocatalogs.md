# Halo and galaxy catalogs

Cosmological simulations are often post-processed with a substructure identification algorithm in order to identify halos and galaxies. The resulting catalogs can be loaded and connect with the particle-level snapshot data.

## Adding and using halo/galaxy catalog information
Currently, we support the usual FOF/Subfind combination and format. Their presence will be automatically detected and the catalogs will be loaded into *ds.data* as shown below.

``` py
from astrodask import load
ds = load("snapshot") # (1)!
```

1.  In this example, we assume a dataset, such as the 'TNG50\_snapshot' test data set, that has its fields (*Masses*, *Velocities*) nested by particle type (*gas*)

The dataset itself passed to load does not possess information about the FoF/Subfind outputs as they are commonly saved in a separate folder or hdf5 file. For typical folder structures of GADGET/AREPO style simulations, an attempt is made to automatically discover and add such information. The path to the catalog can otherwise explicitly be passed to *load()* via the *catalog=...* keyword.


Groups and subhalo information is added into the dataset with the data containers *Group* and *Subhalo*. For example, we can obtain the masses of each group as:


``` py
group_mass = ds.data["Group"]["GroupMass"]
```

In addition to these two data containers, new information is added to all other containers about their belonging to a given group and subhalo.

``` py
groupid = ds.data["PartType0"]["GroupID"]
subhaloid = ds.data["PartType0"]["SubhaloID"]
```

In above example, we fetch the virtual dask arrays holding the group and subhalo belonging of each *PartType0* particle. The *groupid* field returns the integer position into the group catalog that given particle belongs to. For the *subhaloid* the subhalo id within a given *groupid* is given, *where subhaloid==0* marks the belonging to the central subhalo in a halo.

This operation allows us to efficiently query the belonging of given particles. So, for example, we can compute the group IDs of the particles 1000-1099 by running

``` py
groupid[1000:1100].compute()
```


## Working with halo data
### Query all particles belonging to some group
Often we only want to operate with the particles of a given halo. We can efficiently return a virtual view of all fields in *ds.data* for a given halo ID as for example in:


``` py
data = ds.return_data(haloID=42)
```

*data* will have the same structure as *ds.data* but restricted to particles of a given group.

### Operations on particle data for all groups

In many cases, we do not want the particle data of an individual group, but we want to calculate some reduced statistic from the bound particles of each group. For this, we provide the *grouped* functionality. In the following we give a range of examples of its use.


#### Baryon mass
Let's say we want to calculate the baryon mass for each halo from the particles.


``` py
mass = ds.grouped("Masses", parttype="PartType0").sum().evaluate(compute=True)
mass
```

Unless *compute=True* a dask operation is returned.

#### Electron mass
Instead of an existing field, we can also pass another dask array of matching field for the given particle species (here: *PartType0*). The following example calculates the total mass of electrons in each halo.

``` py
import dask.array as da
gas = ds.data["PartType0"]
# total electron mass
me = 9.1e-28 # cgs
mp = 1.7e-24 # cgs
# me and mp units cancel each other
ne = gas["ElectronAbundance"] * 0.76 * gas["Density"]/mp
vol = gas["Masses"] / gas["Density"]
emass_field = vol * me * ne
emass = ds.grouped(emass_field).sum().evaluate(compute=True)
emass
```

#### Heaviest black hole
``` py
bhmassmax = ds.grouped("Masses", parttype="PartType5").max().evaluate()
bhmassmax
```


#### Radial profile for each halo

``` py
import numpy as np
from scipy.stats import binned_statistic

grp = ds.data["Group"]
pos3 = gas["Coordinates"] - grp["GroupPos"][gas["GroupID"]]
dist = da.sqrt(da.sum((pos3)**2, axis=1)) # (1)!

def customfunc(dist, density, volume):
    a = binned_statistic(dist, density, statistic="sum", bins=np.linspace(0, 200, 10))[0]
    b = binned_statistic(dist, volume, statistic="sum", bins=np.linspace(0, 200, 10))[0]
    return a/b

g = ds.grouped(dict(dist=dist, Density=gas["Density"],
                    Volume=vol))
s = g.apply(customfunc).evaluate()
```

1. We do not incorporate periodic boundary conditions in this example for brevity.


Note that here we defined a custom function *customfunc* that will be applied to each halo respectively. The custom function accepts any inputs we feed to *ds.grouped()*. The *customfunc* receives numpy representation (rather than dask arrays) as inputs.