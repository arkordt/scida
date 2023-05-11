import inspect
from collections.abc import MutableMapping
from enum import Enum
from typing import Dict, Optional

import dask.array as da
import dask.dataframe as dd

from .helpers_misc import get_kwargs


class FieldType(Enum):
    INTERNAL = 1
    IO = 2
    DERIVED = 3


class FieldRecipe(object):
    def __init__(
        self, name, func=None, arr=None, description="", units=None, ftype=FieldType.IO
    ):
        if func is None and arr is None:
            raise ValueError("Need to specify either func or arr.")
        self.type = ftype
        self.name = name
        self.description = description
        self.units = units
        self.func = func
        self.arr = arr


class DerivedFieldRecipe(FieldRecipe):
    def __init__(self, name, func, description="", units=None):
        super().__init__(
            name,
            func=func,
            description=description,
            units=units,
            ftype=FieldType.DERIVED,
        )


# class FieldContainerCollection(MutableMapping):
#    """A mutable collection of FieldContainers. Can also hold other FieldContainerCollections."""
#
#    def __init__(self, types=None, fieldrecipes_kwargs=None):
#        if fieldrecipes_kwargs is None:
#            fieldrecipes_kwargs = {}
#        if types is None:
#            types = []
#        self.store = {
#            k: FieldContainer(fieldrecipes_kwargs=fieldrecipes_kwargs) for k in types
#        }
#        self.fieldrecipes_kwargs = fieldrecipes_kwargs
#
#    def __getitem__(self, key):
#        return self.store[key]
#
#    def __setitem__(self, key, value):
#        self.store[key] = value
#
#    def __delitem__(self, key):
#        del self.store[key]
#
#    def __iter__(self):
#        return iter(self.store)
#
#    def __len__(self):
#        return len(self.store)
#
#    def keys(self):
#        return self.store.keys()
#
#    def new_container(self, key, **kwargs):
#        self[key] = FieldContainer(
#            **kwargs, fieldrecipes_kwargs=self.fieldrecipes_kwargs
#        )
#
#    def merge(self, collection, overwrite=True):
#        assert isinstance(collection, FieldContainerCollection)
#        for k in collection.store:
#            if k not in self.store:
#                self.store[k] = FieldContainer(
#                    fieldrecipes_kwargs=self.fieldrecipes_kwargs
#                )
#            if overwrite:
#                c1 = self.store[k]
#                c2 = collection.store[k]
#            else:
#                c1 = collection.store[k]
#                c2 = self.store[k]
#            c1.fields.update(**c2.fields)
#            c1.fieldrecipes.update(**c2.fieldrecipes)
#
#    def register_field(self, parttype, name=None, description=""):
#        if parttype == "all":
#            parttypes = self.store.keys()
#        elif isinstance(parttype, list):
#            parttypes = parttype
#        else:
#            return self.store[parttype].register_field(
#                name=name, description=description
#            )
#
#        # we only construct field upon first call to it (default)
#        def decorator(func, name=name, description=description):
#            if name is None:
#                name = func.__name__
#            for p in parttypes:
#                drvfields = self.store[p].fieldrecipes
#                drvfields[name] = DerivedFieldRecipe(
#                    name, func=func, description=description
#                )
#            return func
#
#        return decorator


class FieldContainer(MutableMapping):
    """A mutable collection of fields. Attempt to construct from derived fields recipes
    if needed."""

    def __init__(
        self, *args, fieldrecipes_kwargs=None, containers=None, aliases=None, **kwargs
    ):
        if aliases is None:
            aliases = {}
        if fieldrecipes_kwargs is None:
            fieldrecipes_kwargs = {}
        self.aliases = aliases
        self.name = kwargs.pop("name", None)
        self.fields: Dict[str, da.Array] = {}
        self.fields.update(*args, **kwargs)
        self.fieldrecipes = {}
        self.fieldrecipes_kwargs = fieldrecipes_kwargs
        self.containers: Dict[
            str, FieldContainer
        ] = dict()  # other containers as subgroups
        if containers is not None:
            for k in containers:
                self.containers[k] = FieldContainer(
                    fieldrecipes_kwargs=fieldrecipes_kwargs
                )
        self.internals = ["uid"]  # names of internal fields/groups

    def new_container(self, key, **kwargs):
        fkws = self.fieldrecipes_kwargs
        self.containers[key] = FieldContainer(
            **kwargs, fieldrecipes_kwargs=fkws, name=key
        )

    def merge(self, collection, overwrite=True):
        if not isinstance(collection, FieldContainer):
            raise TypeError("Can only merge FieldContainers.")
        # TODO: support nested containers
        for k in collection.containers:
            if k not in self.containers:
                self.containers[k] = FieldContainer(
                    fieldrecipes_kwargs=self.fieldrecipes_kwargs
                )
            if overwrite:
                c1 = self.containers[k]
                c2 = collection.containers[k]
            else:
                c1 = collection.containers[k]
                c2 = self.containers[k]
            c1.fields.update(**c2.fields)
            c1.fieldrecipes.update(**c2.fieldrecipes)

    @property
    def fieldcount(self):
        return len(self.fields)

    @property
    def fieldlength(self):
        itr = iter(self.fields.values())
        first = next(itr)
        if all(first.shape[0] == v.shape[0] for v in self.fields.values()):
            return first.shape[0]
        else:
            return None

    # def keys(self) -> set:
    #    # TODO: hacky; also know that we have not / can not write .items() right now
    #    # which will lead to unintended behaviour down the line
    #    return set(self.fields.keys()) | set(self.derivedfields.keys())
    def keys(self, withgroups=True, withrecipes=True, withinternal=False):
        fieldkeys = list(self.fields.keys())
        if not withinternal:
            for ikey in self.internals:
                if ikey in fieldkeys:
                    fieldkeys.remove(ikey)
        if withrecipes:
            recipekeys = self.fieldrecipes.keys()
            fieldkeys = list(set(fieldkeys) | set(recipekeys))
        if withgroups:
            groupkeys = self.containers.keys()
            return list(set(fieldkeys) | set(groupkeys))
        return fieldkeys

    def register_field(
        self,
        containernames=None,
        name: Optional[str] = None,
        description="",
        units=None,
    ):
        # we only construct field upon first call to it (default)
        # if to_containers, we register to the respective children containers
        containers = []
        if isinstance(containernames, list):
            containers = [self.containers[c] for c in containernames]
        elif containernames == "all":
            containers = self.containers.values()
        elif containernames is None:
            containers = [self]
        elif isinstance(containernames, str):  # just a single container as a string?
            containers.append(self.containers[containernames])
        else:
            raise ValueError("Unknown type.")

        def decorator(func, name=name, description=description, units=units):
            if name is None:
                name = func.__name__
            for container in containers:
                drvfields = container.fieldrecipes
                drvfields[name] = DerivedFieldRecipe(
                    name, func, description=description, units=units
                )
            return func

        return decorator

    def __setitem__(self, key, value):
        if isinstance(value, FieldContainer):
            self.containers[key] = value
        else:
            self.fields[key] = value

    def __getitem__(self, key):
        return self._getitem(key)

    def __iter__(self):
        return iter(self.keys())

    @property
    def dataframe(self):
        return self.get_dataframe()

    def get_dataframe(self, fields=None):
        dss = {}
        if fields is None:
            fields = self.keys()
        for k in fields:
            idim = None
            if k not in self.keys():
                # could still be an index two 2D dataset
                i = -1
                while k[i:].isnumeric():
                    i += -1
                i += 1
                if i == 0:
                    raise ValueError("Field '%s' not found" % k)
                idim = int(k[i:])
                k = k.split(k[i:])[0]
            v = self[k]
            assert v.ndim <= 2  # cannot support more than 2 here...
            if idim is not None:
                if v.ndim <= 1:
                    raise ValueError("No second dimensional index for %s" % k)
                if idim >= v.shape[1]:
                    raise ValueError(
                        "Second dimensional index %i not defined for %s" % (idim, k)
                    )

            if v.ndim > 1:
                for i in range(v.shape[1]):
                    if idim is None or idim == i:
                        dss[k + str(i)] = v[:, i]
            else:
                dss[k] = v
        dfs = [dd.from_dask_array(v, columns=[k]) for k, v in dss.items()]
        ddf = dd.concat(dfs, axis=1)
        return ddf

    def add_alias(self, alias, name):
        self.aliases[alias] = name

    def _getitem(self, key, force_derived=False, update_dict=True):
        if key in self.aliases:
            key = self.aliases[key]
        if key in self.containers:
            return self.containers[key]
        if key in self.fields and not force_derived:
            return self.fields[key]
        else:
            if key in self.fieldrecipes:
                func = self.fieldrecipes[key].func
                accept_kwargs = inspect.getfullargspec(func).varkw is not None
                func_kwargs = get_kwargs(func)
                dkwargs = self.fieldrecipes_kwargs
                # first, we overwrite all optional arguments with class instance defaults where func kwarg is None
                kwargs = {
                    k: dkwargs[k]
                    for k in (
                        set(dkwargs)
                        & set([k for k, v in func_kwargs.items() if v is None])
                    )
                }
                # next, we add all optional arguments if func is accepting **kwargs and varname not yet in signature
                if accept_kwargs:
                    kwargs.update(
                        **{
                            k: v
                            for k, v in dkwargs.items()
                            if k not in inspect.getfullargspec(func).args
                        }
                    )
                # finally, instatiate field
                # print("Instantiated field '%s'" % key)
                field = func(self, **kwargs)
                if update_dict:
                    self.fields[key] = field
                return field
            else:
                raise KeyError("Unknown field '%s'" % key)

    def __delitem__(self, key):
        if key in self.fieldrecipes:
            del self.fieldrecipes[key]
        del self.fields[key]

    def __len__(self):
        return len(self.keys())

    def get(self, key, value=None, allow_derived=True, force_derived=False):
        if key in self.fieldrecipes and not allow_derived:
            raise KeyError("Field '%s' is derived (allow_derived=False)" % key)
        else:
            try:
                return self._getitem(
                    key, force_derived=force_derived, update_dict=False
                )
            except KeyError:
                return value
